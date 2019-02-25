"""Related to sounds"""

import pyglet
import random
import os
import zmq
from time import sleep

from config import SOUND_SERVER_IP

class Sample:
    """Represents a sample or sample collection"""
    def __init__(self, path):
        self.name = path
        self.samples = {}

        if os.path.isfile(path):
            print('Added "' + path + '" as folder.')
            self.samples[path] = pyglet.media.load(path, streaming=False)
        else:
            print('In folder "' + path + '" :')
            for file in os.listdir(path):
                # Ignore .gitkeep, .gitignore, etc
                if file.startswith('.git'):
                    continue
                # Ignore windows bullshit
                if file == 'desktop.ini':
                    continue
                complete_path = path + '/' + file
                try:
                    self.samples[file] = pyglet.media.load(complete_path, streaming=False)
                    print(" + " + file)
                except Exception as e:
                    print(" ! Failed to load \"" + file + "\": " + str(e))

            # Notify if there are no sounds in the folder        
            if len(self.samples) == 0:
                print('   <nothing>')

    def get_random_index(self):
        if len(self.samples) > 0:
            index = random.randint(0, len(self.samples) - 1)
            i = 0
            for key in self.samples.keys():
                if i == index:
                    return key
                i = i + 1
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
        self.samples = []
        self.round_globals = []
        self.playerid = None

        self.ctx = zmq.Context()

        self.subscriber = self.ctx.socket(zmq.SUB)
        self.subscriber.setsockopt(zmq.SUBSCRIBE, b'')
        self.subscriber.connect('tcp://' + SOUND_SERVER_IP + ':4000')

        self.publisher = self.ctx.socket(zmq.PUSH)
        self.publisher.connect('tcp://' + SOUND_SERVER_IP + ':4001')

        print('Loading sounds...')
        for path in os.listdir('sounds'):
            self.samples.append(Sample('sounds/' + path))

    def get(self, sound):
        """Get a sample from its sound name"""
        for sample in self.samples:
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

