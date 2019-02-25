import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import server
from sounds import sounds
from state import CSGOState


GAMESTATE = CSGOState()
class PostHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_len = int(self.headers['Content-Length'])
        body = self.rfile.read(content_len)
        self.send_response(200)
        self.end_headers()

        if not self.recieved_post:
            print('\r\n[+] CSGO Gamestate Integration is working\r\n')
            self.recieved_post = True

        GAMESTATE.update(json.loads(body))
        return
    
    def log_message(self, format, *args):
        # Do not spam the console with POSTs
        return


# HTTP Server listening for CSGO Gamestate updates
gamestate_server = HTTPServer(('127.0.0.1', 3000), PostHandler)
gamestate_thread = threading.Thread(target=gamestate_server.serve_forever, daemon=True)

# Local sound client
sound_client_thread = threading.Thread(target=sounds.listen, daemon=True)
# Local sound server
sound_server_thread = threading.Thread(target=server.serve, daemon=True)

def start():
    gamestate_thread.start()
    sound_client_thread.start()
    sound_server_thread.start()
