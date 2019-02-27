"""Related to sounds"""
import hashlib
import pyglet
import random
import socket
import os
from time import sleep

from config import SOUND_SERVER_IP, SOUND_SERVER_PORT
from packets_pb2 import PacketInfo, PacketType, GamestateUpdate, UpdateType, PlaySound

class SampleCollection:
    """Represents a sample collection (e.g. Double kill, Headshot, etc)"""
    def __init__(self, path):
        self.name = path
        self.samples = {}

    def load(self, filename_list, thread):
        """Loads the sound list"""
        for filename in filename_list:
            hash = hashlib.blake2b()
            with open(filename, 'rb') as infile:
                hash.update(infile.read())
            try:
                digest = hash.hexdigest()
                self.samples[digest] = pyglet.media.load(filename, streaming=False)
                print(" + " + filename + ": " + digest)
            except Exception as e:
                print(" ! Failed to load \"" + filename + "\": " + str(e))
            thread.update_status()

    def get_random_hash(self):
        if len(self.samples) > 0:
            return random.choice(self.samples.keys())
        print('[!] Folder "' + self.name + '" has no samples loaded.')
        return None

    def play(self, index):
        """Plays a random (index = None) or specific sample"""
        if index != None:
            try:
                self.samples[index].play()
                print('[+] Playing "%s/%s"' % (self.name, index))
            except:
                print('[!] Sound "' + index + '" missing from folder "' + self.name + '", ignoring.')
        else:
            print("Playing " + self.name)
            if len(self.samples) > 0:
                random.choice(self.samples).play()

class SoundManager:
    """Loads and plays sounds"""
    def __init__(self):
        self.collections = {}
        self.round_globals = []
        self.playerid = None

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((SOUND_SERVER_IP, SOUND_SERVER_PORT))
        self.sock.setblocking(False)

    def load(self, thread):
        for path in os.listdir('sounds'):
            complete_path = 'sounds/' + path
            if not os.path.isfile(complete_path):
                self.collections[path] = SampleCollection(complete_path)
                self.collections[path].load(self.sound_list(complete_path), thread)
    
    def sound_list(self, sounds_dir):
        """Returns the list of sounds in a directory and its subdirectories"""
        list = []
        for path in os.listdir(sounds_dir):
            complete_path = sounds_dir + '/' + path

            # Ignore .gitkeep, .gitignore, etc
            if path.startswith('.git'):
                continue

            if os.path.isfile(complete_path):
                # Ignore windows bullshit
                if path == 'desktop.ini':
                    continue
                
                list.append(complete_path)
            else:
                list.extend(self.sound_list(complete_path))
        return list

    def get(self, type, state):
        """Get a sample from its sound name"""

        if type == UpdateType.MVP: sound = 'MVP'
        elif type == UpdateType.ROUND_WIN: sound = 'Round win'
        elif type == UpdateType.ROUND_LOSE: sound = 'Round lose'
        elif type == UpdateType.SUICIDE: sound = 'Suicide'
        elif type == UpdateType.TEAMKILL: sound = 'Teamkill'
        elif type == UpdateType.DEATH: sound = 'Death'
        elif type == UpdateType.FLASH: sound = 'Flashed'
        elif type == UpdateType.KNIFE: sound = 'Unusual kill'
        elif type == UpdateType.HEADSHOT: sound = 'Headshot'
        elif type == UpdateType.KILL: sound = state.round_kills + ' kills'
        elif type == UpdateType.COLLATERAL: sound = 'Collateral'
        elif type == UpdateType.ROUND_START: sound = 'Round start'
        elif type == UpdateType.TIMEOUT: sound = 'Timeout'

        for sample in self.collections:
            if sample.name.startswith('sounds/' + sound):
                return sample
        print('[!] Folder "' + sound + '" not found, ignoring.')
        return None

    def play(self, hash):
        """Plays a loaded sound"""
        sample = self.get(sound)
        if sample:
            sample.play(index)

    def handle(self, update_type, raw_packet):
        if update_type == UpdateType.PLAY_SOUND:
            packet = PlaySound()
            packet.ParseFromString(raw_packet)
            # TODO import bytes
            if packet['steamid'] == self.playerid or packet['steamid'] == 0:
                self.play(packet['sound_hash'])
            else:
                # TODO request sound
                pass
        else:
            print("Unhandled packet type!")

    def listen(self):
        while True:
            try:
				# 255 bytes should be more than enough for the PacketInfo message
				data = self.sock.recv(255)
				if len(data) == 0:
					break
				
				packet_info = PacketInfo()
				packet_info.ParseFromString(data)
				
				if packet_info['length'] > 2 * 1024 * 1024:
					# Don't allow files or packets over 2 Mb
					break

				data = self.sock.recv(packet_info['length'])
				if len(data) == 0:
					break
				
				self.handle(packet_info['type'], data)
            except ConnectionResetError:
				break
            except socket.error as msg:
				print("Error: " + msg)
				break

    def send(self, update_type, state):
        """Sends a sound to play for everybody"""
        collection = self.get(update_type, state)
        if collection:
            hash = collection.get_random_hash()
            if hash != None:
                print('%d: %s' % (hash, state.steamid))
                update = GamestateUpdate()
                update['update'] = update_type
                update['proposed_sound_hash'] = hash
                update['kill_count'] = state.round_kills
                self.sock.send(update.SerializeToString())
                

sounds = SoundManager()
