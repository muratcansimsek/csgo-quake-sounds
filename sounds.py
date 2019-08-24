"""Related to sounds"""
import hashlib
import os
import random
import threading
from concurrent.futures.thread import ThreadPoolExecutor
from openal import AL_PLAYING, PYOGG_AVAIL, Buffer, OpusFile, Source  # type: ignore
from time import sleep
from threading import Lock
from typing import Callable, Dict, List, Optional

import config
from protocol import GameEvent, PlaySound, SoundResponse
from util import print, get_event_class, small_hash


class SoundManager:
    """Loads and plays sounds"""
    def __init__(self, client) -> None:
        self.playerid = None
        self.client = client
        self.lock = Lock()

        # List of available sounds (filepath:hash dict).
        self.available_sounds: Dict[str, str] = {}

        # List of loaded sounds (hash:sound dict)
        self.loaded_sounds: Dict[bytes, Buffer] = {}

        self.personal_sounds: List[bytes] = []

        with config.lock:
            self.volume = config.config['Sounds'].getint('Volume', 50)

    def max_sounds(self) -> int:
        """Returns the number of sounds that will be loaded."""
        max = 0
        for path in os.listdir('sounds'):
            if path == 'Downloaded':
                continue
            for file in os.listdir(os.path.join('sounds', path)):
                if file.startswith('.git') or file == 'desktop.ini':
                    continue
                max = max + 1
        return max

    def load(self, filepath: str, file_callback: Callable[[], None]) -> None:
        self.load_sync(filepath)
        file_callback()

    def load_sync(self, filepath: str) -> Optional[Buffer]:
        hash = hashlib.blake2b()
        with open(filepath, 'rb') as infile:
            hash.update(infile.read())
            digest = hash.digest()

        # Can't load files - TODO show error & quit
        if not PYOGG_AVAIL:
            return None

        with self.lock:
            self.loaded_sounds[digest] = Buffer(OpusFile(filepath))
            self.available_sounds[filepath] = digest.hex()
            return self.loaded_sounds[digest]

    def reload(self, file_callback: Callable[[], None], error_callback: Callable[[str], None]) -> None:
        """Reloads the list of available sounds."""
        with self.lock:
            self.available_sounds = {}
            self.loaded_sounds = {}

        with ThreadPoolExecutor(max_workers=5) as executor:
            for path in os.listdir('sounds'):
                for file in os.listdir(os.path.join('sounds', path)):
                    if file.startswith('.git') or file == 'desktop.ini':
                        continue

                    filepath = os.path.join('sounds', path, file)
                    if path == 'Downloaded':
                        with self.lock:
                            self.available_sounds[filepath] = file
                    else:
                        if os.stat(filepath).st_size > 2 * 1024 * 1024:
                            error_callback('File %s is too large (over 2 Mb) and will not be loaded.' % filepath)
                            continue

                        executor.submit(self.load, filepath, file_callback)

    def get_random(self, type, state) -> Optional[bytes]:
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
        elif type == GameEvent.Type.KILL: sound = '%d kills' % state.round_kills
        elif type == GameEvent.Type.COLLATERAL: sound = 'Collateral'
        elif type == GameEvent.Type.ROUND_START: sound = 'Round start'
        elif type == GameEvent.Type.TIMEOUT: sound = 'Timeout'

        with self.lock:
            sounds = self.available_sounds.items()
        sound_path = os.path.join('sounds', sound)
        collection: List[bytes] = [bytes.fromhex(v) for k, v in sounds if k.startswith(sound_path)]
        if len(collection) > 0:
            return random.choice(collection)
        print(f'[!] No available samples for action "{sound}".')
        return None

    def _play(self, sound) -> None:
        """Play sound from its file path. Blocking call."""
        sound = Source(sound)
        # gain can be between 0.0 and 2.0 with the GUI's volume slider
        with self.lock:
            gain: float = 0.0 if self.volume == 0 else self.volume / 50.0
            sound.set_gain(gain)
        sound.play()

        while sound.get_state() == AL_PLAYING:
            # Don't end the thread until the sound finished playing
            sleep(1)

    def play(self, packet: PlaySound) -> bool:
        """Tries playing a sound from a PlaySound packet.

        Returns True if the sound was played successfully.
        """
        if str(packet.steamid) != self.playerid and packet.steamid != 0:
            return True

        with self.lock:
            sound: Optional[Buffer] = None
            try:
                sound = self.loaded_sounds[packet.sound_hash]
            except KeyError:
                filepath = os.path.join('sounds', 'Downloaded', packet.sound_hash.hex())
                if filepath in self.available_sounds.keys():
                    sound = self.load_sync(filepath)

            if sound is None:
                print(f'[!] Sound {small_hash(packet.sound_hash)} not found.')
                return False
            else:
                threading.Thread(target=self._play, args=(sound,), daemon=True).start()
                return True

    def save(self, packet: SoundResponse) -> None:
        filepath = os.path.join('sounds', 'Downloaded', packet.hash.hex())
        with open(filepath, 'wb') as outfile:
            outfile.write(packet.data)
        filename = packet.hash.hex()
        with self.lock:
            self.available_sounds[filepath] = filename
        print(f'Finished downloading {small_hash(packet.hash)}.')

    def send(self, update_type, state) -> None:
        """Sends a sound to play for everybody"""
        if self.client == None:
            return

        hash = self.get_random(update_type, state)
        if hash is not None:
            packet = GameEvent()
            packet.update = update_type
            packet.proposed_sound_hash = hash
            packet.kill_count = int(state.round_kills)
            packet.round = int(state.current_round)
            self.client.send(packet)

            # Normal event : play without waiting for server
            if get_event_class(packet) == 'normal':
                playpacket = PlaySound()
                playpacket.steamid = 0
                playpacket.sound_hash = hash
                self.play(playpacket)
