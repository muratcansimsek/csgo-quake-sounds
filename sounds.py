"""Related to sounds"""

import pyglet
import random
import os

class Sample:
    """Represents a sample or sample collection"""
    def __init__(self, path):
        self.name = path
        self.samples = []

        if os.path.isfile(path):
            print("+ " + path)
            self.samples.append(pyglet.media.load(path, streaming=False))
        else:
            print(path + " ->")
            for file in os.listdir(path):
                complete_path = path + '/' + file
                print("   + " + complete_path)
                self.samples.append(pyglet.media.load(complete_path, streaming=False))

    def play(self):
        """Plays a random sample"""
        print("Playing " + self.name)
        if len(self.samples) > 0:
            random.choice(self.samples).play()

class SoundManager:
    """Loads and plays sounds"""
    def __init__(self):
        self.samples = []

        for path in os.listdir('sounds'):
            self.samples.append(Sample('sounds/' + path))

    def play(self, sound):
        """Plays a loaded sound"""
        for sample in self.samples:
            if sample.name.startswith('sounds/' + sound):
                sample.play()
                return
        
        print('Sound not found : ' + sound)
