import sys
from cx_Freeze import setup, Executable

base = None
# To hide console on release versions, uncomment this :
if sys.platform == "win32":
    base = "Win32GUI"

setup(  name = "ccs",
        version = "1.5",
        description = "CS:GO Custom Sounds",
        options = {"build_exe": {
            "packages": ["os", "wx", "pyglet", "google.protobuf", "steamfiles"],
            "excludes": ["tkinter"],
            "include_files": ["cache", "sounds", "gamestate_integration_ccs.cfg", "icon.ico", "config.ini"],
            "bin_includes": ["avbin64.dll"],
            "optimize": 2,
            "include_msvcr": True,
        }},
        executables = [Executable("main.py", base=base, targetName="csgo-custom-sounds.exe")])
