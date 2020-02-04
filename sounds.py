"""Related to sounds"""
import asyncio
import os
import random
import wx  # type: ignore
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from openal import AL_PLAYING, PYOGG_AVAIL, Buffer, OpusFile, Source  # type: ignore
from threading import Lock
from typing import Dict, List
from wxasync import StartCoroutine  # type: ignore

import config


class SoundManager:
    """Loads and plays sounds"""

    def __init__(self, client) -> None:
        self.playerid = None
        self.client = client
        self.lock = Lock()
        self.nb_max_sounds = 0

        # Dict[category:List[sound_data]]
        self.loaded_sounds: Dict[str, List[Buffer]] = defaultdict(list)

        self.volume: int = config.config["Sounds"].getint("Volume", 50)  # type: ignore

    def max_sounds(self) -> int:
        """Returns the number of sounds that will be loaded."""
        max = 0
        for path in os.listdir("sounds"):
            for file in os.listdir(os.path.join("sounds", path)):
                if file.startswith(".git") or file == "desktop.ini":
                    continue
                max = max + 1
        return max

    def load(self, category: str, filepath: str) -> None:
        # Can't load files - TODO show error & quit
        if not PYOGG_AVAIL:
            return

        with self.lock:
            self.loaded_sounds[category].append(Buffer(OpusFile(filepath)))
            wx.CallAfter(
                self.client.gui.SetStatusText,
                f"Loading sounds... ({len(self.loaded_sounds)}/{self.nb_max_sounds})",
            )

    async def reload(self) -> None:
        """Reloads the list of available sounds.

        The async logic is a bit complicated here, but it boils down to the following :
        - No more than 5 sounds will be loaded at the same time
        - Every sound is getting loaded in a separate thread, so the GUI is not blocked
        - We're not waiting using the executor but by waiting for all tasks to end,
        so the operation stays asynchronous
        """
        with self.lock:
            self.loaded_sounds = defaultdict(list)
            self.nb_max_sounds = self.max_sounds()

        executor = ThreadPoolExecutor(max_workers=5)
        loop = asyncio.get_running_loop()
        tasks: List = []
        for category in os.listdir("sounds"):
            for file in os.listdir(os.path.join("sounds", category)):
                if file.startswith(".git") or file == "desktop.ini":
                    continue

                filepath = os.path.join("sounds", category, file)
                tasks.append(
                    loop.run_in_executor(executor, self.load, category, filepath)
                )
        executor.shutdown(wait=False)
        await asyncio.gather(*tasks)
        wx.CallAfter(
            self.client.gui.SetStatusText, f"{self.nb_max_sounds} sounds loaded.",
        )

    async def _play(self, sound) -> None:
        """Play sound from its file path."""
        sound = Source(sound)
        # gain can be between 0.0 and 2.0 with the GUI's volume slider
        gain: float = 0.0 if self.volume == 0 else self.volume / 50.0
        sound.set_gain(gain)
        sound.play()

        while sound.get_state() == AL_PLAYING:
            # Don't end the thread until the sound finished playing
            await asyncio.sleep(1)

    def play(self, sound_name: str) -> bool:
        """Tries playing a sound by its name.

        Returns True if the sound was played successfully.
        """
        with self.lock:
            if len(self.loaded_sounds[sound_name]) > 0:
                sound = random.choice(self.loaded_sounds[sound_name])
                StartCoroutine(self._play(sound), self.client.gui)
                return True
            else:
                print(f"[!] No sound found for '{sound_name}'.")
                return False
