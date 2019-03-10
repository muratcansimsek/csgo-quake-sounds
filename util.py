from threading import Lock

from packets_pb2 import GameEvent

rare_events = [ GameEvent.MVP, GameEvent.SUICIDE, GameEvent.TEAMKILL, GameEvent.KNIFE, GameEvent.COLLATERAL ]
shared_events = [ GameEvent.ROUND_WIN, GameEvent.ROUND_LOSE, GameEvent.ROUND_START, GameEvent.TIMEOUT ]

# Thread-safe printing
print_lock = Lock()
unsafe_print = print
def print(*a, **b):
	with print_lock:
		unsafe_print(*a, **b)

def get_event_class(packet):
    if packet.update in rare_events: return 'rare'
    if packet.update in shared_events: return 'shared'
    if packet.update == GameEvent.KILL and packet.kill_count > 3: return 'rare'
    return 'normal'

def small_hash(hash):
	hex = hash.hex()
	return '%s-%s' % (hex[0:4], hex[-4:])
