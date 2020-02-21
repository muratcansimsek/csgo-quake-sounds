"""Plays quake sounds according to CSGO Gamestate"""
import asyncio
import os
import wx  # type: ignore  # type: ignore
from openal import oalInit, oalQuit  # type: ignore
from shutil import copyfile
from wxasync import WxAsyncApp  # type: ignore

# Local files
import gui
import steamfiles


def get_steam_path() -> str:
    if os.name == "nt":  # windows
        import winreg  # type: ignore

        key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            "SOFTWARE\\WOW6432Node\\Valve\\Steam",
            0,
            winreg.KEY_READ,
        )
        value, regtype = winreg.QueryValueEx(key, "InstallPath")
        winreg.CloseKey(key)
        return value
    else:
        return "~/.steam/root"


def get_csgo_path(steamapps_folder):
    # Get every SteamLibrary folder
    with open(os.path.join(steamapps_folder, "libraryfolders.vdf")) as infile:
        libraryfolders = steamfiles.load(infile)
    folders = [steamapps_folder]
    i = 1
    while True:
        try:
            steamapps = os.path.join(
                libraryfolders["LibraryFolders"][str(i)], "steamapps"
            )
            print(f"Found steamapps folder {steamapps}")
            folders.append(steamapps)
        except KeyError:
            break
        i = i + 1

    # Find the one CS:GO is in
    for folder in folders:
        try:
            appmanifest = os.path.join(folder, "appmanifest_730.acf")
            print(f"Opening appmanifest {appmanifest}...")
            with open(appmanifest) as infile:
                appmanifest = steamfiles.load(infile)
                installdir = os.path.join(
                    folder, "common", appmanifest["AppState"]["installdir"]
                )
            print(f"Valid installdir found: {installdir}")
            return installdir
        except FileNotFoundError:
            continue

    print("CS:GO not found :/")


def main():
    # Ensure gamestate integration cfg is in csgo's cfg directory
    # TODO linux
    csgo_dir = get_csgo_path(get_steam_path() + "\\steamapps")
    if csgo_dir is not None:
        copyfile(
            "gamestate_integration_ccs.cfg",
            os.path.join(csgo_dir, "csgo", "cfg", "gamestate_integration_ccs.cfg"),
        )

    oalInit()
    loop = asyncio.get_event_loop()
    app = WxAsyncApp()
    gui.MainFrame(
        None,
        title="CSGO Custom Sounds",
        size=wx.Size(320, 230),
        style=wx.DEFAULT_FRAME_STYLE & ~(wx.RESIZE_BORDER | wx.MAXIMIZE_BOX),
    )
    loop.run_until_complete(app.MainLoop())

    # Freeing OpenAL buffers might fail if they are still in use
    # We don't really care since the OS will clean up anyway.
    try:
        oalQuit()
    except:  # noqa
        pass


if __name__ == "__main__":
    main()
