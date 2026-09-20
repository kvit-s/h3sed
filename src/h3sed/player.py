# -*- coding: utf-8 -*-
"""
Player plugin for savefile page, shows and edits player resources and tavern heroes.

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
from . lib import controls
from . lib.controls import ColourManager
from . lib.i18n import translate as __
import h3sed.version
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
        self._picks     = []     # Player indexes currently listed in the chooser
        self._ctrls     = {}     # {name: wx.Control}
        self._original  = {}     # Resources and tavern as loaded or last saved
        self._ignore_events = False
        self.prebuild()
        humans = self.savefile.find_human_players()
        if len(humans) == 1: self.select_player(humans[0])  # Savefile marks who the human is


    def format_version_note(self):
        """Returns a caution for savegame versions the player layout is unverified for."""
        if self.savefile.is_player_layout_verified(): return ""
        version = h3sed.version.VERSIONS.get(self.savefile.version)
        return " ".join([
            __("Player data has only been verified for %s savegames; this one is %s.",
               __("Shadow of Death"), __(version.TITLE) if version else self.savefile.version),
            __("Check the values against the game before saving."),
        ])


    def format_player(self, index, with_heroes=True, with_gold=False):
        """Returns label for player by 0-based index, with gold and owned heroes if wanted."""
        parts = [__("Player %s (%s)", index + 1, __(metadata.PLAYER_COLOURS[index]))]
        if self.savefile.is_player_human(index): parts[0] += " %s" % __("[human]")
        if with_gold:
            parts.append(__("%s gold", self.savefile.get_player_resources(index)["gold"]))
        if with_heroes:
            heroes = self.savefile.get_player_heroes(index)
            parts.append(", ".join(map(str, heroes)) if heroes else __("no heroes"))
        return " - ".join(parts)


    def prebuild(self):
        """Builds UI components: player identification prompt and editing fields."""
        self._panel.Freeze()
        self._panel.DestroyChildren()
        self._panel.Sizer and self._panel.Sizer.Clear()
        self._ctrls.clear()
        sizer = self._panel.Sizer = wx.BoxSizer(wx.VERTICAL)

        if self.savefile.find_players() is None:
            sizer.Add(wx.StaticText(self._panel, label=
                      __("Player data was not recognized in this savegame.")),
                      border=10, flag=wx.ALL)
            self._panel.Layout(), self._panel.Thaw()
            return

        note = self._ctrls["versionnote"] = wx.StaticText(self._panel)
        ColourManager.Manage(note, "ForegroundColour", "LinkColour")
        note.Label = self.format_version_note()
        note.Show(bool(note.Label))
        sizer.Add(note, border=10, flag=wx.ALL | wx.GROW)

        askpanel = self._askpanel = wx.Panel(self._panel)
        asksizer = askpanel.Sizer = wx.BoxSizer(wx.VERTICAL)
        intro = wx.StaticText(askpanel, label=__("Choose which player to work with:"))
        edit = self._ctrls["goldsearch"] = wx.TextCtrl(askpanel, size=(120, -1),
                                                       style=wx.TE_PROCESS_ENTER)
        button = wx.Button(askpanel, label=__("&Find player"))
        edit.Bind(wx.EVT_TEXT_ENTER, self.on_identify)
        button.Bind(wx.EVT_BUTTON,   self.on_identify)
        rowsizer = wx.BoxSizer(wx.HORIZONTAL)
        rowsizer.Add(wx.StaticText(askpanel, label=__("Or find yourself by gold amount") + ":"),
                     border=5, flag=wx.RIGHT | wx.ALIGN_CENTER_VERTICAL)
        rowsizer.Add(edit, border=5, flag=wx.RIGHT)
        rowsizer.Add(button)

        status = self._ctrls["status"] = wx.StaticText(askpanel)

        pickpanel = self._ctrls["pickpanel"] = wx.Panel(askpanel)
        picksizer = pickpanel.Sizer = wx.BoxSizer(wx.VERTICAL)
        choice = self._ctrls["pick"] = wx.Choice(pickpanel, size=(420, -1))
        pickbutton = wx.Button(pickpanel, label=__("&Use this player"))
        pickbutton.Bind(wx.EVT_BUTTON, self.on_pick_player)
        choice.Bind(wx.EVT_CHOICE, lambda e: self.on_pick_player())
        pickrow = wx.BoxSizer(wx.HORIZONTAL)
        pickrow.Add(choice,     border=5, flag=wx.RIGHT)
        pickrow.Add(pickbutton)
        picksizer.Add(pickrow)

        asksizer.Add(intro,     border=10, flag=wx.LEFT | wx.TOP | wx.RIGHT)
        asksizer.Add(pickpanel, border=10, flag=wx.ALL)
        asksizer.Add(rowsizer,  border=10, flag=wx.LEFT | wx.RIGHT | wx.BOTTOM)
        asksizer.Add(status,    border=10, flag=wx.LEFT | wx.RIGHT | wx.BOTTOM)
        self.populate_player_choice()

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

        heroes = self._ctrls["heroes"] = wx.StaticText(editpanel)
        ColourManager.Manage(heroes, "ForegroundColour", wx.SYS_COLOUR_GRAYTEXT)

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

        tavernlabel = wx.StaticText(editpanel, label=__("Heroes available in taverns") + ":")
        tavernnote = self._ctrls["tavernnote"] = wx.StaticText(editpanel, label=
            __("Only heroes not already owned or offered elsewhere can be chosen."))
        ColourManager.Manage(tavernnote, "ForegroundColour", wx.SYS_COLOUR_GRAYTEXT)
        tavernsizer = wx.BoxSizer(wx.HORIZONTAL)
        for i in range(metadata.PLAYER_TAVERN_SLOTS):
            ctrl = self._ctrls["tavern%s" % i] = wx.ComboBox(
                editpanel, name="tavern%s" % i, size=(160, -1),
                style=wx.CB_DROPDOWN | wx.CB_READONLY)
            ctrl.Bind(wx.EVT_COMBOBOX, self.on_change_tavern)
            tavernsizer.Add(ctrl, border=5, flag=wx.RIGHT)

        note = wx.StaticText(editpanel, label=
            __("Changes are saved to file with the usual Save command."))
        ColourManager.Manage(note, "ForegroundColour", wx.SYS_COLOUR_GRAYTEXT)

        editsizer.Add(headsizer,   border=10, flag=wx.ALL | wx.GROW)
        editsizer.Add(warning,     border=10, flag=wx.LEFT | wx.RIGHT | wx.BOTTOM)
        editsizer.Add(heroes,      border=10, flag=wx.LEFT | wx.RIGHT | wx.BOTTOM)
        editsizer.Add(gridsizer,   border=10, flag=wx.LEFT | wx.RIGHT | wx.BOTTOM)
        editsizer.Add(tavernlabel, border=10, flag=wx.LEFT | wx.RIGHT)
        editsizer.Add(tavernsizer, border=10, flag=wx.LEFT | wx.RIGHT | wx.TOP)
        editsizer.Add(tavernnote,  border=10, flag=wx.LEFT | wx.RIGHT | wx.BOTTOM)
        editsizer.Add(note,        border=10, flag=wx.LEFT | wx.RIGHT | wx.BOTTOM)

        sizer.Add(askpanel,  flag=wx.GROW)
        sizer.Add(editpanel, flag=wx.GROW)
        editpanel.Hide()
        self._panel.Bind(wx.EVT_SIZE, self.on_size)
        self._panel.Layout()
        self._panel.Thaw()


    def on_size(self, event):
        """Handler for panel resize, re-lays out contents at the new size."""
        event.Skip()
        wx.CallAfter(self.relayout)


    def relayout(self):
        """Lays out and repaints panel contents, sizing labels to their text."""
        if not self._panel: return
        for panel in (self._askpanel, self._editpanel):
            if panel and panel.Shown: panel.Layout()
        self._panel.Layout()
        self._panel.Refresh()
        self._panel.Update()


    def render(self, reparse=False, reload=False, rebuild=False, log=True):
        """Populates editing controls from savefile."""
        if rebuild:
            index, matches = self._index, self._matches
            self.prebuild()
            self._index, self._matches = index, matches
        if reparse: self._original = {}  # Player slot stays valid, its values do not
        if not self._ctrls or self.savefile.find_players() is None: return

        if self._index is None:
            self.show_panel(self._askpanel)
            return

        values = self.savefile.get_player_resources(self._index)
        tavern = self.savefile.get_player_tavern(self._index)
        if not self._original: self._original = self.get_data()
        self._ignore_events = True
        try:
            self._ctrls["header"].Label = self.format_player(self._index, with_heroes=False)
            owned = self.savefile.get_player_heroes(self._index)
            self._ctrls["heroes"].Label = __("Heroes") + ": " + \
                                          (", ".join(map(str, owned)) if owned else __("none"))
            self._ctrls["warning"].Label = "" if len(self._matches) < 2 else \
                __("Several players had this amount of gold: make sure this is you "
                   "before saving.")
            self._ctrls["warning"].Show(len(self._matches) > 1)
            for name, value in values.items():
                if self._ctrls[name].Value != value: self._ctrls[name].Value = value

            choices = [None] + self.savefile.get_available_heroes(self._index)
            labels = [__("none")] + [str(h) for h in choices[1:]]
            for i, hero in enumerate(tavern):
                ctrl = self._ctrls["tavern%s" % i]
                label = str(hero) if hero else __("none")
                if controls.get_combo_labels(ctrl) != labels:
                    controls.set_combo_choices(ctrl, choices, labels, label)
                else: controls.set_combo_value(ctrl, label)
            self.show_panel(self._editpanel)
        finally:
            self._ignore_events = False


    def show_panel(self, panel):
        """Shows one of the plugin panels and hides the other, repainting both."""
        other = self._editpanel if panel is self._askpanel else self._askpanel
        self._panel.Freeze()
        try:
            other.Hide()
            panel.Show()
            self.relayout()
        finally:
            self._panel.Thaw()


    def on_identify(self, event=None):
        """Handler for looking up the player by the gold amount given."""
        text = self._ctrls["goldsearch"].Value.strip().replace(" ", "").replace(",", "")
        status = self._ctrls["status"]
        if not text.isdigit():
            status.Label = __("Enter the gold amount as a plain number.")
            self.relayout()
            return

        self._matches = self.savefile.find_player_by_gold(int(text))
        if not self._matches:
            status.Label = __("No player has %s gold in this savegame.", text) + "\n" + \
                           __("Note that the amount can be cut off in the game status bar: "
                              "check it on the town screen.")
            self.relayout()
            return

        if len(self._matches) > 1:
            status.Label = __("%s players have %s gold.", len(self._matches), text) + "\n" + \
                           __("Pick yourself below by the heroes you have, or spend some gold "
                              "in game and save again to tell them apart.")
            self.populate_player_choice(self._matches)
            self.relayout()
            logger.info("Gold amount %s matches %s players in %s.", text,
                        len(self._matches), self.savefile.filename)
            return

        status.Label = ""
        self.select_player(self._matches[0])


    def populate_player_choice(self, indexes=None):
        """Fills the player chooser, with all players or only the given ones."""
        self._picks = list(range(metadata.PLAYER_COUNT)) if indexes is None else list(indexes)
        self._ctrls["pick"].SetItems([self.format_player(i, with_gold=True) for i in self._picks])
        humans = [i for i, x in enumerate(self._picks) if self.savefile.is_player_human(x)]
        if self._picks: self._ctrls["pick"].Selection = humans[0] if humans else 0


    def on_pick_player(self, event=None):
        """Handler for choosing a player from the chooser."""
        selection = self._ctrls["pick"].Selection
        if not 0 <= selection < len(self._picks): return
        self._ctrls["status"].Label = ""
        self.select_player(self._picks[selection])


    def select_player(self, index):
        """Sets the player being edited, by 0-based index."""
        self._index, self._original = index, {}
        self.savefile.player_index = index  # Lets other plugins know whose heroes are whose
        logger.info("Editing player %s in %s.", self.format_player(index), self.savefile.filename)
        self.render()


    def on_reidentify(self, event=None):
        """Handler for returning to the player identification prompt."""
        self._ctrls["status"].Label = ""
        self._index, self._matches = None, []
        self.savefile.player_index = None
        self.populate_player_choice()
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

        self.command(on_do, ("%s %s: %s", (__(metadata.PLAYER_COLOURS[self._index]),
                                           __(metadata.PLAYER_RESOURCES[name]), value)))


    def on_change_tavern(self, event):
        """Handler for changing a tavern hero, submits an undoable command."""
        if self._ignore_events or self._index is None: return
        ctrl = event.EventObject
        slot = int(ctrl.Name[-1])
        hero = ctrl.GetClientData(ctrl.Selection) if ctrl.Selection >= 0 else None
        heroes = list(self.savefile.get_player_tavern(self._index))
        if len(heroes) > slot and heroes[slot] == hero: return
        heroes[slot:slot + 1] = [hero]

        def on_do():
            self.savefile.set_player_tavern(self._index, heroes)
            self.render(reload=True)
            return True

        self.command(on_do, ("%s %s: %s", (__(metadata.PLAYER_COLOURS[self._index]),
                                           __("tavern hero"), str(hero) if hero else __("none"))))


    def command(self, callable, name):
        """Submits an undoable command to the command processor."""
        def do():
            if not callable(): return False
            self.patch()  # Command processor only patches on redo, not on the first do
            return True
        self._undoredo.Submit(h3sed.gui.PluginCommand(self, do, name=name))


    def get_data(self):
        """Returns current state of the player being edited, for undo-redo."""
        if self._index is None: return None
        return {"resources": dict(self.savefile.get_player_resources(self._index)),
                "tavern":    list(self.savefile.get_player_tavern(self._index))}


    def set_data(self, data):
        """Restores state of the player being edited, for undo-redo."""
        if self._index is None or not data: return
        self.savefile.set_player_resources(self._index, data["resources"])
        self.savefile.set_player_tavern(self._index, data["tavern"])


    def patch(self):
        """Notifies the savefile page that contents have changed."""
        wx.PostEvent(self._panel, h3sed.gui.SavefilePageEvent(self._panel.Id))


    def action(self, **kwargs):
        """Handler for action (save=True) from savefile page."""
        if kwargs.get("save"): self.mark_saved()


    def get_changes(self, html=True):
        """Returns unsaved player changes as HTML or plain text."""
        if self._index is None or not self._original: return ""
        data, diffs = self.get_data(), []
        for name, label in metadata.PLAYER_RESOURCES.items():
            before, after = self._original["resources"][name], data["resources"][name]
            if before != after: diffs.append((__(label), before, after))
        fmt = lambda h: str(h) if h else __("none")
        for i, (before, after) in enumerate(zip(self._original["tavern"], data["tavern"])):
            if before != after:
                diffs.append(("%s %s" % (__("tavern hero"), i + 1), fmt(before), fmt(after)))
        if not diffs: return ""
        title = self.format_player(self._index, with_heroes=False)
        lines = ["%s: %s -> %s" % (a, b, c) for a, b, c in diffs]
        if not html: return "%s\n%s\n" % (title, "\n".join(lines))
        return "<b>%s</b><br />%s<br /><br />" % (title, "<br />".join(lines))


    def mark_saved(self):
        """Resets the record of unsaved changes."""
        if self._index is not None: self._original = self.get_data()
