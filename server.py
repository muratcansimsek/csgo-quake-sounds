"""Sound server used to sync sounds between players"""
import datetime
import hashlib
import os
import signal
import socket
from threading import Lock, Thread

from packets_pb2 import PacketInfo, GameEvent, SoundRequest, SoundResponse, ClientUpdate, PlaySound
from config import SOUND_SERVER_PORT

# temp
from time import sleep

rare_events = [ GameEvent.MVP, GameEvent.SUICIDE, GameEvent.TEAMKILL, GameEvent.KNIFE, GameEvent.COLLATERAL ]
shared_events = [ GameEvent.ROUND_WIN, GameEvent.ROUND_LOSE, GameEvent.ROUND_START, GameEvent.TIMEOUT ]

CLIENT_TIMEOUT = 120
MAX_CLIENTS = 100

# Thread-safe printing
print_lock = Lock()
unsafe_print = print
def print(*a, **b):
	with print_lock:
		unsafe_print(*a, **b)

def small_hash(hash):
	hex = hash.hex()
	return '%s-%s' % (hex[0:4], hex[-4:])

class Shard:
	def __init__(self, name):
		self.name = name
		self.clients = []
		self.lock = Lock()
		self.round = 0
		self.round_events = []
	
	def play(self, steamid, hash):
		packet = PlaySound()
		packet.steamid = steamid
		packet.sound_hash = hash
		raw_packet = packet.SerializeToString()

		header = PacketInfo()
		header.type = PacketInfo.PLAY_SOUND
		header.length = len(raw_packet)
		raw_header = header.SerializeToString()

		print('playing %s for steamid %d in shard %s (%d clients)' % (small_hash(hash), steamid, self.name, len(self.clients)))

		with self.lock:
			for client in self.clients:
				if client.ingame:
					with client.lock:
						client.sock.sendall(raw_header)
						client.sock.sendall(raw_packet)

					if client.round > self.round or client.round < self.round - 1:
						self.round = client.round
						self.round_events = []
	
	def play_shared(self, event, hash):
		should_play = False
		with self.lock:
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
		self.shard = None
		self.map = ''
		self.round = 0
		self.ingame = False
		
		self.sock.settimeout(CLIENT_TIMEOUT)
	
	def check_or_request_sounds(self, hashes):
		"""Request sound if we don't have it in cache"""
		sound_request = SoundRequest()
		with self.server.cache_lock:
			for hash in hashes:
				if hash.hex() not in self.server.cache:
					sound_request.sound_hash.append(hash)
		raw_request = sound_request.SerializeToString()

		header = PacketInfo()
		header.type = PacketInfo.SOUND_REQUEST
		header.length = len(raw_request)

		with self.lock:
			print('Requesting %d/%d sounds from %s' % (len(sound_request.sound_hash), len(hashes), self.addr))
			self.sock.sendall(header.SerializeToString())
			self.sock.sendall(raw_request)

	def get_event_class(self, packet):
		if packet.update in rare_events: return 'rare'
		if packet.update in shared_events: return 'shared'
		if packet.update == GameEvent.KILL and packet.kill_count > 3: return 'rare'
		return 'normal'

	def handle_event(self, packet):
		with self.lock:
			self.round = packet.round
			if self.shard == None:
				return

		event_class = self.get_event_class(packet)
		self.check_or_request_sounds([packet.proposed_sound_hash])

		if event_class == 'shared':
			self.shard.play_shared(packet.update, packet.proposed_sound_hash)
		else:
			self.shard.play(self.steamid if event_class == 'normal' else 0, packet.proposed_sound_hash)
	
	def send_sound(self, packet):
		with self.server.cache_lock:
			if not packet.sound_hash in self.server.cache:
				return
		
		with open('cache/' + packet.sound_hash.hex(), 'rb') as infile:
			data = infile.read()

		res = SoundResponse()
		res.data = data
		res.hash = packet.sound_hash
		raw_res = res.SerializeToString()

		header = PacketInfo()
		header.type = PacketInfo.SOUND_RESPONSE
		header.length = len(raw_res)

		with self.lock:
			print('Sending %s to %d' % (small_hash(packet.sound_hash), self.steamid))
			self.sock.sendall(header.SerializeToString())
			self.sock.sendall(raw_res)
	
	def save_sound(self, packet):
		verif = hashlib.blake2b()
		verif.update(packet.data)
		if packet.hash != verif.digest():
			print("Hashes do not match, dropping file.")
			return

		with self.server.cache_lock:
			if packet.hash.hex() in self.server.cache:
				# Sound already saved
				with self.lock:
					print('%s sent %s but we already have it. Ignoring.' % (str(self.addr), small_hash(packet.hash)))
				return
		with open('cache/' + packet.hash.hex(), 'wb') as outfile:
			outfile.write(packet.data)
		with self.server.cache_lock:
			self.server.cache.append(packet.hash.hex())
		with self.lock:
			print('Saved %s from %s' % (small_hash(packet.hash), self.addr))
		
	def update(self, packet):
		with self.lock:
			self.ingame = packet.status == ClientUpdate.CONNECTED
			self.map = packet.map
			self.steamid = packet.steamid

			# Update shard
			if self.shard == None:
				new_shard = self.server.get_shard(packet.shard_code)
				with new_shard.lock:
					new_shard.clients.append(self)
					self.shard = new_shard
			elif self.shard.name != packet.shard_code:
				print('%s (steamid %d) is now in shard %s' % (str(self.addr), self.steamid, packet.shard_code))
				old_shard = self.server.get_shard(self.shard.name)
				with old_shard.lock:
					old_shard.clients.remove(self)

				new_shard = self.server.get_shard(packet.shard_code)
				with new_shard.lock:
					new_shard.clients.append(self)
					self.shard = new_shard

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
			with self.lock:
				print('Recieved sound list from %s.' % str(self.addr))
			self.check_or_request_sounds(packet.sound_hash)
		else:
			print(str(self.addr) + ": Unhandled packet type!")
	
	def listen(self):
		print(str(self.addr) + " joined.")

		while self.server.running:
			try:
				with self.lock:
					data = self.sock.recv(7)
					if len(data) == 0:
						break
					
					packet_info = PacketInfo()
					packet_info.ParseFromString(data)
					print('Recieved packet of type %d' % packet_info.type)
					
					if packet_info.length > 2 * 1024 * 1024:
						# Don't allow files or packets over 2 Mb
						break

					data = self.sock.recv(packet_info.length)
					if len(data) == 0:
						break
				
				self.handle(packet_info.type, data)
			except ConnectionResetError:
				break
			except socket.error as msg:
				print("Error: " + msg)
				break
			
			sleep(1)

		if self.shard != None:
			with self.shard.lock:
				self.shard.clients.remove(self)

		print(str(self.addr) + " left.")


class Server:
	def __init__(self):
		self.running = True
		self.init_sound_cache()
		self.clients_lock = Lock()
		self.clients = []

		self.shards_lock = Lock()
		self.shards = {}

	def shutdown(self):
		self.running = False
	
	def init_sound_cache(self):
		self.cache_lock = Lock()
		self.cache = []

		for file in os.listdir('cache'):
			# Only add valid files
			if file.startswith('.git') or not os.path.isfile('cache/' + file):
				continue
			with self.cache_lock:
				self.cache.append(file)
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
		self.sock.bind(("0.0.0.0", SOUND_SERVER_PORT))
		self.sock.listen(MAX_CLIENTS)

		while self.running:
			csock, addr = self.sock.accept()
			with self.clients_lock:
				client = Client(self, csock, addr)
				self.clients.append(client)
				Thread(target=client.listen, daemon=True).start()


if __name__ == "__main__":
	server = Server()
	signal.signal(signal.SIGTERM, server.shutdown)
	server.serve()
