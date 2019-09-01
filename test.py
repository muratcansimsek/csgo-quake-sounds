import asyncio
import hashlib
import os
import random
import shutil
import threading
import unittest
from unittest.mock import patch, MagicMock, Mock
from typing import Callable

import sounds
import server
from config import config
from client import Client
from protocol import GameEvent
from state import CSGOState


class DummyGui:
	"""There's probably a better way to do this..."""
	def __init__(self):
		self.updateSoundsBtn = MagicMock(Enabled=True)
		self.shardCodeIpt = MagicMock(GetValue=lambda : 'shard_code')

	def SetStatusText(self, *args):
		pass


class PlayerState:
	is_ingame = True
	phase = 'live'
	current_round = 1

	def __init__(self, steamid):
		self.steamid = steamid
		self.playerid = steamid


class MockState(CSGOState):
	current_round = 1
	round_kills = 3

	def __init__(self, client, steamid):
		self.lock = threading.Lock()
		self.old_state = PlayerState(steamid)
		self.client = client

	def is_alive(self) -> bool:
		return False  # always download/upload sounds


class MockClient(Client):
	"""Simpler client for testing.

	TODO ASYNC REWRITE
	"""

	def __init__(self, steamid=random.randint(1, 999999999)):
		self.gui = DummyGui()
		self.room_name = 'shard_code'
		self.sounds = SoundManager(self)
		self.loop = asyncio.get_event_loop()

		# Mock stuff
		self.sounds.play = Mock()
		self.state = MockState(self, steamid)

		threading.Thread(target=self.listen, daemon=True).start()

		# Wait for server connection before reloading sounds
		asyncio.sleep(0.1)
		await self.reload_sounds()

	def error_callback(self, msg):
		raise Exception(msg)


async def run_server(loop):
	global server
	coro = loop.create_server(server.Connection, '127.0.0.1', 4004, ssl=None)
	server = await loop.run_until_complete(coro)


class TestClient(unittest.TestCase):
	"""Tests for client.py and related code.

	The following tests assume you have at least the default quake sounds in your sound directory.
	The following tests assume the server is working without any bugs that could carry across tests.
	"""

	def setUp(self):
		# Clear cache directory
		shutil.rmtree('cache')
		os.mkdir('cache')
		open('cache/.gitkeep', 'a').close()

		# Run a local sound server
		config.set('Network', 'ServerIP', '127.0.0.1')
		config.set('Network', 'ServerPort', '4004')
		loop = asyncio.new_event_loop()
		asyncio.create_task(run_server(loop))
		sleep(1)  # Wait for server to start (shh it's fine)

	def tearDown(self):
		try:
			shutil.move('./sounds/Timeout/test.ogg', './test.ogg')
		except:
			pass

	def test_receive_sound(self, *args):
		# Alice will send basic stuff
		alice = MockClient('123123123')
		sleep(10)
		self.assertEqual(alice.sounds.play.call_count, 1)

		# Bob will only receive
		bob = MockClient('456456456')
		sleep(1)
		self.assertEqual(bob.sounds.play.call_count, 1)

		# Charlie will send a custom sound
		shutil.move('test.ogg', 'sounds/Timeout/test.ogg')
		charlie = MockClient('789789789')
		sleep(1)

		self.assertEqual(len(server.rooms[0].clients), 3)

		# Send a sound, and assert it is received by bob
		alice.sounds.send(GameEvent.Type.COLLATERAL, alice.state)
		sleep(1)
		self.assertEqual(bob.sounds.play.call_count, 2)

		# Try MVPs
		alice.sounds.send(GameEvent.Type.MVP, alice.state)
		sleep(1)
		self.assertEqual(bob.sounds.play.call_count, 3)
		alice.state.current_round = 2
		alice.sounds.send(GameEvent.Type.MVP, alice.state)
		sleep(1)
		self.assertEqual(bob.sounds.play.call_count, 4)

		# Try charlie's custom sound
		charlie.sounds.send(GameEvent.Type.TIMEOUT, charlie.state)
		sleep(2)
		self.assertEqual(bob.sounds.play.call_count, 5)

if __name__ == '__main__':
	unittest.main()
