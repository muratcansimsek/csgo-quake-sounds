import zmq

# This is the sound server used to sync sounds between multiple players
#
# If you want to play with your friends, run a server with :
# - pip3 install -r requirements.txt
# - python3 server.py
# Don't forget to open TCP ports 4000 and 4001.

def serve():
	context = zmq.Context()

	publisher = context.socket(zmq.PUB)
	publisher.bind('tcp://*:4000')

	subscriber = context.socket(zmq.PULL)
	subscriber.bind('tcp://*:4001')

	print('[+] Sound server started.')
	try:
		zmq.device(zmq.FORWARDER, subscriber, publisher)
	except KeyboardInterrupt:
		pass

	print('[!] Stopping sound server.')
	publisher.close()
	subscriber.close()
	context.term()


if __name__ == "__main__":
	serve()
