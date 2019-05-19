"""Related to sounds"""
import hashlib
import math
import pyglet
import random
import os
from datetime import datetime
from threading import Lock

import config
from packets_pb2 import GameEvent, PacketInfo, PlaySound
from util import print, get_event_class, small_hash


class SampleCollection:
    """Represents a sample collection (e.g. Double kill, Headshot, etc)"""
    def __init__(self, path):
        self.name = path
        self.samples = []

    def load(self, filename_list, file_callback, error_callback):
        """Loads the sound list"""
        for filename in filename_list:
            file_stat = os.stat(filename)
            if file_stat.st_size > 2 * 1024 * 1024:
                error_callback('File %s is too large (over 2 Mb) and will not be loaded.' % filename)
                continue

            hash = hashlib.blake2b()
            with open(filename, 'rb') as infile:
                hash.update(infile.read())
                digest = hash.digest()
                filepath = os.path.join('cache', hash.hexdigest())
                with open(filepath, 'wb') as outfile:
                    infile.seek(0)
                    outfile.write(infile.read())
            try:
                should_stream = self.name in ['MVP', 'Round lose', 'Round start', 'Round win', 'Timeout']
                file = pyglet.media.load(filename, streaming=should_stream)
                print(' + Loaded %s (%s)' % (small_hash(digest), filename))
            except Exception as e:
                msg = 'Error while loading "%s":\n%s' % (filename, str(e))
                error_callback(msg)
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
    def __init__(self, client):
        self.collections = {}
        self.wanted_sounds = {}
        self.cache_lock = Lock()
        self.cache = {}
        self.playerid = None
        self.client = client
        self.loaded = False
        with config.lock:
            self.volume = config.config['Sounds'].getint('Volume', 50)

    def load(self, one_sound_loaded_callback, error_callback):
        """Reloads all sounds from the sounds/ folder"""
        self.loaded = False
        with self.cache_lock:
            for path in os.listdir('sounds'):
                complete_path = os.path.join('sounds', path)
                if not os.path.isfile(complete_path):
                    self.collections[path] = SampleCollection(complete_path)
                    self.collections[path].load(self.sound_list(complete_path), one_sound_loaded_callback, error_callback)

            # Play sound once all sounds are loaded
            # This also prevents windows from minimizing the game when the first sound is played
            playpacket = PlaySound()
            playpacket.steamid = 0
            hash = self.get_random(GameEvent.ROUND_START, None)
            if hash is None:
                hash = self.get_random(GameEvent.HEADSHOT, None)
            playpacket.sound_hash = hash
        self.loaded = True
        self.play(playpacket)

    def sound_list(self, sounds_dir):
        """Returns the list of sounds in a directory and its subdirectories"""
        list = []
        for path in os.listdir(sounds_dir):
            complete_path = os.path.join(sounds_dir, path)

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
        if self.loaded is False:
            return True
        if str(packet.steamid) != self.playerid and packet.steamid != 0:
            return True

        with self.cache_lock:
            # Sound is already loaded
            if packet.sound_hash in self.cache:
                print('[+] Playing %s' % small_hash(packet.sound_hash))
                player = pyglet.media.Player()
                player.volume = math.pow(self.volume, 2) / 10000
                player.queue(self.cache[packet.sound_hash])
                player.play()
                return True
            else:
                filename = os.path.join('cache', packet.sound_hash.hex())
                if os.path.isfile(filename):
                    # Sound is downloaded but not loaded
                    print('[+] Loading and playing %s' % small_hash(packet.sound_hash))
                    self.cache[packet.sound_hash] = pyglet.media.load(filename, streaming=True)
                    player = pyglet.media.Player()
                    player.volume = math.pow(self.volume, 2) / 10000
                    player.queue(self.cache[packet.sound_hash])
                    player.play()
                    return True
                else:
                    # Sound is not downloaded
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
            player = pyglet.media.Player()
            player.volume = math.pow(self.volume, 2) / 10000
            player.queue(self.cache[hash])
            player.play()
            print('[+] Playing %s (%f ms late)' % (small_hash(hash), datetime.now() - wanted_time))

    def save(self, packet):
        filepath = os.path.join('cache', packet.hash.hex())
        with open(filepath, 'wb') as outfile:
            outfile.write(packet.data)
        try:
            file = pyglet.media.load(filepath, streaming=True)
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
            if hash == b'':
                print('?????????????????????????????')
                print('Update type: %s' % str(update_type))
                print('?????????????????????????????')

            packet = GameEvent()
            packet.update = update_type
            packet.proposed_sound_hash = hash
            packet.kill_count = int(state.round_kills)
            packet.round = int(state.current_round)
            self.client.send(PacketInfo.GAME_EVENT, packet)

            # Normal event : play without waiting for server
            if get_event_class(packet) == 'normal':
                playpacket = PlaySound()
                playpacket.steamid = 0
                playpacket.sound_hash = hash
                self.play(playpacket)
