import asyncio
import hashlib
import os
import ssl
import sys
from time import time
from typing import Dict, Optional

import config
from protocol import protocol, ClientUpdate, ClientSoundRequest, GameEvent, PlaySound, SoundResponse, ServerRoomSounds
from util import get_event_class, small_hash


CLIENT_TIMEOUT = 20
available_sounds = set()
rooms = {}


class Room(object):
	clients = []
	last_events: Dict[int, int] = {}
	available_sounds = set()
	missing_sounds = set()

	def play(self, steamid, hash):
		packet = PlaySound()
		packet.steamid = steamid
		packet.sound_hash = hash

		print(f'{str(self)} Playing {small_hash(hash)} for {steamid}')

		played = False
		for client in self.clients:
			if client.steamid != steamid and client.steamid != 0:
				played = True
				print(f'{str(self)} -> {str(client.addr)}')
				client.send(packet)

		if played is True:
			print(f'Done playing {small_hash(hash)}')
		else:
			print("Whoops, nevermind, this guy is all alone")

	def play_shared(self, event, hash):
		if event not in self.last_events or self.last_events[event] + 10 < time():
			self.last_events[event] = time()
			self.play(0, hash)


class Connection(asyncio.Protocol):

	def connection_made(self, transport):
		self.transport = transport
		self.peername = transport.get_extra_info('peername')
		self.buffer = b''
		self.room_name: Optional[str] = None
		self.sounds = set()
		self.steamid = 0
		print(f"{self.peername} connected.")

	def connection_lost(self, exc):
		print(f"{self.peername} disconnected.")
		self.transport.close()

	def data_received(self, data):
		self.buffer = self.buffer + data
		self.try_reading_buffer()

	@property
	def room(self):
		return None if self.room_name is None else rooms[self.room_name]

	def join_room(self, room_name: str) -> bool:
		if self.room_name is not None:
			self.leave_room()
		if room_name not in rooms:
			rooms[room_name] = Room()
		rooms[room_name].clients.append(self)
		self.room_name = room_name

		for sound in self.sounds:
			if sound in available_sounds:
				rooms[room_name].available_sounds.add(sound)
			else:
				rooms[room_name].missing_sounds.add(sound)

		return True

	def leave_room(self) -> None:
		rooms[self.room_name].remove(self)
		if len(rooms[self.room_name]) == 0:
			del rooms[self.room_name]
		self.room_name = None

	def save_sound(self, packet) -> bool:
		global available_sounds

		verif = hashlib.blake2b()
		verif.update(packet.data)
		if packet.hash != verif.digest():
			print("Hashes do not match, dropping file.")
			print('packet hash : %s - digest : %s' % (packet.hash.hex(), verif.digest().hex()))
			return False

		if packet.hash in available_sounds:
			# Sound already saved
			print('%s sent %s but we already have it. Ignoring.' % (str(self.addr), small_hash(packet.hash)))
			return True
		with open('cache/' + packet.hash.hex(), 'wb') as outfile:
			outfile.write(packet.data)
		available_sounds.add(packet.hash)
		self.sounds.add(packet.hash)

		self.room.missing_sounds.remove(packet.hash)
		self.room.available_sounds.add(packet.hash)

		print(f'Saved {small_hash(packet.hash)} from {str(self.addr)}')
		return True

	def try_reading_buffer(self):
		if len(self.buffer) < 4:
			return

		packet_len = int.from_bytes(self.buffer[:4], 'big')
		if packet_len > 3 * 1024 * 1024:
			print(f"{self.peername} sent a packet over 3 Mb.")
			self.transport.close()
			return

		if len(self.buffer) < packet_len + 4:
			return

		packet = protocol.deserialize(self.buffer[4:packet_len+4])
		self.buffer = self.buffer[packet_len+4:]
		print(f"{self.peername} sent a {type(packet)}.")

		if isinstance(packet, ClientUpdate):
			self.steamid = packet.steamid
			self.sounds = packet.sounds_list
			if self.room_name != packet.room_name:
				self.join_room(packet.room_name)

			self.send(
				ServerRoomSounds(
					available_hashes=list(self.room.available_sounds),
					missing_hashes=list(self.room.missing_sounds)
				)
			)
		elif isinstance(packet, ClientSoundRequest):
			if packet.sound_hash not in available_sounds:
				return

			response = SoundResponse()
			with open('cache/' + packet.sound_hash.hex(), 'rb') as infile:
				response.data = infile.read()
				response.hash = packet.sound_hash

			print(f'{self.steamid} is downloading {small_hash(packet.sound_hash)}')
			self.send(response)
			print(f'{self.steamid} is done downloading {small_hash(packet.sound_hash)}')
		elif isinstance(packet, GameEvent):
			if packet.proposed_sound_hash not in self.room.available_sounds:
				return

			event_class = get_event_class(packet)
			steamid = self.steamid if event_class == 'normal' else 0
			if event_class == 'shared':
				self.room.play_shared(packet.type, packet.proposed_sound_hash)
			else:
				self.room.play(steamid if event_class == 'normal' else 0, packet.proposed_sound_hash)
		elif isinstance(packet, SoundResponse):
			self.save_sound(packet)
		else:
			print("Unhandled packet type. Ignoring.")

	def send(self, packet):
		raw_packet = protocol.serialize(packet)
		raw_header = len(raw_packet).to_bytes(4, byteorder='big')
		self.transport.write(raw_header + raw_packet)


if __name__ == '__main__':
	# We're using Python 3.7 mostly for asyncio features.
	if sys.version_info[0] < 3 or sys.version_info[1] < 7:
		print("Python 3.7+ is required, but you are running Python %d.%d." % (sys.version_info[0], sys.version_info[1]))

	for filename in os.listdir('cache'):
		# Only add valid files
		if filename.startswith('.') or not os.path.isfile('cache/' + filename):
			continue
		available_sounds.add(bytes.fromhex(filename))

	with config.lock:
		port = config.config['Network'].getint('ServerPort', 4004)
		try:
			sslctx = ssl.SSLContext()
			sslctx.load_cert_chain(
				config.config['Network'].get('certfile', 'certfile.crt'),
				keyfile=config.config['Network'].get('keyfile', 'keyfile.key'),
			)
		except (FileNotFoundError, ssl.SSLError) as err:
			print(f"Failed to initialize SSL : {err}")
			print(f"Serving without encryption.")
			sslctx = None

	loop = asyncio.get_event_loop()
	coro = loop.create_server(Connection, '0.0.0.0', port, ssl=sslctx)
	server = loop.run_until_complete(coro)

	print(f"Started sound server on {server.sockets[0].getsockname()}")
	try:
		loop.run_forever()
	except KeyboardInterrupt:
		pass

	server.close()
	loop.run_until_complete(server.wait_closed())
	loop.close()
