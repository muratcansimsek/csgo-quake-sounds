"""Related to sounds"""

import pyglet
import random
from os import walk

class SoundManager:
    """Loads and plays sounds"""
    def __init__(self):
        self.samples = {}
        self.mvps = []

        # Load sounds regardless of file extension
        for (_, _, files) in walk('sounds'):
            for filename in files:
                self.load('sounds/' + filename)
        
        # Load all mvp sounds from the "mvps" folder
        for (_, _, files) in walk('mvps'):
            for filename in files:
                self.mvps.append(pyglet.media.load('mvps/' + filename, streaming=False))

    def playMvp(self):
        """Plays a random sound from the mvps folder"""
        random.choice(self.mvps).play()

    def play(self, sound):
        """Plays a loaded sound"""
        for name, sample in self.samples.items():
            if name.startswith('sounds/' + sound):
                sample.play()
                return
        
        print('Sound not found : ' + sound)

    def load(self, filename):
        """Loads a sound for future playback"""
        self.samples[filename] = (pyglet.media.load(filename, streaming=False))
