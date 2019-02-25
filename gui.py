import wx

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
