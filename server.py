"""Sound server used to sync sounds between players"""
import hashlib
import os
import signal
import socket
from threading import Lock, Thread

from packets_pb2 import PacketInfo, GameEvent, SoundRequest, SoundResponse, ClientUpdate, PlaySound
from config import SOUND_SERVER_PORT

CLIENT_TIMEOUT = 120
MAX_CLIENTS = 100

# Thread-safe printing
print_lock = Lock()
unsafe_print = print
def print(*a, **b):
	with print_lock:
		unsafe_print(*a, **b)

class Client:
	def __init__(self, server, sock, addr):
		self.server = server
		self.sock_lock = Lock()
		self.sock = sock
		self.addr = addr
		self.steamid = 0
		self.shard_code = ''
		self.map = ''
		self.round = 0
		self.ingame = False
		
		self.sock.settimeout(CLIENT_TIMEOUT)
	
	def get_event_class(self, packet):
		rare_events = [ GameEvent.Type.MVP, GameEvent.Type.SUICIDE, GameEvent.Type.TEAMKILL, GameEvent.Type.KNIFE, GameEvent.Type.COLLATERAL ]
		shared_events = [ GameEvent.Type.ROUND_WIN, GameEvent.Type.ROUND_LOSE, GameEvent.Type.ROUND_START, GameEvent.Type.TIMEOUT ]
		if packet.update in rare_events: return 'rare'
		if packet.update in shared_events: return 'shared'
		if packet.update == GameEvent.Type.KILL and packet.kill_count > 3: return 'rare'
		return 'normal'

	def handle_event(self, packet):
		self.round = packet.round
		event_class = self.get_event_class(packet)

		if event_class == 'rare':
			self.server.play_sound(self, b'', packet.proposed_sound_hash)
		elif event_class == 'shared':
			# TODO
			self.server.play_sound(self, b'', packet.proposed_sound_hash)
		else:
			self.server.play_sound(self, self.steamid, packet.proposed_sound_hash)
	
	def send_sound(self, packet):
		with self.server.cache_lock:
			if not packet.sound_hash in self.server.cache:
				return
		
		with os.open('cache/' + packet.sound_hash) as infile:
			data = infile.read()

		res = SoundResponse()
		res.data = data
		res.hash = packet.sound_hash
		with self.sock_lock:
			self.sock.send(res.SerializeToString())
	
	def save_sound(self, packet):
		verif = hashlib.blake2b()
		verif.update(packet.data)
		if packet.hash != verif.digest():
			print("Hashes do not match, dropping file.")
			return

		with self.server.cache_lock:
			if packet.hash in self.server.cache:
				# Sound already saved
				return
		with os.open('cache/' + packet.hash) as outfile:
			outfile.write(packet.data)
		with self.server.cache_lock:
			self.server.cache.append(packet.hash)
		
	def update(self, packet):
		self.ingame = packet.status == ClientUpdate.PlayerStatus.CONNECTED
		self.map = packet.map
		self.steamid = packet.steamid

		# Update shard code
		if self.shard_code != packet.shard_code:
			with self.server.shards_lock:
				self.server.shards[self.shard_code].remove(self)
				self.shard_code = packet.shard_code
				try:
					self.server.shards[self.shard_code].append(self)
				except:
					self.server.shards[self.shard_code] = [self]
	
	def handle(self, packet_type, raw_packet):
		if packet_type == PacketInfo.Type.GAME_EVENT:
			packet = GameEvent()
			packet.ParseFromString(raw_packet)
			self.handle_event(packet)
		elif packet_type == PacketInfo.Type.SOUND_REQUEST:
			packet = SoundRequest()
			packet.ParseFromString(raw_packet)
			self.send_sound(packet)
		elif packet_type == PacketInfo.Type.SOUND_RESPONSE:
			packet = SoundResponse()
			packet.ParseFromString(raw_packet)
			self.save_sound(packet)
		elif packet_type == PacketInfo.Type.CLIENT_UPDATE:
			packet = ClientUpdate()
			packet.ParseFromString(raw_packet)
			self.update(packet)
		else:
			print(str(self.addr) + ": Unhandled packet type!")
	
	def listen(self):
		print(str(self.addr) + " joined.")

		while self.server.running:
			try:
				# 255 bytes should be more than enough for the PacketInfo message
				with self.sock_lock:
					data = self.sock.recv(255)
				if len(data) == 0:
					break
				
				packet_info = PacketInfo()
				packet_info.ParseFromString(data)
				
				if packet_info['length'] > 2 * 1024 * 1024:
					# Don't allow files or packets over 2 Mb
					break

				with self.sock_lock:
					data = self.sock.recv(packet_info['length'])
				if len(data) == 0:
					break
				
				self.handle(packet_info['type'], data)
			except ConnectionResetError:
				break
			except socket.error as msg:
				print("Error: " + msg)
				break

		print(str(self.addr) + " left.")


class Server:
	def __init__(self):
		self.running = True
		self.init_sound_cache()
		self.clients_lock = Lock()
		self.clients = []

		self.shards_lock = Lock()
		self.shards = {}

	def play_sound(self, client, steamid, hash):
		packet = PlaySound()
		packet.steamid = steamid
		packet.hash = hash
		
		with self.shards_lock:
			for peer in self.shards[client.shard_code]:
				with peer.sock_lock:
					peer.sock.send(packet.SerializeToString())

	def shutdown(self):
		self.running = False
	
	def init_sound_cache(self):
		self.cache_lock = Lock()
		self.cache = []

		for file in os.listdir('cache'):
            # Only add valid files
			if file.startswith('.git') or not os.path.isfile(file):
				continue
			self.cache.append(file)

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
