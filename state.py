"""Related to CSGO Gamestate"""
from sounds import SoundManager

class CSGOState:
    """Follows the CSGO state via gamestate integration"""

    def __init__(self):
        self.headshots = 0
        self.round_kills = 0
        self.mvps = 0
        self.old_phase = ''
        self.state = []
        self.round = False
        self.is_player = False
        self.sounds = SoundManager()

    def update(self, json):
        """Update the entire game state"""
        player = json.get('player', {})
        if not player:
            return

        self.is_player = False
        provider = json.get('provider', {})
        if provider:
            if provider['steamid'] == player['steamid']:
                self.is_player = True

        try:
            match_stats = player['match_stats']
        except KeyError:
            pass
        else:
            # if match_stats['mvps'] > mvps:
            #     impressive.play()
            self.mvps = match_stats['mvps']
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

    def update_player_state(self):
        """Update the player state"""
        if not self.is_player:
            # Don't play sounds if not ingame
            return

        phase = self.round['phase'] if self.round else 'unknown'
        health = self.state['health']
        if health == 0 or phase == 'freezetime':
            # Don't play sounds while spectating
            return

        if self.state['round_killhs'] > self.headshots:
            # Do not play over double kills, etc
            if self.round_kills < 2 or self.round_kills > 5:
                self.sounds.play('headshot.mp3')

        # "prepare" is never played :(
        if self.old_phase != phase:
            print(phase)
            if phase == 'freezetime':
                self.sounds.play('prepare.mp3')
            if phase == 'live':
                self.sounds.play('play.wav')

        if self.state['round_kills'] != self.round_kills:
            round_kills = self.state['round_kills']
            if round_kills == 2:
                self.sounds.play('doublekill.mp3')
            elif round_kills == 3:
                self.sounds.play('triplekill.mp3')
            elif round_kills == 4:
                self.sounds.play('dominating.mp3')
            elif round_kills == 5:
                self.sounds.play('wickedsick.mp3')

        self.old_phase = phase
        self.headshots = self.state['round_killhs']
