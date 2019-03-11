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
        vbox.Add(self.make_volume_zone(), border=5, flag=wx.ALIGN_CENTER_HORIZONTAL | wx.ALL)
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
    
    def make_volume_zone(self):
        with config.lock:
            self.volumeSlider = wx.Slider(self.panel, value=config.config['Sounds'].getint('Volume', 50), size=(272, 25))
        self.Bind(wx.EVT_SLIDER, lambda e: config.set('Sounds', 'Volume', self.volumeSlider.Value), self.volumeSlider)

        volumeZone = wx.StaticBoxSizer(wx.VERTICAL, self.panel, label="Volume")
        volumeZone.Add(self.volumeSlider)
        return volumeZone
    
    # TODO
    # It isn't very clear that this is REQUIRED for sounds to work
    # Also, "Friends code" doesn't look important when you play solo
    def make_friends_zone(self):
        shardCodeBtn = wx.Button(self.panel, label="Join room")
        self.Bind(wx.EVT_BUTTON, self.UpdateShardCode, shardCodeBtn)
        with config.lock:
            self.shardCodeIpt = wx.TextCtrl(self.panel, value=config.config['Sounds'].get('Room', ''), size=(164, shardCodeBtn.GetMinSize().GetHeight()))
        shardCodeExplanationTxt = wx.StaticText(self.panel, label="To make sure you are in the same server as your\nfriends, join the same room.")

        friendsZone = wx.StaticBoxSizer(wx.VERTICAL, self.panel, label="Room")
        friendsZone.Add(shardCodeExplanationTxt, border=5, flag=wx.LEFT | wx.DOWN)
        friendsInputZone = wx.BoxSizer(wx.HORIZONTAL)
        friendsInputZone.Add(self.shardCodeIpt, border=5, flag=wx.ALIGN_CENTER_VERTICAL | wx.ALL)
        friendsInputZone.Add(shardCodeBtn, border=5, flag=wx.ALIGN_CENTER_VERTICAL | wx.ALL)
        friendsZone.Add(friendsInputZone)

        return friendsZone
    
    def make_settings_zone(self):
        self.preferHeadshotsChk = wx.CheckBox(self.panel, label="Prefer headshot sounds over killstreak sounds")
        self.downloadWhenAliveChk = wx.CheckBox(self.panel, label="Download custom sounds")
        self.uploadWhenAliveChk = wx.CheckBox(self.panel, label="Upload custom sounds")

        whenAliveTxt = wx.StaticText(self.panel, label="When alive:")
        whenAliveWarningTxt = wx.StaticText(self.panel, label="(can impact gameplay on slow connections)")

        openSoundDirBtn = wx.Button(self.panel, label="Open sounds directory")
        self.updateSoundsBtn = wx.Button(self.panel, label="Update sounds")
        self.Bind(wx.EVT_BUTTON, self.OpenSoundsDir, openSoundDirBtn)
        self.Bind(wx.EVT_BUTTON, self.UpdateSounds, self.updateSoundsBtn)

        soundBtns = wx.BoxSizer(wx.HORIZONTAL)
        soundBtns.Add(openSoundDirBtn)
        soundBtns.Add(self.updateSoundsBtn)

        settingsBox = wx.StaticBoxSizer(wx.VERTICAL, self.panel, label="Settings")
        settingsBox.Add(self.preferHeadshotsChk, border=5, flag=wx.ALL)
        settingsBox.Add(whenAliveTxt, border=5, flag=wx.ALL)
        settingsBox.Add(self.downloadWhenAliveChk, border=15, flag=wx.LEFT)
        settingsBox.Add(self.uploadWhenAliveChk, border=15, flag=wx.LEFT)
        settingsBox.Add(whenAliveWarningTxt, border=5, flag=wx.ALL)
        settingsBox.Add(soundBtns, border=5, flag=wx.ALIGN_CENTER | wx.UP | wx.DOWN)

        with config.lock:
            preferHeadshots = config.config['Sounds'].getboolean('PreferHeadshots', False)
            downloadWhenAlive = config.config['Network'].getboolean('DownloadWhenAlive', False)
            uploadWhenAlive = config.config['Network'].getboolean('UploadWhenAlive', False)
        self.preferHeadshotsChk.SetValue(preferHeadshots)
        self.downloadWhenAliveChk.SetValue(downloadWhenAlive)
        self.uploadWhenAliveChk.SetValue(uploadWhenAlive)
        self.Bind(wx.EVT_CHECKBOX, lambda e: config.set('Sounds', 'PreferHeadshots', self.preferHeadshotsChk.Value), self.preferHeadshotsChk)
        self.Bind(wx.EVT_CHECKBOX, lambda e: config.set('Network', 'DownloadWhenAlive', self.downloadWhenAliveChk.Value), self.downloadWhenAliveChk)
        self.Bind(wx.EVT_CHECKBOX, lambda e: config.set('Network', 'UploadWhenAlive', self.uploadWhenAliveChk.Value), self.uploadWhenAliveChk)

        return settingsBox

    def OpenSoundsDir(self, event):
        # TODO linux
        subprocess.Popen('explorer "sounds"')
    
    def UpdateShardCode(self, event):
        self.client.shard_code = self.shardCodeIpt.GetValue()
        config.set('Sounds', 'Room', self.shardCodeIpt.GetValue())
        threading.Thread(target=self.client.client_update, daemon=True).start()
    
    def UpdateSounds(self, event):
        self.updateSoundsBtn.Disable()
        threading.Thread(target=self.client.reload_sounds, daemon=True).start()

    def OnMinimize(self, event):
        if self.IsIconized():
            self.Hide()
    
    def OnClose(self, event):
        self.taskbarIcon.Destroy()
        self.Destroy()
