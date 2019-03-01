"""Related to sounds"""
import datetime
import hashlib
import pyglet
import random
import os
from threading import Lock

from packets_pb2 import GameEvent

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
            try:
                digest = hash.hexdigest()
                file = pyglet.media.load(filename, streaming=True if self.name in streaming_categories else False)
                print(" + " + filename + ": " + digest)
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
        self.cache_lock = Lock()
        self.cache = {}
        self.playerid = None

    def init(self, client):
        self.client = client

    def load(self, one_sound_loaded_callback):
        """Reloads all sounds from the sounds/ folder"""
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
        if type == GameEvent.Type.MVP: sound = 'MVP'
        elif type == GameEvent.Type.ROUND_WIN: sound = 'Round win'
        elif type == GameEvent.Type.ROUND_LOSE: sound = 'Round lose'
        elif type == GameEvent.Type.SUICIDE: sound = 'Suicide'
        elif type == GameEvent.Type.TEAMKILL: sound = 'Teamkill'
        elif type == GameEvent.Type.DEATH: sound = 'Death'
        elif type == GameEvent.Type.FLASH: sound = 'Flashed'
        elif type == GameEvent.Type.KNIFE: sound = 'Unusual kill'
        elif type == GameEvent.Type.HEADSHOT: sound = 'Headshot'
        elif type == GameEvent.Type.KILL: sound = state.round_kills + ' kills'
        elif type == GameEvent.Type.COLLATERAL: sound = 'Collateral'
        elif type == GameEvent.Type.ROUND_START: sound = 'Round start'
        elif type == GameEvent.Type.TIMEOUT: sound = 'Timeout'

        for sample in self.collections:
            if sample.name.startswith('sounds/' + sound):
                return sample.get_random_hash()
        print('[!] Folder "' + sound + '" not found, ignoring.')
        return None

    def play(self, packet):
        if packet.steamid != self.playerid and packet.steamid != 0:
            return
        sound_missing = False
        with self.cache_lock:
            if packet.sound_hash in self.cache:
                self.cache[packet.sound_hash].play()
                print('[+] Playing %s' % small_hash(packet.sound_hash))
            else:
                print('[!] Sound %s missing, requesting from server' % small_hash(packet.sound_hash))
                sound_missing = True
        if sound_missing:
            with self.cache_lock:
                self.wanted_sounds[packet.sound_hash] = datetime.now()
            self.client.request_sound(packet.sound_hash)

    def play_received(self, hash):
        """Try playing a sound if it was received quickly enough"""
        with self.cache_lock:
            wanted_time = self.wanted_sounds[hash]
            self.wanted_sounds.remove(hash)
            if wanted_time + 1000 > datetime.now():
                return
            self.cache[hash].play()
            print('[+] Playing %s (%f ms late)' % (small_hash(hash), datetime.now() - wanted_time))
    
    def save(self, packet):
        with os.open('cache/' + packet.hash) as outfile:
            outfile.write(packet.data)
        try:
            file = pyglet.media.load('cache/' + packet.hash, streaming=True)
            print('Saved %s' % small_hash(packet.hash))
        except Exception as e:
            print(" ! Failed to load \"" + packet.hash + "\": " + str(e))
        else:
            with self.cache_lock:
                self.cache[packet.hash] = file

    def send(self, update_type, state):
        """Sends a sound to play for everybody"""
        collection = self.get(update_type, state)
        if collection:
            hash = collection.get_random_hash()
            if hash != None:
                print('%d: %s' % (hash, state.steamid))
                update = GameEvent()
                update['update'] = update_type
                update['proposed_sound_hash'] = hash
                update['kill_count'] = state.round_kills
                with self.sock_lock:
                    self.sock.send(update.SerializeToString())
                

sounds = SoundManager()
