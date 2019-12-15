"""Related to CSGO Gamestate"""
import json
from threading import Lock, Thread
from http.server import BaseHTTPRequestHandler, HTTPServer

import config
from protocol import GameEvent


class PlayerState:
    def __init__(self, json, sounds):
        self.valid = False
        self.sounds = sounds

        provider = json.get("provider", {})
        if not provider:
            # Not ingame
            return

        player = json.get("player", {})
        if not player:
            # Invalid gamestate
            return

        # Is the GameState tracking local player or spectated player
        self.steamid = provider["steamid"]
        self.playerid = player["steamid"]
        self.is_local_player = self.steamid == self.playerid
        self.is_ingame = player["activity"] != "menu"

        # NOTE : this is modified in compare()
        self.play_timeout = False

        if self.is_ingame:
            sounds.playerid = self.playerid
        else:
            sounds.playerid = None
            return

        try:
            map = json.get("map", {})
            round = json.get("round", {})
            match_stats = player["match_stats"]
            state = player["state"]
            self.current_round = map["round"]
        except KeyError as err:
            print("Invalid json :")
            print(err)
            print(json)
            return

        self.flash_opacity = state["flashed"]
        self.is_knife_active = False
        for weapon in player["weapons"]:
            weapon = player["weapons"][weapon]
            # Taser has no 'type' so we have to check for its name
            if weapon["name"] == "weapon_taser":
                self.is_knife_active = weapon["state"] == "active"
            elif weapon["type"] == "Knife":
                self.is_knife_active = weapon["state"] == "active"
        self.mvps = match_stats["mvps"]
        self.phase = round["phase"] if round else "unknown"
        self.remaining_timeouts = (
            map["team_ct"]["timeouts_remaining"] + map["team_t"]["timeouts_remaining"]
        )
        self.round_kills = state["round_kills"]
        self.round_headshots = state["round_killhs"]
        self.total_deaths = match_stats["deaths"]
        self.total_kills = match_stats["kills"]

        # ------------------------------------------------------------
        # Below, only states that can't be compared to previous states
        # ------------------------------------------------------------

        # Updates only at round end
        if self.phase == "over":
            try:
                self.won_round = round["win_team"] == player["team"]
            except KeyError:
                # Player has not yet joined a team
                self.won_round = False

        # ------------------------------------------------------------

        self.valid = True

    def compare(self, old_state):
        # Init state without playing sounds
        if not old_state or not old_state.valid:
            return

        if not self.is_ingame or not self.valid:
            return

        # Ignore warmup
        if self.phase == "warmup":
            print("[*] New match")
            return

        # Reset state after warmup
        if self.phase != "unknown" and old_state.phase == "unknown":
            print("[*] End of warmup")
            return

        # Check if we should play timeout
        if not self.play_timeout:
            self.play_timeout = old_state.play_timeout
        if self.remaining_timeouts == old_state.remaining_timeouts - 1:
            self.play_timeout = True
            print("[*] Timeout sound queued for next freezetime")

        # Play timeout music
        if self.phase == "freezetime" and self.play_timeout:
            self.sounds.send(GameEvent.Type.TIMEOUT, self)
            self.play_timeout = False

        # Reset state when switching players (used for MVPs)
        if self.playerid != old_state.playerid:
            print("[*] Different player")
            return

        # Play round start, win, lose, MVP
        if self.is_local_player and self.mvps == old_state.mvps + 1:
            self.sounds.send(GameEvent.Type.MVP, self)
        elif self.phase == "live" and self.phase != old_state.phase:
            self.sounds.send(GameEvent.Type.ROUND_START, self)

        # Don't play player-triggered sounds below this ##########
        if not self.is_local_player:
            return
        ##########################################################

        # Lost kills - either teamkilled or suicided
        if self.total_kills < old_state.total_kills:
            if self.total_deaths == old_state.total_deaths + 1:
                self.sounds.send(GameEvent.Type.SUICIDE, self)
            elif self.total_deaths == old_state.total_deaths:
                self.sounds.send(GameEvent.Type.TEAMKILL, self)
        # Didn't suicide or teamkill -> check if player just died
        elif self.total_deaths == old_state.total_deaths + 1:
            self.sounds.send(GameEvent.Type.DEATH, self)

        # Player got flashed
        if self.flash_opacity > 150 and self.flash_opacity > old_state.flash_opacity:
            self.sounds.send(GameEvent.Type.FLASH, self)

        # Player killed someone
        if self.round_kills == old_state.round_kills + 1:
            # Kill with knife equipped
            if self.is_knife_active:
                self.sounds.send(GameEvent.Type.KNIFE, self)
            # Kill with weapon equipped
            else:
                # Headshot
                if self.round_headshots == old_state.round_headshots + 1:
                    # Headshot override : always play Headshot
                    prefer_headshots = config.config["Sounds"].getboolean(
                        "PreferHeadshots", False
                    )
                    if prefer_headshots:
                        self.sounds.send(GameEvent.Type.HEADSHOT, self)
                        return
                    # No headshot override : do not play over double kills, etc
                    if self.round_kills < 2 or self.round_kills > 5:
                        self.sounds.send(GameEvent.Type.HEADSHOT, self)

                # Killstreaks, headshotted or not
                if self.round_kills == 2:
                    self.sounds.send(GameEvent.Type.KILL, self)
                elif self.round_kills == 3:
                    self.sounds.send(GameEvent.Type.KILL, self)
                elif self.round_kills == 4:
                    self.sounds.send(GameEvent.Type.KILL, self)
                elif self.round_kills == 5:
                    self.sounds.send(GameEvent.Type.KILL, self)
        # Player killed multiple players
        elif self.round_kills > old_state.round_kills:
            self.sounds.send(GameEvent.Type.COLLATERAL, self)


class CSGOState:
    """Follows the CSGO state via gamestate integration"""

    def __init__(self, client):
        self.lock = Lock()
        self.old_state = None
        self.client = client

        server = HTTPServer(("127.0.0.1", 3000), PostHandler)
        server.RequestHandlerClass.state = self
        Thread(target=server.serve_forever, daemon=True).start()

    def is_ingame(self):
        return self.old_state is not None and self.old_state.is_ingame is True

    def is_alive(self):
        with self.lock:
            if not self.is_ingame():
                return False
            if self.old_state.phase != "live":
                return False
            if self.old_state.steamid != self.old_state.playerid:
                return False
        return True

    def update(self, json):
        """Update the entire game state"""
        should_update_client = False
        with self.lock:
            newstate = PlayerState(json, self.client.sounds)

            if self.old_state == None or self.old_state.steamid != newstate.steamid:
                should_update_client = True

            newstate.compare(self.old_state)
            self.old_state = newstate
        if self.client != None:
            self.client.update_status()
            if should_update_client:
                self.client.client_update()


class PostHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_len = int(self.headers["Content-Length"])
        body = self.rfile.read(content_len)
        self.send_response(200)
        self.end_headers()
        self.state.update(json.loads(body))
        return

    def log_message(self, format, *args):
        # Do not spam the console with POSTs
        return
