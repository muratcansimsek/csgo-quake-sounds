import subprocess
import threading
import wx

import threads
from sounds import sounds

class MainFrame(wx.Frame):
	def __init__(self, *args, **kw):
		super(MainFrame, self).__init__(*args, **kw)
		self.panel = wx.Panel(self)
		self.SetIcon(wx.Icon("icon.ico"))


		openSoundDirBtn = wx.Button(self.panel, label="Open sounds directory")
		self.Bind(wx.EVT_BUTTON, self.OpenSoundsDir, openSoundDirBtn)


		addAccountBtn = wx.Button(self.panel, label="Add...")
		self.Bind(wx.EVT_BUTTON, self.AddAccount, addAccountBtn)
		self.removeAccountBtn = wx.Button(self.panel, label="Remove")
		self.removeAccountBtn.Disable()
		self.Bind(wx.EVT_BUTTON, self.RemoveAccount, self.removeAccountBtn)
		accountsBtns = wx.BoxSizer(wx.HORIZONTAL)
		accountsBtns.Add(addAccountBtn)
		accountsBtns.Add(self.removeAccountBtn)
		
		accountList = wx.ListBox(self.panel, size=wx.Size(accountsBtns.GetMinSize().GetWidth(), 130), style=wx.LB_SINGLE | wx.LB_SORT)
		self.Bind(wx.EVT_LISTBOX, self.SelectAccount, accountList)
		accountsBox = wx.StaticBoxSizer(wx.VERTICAL, self.panel, "Linked accounts")
		accountsBox.Add(accountList, border=5, flag=wx.LEFT | wx.RIGHT)
		accountsBox.Add(accountsBtns, border=5, flag=wx.ALL)


		hbox = wx.BoxSizer(wx.HORIZONTAL)
		hbox.AddStretchSpacer()
		hbox.Add(openSoundDirBtn, border=50, flag=wx.ALIGN_CENTER | wx.RIGHT)
		hbox.Add(accountsBox, flag=wx.ALIGN_CENTER)
		hbox.AddStretchSpacer()
		self.panel.SetSizer(hbox)
		self.panel.Layout()


		self.CreateStatusBar()
		self.SetStatusText("Loading sounds...")

		# Not handled right now, so disabled - TODO
		addAccountBtn.Disable()
		accountList.Disable()

		SampleLoaderThread(self).start()

		self.Bind(wx.EVT_CLOSE, self.OnClose)
		self.Centre()
		self.Show()
	
	def OpenSoundsDir(self, event):
		# TODO linux
		subprocess.Popen('explorer "sounds"')

	def SelectAccount(self, event):
		# TODO handle deselect
		self.removeAccountBtn.Enable()
	
	def AddAccount(self, event):
		# TODO open auth page
		pass

	def RemoveAccount(self, event):
		# TODO remove acc
		# TODO disable button if no accounts left
		pass
	
	def OnClose(self, event):
		self.Destroy()

class SampleLoaderThread(threading.Thread):
    def __init__(self, gui):
        threading.Thread.__init__(self, daemon=True)
        self.gui = gui

    def update_status(self):
        wx.CallAfter(self.gui.SetStatusText, 'Loading sounds... (%d/%d)' % (self.nb_sounds, self.max_sounds))
        self.nb_sounds = self.nb_sounds + 1
    
    def run(self):
        self.nb_sounds = 0
        self.max_sounds = len(sounds.sound_list('sounds'))
        self.update_status()
        sounds.load(self)
        wx.CallAfter(self.gui.SetStatusText, '%d sounds loaded.' % self.max_sounds)
        
        # Local sound client
        sound_client_thread = threading.Thread(target=sounds.listen, daemon=True)
        sound_client_thread.start()

        # Start the rest of the client/server threads
        threads.start()
