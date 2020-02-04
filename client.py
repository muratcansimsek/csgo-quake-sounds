from sounds import SoundManager
from state import CSGOState


class Client:
    def __init__(self, gui) -> None:
        self.gui = gui
        self.sounds = SoundManager(self)
        self.state = CSGOState(self)

    async def update_status(self) -> None:
        with self.state.lock:
            if self.state.old_state is None:
                self.gui.SetStatusText("Waiting for CS:GO...")
            elif self.state.old_state.is_ingame:
                phase = self.state.old_state.phase
                if phase == "unknown":
                    phase = ""
                else:
                    phase = " (%s)" % phase
                self.gui.SetStatusText(
                    f"Round {self.state.old_state.current_round}{phase}"
                )
            else:
                self.gui.SetStatusText("Not in a match.")

    async def reload_sounds(self) -> None:
        """Reloads all sounds.

        Do not call outside of gui, unless you disable the update sounds button first.
        """
        await self.sounds.reload()
        await self.update_status()
        self.gui.updateSoundsBtn.Enable()
        self.sounds.play("Round start")
