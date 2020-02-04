import sys
from cx_Freeze import setup, Executable  # type: ignore
from typing import Dict

buildOptions: Dict = dict(
    packages=["aiofiles", "pyogg", "openal", "wx", "wxasync"],
    excludes=["tkinter"],
    include_files=[
        "sounds",
        "gamestate_integration_ccs.cfg",
        "icon.ico",
        "config.ini",
    ],
    optimize=2,
    include_msvcr=True,
)

base = "Win32GUI" if sys.platform == "win32" else None

executables = [Executable("main.py", base=base, targetName="csgo-custom-sounds.exe")]

setup(
    name="csgo-custom-sounds",
    version="1.5",
    description="Play custom sounds via Gamestate Integration",
    options=dict(build_exe=buildOptions),
    executables=executables,
)
