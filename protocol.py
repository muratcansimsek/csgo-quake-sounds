import enum
import packel
from packel.types import PacketType
from typing import ClassVar, List, Type


### packel extensions ----------------------------------------------------------------
class Hash(PacketType):
	is_dynamic_length: ClassVar[bool] = False
	type: ClassVar[Type] = bytes

	@staticmethod
	def default() -> bytes:
		return Hash.serialize(b'')

	@staticmethod
	def deserialize(b: bytes) -> bytes:
		return b

	@staticmethod
	def serialize(v) -> bytes:
		if len(v) > 64:
			raise ValueError("Hash longer than 64 bytes.")
		return v.ljust(64, b'\x00')

class HashList(PacketType):
	is_dynamic_length: ClassVar[bool] = True
	type: ClassVar[Type] = List

	@staticmethod
	def default() -> List[bytes]:
		return []

	@staticmethod
	def deserialize(b: bytes) -> List[bytes]:
		out: List[bytes] = []

		pos = 4
		nb_hashes = int.from_bytes(b[:4], 'big')
		for i in range(nb_hashes):
			out.append(Hash.deserialize(b[pos:pos+64]))
			pos = pos + 64

		return out

	@staticmethod
	def serialize(v: List[bytes]) -> bytes:
		nb_hashes = len(v)
		out = nb_hashes.to_bytes(4, 'big')
		for hash in v:
			out = out + Hash.serialize(hash)
		return out


### Sent to server -------------------------------------------------------------------
class KeepAlive(packel.Packet):
	pass

class ClientSoundRequest(packel.Packet):
	"""Packet sent when the client wants to download a sound."""
	sound_hash = Hash()

class GameEvent(packel.Packet):
	class Type(enum.Enum):
		MVP = 0
		ROUND_WIN = 1
		ROUND_LOSE = 2
		SUICIDE = 3
		TEAMKILL = 4
		DEATH = 5
		FLASH = 6
		KNIFE = 7
		HEADSHOT = 8
		KILL = 9
		COLLATERAL = 10
		ROUND_START = 11
		TIMEOUT = 12

	type = packel.Int32()
	proposed_sound_hash = Hash()
	kill_count = packel.Int32()

class ClientUpdate(packel.Packet):
	steamid = packel.Int64()
	room_name = packel.String()
	sounds_list = HashList()


### Sent to client -------------------------------------------------------------------
class ServerRoomSounds(packel.Packet):
	"""Packet sent when a room's sounds list is updated :

	- When a client joins or leaves a room
	- When a missing sound was uploaded
	"""
	available_hashes = HashList()
	missing_hashes = HashList()

class PlaySound(packel.Packet):
	steamid = packel.Int64()
	sound_hash = Hash()


### Sent to both ---------------------------------------------------------------------
class SoundResponse(packel.Packet):
	"""Packet sent either by the client or the server, containing a sound file."""
	data = packel.Bytes()
	hash = Hash()


protocol = packel.Protocol([
	# Sent to server
	KeepAlive, ClientUpdate, ClientSoundRequest, GameEvent,

	# Sent to client
	ServerRoomSounds, PlaySound,

	# Both
	SoundResponse,

	# vvv New packets go here vvv
])
