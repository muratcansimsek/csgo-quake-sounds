"""Related to sounds"""

import pyglet

class SoundManager:
    """Loads and plays sounds"""
    def __init__(self):
        self.samples = []

        filenames = [
            'headshot.mp3',
            'play.wav',
            'prepare.mp3',
            'impressive.mp3',
            'doublekill.mp3',
            'triplekill.mp3',
            'dominating.mp3',
            'wickedsick.mp3',
        ]

        for filename in filenames:
            self.load('sounds/' + filename)

    def play(self, sound):
        """Plays a loaded sound"""
        self.samples['sounds/' + sound].play()

    def load(self, filename):
        """Loads a sound for future playback"""
        self.samples.append(pyglet.media.load(filename, streaming=False))
