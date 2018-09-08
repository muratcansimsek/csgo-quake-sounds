"""Related to CSGO Gamestate"""
from sounds import sounds

from config import HEADSHOTS_OVERRIDE

class PlayerState:
    def __init__(self, json):
        self.valid = False

        provider = json.get('provider', {})
        if not provider:
            # Not ingame
            return

        player = json.get('player', {})
        if not player:
            # Invalid gamestate
            return

        # Is the GameState tracking local player or spectated player
        self.steamid = provider['steamid']
        self.playerid = player['steamid']
        self.is_local_player = self.steamid == self.playerid
        self.is_ingame = player['activity'] != 'menu'

        # NOTE : this is modified in compare()
        self.play_timeout = False

        # Don't try to get ingame state
        if not self.is_ingame:
            return

        try:
            map = json.get('map', {})
            round = json.get('round', {})
            match_stats = player['match_stats']
            state = player['state']
            self.current_round = map['round']
        except KeyError as err:
            print('Invalid json :')
            print(err)
            print(json)
            return

        self.flash_opacity = state['flashed']
        self.is_knife_active = False
        for weapon in player['weapons']:
            weapon = player['weapons'][weapon]
            # Taser has no 'type' so we have to check for its name
            if weapon['name'] == 'weapon_taser':
                self.is_knife_active = weapon['state'] == 'active'
            elif weapon['type'] == 'Knife':
                self.is_knife_active = weapon['state'] == 'active'
        self.mvps = match_stats['mvps']
        self.phase = round['phase'] if round else 'unknown'
        self.remaining_timeouts = map['team_ct']['timeouts_remaining'] + map['team_t']['timeouts_remaining']
        self.round_kills = state['round_kills']
        self.round_headshots = state['round_killhs']
        self.total_deaths = match_stats['deaths']
        self.total_kills = match_stats['kills']

        # ------------------------------------------------------------
        # Below, only states that can't be compared to previous states
        # ------------------------------------------------------------

        # Updates only at round end
        if self.phase == 'over':
            try:
                self.won_round = round['win_team'] == player['team']
            except KeyError:
                # Player has not yet joined a team
                self.won_round = False

        # ------------------------------------------------------------

        self.valid = True

    def compare(self, old_state):
        # Init state without playing sounds
        if not old_state or not old_state.is_ingame:
            return

        # Ignore warmup
        if self.phase == 'warmup':
            print('[*] New match')
            return

        # Reset state after warmup
        if self.phase != 'unknown' and old_state.phase == 'unknown':
            print('[*] End of warmup')
            return

        # Check if we should play timeout
        if not self.play_timeout:
            self.play_timeout = old_state.play_timeout
        if self.remaining_timeouts == old_state.remaining_timeouts - 1:
            self.play_timeout = True
            print('[*] Timeout sound queued for next freezetime')

        # Play timeout music
        if self.phase == 'freezetime' and self.play_timeout:
            sounds.send('Timeout', 'global')
            self.play_timeout = False

        # Reset state when switching players (used for MVPs)
        if self.playerid != old_state.playerid:
            print('[*] Different player')
            return

        # Play round start, win, lose, MVP
        if self.is_local_player and self.mvps == old_state.mvps + 1:
            sounds.send('MVP', 'global')
        elif self.phase != old_state.phase:
            if self.phase == 'over' and self.mvps == old_state.mvps:
                sounds.send('Round win' if self.won_round else 'Round lose', 'global')
            elif self.phase == 'live':
                sounds.send('Round start', 'global')

        # Don't play player-triggered sounds below this ##########
        if not self.is_local_player:
            return
        ##########################################################

        # Lost kills - either teamkilled or suicided
        if self.total_kills < old_state.total_kills:
            if self.total_deaths == old_state.total_deaths + 1:
                sounds.send('Suicide', 'rare')
            elif self.total_deaths == old_state.total_deaths:
                sounds.send('Teamkill', 'rare')
        # Didn't suicide or teamkill -> check if player just died
        elif self.total_deaths == old_state.total_deaths + 1:
            sounds.send('Death', self.steamid)

        # Player got flashed
        if self.flash_opacity > 100 and self.flash_opacity > old_state.flash_opacity:
            sounds.send('Flashed', self.steamid)

        # Player killed someone
        if self.round_kills == old_state.round_kills + 1:
            # Kill with knife equipped
            if self.is_knife_active:
                sounds.send('Unusual kill', 'rare')
            # Kill with weapon equipped
            else:
                # Headshot
                if self.round_headshots == old_state.round_headshots + 1:
                    # Headshot override : always play Headshot
                    if HEADSHOTS_OVERRIDE:
                        sounds.send('Headshot', self.steamid)
                        return
                    # No headshot override : do not play over double kills, etc
                    if self.round_kills < 2 or self.round_kills > 5:
                        sounds.send('Headshot', self.steamid)

                # Killstreaks, headshotted or not
                if self.round_kills == 2:
                    sounds.send('2 kills', self.steamid)
                elif self.round_kills == 3:
                    sounds.send('3 kills', self.steamid)
                elif self.round_kills == 4:
                    sounds.send('4 kills', 'rare')
                elif self.round_kills == 5:
                    sounds.send('5 kills', 'rare')
        # Player killed multiple players
        elif self.round_kills > old_state.round_kills:
            sounds.send('Collateral', 'rare')

class CSGOState:
    """Follows the CSGO state via gamestate integration"""

    def __init__(self):
        self.old_state = None
        self.round_globals = []

    def update(self, json):
        """Update the entire game state"""
        newstate = PlayerState(json)

        # Ignore invalid states
        if not newstate.valid:
            return

        if newstate.is_ingame:
            sounds.playerid = newstate.playerid
            if self.old_state and newstate.current_round != self.old_state.current_round:
                sounds.round_globals = []

            # Play sounds and update state
            newstate.compare(self.old_state)
            self.old_state = newstate
        else:
            # Reset state in main menu
            self.old_state = None
            sounds.playerid = None

