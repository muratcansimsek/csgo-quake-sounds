"""Related to sounds"""
import hashlib
import os
import random
import threading
from concurrent.futures.thread import ThreadPoolExecutor
from pydub import AudioSegment  # type: ignore
from pydub.playback import play  # type: ignore
from threading import Lock
from typing import Callable, Dict, List, Optional

import config
from packets_pb2 import GameEvent, PacketInfo, PlaySound
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
        self.loaded_sounds: Dict[bytes, AudioSegment] = {}

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
        """Loads a file (which is quite slow with pydub)."""
        hash = hashlib.blake2b()
        with open(filepath, 'rb') as infile:
            hash.update(infile.read())
            digest = hash.digest()
        # This fails :/ loading the file twice instead
        # sound = AudioSegment.from_file(infile)
        sound = AudioSegment.from_file(filepath)
        with self.lock:
            self.loaded_sounds[digest] = sound
            self.available_sounds[filepath] = digest.hex()
        file_callback()

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

        with self.lock:
            sounds = self.available_sounds.items()
        sound_path = os.path.join('sounds', sound)
        collection: List[bytes] = [bytes.fromhex(v) for k, v in sounds if k.startswith(sound_path)]
        if len(collection) > 0:
            return random.choice(collection)
        print(f'[!] No available samples for action "{sound}".')
        return None

    def _play(self, sound, gain) -> None:
        """Play sound from its file path. Blocking call."""
        play(sound.apply_gain(gain))

    def play(self, packet) -> bool:
        """Tries playing a sound from a PlaySound packet.

        Returns True if the sound was played successfully.
        """
        if str(packet.steamid) != self.playerid and packet.steamid != 0:
            return True

        with self.lock:
            # 0 = -10db ; 50 = +0db ; 100 = +10db
            gain: float = self.volume - 50
            if gain != 0:
                gain = gain / 5

            sound: Optional[AudioSegment] = None
            try:
                sound = self.loaded_sounds[packet.sound_hash]
            except KeyError:
                filepath = os.path.join('sounds', 'Downloaded', packet.sound_hash.hex())
                if filepath in self.available_sounds.keys():
                    sound = AudioSegment.from_file(filepath)
                    self.loaded_sounds[packet.sound_hash] = sound

            if sound is None:
                print(f'[!] Sound {small_hash(packet.sound_hash)} not found.')
                return False
            else:
                threading.Thread(target=self._play, args=(sound, gain,), daemon=True).start()
                return True

    def save(self, packet) -> None:
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
        if hash != None:
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
