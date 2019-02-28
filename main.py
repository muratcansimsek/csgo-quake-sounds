"""Plays quake sounds according to CSGO Gamestate"""
import os
from steamfiles import acf
import subprocess
import sys
import threading
import winreg
import wx
from shutil import copyfile

import time

# Local files
import gui
from sounds import sounds

# Get steam path from windows registry - TODO linux
def get_steam_path():
	key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, "SOFTWARE\\WOW6432Node\\Valve\\Steam", 0, winreg.KEY_READ)
	value, regtype = winreg.QueryValueEx(key, "InstallPath")
	winreg.CloseKey(key)
	return value

# TODO linux
def get_csgo_path(steamapps_folder):
	appmanifest = steamapps_folder + "\\appmanifest_730.acf"
	with open(appmanifest, "r") as f:
		data = acf.load(f)
	return steamapps_folder + "\\common\\" + data["AppState"]["installdir"]


if __name__ == "__main__":
	# Ensure gamestate integration cfg is in csgo's cfg directory
	# TODO in case of different install path, scan libraryfolders.vdf directories
	# TODO linux
	csgo_dir = get_csgo_path(get_steam_path() + "\\steamapps")
	copyfile("gamestate_integration_ccs.cfg", csgo_dir + "\\csgo\\cfg\\gamestate_integration_ccs.cfg")

	app = wx.App()
	frame = gui.MainFrame(None, title="CSGO Custom Sounds", size=wx.Size(550, 370), style=wx.DEFAULT_FRAME_STYLE & ~(wx.RESIZE_BORDER | wx.MAXIMIZE_BOX))
	app.MainLoop()
