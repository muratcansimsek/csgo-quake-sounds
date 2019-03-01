import json
import socket
import wx
from http.server import BaseHTTPRequestHandler, HTTPServer
from time import sleep
from threading import Thread, Lock

from config import SOUND_SERVER_IP, SOUND_SERVER_PORT
from packets_pb2 import PacketInfo, GameEvent, PlaySound, SoundRequest, SoundResponse, ClientUpdate
from sounds import sounds
from state import CSGOState

GAMESTATE = CSGOState()

# Thread-safe printing
print_lock = Lock()
unsafe_print = print
def print(*a, **b):
	with print_lock:
		unsafe_print(*a, **b)

class PostHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_len = int(self.headers['Content-Length'])
        body = self.rfile.read(content_len)
        self.send_response(200)
        self.end_headers()

        if not self.recieved_post:
            print('\r\n[+] CSGO Gamestate Integration is working\r\n')
            self.recieved_post = True

        GAMESTATE.update(json.loads(body))
        return
    
    def log_message(self, format, *args):
        # Do not spam the console with POSTs
        return

class Client:
    def __init__(self, gui):
        self.sock_lock = Lock()
        self.connected = False
        self.reconnect_timeout = 1
        self.gui = gui
        self.shard_code = b''

        sounds.init(self)
        gamestate_server = HTTPServer(('127.0.0.1', 3000), PostHandler)
        Thread(target=gamestate_server.serve_forever, daemon=True).start()
        Thread(target=self.listen, daemon=True).start()
    
    def update_status(self):
        # TODO show true status
        wx.CallAfter(self.gui.SetStatusText, 'Waiting for CS:GO...')
    
    def reload_sounds(self):
        """Reloads all sounds. Not thread safe, should only be called from GUI"""
        loaded_sounds = 0
        max_sounds = len(sounds.sound_list('sounds'))

        def file_callback(self, hash, file):
            global loaded_sounds

            with self.cache_lock:
                self.cache[hash] = file
            wx.CallAfter(self.gui.SetStatusText, 'Loading sounds... (%d/%d)' % (loaded_sounds, max_sounds))
            loaded_sounds = loaded_sounds + 1

        sounds.load(file_callback)
        wx.CallAfter(self.gui.updateSoundsBtn.Enable)
        self.update_status()

        # Send sound list to server
        packet = SoundRequest()
        with self.cache_lock:
            for hash in self.cache:
                packet.sound_hash.add(hash)
        raw_packet = packet.SerializeToString()
        header = PacketInfo()
        header.type = PacketInfo.Type.SOUND_LIST
        header.length = len(raw_packet)
        with self.sock_lock:
            self.sock.send(header.SerializeToString())
            self.sock.send(raw_packet)

    def request_sound(self, hash):
        packet = SoundRequest()
        packet.sound_hash.add(hash)
        raw_packet = packet.SerializeToString()
        header = PacketInfo()
        header.type = PacketInfo.Type.SOUND_REQUEST
        header.length = len(raw_packet)

        with self.sock_lock:
            self.sock.send(header.SerializeToString())
            self.sock.send(raw_packet)

    def handle(self, packet_type, raw_packet):
        if packet_type == PacketInfo.Type.PLAY_SOUND:
            packet = PlaySound()
            packet.ParseFromString(raw_packet)
            sounds.play(packet)
        elif packet_type == PacketInfo.Type.SOUND_REQUEST:
            packet = SoundRequest()
            packet.ParseFromString(raw_packet)
            # TODO send sound
        elif packet_type == PacketInfo.type.SOUND_RESPONSE:
            packet = SoundResponse()
            packet.ParseFromString(raw_packet)
            sounds.save(packet)
            sounds.play_received(packet.hash)
        else:
            print("Unhandle packet type!")

    def try_reconnect(self):
        """Tries reconnecting - returns False if disconnected"""
        with self.sock_lock:
            if not self.connected:
                try:
                    self.sock = socket.create_connection((SOUND_SERVER_IP, SOUND_SERVER_PORT))
                    self.connected = True
                    self.reconnect_timeout = 1

                    packet = ClientUpdate()
                    packet.status = ClientUpdate.PlayerStatus.UNCONNECTED
                    packet.map = ''
                    packet.steamid = 0
                    packet.shard_code = self.shard_code
                    raw_packet = packet.SerializeToString()
                    header = PacketInfo()
                    header.type = PacketInfo.Type.CLIENT_UPDATE
                    header.length = len(raw_packet)
                    self.sock.send(header.SerializeToString())
                    self.sock.send(raw_packet)

                except ConnectionRefusedError:
                    self.connected = False

                    sleep(self.reconnect_timeout)
                    self.reconnect_timeout *= 2
                    if self.reconnect_timeout > 60:
                        self.reconnect_timeout = 60

                    return False
        return True

    def listen(self):
        while True:
            if not self.try_reconnect():
                continue

            try:
                # 255 bytes should be more than enough for the PacketInfo message
                with self.sock_lock:
                    self.sock.settimeout(0.1)
                    data = self.sock.recv(255)
                    self.sock.settimeout(None)
                if len(data) == 0:
                    break
                
                packet_info = PacketInfo()
                packet_info.ParseFromString(data)
                if packet_info.length > 2 * 1024 * 1024:
                    # Don't allow files or packets over 2 Mb
                    break

                with self.sock_lock:
                    data = self.sock.recv(packet_info.length)
                if len(data) == 0:
                    break
                
                self.handle(packet_info.type, data)
            except ConnectionResetError:
                self.connected = False
            except socket.timeout:
                pass
            except socket.error as msg:
                print("Connection error: " + str(msg))
                break
