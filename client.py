import socket
import wx
from http.server import HTTPServer
from queue import Empty, LifoQueue
from time import sleep
from threading import Thread, Lock

import config
from packets_pb2 import PacketInfo, GameEvent, PlaySound, SoundRequest, SoundResponse, ClientUpdate
from sounds import sounds
from state import state, PostHandler
from util import print, small_hash

class Client:
	def __init__(self):
		self.sock_lock = Lock()
		self.connected = False
		self.packet_sent = True
		self.reconnect_timeout = 1
		self.shard_code = ''

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
			self.sock.sendall(header.SerializeToString())
			self.sock.sendall(raw_packet)
			self.packet_sent = True

		round_change_types = [ GameEvent.ROUND_WIN, GameEvent.ROUND_LOSE, GameEvent.SUICIDE, GameEvent.DEATH, GameEvent.ROUND_START ]
		if type == PacketInfo.GAME_EVENT:
			if packet.update in round_change_types:
				try:
					item = self.download_queue.get(block=False)
					self.request_sound(item)
				except Empty:
					pass
				try:
					item = self.upload_queue.get(block=False)
					self.respond_sound(item)
				except Empty:
					pass

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
		if not self.connected:
			wx.CallAfter(self.gui.SetStatusText, 'Connecting to sound sync server...')
			return
		with state.lock:
			if state.old_state == None:
				wx.CallAfter(self.gui.SetStatusText, 'Waiting for CS:GO...')
			elif state.old_state.is_ingame:
				wx.CallAfter(self.gui.SetStatusText, '%s - round %s - steamID %s' % (state.old_state.phase, state.old_state.current_round, state.old_state.steamid))
			else:
				wx.CallAfter(self.gui.SetStatusText, 'Ready.')
		
	def file_callback(self, hash, file):
		sounds.cache[hash] = file
		wx.CallAfter(self.gui.SetStatusText, 'Loading sounds... (%d/%d)' % (self.loaded_sounds, self.max_sounds))
		self.loaded_sounds = self.loaded_sounds + 1
	
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

	def request_sound(self, hash):
		if state.is_alive() and not self.gui.downloadWhenAliveChk.Value:
			self.download_queue.put(hash)
			return

		wx.CallAfter(self.gui.SetStatusText, 'Downloading %s... (%d/%d)' % (small_hash(hash), self.downloaded + 1, self.download_total))
		packet = SoundRequest()
		packet.sound_hash.append(hash)
		self.send(PacketInfo.SOUND_REQUEST, packet)
		self.downloaded = self.downloaded + 1

		if not state.is_alive() or self.gui.downloadWhenAliveChk.Value:
			# Still not playing : request more sounds!
			try:
				item = self.download_queue.get(block=False)
				self.request_sound(item)
			except Empty:
				pass
	
	def respond_sound(self, hash):
		if state.is_alive() and not self.gui.uploadWhenAliveChk.Value:
			self.upload_queue.put(hash)
			return

		wx.CallAfter(self.gui.SetStatusText, 'Uploading %s... (%d/%d)' % (small_hash(hash), self.uploaded + 1, self.upload_total))
		with open('cache/' + hash.hex(), 'rb') as infile:
			packet = SoundResponse()
			packet.data = infile.read()
			packet.hash = hash
			self.send(PacketInfo.SOUND_RESPONSE, packet)
			self.uploaded = self.uploaded + 1

		if not state.is_alive() or self.gui.uploadWhenAliveChk.Value:
			# Still not playing : send more sounds!
			try:
				item = self.upload_queue.get(block=False)
				self.respond_sound(item)
			except Empty:
				self.update_status()

	def handle(self, packet_type, raw_packet):
		print('Received %s packet' % PacketInfo.Type.Name(packet_type))

		if packet_type == PacketInfo.PLAY_SOUND:
			packet = PlaySound()
			packet.ParseFromString(raw_packet)
			if not sounds.play(packet):
				self.download_total = self.download_total + 1
				self.request_sound(packet.sound_hash)
		elif packet_type == PacketInfo.SOUND_REQUEST:
			req = SoundRequest()
			req.ParseFromString(raw_packet)

			for hash in req.sound_hash:
				self.upload_total = self.upload_total + 1
				self.respond_sound(hash)
		elif packet_type == PacketInfo.SOUND_RESPONSE:
			packet = SoundResponse()
			packet.ParseFromString(raw_packet)
			sounds.save(packet)
			sounds.play_received(packet.hash)
		elif packet_type == PacketInfo.SOUNDS_LIST:
			packet = SoundRequest()
			packet.ParseFromString(raw_packet)
			for hash in packet.sound_hash:
				with sounds.cache_lock:
					if hash not in sounds.cache:
						self.download_total = self.download_total + 1
						self.request_sound(hash)
		else:
			print("Unhandle packet type!")

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
					if packet_info.length > 2 * 1024 * 1024:
						# Don't allow files or packets over 2 Mb
						print('Invalid payload size, reconnecting')
						self.connected = False
						self.sock.shutdown(socket.SHUT_RDWR)
						continue

					data = b''
					received = 0
					while received < packet_info.length:
						chunk = self.sock.recv(packet_info.length - received)
						data += chunk
						received += len(chunk)
				self.handle(packet_info.type, data)
			except ConnectionResetError:
				print("Connection reset, reconnecting")
				self.connected = False
				self.sock.shutdown(socket.SHUT_RDWR)
			except socket.timeout:
				pass
			except socket.error as msg:
				print("Connection error: " + str(msg))
				self.connected = False
				self.sock.shutdown(socket.SHUT_RDWR)
