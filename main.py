"""Plays quake sounds according to CSGO Gamestate"""
from flask import Flask, request
from state import CSGOState

APP = Flask(__name__)
@APP.route("/", methods=["POST"])
def main():
    """Gamestate loop, gets called multiple times per second"""
    GAMESTATE.update(request.json)
    return 'k'

print('\r\n           - Keep this window open while CSGO is running -')
print('Reminder : you need to copy gamestate_integration_quake.cfg into csgo/cfg\r\n')

GAMESTATE = CSGOState()
APP.run(port=3000)
