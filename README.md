# csgo-quake-sounds

Plays quake sounds in Counter-Strike : Global Offensive matches with Gamestate Integration.

[Download](https://github.com/kiwec/csgo-quake-sounds/releases/latest)

### FAQ

* Will I get banned for using this ?

No.

* Does it work in matchmaking ? On faceit ?

Yes.

* Can I add my own sounds ?

Yes. Feel free to remove the ones you don't like, too.

* What's this networking stuff ?

If you play with friends, sounds will be shared when spectating, or on certain rare events.

This allows everyone to use their own custom sounds, without hearing different sounds.

### Running (client)

If you don't want to use the installer, do the following :

* Install [AVbin](https://github.com/AVbin/AVbin/downloads)

* `git clone https://github.com/kiwec/csgo-quake-sounds.git && cd csgo-quake-sounds`

* `pip install -r requirements.txt`

Then, run it :

* `python main.py`

Please note that your version of Python should be 3.6 or higher.

### Running (server)

* Optional: edit config.py

* `python server.py`

No dependencies required other than Python 3.6+.
