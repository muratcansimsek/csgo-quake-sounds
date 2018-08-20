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
        self.state = {}
        self.match_stats = {}
        self.round = False
        self.is_player = False
        self.sounds = SoundManager()

    def update(self, json):
        """Update the entire game state"""
        player = json.get('player', {})
        if not player:
            return

        print(json)

        self.is_player = False
        provider = json.get('provider', {})
        if provider:
            if provider['steamid'] == player['steamid']:
                self.is_player = True

        try:
            self.match_stats = player['match_stats']
        except KeyError:
            pass
        else:
            self.update_match_state()

        try:
            self.state = player['state']
        except KeyError:
            pass
        else:
            self.round = json.get('round', {})
            self.update_player_state()

    def update_match_state(self):
        """Update the match state"""
        if self.is_player:
            if self.match_stats['mvps'] > self.mvps:
                sleep(1)
                self.sounds.play('mvp')
            self.mvps = self.match_stats['mvps']

    def update_player_state(self):
        """Update the player state"""
        if not self.is_player:
            # Don't play sounds while spectating
            return

        phase = self.round['phase'] if self.round else 'unknown'
        if self.old_phase != phase:
            print(phase)
            if phase == 'live':
                self.sounds.play('ready')

        if self.state['round_kills'] != self.round_kills:
            self.round_kills = self.state['round_kills']
            if self.round_kills == 2:
                self.sounds.play('2kills')
            elif self.round_kills == 3:
                self.sounds.play('3kills')
            elif self.round_kills == 4:
                self.sounds.play('4kills')
            elif self.round_kills == 5:
                self.sounds.play('5kills')

        if self.state['round_killhs'] > self.headshots:
            # Do not play over double kills, etc
            if self.round_kills < 2 or self.round_kills > 5:
                self.sounds.play('headshot')

        self.old_phase = phase
        self.headshots = self.state['round_killhs']
