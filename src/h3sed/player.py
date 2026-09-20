# -*- coding: utf-8 -*-
"""
Player plugin for savefile page, shows and edits player resources like gold.

Savefile does not record which player slot the human plays, so the player is
identified by the amount of gold the user sees in game.

------------------------------------------------------------------------------
This file is part of h3sed - Heroes3 Savegame Editor.
Released under the MIT License.

@created   20.09.2026
@modified  20.09.2026
------------------------------------------------------------------------------
"""
import logging

import wx

import h3sed
from . lib.controls import ColourManager
from . lib.i18n import translate as __
from . import metadata

logger = logging.getLogger(__name__)


class PlayerPlugin(object):
    """Provides UI functionality for viewing and changing player resources."""


    def __init__(self, savefile, panel, commandprocessor):
        self.name       = "player"
        self.savefile   = savefile
        self._panel     = panel  # wxPanel container for plugin components
        self._undoredo  = commandprocessor  # wx.CommandProcessor
        self._index     = None   # 0-based index of identified player, if any
        self._matches   = []     # Player indexes matching the gold amount given
        self._ctrls     = {}     # {name: wx.Control}
        self._original  = {}     # {resource name: value} as loaded or last saved
        self._ignore_events = False
        self.prebuild()


    def prebuild(self):
        """Builds UI components: player identification prompt and resource fields."""
        self._panel.Freeze()
        self._panel.DestroyChildren()
        self._panel.Sizer and self._panel.Sizer.Clear()
        self._ctrls.clear()
        sizer = self._panel.Sizer = wx.BoxSizer(wx.VERTICAL)

        if self.savefile.find_players() is None:
            sizer.Add(wx.StaticText(self._panel, label=
                      __("Player resources were not recognized in this savegame.")),
                      border=10, flag=wx.ALL)
            self._panel.Layout(), self._panel.Thaw()
            return

        askpanel = self._askpanel = wx.Panel(self._panel)
        asksizer = askpanel.Sizer = wx.BoxSizer(wx.VERTICAL)
        intro = wx.StaticText(askpanel, label=
            __("Savegame does not record which player you are.") + "\n" +
            __("Enter the amount of gold your player has in game:"))
        edit = self._ctrls["goldsearch"] = wx.TextCtrl(askpanel, size=(120, -1),
                                                       style=wx.TE_PROCESS_ENTER)
        button = wx.Button(askpanel, label=__("&Find player"))
        edit.Bind(wx.EVT_TEXT_ENTER, self.on_identify)
        button.Bind(wx.EVT_BUTTON,   self.on_identify)
        rowsizer = wx.BoxSizer(wx.HORIZONTAL)
        rowsizer.Add(edit, border=5, flag=wx.RIGHT)
        rowsizer.Add(button)

        status = self._ctrls["status"] = wx.StaticText(askpanel)

        # Shown only when several players hold the same amount of gold
        pickpanel = self._ctrls["pickpanel"] = wx.Panel(askpanel)
        picksizer = pickpanel.Sizer = wx.BoxSizer(wx.HORIZONTAL)
        picklabel = wx.StaticText(pickpanel, label=__("Choose your colour") + ":")
        choice = self._ctrls["pick"] = wx.Choice(pickpanel)
        pickbutton = wx.Button(pickpanel, label=__("&Use this player"))
        pickbutton.Bind(wx.EVT_BUTTON, self.on_pick_player)
        picksizer.Add(picklabel, border=5, flag=wx.RIGHT | wx.ALIGN_CENTER_VERTICAL)
        picksizer.Add(choice,    border=5, flag=wx.RIGHT)
        picksizer.Add(pickbutton)

        asksizer.Add(intro,     border=10, flag=wx.LEFT | wx.TOP | wx.RIGHT)
        asksizer.Add(rowsizer,  border=10, flag=wx.ALL)
        asksizer.Add(status,    border=10, flag=wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.GROW)
        asksizer.Add(pickpanel, border=10, flag=wx.LEFT | wx.RIGHT | wx.BOTTOM)
        pickpanel.Hide()

        editpanel = self._editpanel = wx.Panel(self._panel)
        editsizer = editpanel.Sizer = wx.BoxSizer(wx.VERTICAL)
        header = self._ctrls["header"] = wx.StaticText(editpanel)
        header.Font = header.Font.Bold()
        warning = self._ctrls["warning"] = wx.StaticText(editpanel)
        ColourManager.Manage(warning, "ForegroundColour", "LinkColour")
        change = wx.Button(editpanel, label=__("Change player") + " ..")
        change.ToolTip = __("Identify the player by gold amount again")
        change.Bind(wx.EVT_BUTTON, self.on_reidentify)
        headsizer = wx.BoxSizer(wx.HORIZONTAL)
        headsizer.Add(header, border=5, flag=wx.RIGHT | wx.ALIGN_CENTER_VERTICAL)
        headsizer.AddStretchSpacer()
        headsizer.Add(change)

        gridsizer = wx.FlexGridSizer(cols=2, vgap=5, hgap=10)
        for name, label in metadata.PLAYER_RESOURCES.items():
            maximum = metadata.PLAYER_GOLD_MAX if "gold" == name else metadata.PLAYER_RESOURCE_MAX
            ctrl = self._ctrls[name] = wx.SpinCtrl(editpanel, name=name, size=(120, -1),
                                                   style=wx.ALIGN_RIGHT, min=0, max=maximum)
            ctrl.ToolTip = __("Maximum %s", maximum)
            ctrl.Bind(wx.EVT_SPINCTRL, self.on_change_resource)
            gridsizer.Add(wx.StaticText(editpanel, label=__(label) + ":"),
                          flag=wx.ALIGN_CENTER_VERTICAL)
            gridsizer.Add(ctrl)

        note = wx.StaticText(editpanel, label=
            __("Changes are saved to file with the usual Save command."))
        ColourManager.Manage(note, "ForegroundColour", wx.SYS_COLOUR_GRAYTEXT)

        editsizer.Add(headsizer, border=10, flag=wx.ALL | wx.GROW)
        editsizer.Add(warning,   border=10, flag=wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.GROW)
        editsizer.Add(gridsizer, border=10, flag=wx.LEFT | wx.RIGHT | wx.BOTTOM)
        editsizer.Add(note,      border=10, flag=wx.LEFT | wx.RIGHT | wx.BOTTOM)

        sizer.Add(askpanel,  flag=wx.GROW)
        sizer.Add(editpanel, flag=wx.GROW)
        editpanel.Hide()
        self._panel.Layout()
        self._panel.Thaw()


    def render(self, reparse=False, reload=False, rebuild=False, log=True):
        """Populates resource controls from savefile."""
        if rebuild:
            index, matches = self._index, self._matches
            self.prebuild()
            self._index, self._matches = index, matches
        if reparse: self._original = {}  # Player slot stays valid, its values do not
        if not self._ctrls or self.savefile.find_players() is None: return

        if self._index is None:
            self._editpanel.Hide(), self._askpanel.Show()
            self._panel.Layout()
            return

        values = self.savefile.get_player_resources(self._index)
        if not self._original: self._original = dict(values)
        self._ignore_events = True
        try:
            self._ctrls["header"].Label = __("Player %s (%s)", self._index + 1,
                                             __(metadata.PLAYER_COLOURS[self._index]))
            self._ctrls["warning"].Label = "" if len(self._matches) < 2 else \
                __("Several players had this amount of gold: make sure this is you "
                   "before saving.")
            self._ctrls["warning"].Show(len(self._matches) > 1)
            for name, value in values.items():
                if self._ctrls[name].Value != value: self._ctrls[name].Value = value
            self._askpanel.Hide(), self._editpanel.Show()
            self._panel.Layout()
        finally:
            self._ignore_events = False


    def on_identify(self, event=None):
        """Handler for looking up the player by the gold amount given."""
        text = self._ctrls["goldsearch"].Value.strip().replace(" ", "").replace(",", "")
        status, pickpanel = self._ctrls["status"], self._ctrls["pickpanel"]
        pickpanel.Hide()
        if not text.isdigit():
            status.Label = __("Enter the gold amount as a plain number.")
            self._panel.Layout()
            return

        self._matches = self.savefile.find_player_by_gold(int(text))
        if not self._matches:
            status.Label = __("No player has %s gold in this savegame.", text) + "\n" + \
                           __("Note that the amount can be cut off in the game status bar: "
                              "check it on the town screen.")
            self._panel.Layout()
            return

        if len(self._matches) > 1:
            status.Label = __("%s players have %s gold.", len(self._matches), text) + "\n" + \
                           __("Pick your colour below, or spend some gold in game and save "
                              "again to tell them apart.")
            self._ctrls["pick"].SetItems(["%s. %s" % (i + 1, __(metadata.PLAYER_COLOURS[i]))
                                          for i in self._matches])
            self._ctrls["pick"].Selection = 0
            pickpanel.Show()
            self._panel.Layout()
            logger.info("Gold amount %s matches %s players in %s.", text,
                        len(self._matches), self.savefile.filename)
            return

        status.Label = ""
        self.select_player(self._matches[0])


    def on_pick_player(self, event=None):
        """Handler for choosing among players holding the same amount of gold."""
        selection = self._ctrls["pick"].Selection
        if selection < 0: return
        self._ctrls["status"].Label = ""
        self._ctrls["pickpanel"].Hide()
        self.select_player(self._matches[selection])


    def select_player(self, index):
        """Sets the player being edited, by 0-based index."""
        self._index, self._original = index, {}
        logger.info("Editing player %s (%s) resources in %s.", index + 1,
                    metadata.PLAYER_COLOURS[index], self.savefile.filename)
        self.render()


    def on_reidentify(self, event=None):
        """Handler for returning to the player identification prompt."""
        self._ctrls["status"].Label = ""
        self._ctrls["pickpanel"].Hide()
        self._index, self._matches = None, []
        self.render()


    def on_change_resource(self, event):
        """Handler for changing a resource value, submits an undoable command."""
        if self._ignore_events or self._index is None: return
        name, value = event.EventObject.Name, event.EventObject.Value
        if self.savefile.get_player_resources(self._index)[name] == value: return

        def on_do():
            self.savefile.set_player_resources(self._index, {name: value})
            self.render(reload=True)
            return True

        label = ("%s %s: %s", (__(metadata.PLAYER_COLOURS[self._index]),
                               __(metadata.PLAYER_RESOURCES[name]), value))
        self._undoredo.Submit(h3sed.gui.PluginCommand(self, on_do, name=label))


    def get_data(self):
        """Returns current resources of the player being edited, for undo-redo."""
        return None if self._index is None else \
               dict(self.savefile.get_player_resources(self._index))


    def set_data(self, data):
        """Restores resources of the player being edited, for undo-redo."""
        if self._index is not None and data: self.savefile.set_player_resources(self._index, data)


    def patch(self):
        """Notifies the savefile page that contents have changed."""
        wx.PostEvent(self._panel, h3sed.gui.SavefilePageEvent(self._panel.Id))


    def action(self, **kwargs):
        """Handler for action (save=True) from savefile page."""
        if kwargs.get("save"): self.mark_saved()


    def get_changes(self, html=True):
        """Returns unsaved resource changes as HTML or plain text."""
        if self._index is None or not self._original: return ""
        values = self.savefile.get_player_resources(self._index)
        diffs = [(metadata.PLAYER_RESOURCES[k], self._original[k], v)
                 for k, v in values.items() if self._original.get(k) != v]
        if not diffs: return ""
        title = __("Player %s (%s)", self._index + 1, __(metadata.PLAYER_COLOURS[self._index]))
        lines = ["%s: %s -> %s" % (__(a), b, c) for a, b, c in diffs]
        if not html: return "%s\n%s\n" % (title, "\n".join(lines))
        return "<b>%s</b><br />%s<br /><br />" % (title, "<br />".join(lines))


    def mark_saved(self):
        """Resets the record of unsaved changes."""
        if self._index is not None:
            self._original = dict(self.savefile.get_player_resources(self._index))
