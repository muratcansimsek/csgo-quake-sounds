# csgo-quake-sounds

Plays quake sounds in Counter-Strike : Global Offensive matches with Gamestate Integration.

[Download](https://github.com/kiwec/csgo-quake-sounds/releases/latest)

### FAQ

* Will I get banned for using this ?

No.

* Does it work in matchmaking ? On faceit ?

Yes.

* Why can't my spectating friends hear my sounds ?

You have to setup a sound server - follow the instructions in server.py.

* Can I add my own sounds ?

Yes. Feel free to remove the ones you don't like, too.

However, if you play with a sound server, make sure everyone has the same sounds folder, or sometimes nothing will play.

### Running

If you don't want to use the installer, do the following :

* Install [AVbin](https://github.com/AVbin/AVbin/downloads)

* `git clone https://github.com/kiwec/csgo-quake-sounds.git && cd csgo-quake-sounds`

* `pip3 install -r requirements.txt`

* Copy `gamestate_integration_quake.cfg` into your `csgo/cfg/` directory

By default, on linux it is `~/.steam/steam/steamapps/common/Counter-Strike\ Global\ Offensive/csgo/cfg/`.

Then, run it :

* `python3 main.py`

### Building (installer)

pynsist doesn't allow a lot of customization so follow these instructions :

* Run `pynsist installer.cfg --no-makensis`

* Edit `build/nsis/installer.nsi`, replace `SetOutPath "%HOMEDRIVE%\%HOMEPATH%"` with `SetOutPath "$INSTDIR"`

* Add [AVbin](https://github.com/AVbin/AVbin/downloads) as a dependency

* Right click `installer.nsi`, click "Compile NSIS Script"

