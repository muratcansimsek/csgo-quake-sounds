"""Sound server used to sync sounds between players"""
import datetime
import hashlib
import os
import signal
import socket
import sys
from google.protobuf.message import DecodeError
from threading import Lock, Thread

import config
from util import print, get_event_class, small_hash
from packets_pb2 import PacketInfo, GameEvent, SoundRequest, SoundResponse, ClientUpdate, PlaySound

CLIENT_TIMEOUT = 20
MAX_CLIENTS = 100


class Shard:
	def __init__(self, name):
		self.name = name
		self.clients = []
		self.lock = Lock()
		self.round = 0
		self.round_events = []

		# List of available sound hashes
		# Every sound in this list will be downloaded by users that join the shard
		self.sounds = []

	def __str__(self):
		return f'[{self.name} ({len(self.clients)})]'

	def play(self, steamid, hash):
		packet = PlaySound()
		packet.steamid = steamid
		packet.sound_hash = hash
		raw_packet = packet.SerializeToString()

		header = PacketInfo()
		header.type = PacketInfo.PLAY_SOUND
		header.length = len(raw_packet)
		raw_header = header.SerializeToString()

		print(f'{str(self)} Playing {small_hash(hash)} for {steamid}')

		played = False
		with self.lock:
			for client in self.clients:
				with client.lock:
					if client.steamid != steamid and client.steamid != 0:
						played = True
						print(f'{str(self)} -> {str(client.addr)}')
						client.sock.sendall(raw_header)
						client.sock.sendall(raw_packet)

					if client.round > self.round or client.round < self.round - 1:
						self.round = client.round
						self.round_events = []

		if played is True:
			print(f'Done playing {small_hash(hash)}')
		else:
			print("Whoops, nevermind, this guy is all alone")

	def play_shared(self, event, hash):
		should_play = False
		with self.lock:
			if self.name == b'':
				# Don't play sounds in default shard :
				# The players that didn't set a shard yet would hear random sounds
				return
			if event not in self.round_events:
				self.round_events.append(event)
				should_play = True
		if should_play:
			self.play(0, hash)


