# csgo-quake-sounds

Custom sounds in your Counter-Strike : Global Offensive matches.

[Download](https://github.com/kiwec/csgo-quake-sounds/releases/latest)

### FAQ

* Does it work in matchmaking ? On faceit ?

Yes.

* Will I get banned for using this ?

No. This is using [Game State Integration](https://developer.valvesoftware.com/wiki/Counter-Strike:_Global_Offensive_Game_State_Integration), which is allowed by Valve.

* How do I add my own sounds ?

Drop your sounds in the corresponding `sounds` folder. Feel free to remove the ones you don't like, too.

Please keep in mind that only OPUS files are supported.

### Running

You probably want to use the [installer](https://github.com/kiwec/csgo-quake-sounds/releases/latest).

However, if you want to try the latest version, execute these commands :

* `git clone https://github.com/kiwec/csgo-quake-sounds.git && cd csgo-quake-sounds`

* `python setup.py install --user`

Then, run it :

* `python main.py`

### Building

Run the following commands :

* `python setup.py install --user`

* `pip install cx_Freeze`

* Run `python build.py build`
