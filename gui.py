import subprocess
import threading
import wx
import wx.adv

import client
import config
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

        vbox = wx.BoxSizer(wx.VERTICAL)
        vbox.AddStretchSpacer()
        vbox.Add(self.make_friends_zone(), border=5, flag=wx.ALIGN_CENTER_HORIZONTAL | wx.ALL)
        vbox.Add(self.make_settings_zone(), border=5, flag=wx.ALIGN_CENTER_HORIZONTAL | wx.ALL)
        vbox.AddStretchSpacer()
        self.panel.SetSizer(vbox)
        self.panel.Layout()

        self.CreateStatusBar()
        self.SetStatusText("Loading sounds...")

        # Start threads
        self.client = client.Client()
        self.client.init(self)
        self.UpdateSounds(None)

        self.taskbarIcon = TaskbarIcon(self)
        self.Bind(wx.EVT_ICONIZE, self.OnMinimize)
        self.Bind(wx.EVT_CLOSE, self.OnClose)
        self.Centre()
        self.Show()
    
    def make_friends_zone(self):
        shardCodeBtn = wx.Button(self.panel, label="Set code")
        shardCodeIpt = wx.TextCtrl(self.panel, value=config.SHARD_CODE, size=(164, shardCodeBtn.GetMinSize().GetHeight()))
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
        threading.Thread(target=self.client.reload_sounds, daemon=True).start()

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
