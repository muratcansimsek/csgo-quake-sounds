### Building an installer

pynsist doesn't allow a lot of customization so follow these instructions :

* Run `pynsist installer.cfg --no-makensis`

* Edit `build/nsis/installer.nsi`, replace `SetOutPath "%HOMEDRIVE%\%HOMEPATH%"` with `SetOutPath "$INSTDIR"`

* Add [AVbin](https://github.com/AVbin/AVbin/downloads) as a dependency

* Right click `installer.nsi`, click "Compile NSIS Script"

