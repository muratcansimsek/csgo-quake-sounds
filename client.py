import os
import socket
import wx
from http.server import HTTPServer
from queue import LifoQueue
from time import sleep
from threading import Thread, Lock

import config
from packets_pb2 import PacketInfo, PlaySound, SoundRequest, SoundResponse, ClientUpdate
from sounds import sounds
from state import state, PostHandler
from util import print

class Client:
	def __init__(self):
		self.sock_lock = Lock()
		self.sock = None
		self.connected = False
		self.packet_sent = True
		self.reconnect_timeout = 1
		self.shard_code = ''

		# The following are only accessed from the network thread,
		# and are safe to use without locking.
		self.download_queue = LifoQueue()
		self.upload_queue = LifoQueue()
		self.downloaded = 0
		self.download_total = 0
		self.uploaded = 0
		self.upload_total = 0

	def init(self, gui):
		"""Non-blocking init"""
		self.gui = gui
		self.shard_code = gui.shardCodeIpt.GetValue()
		sounds.init(self)
		state.init(self)
		gamestate_server = HTTPServer(('127.0.0.1', 3000), PostHandler)
		Thread(target=gamestate_server.serve_forever, daemon=True).start()
		Thread(target=self.listen, daemon=True).start()
		Thread(target=self.keepalive, daemon=True).start()
	
	def send(self, type, packet):
		raw_packet = packet.SerializeToString()
		header = PacketInfo()
		header.type = type
		header.length = len(raw_packet)
		
		with self.sock_lock:
			if not self.connected:
				return
			print('Sending %s packet' % PacketInfo.Type.Name(type))
			try:
				self.sock.sendall(header.SerializeToString())
			except:
				self.connected = False
				self.sock.shutdown(socket.SHUT_RDWR)
				return

			total_sent = 0
			while total_sent < header.length:
				# Give some feedback about sound upload status
				if header.type == PacketInfo.SOUND_RESPONSE:
					wx.CallAfter(
						self.gui.SetStatusText,
						'Uploading sound {0}/{1}... ({2}%)'.format(
							self.uploaded + 1,
							self.upload_total,
							int(total_sent / header.length * 100)
						)
					)

				sent = self.sock.send(raw_packet)
				if sent == 0:
					self.connected = False
					self.sock.shutdown(socket.SHUT_RDWR)
					return
				total_sent += sent
			self.packet_sent = True

	def client_update(self):
		packet = ClientUpdate()
		with state.lock:
			if state.old_state == None or not state.old_state.is_ingame:
				packet.status = ClientUpdate.UNCONNECTED
				packet.map = b''
				packet.steamid = 0
			else:
				packet.status = ClientUpdate.CONNECTED
				packet.map = b'' # TODO
				packet.steamid = int(state.old_state.steamid)

		packet.shard_code = self.shard_code.encode('utf-8')
		self.send(PacketInfo.CLIENT_UPDATE, packet)

	def update_status(self):
		with self.sock_lock:
			if not self.connected:
				wx.CallAfter(self.gui.SetStatusText, 'Connecting to sound sync server...')
				return
			with state.lock:
				if state.old_state == None:
					wx.CallAfter(self.gui.SetStatusText, 'Waiting for CS:GO...')
				elif state.old_state.is_ingame:
					phase = state.old_state.phase
					if phase == 'unknown':
						phase = ''
					else:
						phase = ' (%s)' % phase
					wx.CallAfter(self.gui.SetStatusText, 'Room "%s" - Round %s%s' % (self.shard_code, state.old_state.current_round, phase))
				else:
					wx.CallAfter(self.gui.SetStatusText, 'Room "%s" - Not in a match.' % self.shard_code)
		
	def file_callback(self, hash, file):
		sounds.cache[hash] = file
		self.loaded_sounds = self.loaded_sounds + 1
		wx.CallAfter(self.gui.SetStatusText, 'Loading sounds... (%d/%d)' % (self.loaded_sounds, self.max_sounds))
	
	def error_callback(self, msg):
		dialog = wx.GenericMessageDialog(self.gui, message=msg, caption='Sound loading error', style=wx.OK | wx.ICON_ERROR)
		wx.CallAfter(dialog.ShowModal)
	
	def reload_sounds(self):
		"""Reloads all sounds. Not thread safe, should only be called from GUI"""
		self.loaded_sounds = 0
		self.max_sounds = len(sounds.sound_list('sounds'))

		sounds.load(self.file_callback, self.error_callback)
		wx.CallAfter(self.gui.updateSoundsBtn.Enable)
		self.update_status()

		# Send sound list to server
		with self.sock_lock:
			if not self.connected:
				return
		packet = SoundRequest()
		with sounds.cache_lock:
			for hash in sounds.cache:
				packet.sound_hash.append(hash)
		self.send(PacketInfo.SOUNDS_LIST, packet)

	def request_sounds(self):
		if state.is_alive() and not self.gui.downloadWhenAliveChk.Value:
			return
		if self.download_queue.empty():
			if self.download_total != 0:
				self.update_status()
				self.download_total = 0
			return

		hash = self.download_queue.get()
		packet = SoundRequest()
		packet.sound_hash.append(hash)
		self.send(PacketInfo.SOUND_REQUEST, packet)
		self.downloaded = self.downloaded + 1

	def respond_sounds(self):
		if state.is_alive() and not self.gui.uploadWhenAliveChk.Value:
			return
		if self.upload_queue.empty():
			if self.upload_total != 0:
				self.update_status()
				self.upload_total = 0
			return

		hash = self.upload_queue.get()
		filepath = os.path.join('cache', hash.hex())
		with open(filepath, 'rb') as infile:
			packet = SoundResponse()
			packet.data = infile.read()
			packet.hash = hash
			self.send(PacketInfo.SOUND_RESPONSE, packet)
			self.uploaded = self.uploaded + 1

	def handle(self, packet_type, raw_packet):
		print('Received %s packet' % PacketInfo.Type.Name(packet_type))

		if packet_type == PacketInfo.PLAY_SOUND:
			packet = PlaySound()
			packet.ParseFromString(raw_packet)
			if not sounds.play(packet):
				self.download_total = self.download_total + 1
				self.download_queue.put(packet.sound_hash)
		elif packet_type == PacketInfo.SOUND_REQUEST:
			req = SoundRequest()
			req.ParseFromString(raw_packet)

			self.upload_total += len(req.sound_hash)
			for hash in req.sound_hash:
				self.upload_queue.put(hash)
		elif packet_type == PacketInfo.SOUND_RESPONSE:
			packet = SoundResponse()
			packet.ParseFromString(raw_packet)
			sounds.save(packet)
			sounds.play_received(packet.hash)
		elif packet_type == PacketInfo.SOUNDS_LIST:
			packet = SoundRequest()
			packet.ParseFromString(raw_packet)

			download_list = []
			with sounds.cache_lock:
				for hash in packet.sound_hash:
					if hash not in sounds.cache:
						download_list.append(hash)
			self.download_total += len(download_list)
			for hash in download_list:
				self.download_queue.put(hash)
		else:
			print("Unhandled packet type!")

	def try_reconnect(self):
		"""Tries reconnecting - returns False if disconnected"""
		with self.sock_lock:
			if not self.connected:
				try:
					with config.lock:
						ip = config.config['Network'].get('ServerIP', 'kiwec.net')
						port = config.config['Network'].getint('ServerPort', 4004)
					self.sock = socket.create_connection((ip, port))
					self.connected = True
					self.reconnect_timeout = 1
				except ConnectionRefusedError:
					self.connected = False
					if self.sock is not None:
						self.sock.shutdown(socket.SHUT_RDWR)

					sleep(self.reconnect_timeout)
					self.reconnect_timeout *= 2
					if self.reconnect_timeout > 60:
						self.reconnect_timeout = 60

					return False
			else:
				return True
		self.client_update()
		return True

	def keepalive(self):
		while True:
			# Send a packet every 10 seconds
			should_update = True
			with self.sock_lock:
				if self.packet_sent:
					should_update = False

			if should_update:
				self.client_update()

			with self.sock_lock:
				self.packet_sent = False

			sleep(10)

	def listen(self):
		while True:
			if not self.try_reconnect():
				continue

			try:
				with self.sock_lock:
					self.sock.settimeout(0.1)
					data = self.sock.recv(7)
					self.sock.settimeout(None)
					if len(data) == 0:
						print('Invalid header size, reconnecting')
						self.connected = False
						self.sock.shutdown(socket.SHUT_RDWR)
						continue

					packet_info = PacketInfo()
					packet_info.ParseFromString(data)
					if packet_info.length > 3 * 1024 * 1024:
						# Don't allow files or packets over 3 Mb
						print('Invalid payload size, reconnecting')
						self.connected = False
						self.sock.shutdown(socket.SHUT_RDWR)
						continue

					data = b''
					received = 0
					while received < packet_info.length:
						# Give some feedback about download status
						if packet_info.type == PacketInfo.SOUND_RESPONSE:
							wx.CallAfter(
								self.gui.SetStatusText,
								'Downloading sound {0}/{1}... ({2}%)'.format(
									self.downloaded + 1,
									self.download_total,
									int(received / packet_info.length * 100)
								)
							)

						chunk = self.sock.recv(packet_info.length - received)
						data += chunk
						received += len(chunk)
				self.handle(packet_info.type, data)
			except ConnectionResetError:
				print("Connection reset, reconnecting")
				self.connected = False
				self.sock.shutdown(socket.SHUT_RDWR)
			except socket.timeout:
				self.sock.settimeout(None)
				self.request_sounds()
				self.respond_sounds()
			except socket.error as msg:
				print("Connection error: " + str(msg))
				self.connected = False
				self.sock.shutdown(socket.SHUT_RDWR)
