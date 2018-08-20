"""Related to CSGO Gamestate"""
from sounds import SoundManager
from time import sleep

class CSGOState:
    """Follows the CSGO state via gamestate integration"""

    def __init__(self):
        self.headshots = 0
        self.round_kills = 0
        self.mvps = 0
        self.old_phase = ''
        self.deaths = 0
        self.kills = 0
        self.flashed = False
        self.timeouts = 2
        self.is_player = False
        self.sounds = SoundManager()
        self.json = {}

        # Prefer playing the headshot sound over double kills, etc
        self.headshots_override = True

    def update(self, json):
        """Update the entire game state"""
        self.json = json

        player = json.get('player', {})
        if not player:
            # Player not ingame -> no point in tracking stats
            return

        self.is_player = False
        provider = json.get('provider', {})
        if provider:
            if provider['steamid'] == player['steamid']:
                self.is_player = True

        if self.is_player:
            # Update state.player only if steamid matches
            self.update_player(player)

    def update_player(self, player):
        """Update state.player"""
        try:
            match_stats = player['match_stats']
        except KeyError:
            pass
        else:
            self.update_player_match_stats(match_stats)

        try:
            map = self.json.get('map', {})
            round = self.json.get('round', {})
            phase = round['phase'] if round else 'unknown'

            if phase == 'freezetime':
                newtimeouts = map['team_ct']['timeouts_remaining'] + map['team_t']['timeouts_remaining']
                if self.timeouts < newtimeouts:
                    self.sounds.play('Timeout')
                self.timeouts = newtimeouts

            if self.old_phase != phase and phase == 'live':
                self.sounds.play('Round start')

            self.old_phase = phase
        except KeyError:
            pass

        try:
            state = player['state']
        except KeyError:
            pass
        else:
            if state['flashed'] > 100:
                if not self.flashed:
                    self.sounds.play('Flashed')
                    self.flashed = True
            else:
                self.flashed = False

            for weapon in player['weapons']:
                weapon = player['weapons'][weapon]
                if weapon['type'] == 'Knife' and weapon['state'] == 'active':
                    if state['round_kills'] > self.round_kills:
                        self.sounds.play('Unusual kill')
                        self.round_kills = state['round_kills']
                        return
            self.update_round_kills(state['round_kills'], state['round_killhs'])

    def update_player_match_stats(self, match_stats):
        """Play MVPs, teamkills and suicides"""
        if match_stats['mvps'] > self.mvps:
            sleep(1)
            self.sounds.play('MVP')
        self.mvps = match_stats['mvps']

        # Lost a kill - either teamkilled or suicided
        if match_stats['kills'] < self.kills:
            if match_stats['deaths'] > self.deaths:
                self.sounds.play('Suicide')
            else:
                self.sounds.play('Teamkill')
        self.kills = match_stats['kills']
        self.deaths = match_stats['deaths']
    
    def update_round_kills(self, rk, rhs):
        """Play kills and headshots"""
        if rhs > self.headshots:
            if self.headshots_override:
                self.sounds.play('Headshot')
                self.headshots = rhs
                return

            # Do not play over double kills, etc
            if self.round_kills < 2 or self.round_kills > 5:
                self.sounds.play('Headshot')

        if rk != self.round_kills:
            self.round_kills = rk
            if self.round_kills == 2:
                self.sounds.play('2 kills')
            elif self.round_kills == 3:
                self.sounds.play('3 kills')
            elif self.round_kills == 4:
                self.sounds.play('4 kills')
            elif self.round_kills == 5:
                self.sounds.play('5 kills')
        
        self.headshots = rhs
