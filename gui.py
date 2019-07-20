import subprocess
import threading
import wx
import wx.adv

import client
import config
from packets_pb2 import GameEvent, PlaySound


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

        # Client needs self.shardCodeIpt
        friends_zone = self.make_friends_zone()

        # Start threads
        self.CreateStatusBar()
        self.SetStatusText("Loading sounds...")
        self.client = client.Client(self)

        vbox = wx.BoxSizer(wx.VERTICAL)
        vbox.AddStretchSpacer()
        vbox.Add(friends_zone, border=5, flag=wx.ALIGN_CENTER_HORIZONTAL | wx.ALL)
        vbox.Add(self.make_volume_zone(), border=5, flag=wx.ALIGN_CENTER_HORIZONTAL | wx.ALL)
        vbox.Add(self.make_settings_zone(), border=5, flag=wx.ALIGN_CENTER_HORIZONTAL | wx.ALL)
        vbox.AddStretchSpacer()
        self.panel.SetSizer(vbox)
        self.panel.Layout()
        self.UpdateSounds(None)

        self.taskbarIcon = TaskbarIcon(self)
        self.Bind(wx.EVT_ICONIZE, self.OnMinimize)
        self.Bind(wx.EVT_SHOW, self.OnUnMinimize)
        self.Bind(wx.EVT_CLOSE, self.OnClose)
        self.Centre()
        self.Show()
    
    def make_volume_zone(self):
        with self.client.sounds.cache_lock:
            self.volumeSlider = wx.Slider(self.panel, value=self.client.sounds.volume, size=(272, 25))
        self.Bind(wx.EVT_COMMAND_SCROLL_CHANGED, self.OnVolumeSlider, self.volumeSlider)

        volumeZone = wx.StaticBoxSizer(wx.VERTICAL, self.panel, label="Volume")
        volumeZone.Add(self.volumeSlider)
        return volumeZone

    def make_friends_zone(self):
        self.shardCodeBtn = wx.Button(self.panel, label="Join room")
        self.Bind(wx.EVT_BUTTON, self.JoinOrLeaveRoom, self.shardCodeBtn)
        with config.lock:
            self.shardCodeIpt = wx.TextCtrl(self.panel, value=config.config['Sounds'].get('Room', ''), size=(164, self.shardCodeBtn.GetMinSize().GetHeight()))
        self.shardCodeIpt.SetFocus()
        shardCodeExplanationTxt = wx.StaticText(self.panel, label="In order to hear your teammates' sounds, you\nneed to join the same room.")

        friendsZone = wx.StaticBoxSizer(wx.VERTICAL, self.panel, label="Room")
        friendsZone.Add(shardCodeExplanationTxt, border=5, flag=wx.LEFT | wx.DOWN)
        friendsInputZone = wx.BoxSizer(wx.HORIZONTAL)
        friendsInputZone.Add(self.shardCodeIpt, border=5, flag=wx.ALIGN_CENTER_VERTICAL | wx.ALL)
        friendsInputZone.Add(self.shardCodeBtn, border=5, flag=wx.ALIGN_CENTER_VERTICAL | wx.ALL)
        friendsZone.Add(friendsInputZone)

        return friendsZone
    
    def make_settings_zone(self):
        self.preferHeadshotsChk = wx.CheckBox(self.panel, label="Prefer headshot sounds over killstreak sounds")

        openSoundDirBtn = wx.Button(self.panel, label="Open sounds directory")
        self.updateSoundsBtn = wx.Button(self.panel, label="Update sounds")
        self.Bind(wx.EVT_BUTTON, self.OpenSoundsDir, openSoundDirBtn)
        self.Bind(wx.EVT_BUTTON, self.UpdateSounds, self.updateSoundsBtn)

        soundBtns = wx.BoxSizer(wx.HORIZONTAL)
        soundBtns.Add(openSoundDirBtn)
        soundBtns.Add(self.updateSoundsBtn)

        settingsBox = wx.StaticBoxSizer(wx.VERTICAL, self.panel, label="Settings")
        settingsBox.Add(self.preferHeadshotsChk, border=5, flag=wx.ALL)
        settingsBox.Add(soundBtns, border=5, flag=wx.ALIGN_CENTER | wx.UP | wx.DOWN)

        with config.lock:
            preferHeadshots = config.config['Sounds'].getboolean('PreferHeadshots', False)
        self.preferHeadshotsChk.SetValue(preferHeadshots)
        self.Bind(wx.EVT_CHECKBOX, lambda e: config.set('Sounds', 'PreferHeadshots', self.preferHeadshotsChk.Value), self.preferHeadshotsChk)

        return settingsBox

    def SetStatusText(self, text):
        """Override default SetStatusText to avoid minimizing CS:GO"""
        if self.IsIconized():
            return
        super().SetStatusText(text)

    def OnUnMinimize(self, event):
        threading.Thread(target=self.client.update_status, daemon=True).start()

    def OnVolumeSlider(self, event):
        config.set('Sounds', 'Volume', self.volumeSlider.Value)
        with self.client.sounds.cache_lock:
            # Volume didn't change
            if self.client.sounds.volume == self.volumeSlider.Value:
                return
            self.client.sounds.volume = self.volumeSlider.Value
            playpacket = PlaySound()
            playpacket.steamid = 0
            playpacket.sound_hash = self.client.sounds.get_random(GameEvent.HEADSHOT, None)
        self.client.sounds.play(playpacket)

    def OpenSoundsDir(self, event):
        # TODO linux
        subprocess.Popen('explorer "sounds"')
    
    def JoinOrLeaveRoom(self, event):
        # Don't join without a room name
        if self.shardCodeIpt.GetValue() == '':
            return

        if self.client.room_name is None:
            self.client.room_name = self.shardCodeIpt.GetValue()
            config.set('Sounds', 'Room', self.shardCodeIpt.GetValue())
            threading.Thread(target=self.client.client_update, daemon=True).start()
            self.shardCodeIpt.Disable()
            self.shardCodeBtn.SetLabel('Leave room')
        else:
            self.client.room_name = None
            self.shardCodeIpt.Enable()
            self.shardCodeBtn.SetLabel('Join room')
    
    def UpdateSounds(self, event):
        self.updateSoundsBtn.Disable()
        threading.Thread(target=self.client.reload_sounds, daemon=True).start()

    def OnMinimize(self, event):
        if self.IsIconized():
            self.Hide()
    
    def OnClose(self, event):
        self.taskbarIcon.Destroy()
        self.Destroy()
