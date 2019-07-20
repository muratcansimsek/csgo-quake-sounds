import os
import socket
import wx  # type: ignore
from queue import Empty, Queue, LifoQueue
from time import sleep
from threading import Thread
from typing import Optional

import config
from packets_pb2 import PacketInfo, PlaySound, SoundRequest, SoundResponse, ClientUpdate
from sounds import SoundManager
from state import CSGOState
from util import print


class Client:
	sock = None
	connected = False
	reconnect_timeout = 1
	room_name: Optional[str] = None
	downloaded = 0
	download_total = 0
	uploaded = 0
	upload_total = 0
	loaded_sounds = 0
	max_sounds = 0

	packets_to_send: Queue = Queue()
	sounds_to_download: LifoQueue = LifoQueue()
	sounds_to_upload: LifoQueue = LifoQueue()

	def __init__(self, gui) -> None:
		self.gui = gui
		self.sounds = SoundManager(self)
		self.state = CSGOState(self)

		Thread(target=self.listen, daemon=True).start()
		Thread(target=self.keepalive, daemon=True).start()

	def send(self, type, packet):
		# Build the packet...
		raw_packet = packet.SerializeToString()
		raw_header = len(raw_packet).to_bytes(4, byteorder='big') + type.to_bytes(4, byteorder='big')

		# ...And off it goes
		self.packets_to_send.put([raw_header, raw_packet])

	def client_update(self) -> None:
		"""Thread-safe: Send a packet informing the server of our current state."""
		if self.room_name is None:
			return

		packet = ClientUpdate()

		# Unused
		packet.status = ClientUpdate.CONNECTED
		packet.map = b''

		# Set current steamid and shard core
		packet.steamid = 0
		with self.state.lock:
			if self.state.old_state is not None and self.state.old_state.steamid is not None:
				packet.steamid = int(self.state.old_state.steamid)
		packet.shard_code = self.room_name.encode('utf-8')

		self.send(PacketInfo.CLIENT_UPDATE, packet)

	def update_status(self):
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

		# Send the list of all the sounds we own (except from the ones in the Downloaded folder) to server
		packet = SoundRequest()
		download_folder = os.path.join('sounds', 'Downloaded')
		with self.sounds.lock:
			available_sounds = self.sounds.available_sounds.items()
		personal_sounds = [bytes.fromhex(v) for k, v in available_sounds if not k.startswith(download_folder)]
		packet.sound_hash.extend(personal_sounds)
		self.send(PacketInfo.SOUNDS_LIST, packet)

	def request_sounds(self):
		try:
			hash = self.sounds_to_download.get(block=False)
			packet = SoundRequest()
			packet.sound_hash.append(hash)
			self.send(PacketInfo.SOUND_REQUEST, packet)
		except Empty:
			if self.download_total != 0:
				self.update_status()
				self.download_total = 0

	def respond_sounds(self) -> None:
		try:
			hash = self.sounds_to_upload.get(block=False)
			with self.sounds.lock:
				for filepath, filehash in self.sounds.available_sounds.items():
					if filehash == hash:
						with open(filepath, 'rb') as infile:
							packet = SoundResponse()
							packet.data = infile.read()
						packet.hash = hash
						self.send(PacketInfo.SOUND_RESPONSE, packet)
						return
		except Empty:
			if self.upload_total != 0:
				self.update_status()
				self.upload_total = 0

	def handle(self, packet_type, raw_packet) -> None:
		print('Received %s packet' % PacketInfo.Type.Name(packet_type))

		if packet_type == PacketInfo.PLAY_SOUND and self.state.is_ingame():
			packet = PlaySound()
			packet.ParseFromString(raw_packet)
			if not self.sounds.play(packet):
				self.download_total = self.download_total + 1
				self.sounds_to_download.put(packet.sound_hash)
		elif packet_type == PacketInfo.SOUND_REQUEST:
			req = SoundRequest()
			req.ParseFromString(raw_packet)

			self.upload_total += len(req.sound_hash)
			for hash in req.sound_hash:
				self.sounds_to_upload.put(hash)
		elif packet_type == PacketInfo.SOUND_RESPONSE:
			packet = SoundResponse()
			packet.ParseFromString(raw_packet)
			self.sounds.save(packet)
		elif packet_type == PacketInfo.SOUNDS_LIST:
			packet = SoundRequest()
			packet.ParseFromString(raw_packet)

			with self.sounds.lock:
				available_sounds = self.sounds.available_sounds.values()
			for hash in packet.sound_hash:
				if hash.hex() not in available_sounds:
					self.sounds_to_download.put(hash)
					self.download_total = self.download_total + 1
		else:
			print("Unhandled packet type!")

	def keepalive(self):
		while True:
			self.client_update()
			sleep(10)

	def listen(self):
		while True:
			# No room joined : disconnect and wait
			if self.room_name is None:
				if self.connected is True:
					self.connected = False
					if self.sock is not None:
						self.sock.shutdown(socket.SHUT_RDWR)
				sleep(0.1)
				continue

			if not self.connected:
				# Reset packet queue
				self.packets_to_send = Queue()
				self.sounds_to_download = LifoQueue()
				self.sounds_to_upload = LifoQueue()

				try:
					with config.lock:
						ip = config.config['Network'].get('ServerIP', 'kiwec.net')
						port = config.config['Network'].getint('ServerPort', 4004)
					self.sock = socket.create_connection((ip, port))
					self.connected = True
					self.reconnect_timeout = 1
					self.client_update()
				except ConnectionRefusedError:
					self.connected = False
					if self.sock is not None:
						self.sock.shutdown(socket.SHUT_RDWR)

					sleep(self.reconnect_timeout)
					self.reconnect_timeout *= 2
					if self.reconnect_timeout > 60:
						self.reconnect_timeout = 60
					continue

			# The big network loop
			try:

				# Let's try SENDING some packets!
				if not self.state.is_alive():
					self.request_sounds()
					self.respond_sounds()
				try:
					raw_header, raw_packet = self.packets_to_send.get(block=False)
					self.sock.sendall(raw_header)
					packet_length = int.from_bytes(raw_header[0:4], byteorder='big')
					packet_type = int.from_bytes(raw_header[4:8], byteorder='big')

					total_sent = 0
					while total_sent < packet_length:
						# Give some feedback about sound upload status
						if packet_type == PacketInfo.SOUND_RESPONSE:
							sent_percent = int(total_sent / packet_length * 100)
							wx.CallAfter(
								self.gui.SetStatusText,
								f'Uploading sound {self.uploaded + 1}/{self.upload_total}... ({sent_percent}%)'
							)

						sent = self.sock.send(raw_packet)
						if sent == 0:
							raise ConnectionResetError
						total_sent += sent
						if total_sent < packet_length:
							raw_packet = raw_packet[sent:]
				except Empty:
					# Nothing to send :(
					pass

				# Let's try RECEIVING some packets!
				self.sock.settimeout(0.1)
				data = self.sock.recv(8)
				self.sock.settimeout(None)
				if len(data) == 0:
					print('Invalid header size, reconnecting')
					self.connected = False
					self.sock.shutdown(socket.SHUT_RDWR)
					continue


				packet_len = int.from_bytes(data[0:4], byteorder='big')
				packet_type = int.from_bytes(data[4:8], byteorder='big')
				if packet_len > 3 * 1024 * 1024:
					# Don't allow files or packets over 3 Mb
					print('Invalid payload size, reconnecting')
					self.connected = False
					self.sock.shutdown(socket.SHUT_RDWR)
					continue

				data = b''
				received = 0
				while received < packet_len:
					# Give some feedback about download status
					if packet_type == PacketInfo.SOUND_RESPONSE:
						wx.CallAfter(
							self.gui.SetStatusText,
							'Downloading sound {0}/{1}... ({2}%)'.format(
								self.downloaded + 1,
								self.download_total,
								int(received / packet_len * 100)
							)
						)

					chunk = self.sock.recv(packet_len - received)
					data += chunk
					received += len(chunk)
				self.handle(packet_type, data)

			# Handle connection errors
			except ConnectionResetError:
				print("Connection reset, reconnecting")
				self.connected = False
				self.sock.shutdown(socket.SHUT_RDWR)
			except socket.timeout:
				self.sock.settimeout(None)
			except socket.error as msg:
				print("Connection error: " + str(msg))
				self.connected = False
				self.sock.shutdown(socket.SHUT_RDWR)
