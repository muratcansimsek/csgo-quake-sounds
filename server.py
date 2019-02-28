"""Sound server used to sync sounds between players"""
import os
import signal
import socket
from threading import Lock, Thread

from packets_pb2 import PacketInfo, GameEvent, ChangeSteamID
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
		self.sock = sock
		self.addr = addr
		self.steamid = 0
		
		self.sock.settimeout(CLIENT_TIMEOUT)

	def update(self, packet):
		pass
	
	def set_steamid(self, packet):
		pass
	
	def handle(self, packet_type, raw_packet):
		if packet_type == PacketInfo.Type.GAME_EVENT:
			packet = GameEvent()
			packet.ParseFromString(raw_packet)
			self.update(packet)
		elif packet_type == PacketInfo.Type.ChangeSteamID:
			packet = ChangeSteamID()
			packet.ParseFromString(raw_packet)
			self.set_steamid(packet)
		else:
			print(str(self.addr) + ": Unhandled packet type!")
	
	def listen(self):
		print(str(self.addr) + " joined.")

		while self.server.running:
			try:
				# 255 bytes should be more than enough for the PacketInfo message
				data = self.sock.recv(255)
				if len(data) == 0:
					break
				
				packet_info = PacketInfo()
				packet_info.ParseFromString(data)
				
				if packet_info['length'] > 2 * 1024 * 1024:
					# Don't allow files or packets over 2 Mb
					break

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
	from steam import SteamClient
	from csgo import CSGOClient

	import logging

	logging.basicConfig(format='[%(asctime)s] %(levelname)s %(name)s: %(message)s', level=logging.DEBUG)

	client = SteamClient()
	cs = CSGOClient(client)

	@client.on('logged_on')
	def start_csgo():
		print("Logged on. Launching CS:GO...")
		cs.launch()
	
	@cs.on('csgo_welcome')
	def cs_ready(evt):
		print("Launched CS:GO. Scanning profiles :)")
		print("server acc id : " + str(cs.account_id))
		print("requesting profile")
		cs.request_live_game_for_user(76561198198426523 & 0xFFFFFFFF)
		print("waiting for ev")
		response, = cs.wait_event('live_game_for_user')
		print("response: " + str(response))
	
	client.cli_login()
	print("logged in!")
	client.run_forever()

	server = Server()
	signal.signal(signal.SIGTERM, server.shutdown)
	server.serve()