class Client:
	def __init__(self, server, sock, addr):
		self.server = server
		self.lock = Lock()
		self.sock = sock
		self.addr = addr
		self.steamid = 0
		self.round = 0

		self.shard = None
		self.last_shard_change = datetime.datetime.min

		# List of sound hashes the user posesses
		# The sounds may not be cached by the server
		self.sounds = []

		self.sock.settimeout(CLIENT_TIMEOUT)
		Thread(target=self.listen, daemon=True).start()

	def send(self, type, packet):
		raw_packet = packet.SerializeToString()
		raw_header = len(raw_packet).to_bytes(4, byteorder='big') + type.to_bytes(4, byteorder='big')
		with self.lock:
			print(f'Sending {PacketInfo.Type.Name(type)} to {str(self.addr)}')
			self.sock.sendall(raw_header)
			self.sock.sendall(raw_packet)

	def check_or_request_sounds(self, hashes):
		"""Request sound if we don't have it in cache"""
		sound_request = SoundRequest()
		with self.server.cache_lock:
			for hash in hashes:
				if len(hash) != 64:
					print('%d no %s' % (len(hash), str(hash)))
				with self.lock:
					if hash not in self.sounds:
						self.sounds.append(hash)
				if hash not in self.server.cache:
					sound_request.sound_hash.append(hash)

		if len(sound_request.sound_hash) > 0:
			print(f"Missing {len(sound_request.sound_hash)} sounds in cache, asking {str(self.addr)} for them")
			self.send(PacketInfo.SOUND_REQUEST, sound_request)
		elif len(hashes) > 1:
			print(f"We already have all of {str(self.addr)}'s sounds")

	def handle_event(self, packet):
		with self.lock:
			self.round = packet.round

		event_class = get_event_class(packet)
		if len(packet.proposed_sound_hash) != 64:
			print('This is not okay: %s' % str(packet))
			print('Serialized: %s' % str(packet.SerializeToString()))

		self.check_or_request_sounds([packet.proposed_sound_hash])

		with self.lock:
			if self.shard == None:
				return
			shard = self.shard
			steamid = self.steamid if event_class == 'normal' else 0
		if event_class == 'shared':
			shard.play_shared(packet.update, packet.proposed_sound_hash)
		else:
			shard.play(steamid if event_class == 'normal' else 0, packet.proposed_sound_hash)

	def send_sound(self, packet):
		"""Handles a SoundRequest packet - LOCKS"""
		with self.server.cache_lock:
			if not packet.sound_hash in self.server.cache:
				return

		res = SoundResponse()
		with open('cache/' + packet.sound_hash.hex(), 'rb') as infile:
			res.data = infile.read()
			res.hash = packet.sound_hash

		print(f'{self.steamid} is downloading {small_hash(packet.sound_hash)}')
		self.send(PacketInfo.SOUND_RESPONSE, res)
		print(f'{self.steamid} is done downloading {small_hash(packet.sound_hash)}')

	def save_sound(self, packet):
		"""Handles a SoundResponse packet - LOCKS"""
		verif = hashlib.blake2b()
		verif.update(packet.data)
		if packet.hash != verif.digest():
			print("Hashes do not match, dropping file.")
			print('packet hash : %s - digest : %s' % (packet.hash.hex(), verif.digest().hex()))
			return

		with self.server.cache_lock:
			if packet.hash in self.server.cache:
				# Sound already saved
				print('%s sent %s but we already have it. Ignoring.' % (str(self.addr), small_hash(packet.hash)))
				return
		with open('cache/' + packet.hash.hex(), 'wb') as outfile:
			outfile.write(packet.data)
		with self.server.cache_lock:
			self.server.cache.append(packet.hash)
		with self.lock:
			print(f'Saved {small_hash(packet.hash)} from {str(self.addr)}')
			self.sounds.append(packet.hash)
			shard = self.shard
		if shard != None:
			req = SoundRequest()
			req.sound_hash.append(packet.hash)

			# Add hash to shard sound list and notify clients
			with shard.lock:
				shard.sounds.append(packet.hash)
				print(f'Notifying {str(shard)} of the new sound {small_hash(packet.hash)}')
				for client in shard.clients:
					should_send = False
					with client.lock:
						if packet.hash not in client.sounds:
							should_send = True
					if should_send:
						client.send(PacketInfo.SOUNDS_LIST, req)

	def join_shard(self, name):
		"""Join a shard by name - LOCKS"""
		with self.lock:
			if name == b'':
				self.shard = None
				return

			print('%s (steamid %d) is now in shard %s' % (str(self.addr), self.steamid, name.decode('utf-8')))
			self.last_shard_change = datetime.datetime.now()
			new_shard = self.server.get_shard(name)
			with new_shard.lock:
				new_shard.clients.append(self)
				self.shard = new_shard

				# Add client's cached sounds to shard's download list
				with self.server.cache_lock:
					for hash in self.sounds:
						if hash in self.server.cache and hash not in new_shard.sounds:
							new_shard.sounds.append(hash)

				# Send missing sounds list (as in the client doesn't have them) to client
				packet = SoundRequest()
				for hash in new_shard.sounds:
					if hash not in self.sounds:
						packet.sound_hash.append(hash)
		if len(packet.sound_hash) > 0:
			self.send(PacketInfo.SOUNDS_LIST, packet)

	def leave_shard(self):
		"""Leave the shard the Client is in - DOES NOT LOCK"""
		if self.shard == None:
			return
		self.last_shard_change = datetime.datetime.now()
		old_shard = self.shard
		with old_shard.lock:
			old_shard.clients.remove(self)

			# No users left : remove shard from server
			if len(old_shard.clients) == 0:
				with self.server.shards_lock:
					del self.server.shards[old_shard.name]

	def update(self, packet):
		with self.lock:
			self.steamid = packet.steamid

			if self.shard == None and packet.shard_code == b'':
				return
			if self.shard != None and self.shard.name == packet.shard_code:
				return
			# Don't allow client to switch shards more than 1x/second
			# TODO add restriction on client
			if (datetime.datetime.now() - self.last_shard_change).seconds < 1:
				return

			self.leave_shard()
		self.join_shard(packet.shard_code)

	def handle(self, packet_type, raw_packet):
		if packet_type == PacketInfo.GAME_EVENT:
			packet = GameEvent()
			packet.ParseFromString(raw_packet)
			self.handle_event(packet)
		elif packet_type == PacketInfo.SOUND_REQUEST:
			packet = SoundRequest()
			packet.ParseFromString(raw_packet)
			self.send_sound(packet)
		elif packet_type == PacketInfo.SOUND_RESPONSE:
			packet = SoundResponse()
			packet.ParseFromString(raw_packet)
			self.save_sound(packet)
		elif packet_type == PacketInfo.CLIENT_UPDATE:
			packet = ClientUpdate()
			packet.ParseFromString(raw_packet)
			self.update(packet)
		elif packet_type == PacketInfo.SOUNDS_LIST:
			packet = SoundRequest()
			packet.ParseFromString(raw_packet)
			self.check_or_request_sounds(packet.sound_hash)
		else:
			print(str(self.addr) + ": Unhandled packet type!")

	def listen(self):
		print(str(self.addr) + " joined")

		while self.server.running:
			try:
				data = self.sock.recv(8)
				if len(data) == 0:
					break

				packet_len = int.from_bytes(data[0:4], byteorder='big')
				packet_type = int.from_bytes(data[4:8], byteorder='big')
				if packet_len > 3 * 1024 * 1024:
					# Don't allow files or packets over 3 Mb
					print('%s Received file over 2Mb, disconnecting' % str(self.addr))
					break

				try:
					if packet_type != PacketInfo.CLIENT_UPDATE:
						print('%s Received %s ' % (str(self.addr), PacketInfo.Type.Name(packet_type)))
				except:
					print('%s Received invalid packet type, disconnecting' % str(self.addr))
					with self.lock:
						self.sock.shutdown(socket.SHUT_RDWR)
					break

				data = b''
				received = 0
				while received < packet_len:
					chunk = self.sock.recv(packet_len - received)
					data += chunk
					received += len(chunk)
				self.handle(packet_type, data)
			except DecodeError:
				break
			except ConnectionResetError:
				break
			except socket.error as msg:
				print('%s Error: %s' % (str(self.addr), str(msg)))
				break

		with self.lock:
			self.leave_shard()
			try:
				self.sock.shutdown(socket.SHUT_RDWR)
			except:
				pass
			print(str(self.addr) + " left")


