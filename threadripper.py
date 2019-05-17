from queue import Queue, LifoQueue


class Threadripper:
	"""The One object to be accessed across threads.

	Having 4 threads access each other is a nightmare.
	How about they all access one object instead ?
	Queues are thread safe : they don't need locks :)
	"""

	sounds_to_play = Queue()

	sounds_to_download = LifoQueue()
	sounds_to_upload = LifoQueue()

	# Every item in the Queue is an array of two protobufs.
	# The first packet is a PacketInfo packet. Second is data.
	packets_to_send = Queue()


# Export for global usage
threadripper = Threadripper()
