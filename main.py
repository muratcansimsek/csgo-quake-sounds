"""Plays quake sounds according to CSGO Gamestate"""
from flask import Flask, request
from state import CSGOState

GAMESTATE = CSGOState()
APP = Flask(__name__)
@APP.route("/", methods=["POST"])
def main():
    """Gamestate loop, gets called multiple times per second"""
    GAMESTATE.update(request.json)
    return 'k'

if __name__ == "__main__":
    print('Running')
    APP.run(port=3000)
