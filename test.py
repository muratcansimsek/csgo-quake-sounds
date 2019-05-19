import random
import threading
import unittest
from time import sleep
from unittest.mock import patch, MagicMock, Mock

import sounds
import server
from config import config
from client import Client
from packets_pb2 import GameEvent
from threadripper import Threadripper


class DummyGui:
	"""There's probably a better way to do this..."""
	def __init__(self):
		self.updateSoundsBtn = MagicMock(Enabled=True)
		self.downloadWhenAliveChk = MagicMock(Enabled=True)
		self.uploadWhenAliveChk = MagicMock(Enabled=True)
		self.shardCodeIpt = MagicMock(GetValue=lambda : 'shard_code')

	def SetStatusText(self, *args):
		pass


class MockClient(Client):
	"""Simpler client for testing."""

	def __init__(self, steamid=random.randint(1, 999999999)):
		self.threadripper = Threadripper()
		self.gui = DummyGui()
		self.shard_code = 'shard_code'
		self.sounds = sounds.SoundManager(self)

		# Load sounds silently
		self.sounds.play = Mock()

		self.state = Mock(
			current_round=1,
			round_kills=3,
			lock=threading.Lock(),
			old_state=Mock(steamid=steamid)
		)
		threading.Thread(target=self.listen, daemon=True).start()

		# Wait for server connection before reloading sounds
		sleep(0.1)
		self.reload_sounds()

	def error_callback(self, msg):
		raise Exception(msg)


class TestClient(unittest.TestCase):
	"""Tests for client.py and related code.

	The following tests assume you have at least the default quake sounds in your sound directory.
	The following tests assume the server is working without any bugs that could carry across tests.
	"""

	def setUp(self):
		# Run a local sound server
		config.set('Network', 'ServerIP', '127.0.0.1')
		config.set('Network', 'ServerPort', '4004')
		self.server = server.Server()
		threading.Thread(target=self.server.serve, daemon=True).start()
		sleep(1)  # Wait for server to start (shh it's fine)

	# @patch('util.unsafe_print')  # Feel free to comment this for easier debugging
	@patch('wx.CallAfter')
	def test_receive_sound(self, *args):
		alice = MockClient('123123123')
		self.assertEqual(alice.sounds.play.call_count, 1)
		bob = MockClient('456456456')
		self.assertEqual(bob.sounds.play.call_count, 1)
		charlie = MockClient('789789789')
		self.assertEqual(charlie.sounds.play.call_count, 1)

		# Wait for clients to connect to server
		sleep(0.1)
		with self.server.clients_lock:
			self.assertEqual(len(self.server.clients), 3)
			# For some reason, the second socket MAGICALLY TAKES OVER the first one
			# Yes, THEY'RE IN SEPARATE THREADS, contained in separate classes,
			# and NEVER INTERACT with each other.
			# So, what happens ? Second socket changes first socket's steam id, but it
			# never sets its own ! As a result, one of the clients is in a glitched state.
			# This is where I give up.
			print(self.server.clients[0].steamid)
			print(self.server.clients[1].steamid)
			print(self.server.clients[2].steamid)

		# Send a sound, and assert it is received by bob
		alice.sounds.send(GameEvent.COLLATERAL, alice.state)
		sleep(0.5)
		self.assertEqual(bob.sounds.play.call_count, 2)

if __name__ == '__main__':
	unittest.main()