class Server:
	def __init__(self):
		self.running = True
		self.init_sound_cache()
		self.clients_lock = Lock()
		self.clients = []

		self.shards_lock = Lock()
		self.shards = {}

	def shutdown(self, signum, frame):
		self.running = False

	def init_sound_cache(self):
		self.cache_lock = Lock()
		self.cache = []

		for filename in os.listdir('cache'):
			# Only add valid files
			if filename.startswith('.') or not os.path.isfile('cache/' + filename):
				continue
			with self.cache_lock:
				self.cache.append(bytes.fromhex(filename))
		with self.cache_lock:
			print('%d sounds in cache.' % len(self.cache))

	def get_shard(self, name):
		with self.shards_lock:
			if name in self.shards:
				return self.shards[name]
			else:
				self.shards[name] = Shard(name)
				return self.shards[name]


	def serve(self):
		self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
		with config.lock:
			port = config.config['Network'].getint('ServerPort', 4004)
		self.sock.bind(("0.0.0.0", port))
		self.sock.listen(MAX_CLIENTS)

		while self.running:
			csock, addr = self.sock.accept()
			with self.clients_lock:
				client = Client(self, csock, addr)
				self.clients.append(client)


if __name__ == "__main__":
	# Python 3.6 is required because we use hashlib's blake2b implementation
	# ...which did not exist before 3.6.
	if sys.version_info[0] < 3 or sys.version_info[1] < 6:
		print('Python 3.6+ is required, but you are running Python %d.%d.' % (sys.version_info[0], sys.version_info[1]))
	else:
		server = Server()
		signal.signal(signal.SIGTERM, server.shutdown)
		server.serve()
