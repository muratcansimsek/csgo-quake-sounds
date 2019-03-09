"""Related to sounds"""
import hashlib
import pyglet
import random
import os
from datetime import datetime
from threading import Lock

from packets_pb2 import GameEvent, PacketInfo

streaming_categories = ['MVP', 'Round lose', 'Round start', 'Round win', 'Timeout']

def small_hash(hash):
    hex = hash.hex()
    return '%s-%s' % (hex[0:4], hex[-4:])

class SampleCollection:
    """Represents a sample collection (e.g. Double kill, Headshot, etc)"""
    def __init__(self, path):
        self.name = path
        self.samples = []

    def load(self, filename_list, file_callback):
        """Loads the sound list"""
        for filename in filename_list:
            hash = hashlib.blake2b()
            with open(filename, 'rb') as infile:
                hash.update(infile.read())
                digest = hash.digest()
                with open('cache/' + hash.hexdigest(), 'wb') as outfile:
                    infile.seek(0)
                    outfile.write(infile.read())
            try:
                file = pyglet.media.load(filename, streaming=True if self.name in streaming_categories else False)
                print(' + Loaded %s (%s)' % (small_hash(digest), filename))
            except Exception as e:
                print(" ! Failed to load \"" + filename + "\": " + str(e))
            else:
                self.samples.append(digest)
                file_callback(digest, file)

    def get_random_hash(self):
        if len(self.samples) > 0:
            return random.choice(self.samples)
        print('[!] Folder "' + self.name + '" has no samples loaded.')
        return None


class SoundManager:
    """Loads and plays sounds"""
    def __init__(self):
        self.collections = {}
        self.wanted_sounds = {}
        self.cache_lock = Lock()
        self.cache = {}
        self.playerid = None
        self.client = None

    def init(self, client):
        self.client = client

    def load(self, one_sound_loaded_callback):
        """Reloads all sounds from the sounds/ folder"""
        with self.cache_lock:
            for path in os.listdir('sounds'):
                complete_path = 'sounds/' + path
                if not os.path.isfile(complete_path):
                    self.collections[path] = SampleCollection(complete_path)
                    self.collections[path].load(self.sound_list(complete_path), one_sound_loaded_callback)
        
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

    def get_random(self, type, state):
        """Get a sample from its sound name"""
        if type == GameEvent.MVP: sound = 'MVP'
        elif type == GameEvent.ROUND_WIN: sound = 'Round win'
        elif type == GameEvent.ROUND_LOSE: sound = 'Round lose'
        elif type == GameEvent.SUICIDE: sound = 'Suicide'
        elif type == GameEvent.TEAMKILL: sound = 'Teamkill'
        elif type == GameEvent.DEATH: sound = 'Death'
        elif type == GameEvent.FLASH: sound = 'Flashed'
        elif type == GameEvent.KNIFE: sound = 'Unusual kill'
        elif type == GameEvent.HEADSHOT: sound = 'Headshot'
        elif type == GameEvent.KILL: sound = '%d kills' % state.round_kills
        elif type == GameEvent.COLLATERAL: sound = 'Collateral'
        elif type == GameEvent.ROUND_START: sound = 'Round start'
        elif type == GameEvent.TIMEOUT: sound = 'Timeout'
        
        return self.collections[sound].get_random_hash()

    def play(self, packet):
        if str(packet.steamid) != self.playerid and packet.steamid != 0:
            return True
        sound_missing = False
        with self.cache_lock:
            if packet.sound_hash in self.cache:
                print('[+] Playing %s' % small_hash(packet.sound_hash))
                self.cache[packet.sound_hash].play()
                return True
            else:
                print('[!] Sound %s missing, requesting from server' % small_hash(packet.sound_hash))
                self.wanted_sounds[packet.sound_hash] = datetime.now()
                return False

    def play_received(self, hash):
        """Try playing a sound if it was received quickly enough"""
        with self.cache_lock:
            if hash not in self.wanted_sounds:
                return
            wanted_time = self.wanted_sounds[hash]
            self.wanted_sounds.remove(hash)
            if wanted_time + 1000 > datetime.now():
                return
            self.cache[hash].play()
            print('[+] Playing %s (%f ms late)' % (small_hash(hash), datetime.now() - wanted_time))
    
    def save(self, packet):
        with open('cache/' + packet.hash.hex(), 'wb') as outfile:
            outfile.write(packet.data)
        try:
            file = pyglet.media.load('cache/' + packet.hash.hex(), streaming=True)
            print('Saved %s' % small_hash(packet.hash))
        except Exception as e:
            print(" ! Failed to load \"" + small_hash(packet.hash) + "\": " + str(e))
        else:
            with self.cache_lock:
                self.cache[packet.hash] = file

    def send(self, update_type, state):
        """Sends a sound to play for everybody"""
        if self.client == None:
            return
        
        hash = self.get_random(update_type, state)
        if hash != None:
            packet = GameEvent()
            packet.update = update_type
            packet.proposed_sound_hash = hash
            packet.kill_count = state.round_kills
            self.client.send(PacketInfo.GAME_EVENT, packet)
                

sounds = SoundManager()
