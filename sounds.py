"""Related to sounds"""
import hashlib
import pyglet
import random
import os
import zmq
from time import sleep

from config import SOUND_SERVER_IP

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

    def get_random_index(self):
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

        self.ctx = zmq.Context()

        self.subscriber = self.ctx.socket(zmq.SUB)
        self.subscriber.setsockopt(zmq.SUBSCRIBE, b'')
        self.subscriber.connect('tcp://' + SOUND_SERVER_IP + ':4000')

        self.publisher = self.ctx.socket(zmq.PUSH)
        self.publisher.connect('tcp://' + SOUND_SERVER_IP + ':4001')

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

    def get(self, sound):
        """Get a sample from its sound name"""
        for sample in self.collections:
            if sample.name.startswith('sounds/' + sound):
                return sample
        print('[!] Folder "' + sound + '" not found, ignoring.')
        return None

    def play(self, sound, index):
        """Plays a loaded sound"""
        sample = self.get(sound)
        if sample:
            sample.play(index)

    def listen(self):
        while True:
            try:
                [sound, index, steamid] = self.subscriber.recv_json()
                print('<- "%s/%s" (%s)' % (sound, index, steamid))
            except KeyboardInterrupt:
                break
            else:
                if steamid == 'global' and sound not in self.round_globals:
                    # Avoid playing MVP and round end sounds at the same time
                    if sound == 'MVP' or sound == 'Round win':
                        if 'MVP' in self.round_globals or 'Round win' in self.round_globals:
                            continue

                    # Keep old sound sync
                    if sound == 'MVP':
                        self.round_globals.append(sound)
                        sleep(1)

                    self.play(sound, index)
                    self.round_globals.append(sound)
                elif steamid == 'rare' or steamid == self.playerid:
                    self.play(sound, index)

        # Clean up
        self.publisher.close()
        self.subscriber.close()
        self.ctx.term()

    def send(self, sound, steamid):
        """Sends a sound to play for everybody"""
        sample = self.get(sound)
        if sample:
            index = sample.get_random_index()
            if index != None:
                print('-> "%s/%s" (%s)' % (sound, index, steamid))
                self.publisher.send_json([sound, index, steamid])

sounds = SoundManager()
