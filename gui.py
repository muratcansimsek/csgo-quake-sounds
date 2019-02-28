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

        thbox = wx.BoxSizer(wx.HORIZONTAL)
        thbox.Add(self.make_friends_zone(), border=230, flag=wx.ALIGN_RIGHT | wx.LEFT)

        hbox = wx.BoxSizer(wx.HORIZONTAL)
        hbox.AddStretchSpacer()
        hbox.Add(self.make_settings_zone(), border=10, flag=wx.ALIGN_LEFT | wx.ALL)
        hbox.Add(self.make_account_zone(), border=10, flag=wx.ALIGN_RIGHT | wx.ALL)
        hbox.AddStretchSpacer()

        vbox = wx.BoxSizer(wx.VERTICAL)
        vbox.AddStretchSpacer()
        vbox.Add(thbox, flag=wx.ALIGN_CENTER_HORIZONTAL)
        vbox.Add(hbox, flag=wx.ALIGN_CENTER_HORIZONTAL)
        vbox.AddStretchSpacer()
        self.panel.SetSizer(vbox)
        self.panel.Layout()

        self.CreateStatusBar()
        self.SetStatusText("Loading sounds...")

        # Start threads
        self.UpdateSounds(None)
        sound_client_thread = threading.Thread(target=sounds.listen, daemon=True)
        sound_client_thread.start()
        threads.start()

        self.taskbarIcon = TaskbarIcon(self)
        self.Bind(wx.EVT_ICONIZE, self.OnMinimize)
        self.Bind(wx.EVT_CLOSE, self.OnClose)
        self.Centre()
        self.Show()
    
    def make_account_zone(self):
        addAccountBtn = wx.Button(self.panel, label="Add...")
        self.Bind(wx.EVT_BUTTON, self.AddAccount, addAccountBtn)
        self.removeAccountBtn = wx.Button(self.panel, label="Remove")
        self.removeAccountBtn.Disable()
        self.Bind(wx.EVT_BUTTON, self.RemoveAccount, self.removeAccountBtn)
        accountsBtns = wx.BoxSizer(wx.HORIZONTAL)
        accountsBtns.Add(addAccountBtn)
        accountsBtns.Add(self.removeAccountBtn)
        
        accountList = wx.ListBox(self.panel, size=wx.Size(accountsBtns.GetMinSize().GetWidth(), 107), style=wx.LB_SINGLE | wx.LB_SORT)
        self.Bind(wx.EVT_LISTBOX, self.SelectAccount, accountList)
        accountsBox = wx.StaticBoxSizer(wx.VERTICAL, self.panel, "Linked accounts")
        accountsBox.Add(accountList, border=5, flag=wx.LEFT | wx.RIGHT)
        accountsBox.Add(accountsBtns, border=5, flag=wx.ALL)
        
        # TODO
        addAccountBtn.Disable()
        accountList.Disable()

        return accountsBox
    
    def make_friends_zone(self):
        shardCodeBtn = wx.Button(self.panel, label="Set code")
        shardCodeIpt = wx.TextCtrl(self.panel, value=config.SHARD_CODE, size=(150, shardCodeBtn.GetMinSize().GetHeight()))
        shardCodeExplanationTxt = wx.StaticText(self.panel, label="To make sure you are in the same server as your\nfriends, use the same friends code.")

        friendsZone = wx.StaticBoxSizer(wx.VERTICAL, self.panel, label="Friends code")
        friendsZone.Add(shardCodeExplanationTxt, border=5, flag=wx.LEFT | wx.DOWN)
        friendsInputZone = wx.BoxSizer(wx.HORIZONTAL)
        friendsInputZone.Add(shardCodeIpt, border=5, flag=wx.ALIGN_CENTER_VERTICAL | wx.ALL)
        friendsInputZone.Add(shardCodeBtn, border=5, flag=wx.ALIGN_CENTER_VERTICAL | wx.ALL)
        friendsZone.Add(friendsInputZone)

        # TODO
        shardCodeBtn.Disable()

        return friendsZone
    
    def make_settings_zone(self):
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
        self.updateSoundsBtn = wx.Button(self.panel, label="Update sounds")
        self.Bind(wx.EVT_BUTTON, self.UpdateSounds, self.updateSoundsBtn)

        soundBtns = wx.BoxSizer(wx.HORIZONTAL)
        soundBtns.Add(openSoundDirBtn)
        soundBtns.Add(self.updateSoundsBtn)

        settingsBox = wx.StaticBoxSizer(wx.VERTICAL, self.panel, label="Settings")
        settingsBox.Add(preferHeadshotsChk, border=5, flag=wx.ALL)
        settingsBox.Add(whenAliveTxt, border=5, flag=wx.ALL)
        settingsBox.Add(downloadWhenAliveChk, border=15, flag=wx.LEFT)
        settingsBox.Add(uploadWhenAliveChk, border=15, flag=wx.LEFT)
        settingsBox.Add(whenAliveWarningTxt, border=5, flag=wx.ALL)
        settingsBox.Add(soundBtns, border=5, flag=wx.ALIGN_CENTER | wx.UP | wx.DOWN)

        # TODO
        preferHeadshotsChk.Disable()
        downloadWhenAliveChk.Disable()
        uploadWhenAliveChk.Disable()

        return settingsBox

    def OpenSoundsDir(self, event):
        # TODO linux
        subprocess.Popen('explorer "sounds"')
    
    def UpdateSounds(self, event):
        self.updateSoundsBtn.Disable()
        SampleLoaderThread(self).start()

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
        wx.CallAfter(self.gui.updateSoundsBtn.Enable)
        wx.CallAfter(self.gui.SetStatusText, 'Waiting for CS:GO...')
