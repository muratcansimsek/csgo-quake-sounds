# csgo-quake-sounds

Plays quake sounds in Counter-Strike : Global Offensive matches with Gamestate Integration.

### FAQ

* Will I get banned for using this ?

No.

* Does it work in matchmaking ?

Yes.

* Can I add my own sound in the mvps folder ?

Yes. Feel free to remove the ones you don't like, too.

### Installation

* Copy gamestate_integration_quake.cfg into csgo/cfg

* Run the installer from the [releases page](https://github.com/kiwec/csgo-quake-sounds/releases) or clone this repository and run the following :

```sh
pip3 install -r requirements.txt
python3 main.py
```

### Compiling

pynsist breaks working directory so follow these instructions :

* Run `pynsist installer.cfg --no-makensis`

* Edit build/nsis/installer.nsi, replace `SetOutPath "%HOMEDRIVE%\%HOMEPATH%"` with `SetOutPath "$INSTDIR"`

* Right click installer.nsi, click "Compile NSIS Script"
