"""Plays quake sounds according to CSGO Gamestate"""
import asyncio
import winreg  # type: ignore
import wx  # type: ignore  # type: ignore
from openal import oalInit, oalQuit  # type: ignore
from shutil import copyfile
from steamfiles import acf  # type: ignore
from wxasync import WxAsyncApp

# Local files
import gui

# Get steam path from windows registry - TODO linux
def get_steam_path():
	key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, "SOFTWARE\\WOW6432Node\\Valve\\Steam", 0, winreg.KEY_READ)
	value, regtype = winreg.QueryValueEx(key, "InstallPath")
	winreg.CloseKey(key)
	return value

# TODO linux
def get_csgo_path(steamapps_folder):
	# Get every SteamLibrary folder
	with open(steamapps_folder + '\\libraryfolders.vdf') as infile:
		libraryfolders = acf.load(infile)
	folders = [steamapps_folder]
	i = 1
	while True:
		try:
			print('Found steamapps folder %s' % (libraryfolders['LibraryFolders'][str(i)] + '\\steamapps'))
			folders.append(libraryfolders['LibraryFolders'][str(i)] + '\\steamapps')
		except KeyError:
			break
		i = i + 1

	# Find the one CS:GO is in
	for folder in folders:
		try:
			print('Opening appmanifest %s...' % (folder + '\\appmanifest_730.acf'))
			with open(folder + '\\appmanifest_730.acf') as infile:
				appmanifest = acf.load(infile)
			print('Valid installdir found: %s' % (folder + "\\common\\" + appmanifest["AppState"]["installdir"]))
			return folder + "\\common\\" + appmanifest["AppState"]["installdir"]
		except FileNotFoundError:
			continue

	print('CS:GO not found :/')

def main():
	# Ensure gamestate integration cfg is in csgo's cfg directory
	# TODO linux
	csgo_dir = get_csgo_path(get_steam_path() + "\\steamapps")
	if csgo_dir is not None:
		copyfile("gamestate_integration_ccs.cfg", csgo_dir + "\\csgo\\cfg\\gamestate_integration_ccs.cfg")

	oalInit()
	loop = asyncio.get_event_loop()
	app = WxAsyncApp()
	gui.MainFrame(None, title="CSGO Custom Sounds", size=wx.Size(320, 340), style=wx.DEFAULT_FRAME_STYLE & ~(wx.RESIZE_BORDER | wx.MAXIMIZE_BOX))
	loop.run_until_complete(app.MainLoop())

	# Devices might not always be ready to get closed - but OS will clean up anyway,
	# so we can leave this line commented out
	oalQuit()

if __name__ == "__main__":
	main()
