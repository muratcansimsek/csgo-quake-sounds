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
    def __init__(self):
        self.sock_lock = Lock()
        self.connected = False
        self.reconnect_timeout = 1
        self.shard_code = b''

    def init(self, gui):
        """Non-blocking init"""
        self.gui = gui
        gamestate_server = HTTPServer(('127.0.0.1', 3000), PostHandler)
        Thread(target=gamestate_server.serve_forever, daemon=True).start()
        Thread(target=self.listen, daemon=True).start()
    
    def update_status(self):
        if not self.connected:
            wx.CallAfter(self.gui.SetStatusText, 'Connecting to sound sync server...')
            return
        with GAMESTATE.lock:
            if GAMESTATE.old_state == None:
                wx.CallAfter(self.gui.SetStatusText, 'Waiting for CS:GO...')
            elif GAMESTATE.is_ingame:
                wx.CallAfter(self.gui.SetStatusText, '%s - round %s - steamID %s' % (GAMESTATE.old_state.phase, GAMESTATE.old_state.current_round, GAMESTATE.old_state.steamid))
            else:
                wx.CallAfter(self.gui.SetStatusText, 'not in a game server')
        
    def file_callback(self, hash, file):
        with sounds.cache_lock:
            sounds.cache[hash] = file
        wx.CallAfter(self.gui.SetStatusText, 'Loading sounds... (%d/%d)' % (self.loaded_sounds, self.max_sounds))
        self.loaded_sounds = self.loaded_sounds + 1
    
    def reload_sounds(self):
        """Reloads all sounds. Not thread safe, should only be called from GUI"""
        self.loaded_sounds = 0
        self.max_sounds = len(sounds.sound_list('sounds'))

        sounds.load(self.file_callback)
        wx.CallAfter(self.gui.updateSoundsBtn.Enable)
        self.update_status()

        # Send sound list to server
        with self.sock_lock:
            if not self.connected:
                return
        packet = SoundRequest()
        with sounds.cache_lock:
            for hash in sounds.cache:
                packet.sound_hash.append(bytes.fromhex(hash))
        raw_packet = packet.SerializeToString()
        header = PacketInfo()
        header.type = PacketInfo.SOUNDS_LIST
        header.length = len(raw_packet)
        with self.sock_lock:
            print("Sending sounds list")
            print(str(header))
            self.sock.sendall(header.SerializeToString())
            self.sock.sendall(raw_packet)

    def request_sound(self, hash):
        packet = SoundRequest()
        packet.sound_hash.append(hash)
        raw_packet = packet.SerializeToString()
        header = PacketInfo()
        header.type = PacketInfo.SOUND_REQUEST
        header.length = len(raw_packet)

        with self.sock_lock:
            print("Requesting sound")
            print(str(header))
            self.sock.sendall(header.SerializeToString())
            self.sock.sendall(raw_packet)

    def handle(self, packet_type, raw_packet):
        if packet_type == PacketInfo.PLAY_SOUND:
            packet = PlaySound()
            packet.ParseFromString(raw_packet)
            if not sounds.play(packet):
                self.request_sound(packet.sound_hash)
        elif packet_type == PacketInfo.SOUND_REQUEST:
            req = SoundRequest()
            req.ParseFromString(raw_packet)
            
            for hash in req.sound_hash:
                with open('cache/' + hash.hex(), 'rb') as infile:
                    packet = SoundResponse()
                    packet.data = infile.read()
                    packet.hash = hash
                    raw_packet = packet.SerializeToString()
                    header = PacketInfo()
                    header.type = PacketInfo.SOUND_RESPONSE
                    header.length = len(raw_packet)
                    with self.sock_lock:
                        self.sock.sendall(header.SerializeToString())
                        self.sock.sendall(raw_packet)
        elif packet_type == PacketInfo.SOUND_RESPONSE:
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
                    packet.status = ClientUpdate.UNCONNECTED
                    packet.map = b''
                    packet.steamid = 0
                    packet.shard_code = self.shard_code
                    raw_packet = packet.SerializeToString()
                    header = PacketInfo()
                    header.type = PacketInfo.CLIENT_UPDATE
                    header.length = len(raw_packet)
                    print("Sending client update")
                    print(str(header))
                    self.sock.sendall(header.SerializeToString())
                    self.sock.sendall(raw_packet)

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
                with self.sock_lock:
                    self.sock.settimeout(0.1)
                    data = self.sock.recv(7)
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
