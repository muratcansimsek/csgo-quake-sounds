import asyncio
import os
import wx  # type: ignore
import packel
from queue import Empty, Queue, LifoQueue
from time import sleep
from threading import Thread
from typing import Optional

import config
from protocol import protocol, ClientUpdate, ClientSoundRequest, GameEvent, PlaySound, SoundResponse, ServerRoomSounds
from sounds import SoundManager
from state import CSGOState
from util import print


class Client:
	connected = False
	reconnect_timeout = 1
	room_name: Optional[str] = None
	downloaded = 0
	download_total = 0
	uploaded = 0
	upload_total = 0
	loaded_sounds = 0
	max_sounds = 0
	reader = None
	writer = None

	packets_to_send: Queue = Queue()
	sounds_to_download: LifoQueue = LifoQueue()
	sounds_to_upload: LifoQueue = LifoQueue()

	def __init__(self, gui) -> None:
		self.gui = gui
		self.sounds = SoundManager(self)
		self.state = CSGOState(self)
		self.loop = asyncio.new_event_loop()

		Thread(target=self.listen, daemon=True).start()
		Thread(target=self.keepalive, daemon=True).start()

	def send(self, packet: packel.Packet):
		self.packets_to_send.put(packet)

	def client_update(self) -> None:
		"""Thread-safe: Send a packet informing the server of our current state."""
		if self.room_name is None:
			if self.writer is not None and not self.writer.is_closing():
				self.writer.close()
			return

		packet = ClientUpdate(shard_code=self.room_name)

		with self.state.lock:
			if self.state.old_state is not None and self.state.old_state.steamid is not None:
				packet.steamid = int(self.state.old_state.steamid)

		download_folder = os.path.join('sounds', 'Downloaded')
		with self.sounds.lock:
			available_sounds = self.sounds.available_sounds.items()
		packet.sounds_list = [bytes.fromhex(v) for k, v in available_sounds if not k.startswith(download_folder)]

		self.send(packet)

	def update_status(self) -> None:
		if not self.connected:
			wx.CallAfter(self.gui.SetStatusText, 'Connecting to sound sync server...')
			return
		with self.state.lock:
			if self.state.old_state == None:
				wx.CallAfter(self.gui.SetStatusText, 'Waiting for CS:GO...')
			elif self.state.old_state.is_ingame:
				phase = self.state.old_state.phase
				if phase == 'unknown':
					phase = ''
				else:
					phase = ' (%s)' % phase
				wx.CallAfter(
					self.gui.SetStatusText,
					f'Room "{self.room_name}" - Round {self.state.old_state.current_round}{phase}'
				)
			else:
				wx.CallAfter(self.gui.SetStatusText, 'Room "%s" - Not in a match.' % self.room_name)

	def file_callback(self) -> None:
		self.loaded_sounds = self.loaded_sounds + 1
		wx.CallAfter(self.gui.SetStatusText, 'Loading sounds... (%d/%d)' % (self.loaded_sounds, self.max_sounds))

	def error_callback(self, msg: str) -> None:
		self.loaded_sounds = self.loaded_sounds + 1
		dialog = wx.GenericMessageDialog(
			self.gui, message=msg, caption='Sound loading error', style=wx.OK | wx.ICON_ERROR
		)
		wx.CallAfter(dialog.ShowModal)
	
	def reload_sounds(self) -> None:
		"""Reloads all sounds. Do not call outside of gui, unless you disable/reenable the update sounds button."""
		self.loaded_sounds = 0
		self.max_sounds = self.sounds.max_sounds()
		self.sounds.reload(self.file_callback, self.error_callback)
		wx.CallAfter(self.gui.updateSoundsBtn.Enable)
		self.update_status()
		self.client_update()

		# Play round start sound
		playpacket = PlaySound()
		playpacket.steamid = 0
		random_hash = self.sounds.get_random(GameEvent.Type.ROUND_START, None)
		if random_hash is not None:
			playpacket.sound_hash = random_hash
			self.sounds.play(playpacket)

	def request_sounds(self):
		try:
			hash = self.sounds_to_download.get(block=False)
			if hash not in self.sounds.available_sounds.values():
				self.send(ClientSoundRequest(sound_hash=hash))
		except Empty:
			if self.download_total != 0:
				self.update_status()
				self.download_total = 0

	def respond_sounds(self) -> None:
		try:
			packet = SoundResponse()
			packet.hash = self.sounds_to_upload.get(block=False)
			hash = packet.hash.hex()
			sound_filepath: Optional[str] = None
			with self.sounds.lock:
				for filepath, filehash in self.sounds.available_sounds.items():
					if filehash == hash:
						sound_filepath = filepath
						break
			if sound_filepath is not None:
				with open(filepath, 'rb') as infile:
					packet.data = infile.read()
				self.send(packet)
		except Empty:
			if self.upload_total != 0:
				self.update_status()
				self.upload_total = 0

	def handle(self, packet) -> None:
		print(f"Received {type(packet)}")

		if isinstance(packet, PlaySound):
			if self.state.is_ingame():
				if not self.sounds.play(packet):
					self.download_total = self.download_total + 1
					self.sounds_to_download.put(packet.sound_hash)
		elif isinstance(packet, ServerRoomSounds):
			with self.sounds.lock:
				for hash in packet.available_hashes:
					if hash not in self.sounds.available_sounds.values():
						self.sounds_to_download.put(hash)

			while True:
				try:
					self.sounds_to_upload.get()
				except Empty:
					break
			for hash in packet.missing_hashes:
				self.sounds_to_upload.put(hash)
				self.upload_total += 1
		elif isinstance(packet, SoundResponse):
			# Give some feedback about download status
			wx.CallAfter(self.gui.SetStatusText, f"Downloading sound {self.downloaded + 1}/{self.download_total}...")
			self.sounds.save(packet)
		else:
			print("Unhandled packet type!")

	def keepalive(self):
		while True:
			self.client_update()
			sleep(10)

	async def connect(self):
		while self.room_name is None:
			await asyncio.sleep(0.1)

		while self.writer is None or self.writer.is_closing():
			# Reset packet queue
			self.packets_to_send = Queue()
			self.sounds_to_download = LifoQueue()
			self.sounds_to_upload = LifoQueue()
			self.recvbuf = b''

			with config.lock:
				ip = config.config['Network'].get('ServerIP', 'kiwec.net')
				port = config.config['Network'].getint('ServerPort', 4004)
				ssl = config.config['Network'].getboolean('SSL', False)
				if ssl is False:
					ssl = None

			try:
				self.reader, self.writer = await asyncio.open_connection(ip, port, ssl=ssl)
				self.reconnect_timeout = 1
				self.client_update()
			except ConnectionRefusedError:
				await asyncio.sleep(self.reconnect_timeout)
				self.reconnect_timeout *= 2
				if self.reconnect_timeout > 60:
					self.reconnect_timeout = 60

	async def run(self):
		while True:
			if not self.state.is_alive():
				self.request_sounds()
				self.respond_sounds()

			# Send stuff
			try:
				packet = self.packets_to_send.get(timeout=0.1)
				raw_packet = protocol.serialize(packet)
				raw_header = len(raw_packet).to_bytes(4, byteorder='big')

				if isinstance(packet, SoundResponse):
					wx.CallAfter(
						self.gui.SetStatusText,
						f'Uploading sound {self.uploaded + 1}/{self.upload_total}...)'
					)

				self.writer.write(raw_header + raw_packet)
				await self.writer.drain()
			except Empty:
				pass

			# Receive stuff
			data = await self.reader.read(4)
			if not data: break
			self.recvbuf = self.recvbuf + data

			if len(self.recvbuf) >= 4:
				recv_len = int.from_bytes(self.recvbuf[:4], 'big')
				remaining = (recv_len + 4) - len(self.recvbuf)
				if remaining > 0:
					data = await self.reader.read(remaining)
					if not data: break
					self.recvbuf = self.recvbuf + data
					remaining = (recv_len + 4) - len(self.recvbuf)
				if remaining <= 0:
					raw_packet = self.recvbuf[4:recv_len+4]
					self.recvbuf = self.recvbuf[recv_len+4:]
					self.handle(protocol.deserialize(raw_packet))

	def listen(self):
		while True:
			self.loop.run_until_complete(self.connect())
			self.loop.run_until_complete(self.run())
