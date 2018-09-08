"""Plays quake sounds according to CSGO Gamestate"""
from http.server import BaseHTTPRequestHandler, HTTPServer
from sounds import sounds
from state import CSGOState
import json
import os, signal, subprocess, sys, threading

GAMESTATE = CSGOState()
recieved_post = False

class PostHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_len = int(self.headers['Content-Length'])
        body = self.rfile.read(content_len)
        self.send_response(200)
        self.end_headers()

        global recieved_post
        if not recieved_post:
            print('\r\n[+] CSGO Gamestate Integration is working\r\n')
            recieved_post = True

        GAMESTATE.update(json.loads(body))
        return
    
    def log_message(self, format, *args):
        # Do not spam the console with POSTs
        return


print('\r\n           - Keep this window open while CSGO is running -')
print('Reminder : you need to copy gamestate_integration_quake.cfg into csgo/cfg\r\n')

# HTTP Server listening for CSGO Gamestate updates
server = HTTPServer(('127.0.0.1', 3000), PostHandler)
threading.Thread(target=server.serve_forever, daemon=True).start()

# Host local sound server
server = subprocess.Popen([sys.executable, './server.py'], stdout=None)

# Kill local sound server when listener is closed
def kill_server():
    server.terminate()
    server.wait()
signal.signal(signal.SIGTERM, kill_server)

# Listen for sound server updates
sounds.listen()
