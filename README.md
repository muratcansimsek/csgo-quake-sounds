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

### Running

If you don't to use the installer, do the following :

* Install [AVbin](https://github.com/AVbin/AVbin/downloads)

* `git clone https://github.com/kiwec/csgo-quake-sounds.git && cd csgo-quake-sounds`

* `pip3 install -r requirements.txt`

* Copy `gamestate_integration_quake.cfg` into your `csgo/cfg/` directory

By default, on linux it is `~/.steam/steam/steamapps/common/Counter-Strike\ Global\ Offensive/csgo/cfg/`.

Then, run it :

* `python3 main.py`

### Compiling (installer)

pynsist doesn't allow a lot of customization so follow these instructions :

* Run `pynsist installer.cfg --no-makensis`

* Edit `build/nsis/installer.nsi`, replace `SetOutPath "%HOMEDRIVE%\%HOMEPATH%"` with `SetOutPath "$INSTDIR"`

* Add [AVbin](https://github.com/AVbin/AVbin/downloads) as a dependency

* Right click `installer.nsi`, click "Compile NSIS Script"

