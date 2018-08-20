"""Related to CSGO Gamestate"""
from sounds import SoundManager
from time import sleep

sounds = SoundManager()

class PlayerState:
    def __init__(self, json):
        # Set this to True to override "double kill"-type sounds with "Headshot" if headshot
        self.headshots_override = False

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
        self.is_local_player = provider['steamid'] == player['steamid']
        self.is_ingame = player['activity'] != 'menu'

        # Don't try to get ingame state
        if not self.is_ingame:
            self.valid = True
            return
        
        try:
            map = json.get('map', {})
            round = json.get('round', {})
            match_stats = player['match_stats']
            state = player['state']
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
            self.won_round = round['win_team'] == player['team']

        # ------------------------------------------------------------

        self.valid = True

    def compare(self, old_state):
        # Init state without playing sounds
        if not old_state or not old_state.is_ingame:
            return
        
        # Reset state after warmup
        if self.phase != 'unknown' and old_state.phase == 'unknown':
            return

        # Lost kills - either teamkilled or suicided
        if self.total_kills < old_state.total_kills:
            if self.total_deaths == old_state.total_deaths + 1:
                sounds.play('Suicide')
            else:
                sounds.play('Teamkill')
        # Didn't suicide or teamkill -> check if player just died
        elif self.total_deaths == old_state.total_deaths + 1:
            sounds.play('Death')

        # Play MVP music
        if self.mvps == old_state.mvps + 1:
            sleep(1)
            sounds.play('MVP')

        # New phase
        if self.phase != old_state.phase:
            if self.phase == 'live':
                sounds.play('Round start')
            elif self.phase == 'freezetime':
                # Play timeout music
                if self.remaining_timeouts == old_state.remaining_timeouts - 1:
                    sounds.play('Timeout')
            elif self.phase == 'over':
                # NOTE : this check is useless since mvp and round win aren't in sync
                if self.mvps == old_state.mvps:
                    sounds.play('Round win' if self.won_round else 'Round lose')
        
        # Player got flashed
        if self.flash_opacity > 100 and self.flash_opacity > old_state.flash_opacity:
            sounds.play('Flashed')
        
        # Player killed someone
        if self.round_kills == old_state.round_kills + 1:
            # Kill with knife equipped
            if self.is_knife_active:
                sounds.play('Unusual kill')
            # Kill with weapon equipped
            else:
                # Headshot
                if self.round_headshots == old_state.round_headshots + 1:
                    # Always play Headshot
                    if self.headshots_override:
                        sounds.play('Headshot')
                    # Do not play over double kills, etc
                    elif self.round_kills < 2 or self.round_kills > 5:
                        sounds.play('Headshot')
                # Bodyshot
                else:
                    if self.round_kills == 2:
                        sounds.play('2 kills')
                    elif self.round_kills == 3:
                        sounds.play('3 kills')
                    elif self.round_kills == 4:
                        sounds.play('4 kills')
                    elif self.round_kills == 5:
                        sounds.play('5 kills')
        # Player killed multiple players
        elif self.round_kills > old_state.round_kills:
            sounds.play('Collateral')


class CSGOState:
    """Follows the CSGO state via gamestate integration"""

    def __init__(self):
        self.old_state = None

    def update(self, json):
        """Update the entire game state"""
        newstate = PlayerState(json)

        # Ignore invalid states
        if not newstate.valid:
            return

        if newstate.is_ingame:
            # Only track state on local player
            if newstate.is_local_player:
                newstate.compare(self.old_state)
                self.old_state = newstate
        else:
            # Reset state in main menu
            self.old_state = None
