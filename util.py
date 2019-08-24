from threading import Lock

from protocol import GameEvent

rare_events = [
	GameEvent.Type.MVP, GameEvent.Type.SUICIDE, GameEvent.Type.TEAMKILL, GameEvent.Type.KNIFE, GameEvent.Type.COLLATERAL
]
shared_events = [
	GameEvent.Type.ROUND_WIN, GameEvent.Type.ROUND_LOSE, GameEvent.Type.ROUND_START, GameEvent.Type.TIMEOUT
]

# Thread-safe printing
print_lock = Lock()
unsafe_print = print
def print(*a, **b):
	with print_lock:
		unsafe_print(*a, **b)

def get_event_class(packet):
    if packet.type in rare_events: return 'rare'
    if packet.type in shared_events: return 'shared'
    is_kill = (packet.type == GameEvent.KILL or packet.type == GameEvent.HEADSHOT)
    if is_kill and packet.kill_count > 3: return 'rare'
    return 'normal'

def small_hash(hash):
	hex = hash.hex()
	return '%s-%s' % (hex[0:4], hex[-4:])
