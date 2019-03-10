@echo off

echo Building (pyinstaller)...
rem Add -w option to hide console in releases
pyinstaller -i icon.ico --log-level WARN --exclude-module tkinter -r avbin.dll main.py

echo Copying sounds...
robocopy sounds dist\main\sounds /E > nul

echo Wrapping up...
copy gamestate_integration_ccs.cfg dist\main\ > nul
copy icon.ico dist\main\ > nul
mkdir dist\main\cache
del main.spec

echo We're done! Build is in dist/main/.
