import subprocess
import threading
import wx
import wx.adv

import config
import threads
from sounds import sounds

class TaskbarIcon(wx.adv.TaskBarIcon):
    def __init__(self, frame):
        super().__init__()
        self.frame = frame
        self.SetIcon(wx.Icon("icon.ico"))
        self.Bind(wx.adv.EVT_TASKBAR_LEFT_DOWN, self.OnLeftClick)
    
    def OnLeftClick(self, evt):
        self.frame.Show()
        self.frame.Restore()


class MainFrame(wx.Frame):
    def __init__(self, *args, **kw):
        super().__init__(*args, **kw)
        self.panel = wx.Panel(self)
        self.SetIcon(wx.Icon("icon.ico"))

        # TODO checkbox events
        preferHeadshotsChk = wx.CheckBox(self.panel, label="Prefer headshot sounds over killstreak sounds")
        preferHeadshotsChk.SetValue(config.HEADSHOTS_OVERRIDE)
        whenAliveTxt = wx.StaticText(self.panel, label="When alive:")
        downloadWhenAliveChk = wx.CheckBox(self.panel, label="Download custom sounds")
        downloadWhenAliveChk.SetValue(config.DOWNLOAD_WHEN_ALIVE)
        uploadWhenAliveChk = wx.CheckBox(self.panel, label="Upload custom sounds")
        uploadWhenAliveChk.SetValue(config.UPLOAD_WHEN_ALIVE)
        whenAliveWarningTxt = wx.StaticText(self.panel, label="(can impact gameplay on slow connections)")
        openSoundDirBtn = wx.Button(self.panel, label="Open sounds directory")
        self.Bind(wx.EVT_BUTTON, self.OpenSoundsDir, openSoundDirBtn)

        settingsBox = wx.StaticBoxSizer(wx.VERTICAL, self.panel, label="Settings")
        settingsBox.Add(preferHeadshotsChk, border=5, flag=wx.LEFT | wx.DOWN)
        settingsBox.Add(whenAliveTxt, border=5, flag=wx.ALL)
        settingsBox.Add(downloadWhenAliveChk, border=10, flag=wx.LEFT)
        settingsBox.Add(uploadWhenAliveChk, border=10, flag=wx.LEFT)
        settingsBox.Add(whenAliveWarningTxt, border=5, flag=wx.ALL)
        settingsBox.Add(openSoundDirBtn, border=5, flag=wx.ALIGN_CENTER | wx.UP | wx.DOWN)


        addAccountBtn = wx.Button(self.panel, label="Add...")
        self.Bind(wx.EVT_BUTTON, self.AddAccount, addAccountBtn)
        self.removeAccountBtn = wx.Button(self.panel, label="Remove")
        self.removeAccountBtn.Disable()
        self.Bind(wx.EVT_BUTTON, self.RemoveAccount, self.removeAccountBtn)
        accountsBtns = wx.BoxSizer(wx.HORIZONTAL)
        accountsBtns.Add(addAccountBtn)
        accountsBtns.Add(self.removeAccountBtn)
        
        accountList = wx.ListBox(self.panel, size=wx.Size(accountsBtns.GetMinSize().GetWidth(), 102), style=wx.LB_SINGLE | wx.LB_SORT)
        self.Bind(wx.EVT_LISTBOX, self.SelectAccount, accountList)
        accountsBox = wx.StaticBoxSizer(wx.VERTICAL, self.panel, "Linked accounts")
        accountsBox.Add(accountList, border=5, flag=wx.LEFT | wx.RIGHT)
        accountsBox.Add(accountsBtns, border=5, flag=wx.ALL)


        hbox = wx.BoxSizer(wx.HORIZONTAL)
        hbox.AddStretchSpacer()
        hbox.Add(settingsBox, flag=wx.ALIGN_CENTER_VERTICAL)
        hbox.AddStretchSpacer()
        hbox.Add(accountsBox, flag=wx.ALIGN_CENTER_VERTICAL)
        hbox.AddStretchSpacer()
        self.panel.SetSizer(hbox)
        self.panel.Layout()


        self.CreateStatusBar()
        self.SetStatusText("Loading sounds...")

        # Not handled right now, so disabled - TODO
        addAccountBtn.Disable()
        accountList.Disable()

        SampleLoaderThread(self).start()

        openSoundDirBtn.SetFocus()
        self.taskbarIcon = TaskbarIcon(self)
        self.Bind(wx.EVT_ICONIZE, self.OnMinimize)
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

    def OnMinimize(self, event):
        if self.IsIconized():
            self.Hide()
    
    def OnClose(self, event):
        self.taskbarIcon.RemoveIcon()
        self.taskbarIcon.Destroy()
        self.Destroy()

class SampleLoaderThread(threading.Thread):
    def __init__(self, gui):
        threading.Thread.__init__(self, daemon=True)
        self.gui = gui

    def update_status(self):
        wx.CallAfter(self.gui.SetStatusText, 'Loading sounds... (%d/%d)' % (self.nb_sounds, self.max_sounds))
        self.nb_sounds = self.nb_sounds + 1
    
    def set_status(self, msg):
        wx.CallAfter(self.gui.SetStatusText, msg)
    
    def run(self):
        self.nb_sounds = 0
        self.max_sounds = len(sounds.sound_list('sounds'))
        self.update_status()
        sounds.load(self)
        wx.CallAfter(self.gui.SetStatusText, 'Waiting for CS:GO...')
        
        # Local sound client
        sound_client_thread = threading.Thread(target=sounds.listen, daemon=True)
        sound_client_thread.start()

        # Start the rest of the client/server threads
        threads.start()
