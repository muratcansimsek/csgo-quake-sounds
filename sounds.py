"""Related to sounds"""

import pyglet
from os import walk

class SoundManager:
    """Loads and plays sounds"""
    def __init__(self):
        self.samples = {}

        filenames = []
        for (_, _, files) in walk('sounds'):
            filenames.extend(files)

        for filename in filenames:
            self.load('sounds/' + filename)

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
