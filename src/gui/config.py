# -*- coding: UTF-8 -*-

import traceback
from .base import BaseArchivCZSKScreen, Screen
from .common import TipBar
from ..archivczsk import _, log
from ..compat import DMM_IMAGE
from ..engine.tools.util import toString, toUnicode
from Components.ConfigList import ConfigListScreen
from Components.ActionMap import ActionMap
from Components.Label import Label
from Components.Button import Button
from Screens.ChoiceBox import ChoiceBox
from Components.config import  ConfigSelection, ConfigYesNo, ConfigText, ConfigInteger, ConfigNumber, KEY_OK
from Components.SelectionList import SelectionList

# ##################################################################################################################

class ArchivCZSKSelectMultiScreen(Screen):

# (description, value, selected):
	def __init__(self, session, choices=[]):
		Screen.__init__(self, session)

		self["list"] = SelectionList(enableWrapAround=True)

		for i, x in enumerate(choices):
			self["list"].addSelection(toString(x[0]), x[1], i, len(x) > 2 and x[2])

		self["key_red"] = Button(_("Cancel"))
		self["key_green"] = Button(_("Save"))
		self["key_yellow"] = Button(_("Sort by"))
		self["key_blue"] = Button(_("Toggle selection")) if hasattr(self['list'], 'toggleAllSelection') else Button(" ")

		self["hint"] = Label(_("Press OK to toggle the selection"))

		self["setupActions"] = ActionMap(["SetupActions", "ColorActions"],
		{
			"red": self.cancel,
			"green": self.save,
			"yellow": self.sortBy,
			"blue": self.toggleAllSelection,
			"save": self.save,
			"cancel": self.cancel,
			"ok": self["list"].toggleSelection,
		}, -2)
		self.setTitle(_("Select values"))

	def toggleAllSelection(self):
		try:
			self["list"].toggleAllSelection()
		except:
			log.error("toggleAllSelection command on SelectionList is not supported")

	def save(self):
		val = [x[0][2] for x in self["list"].list if x[0][3]]
		self.close(val)

	def cancel(self):
		self.close(None)

	def sortBy(self):
		lst = self["list"].list
		if len(lst) > 1:
			menu = [(_("Alphabet"), "0"), (_("Reverse list"), "2"), (_("Standard list"), "1")]

			def sortAction(choice):
				if choice:
					reverse_flag = False
					sort_type = int(choice[1])
					if choice[1] == "2":
						sort_type = reverse_flag = 1
					elif choice[1] == "3":
						reverse_flag = not reverse_flag
					self["list"].sort(sortType=sort_type, flag=reverse_flag)
					self["list"].moveToIndex(0)
			self.session.openWithCallback(sortAction, ChoiceBox, title=_("Select sort method:"), list=menu, skin_name="ArchivCZSKChoiceBox")

# ##################################################################################################################

class SimpleConfigSelection(object):
	def __init__(self, title, choices=[], default=None, tooltip=_("Use LEFT/RIGHT keys to change the value")):
		self.title = title
		self.tooltip = tooltip
		self.choices = choices

		c = []
		for s in self.choices:
			if isinstance(s, type(())):
				c.append(s)
			else:
				c.append( (s, s,))

		self.config_entry = ConfigSelection(c, default=default)

	def get_value(self):
		return self.config_entry.value

# ##################################################################################################################

class SimpleConfigText(object):
	def __init__(self, title, default="", tooltip=None):
		self.title = title
		self.tooltip = tooltip
		self.config_entry = ConfigText(default=default, fixed_size=False)

	def get_value(self):
		return self.config_entry.value

# ##################################################################################################################

class ConfigMultiSelection(ConfigSelection):
	def __init__(self, choices=[]):
		ConfigSelection.__init__(self, choices=[('', '')])
		self.xchoices = choices

		self.xchoices_selected = []
		for i, c in enumerate(choices):
			if c[2]:
				self.xchoices_selected.append(i)

		xchoices_str = ', '.join(self.xchoices[i][1] for i in self.xchoices_selected)
		self.setChoices( [(xchoices_str, xchoices_str,)] )

	def handleKey(self, key):
		pass

	def open_selection(self, session):
		def selection_cbk(v):
			log.debug('selection resp: %s' % str(v))

			if isinstance(v, type([])):
				self.xchoices_selected = v
				xchoices_str = ', '.join(self.xchoices[i][1] for i in self.xchoices_selected)
				self.setChoices( [(xchoices_str, xchoices_str,)] )

		session.openWithCallback(selection_cbk, ArchivCZSKSelectMultiScreen, [(c[1], c[0], i in self.xchoices_selected,) for i, c in enumerate(self.xchoices)])

# ##################################################################################################################

class SimpleConfigMultiSelection(object):
	def __init__(self, title, choices=[], selected=[], tooltip=_("Press OK to open selection")):
		self.title = title
		self.tooltip = tooltip
		self.choices = choices

		c = []
		for s in self.choices:
			if isinstance( s, type(()) ):
				c.append( (s[0], s[1], s[0] in selected,) )
			else:
				c.append( (s, s, s in selected,) )

		self.config_entry = ConfigMultiSelection(choices=c)

	def get_value(self):
		return [self.choices[i][0] for i in self.config_entry.xchoices_selected]

# ##################################################################################################################

class SimpleConfigInteger(object):
	def __init__(self, title, limit_from=0, limit_to=999999, default=0, tooltip=_("Use number keys to enter value")):
		self.title = title
		self.tooltip = tooltip
		self.config_entry = ConfigInteger(default=default, limits=(limit_from, limit_to))

	def get_value(self):
		return self.config_entry.value

# ##################################################################################################################

class SimpleConfigNumber(object):
	def __init__(self, title, default=0, tooltip=None):
		self.title = title
		self.tooltip = tooltip
		self.config_entry = ConfigNumber(default=default)

	def get_value(self):
		return self.config_entry.value

# ##################################################################################################################

class SimpleConfigYesNo(object):
	def __init__(self, title, default=False, tooltip=_("Use LEFT/RIGHT keys to change the value")):
		self.title = title
		self.tooltip = tooltip
		self.config_entry = ConfigYesNo(default=default)

	def get_value(self):
		return self.config_entry.value

# ##################################################################################################################

class ArchivCZSKSimpleConfigScreen(BaseArchivCZSKScreen, ConfigListScreen):
	def __init__(self, session, config_entries, title=None):
		BaseArchivCZSKScreen.__init__(self, session)
		ConfigListScreen.__init__(self, [], session=session, on_change=self.changedEntry)
		self.onChangedEntry = []
		self.onUpdateGUI = []
		self.session = session
		self.config_list_entries = self.create_config_list(config_entries)
		self['config'].list = self.config_list_entries
		self['config'].setList(self.config_list_entries)
		self["key_yellow"] = Label(" ")
		self["key_green"] = Label(_("Apply"))
		self["key_red"] = Label(_("Cancel"))
		self["key_blue"] = Label(" ")
		self["tooltip"] = Label(" ")

		self["actions"] = ActionMap(["SetupActions", "ColorActions", "DirectionActions"],
			{
				"cancel": self.keyCancel,
				"green": self.keyGreen,
				"ok": self.keyOk,
				"red": self.keyCancel,
				"blue": self.keyBlue,
				"yellow": self.keyYellow,
				'left': self.keyLeft,
				'down': self.keyDown,
				'up': self.keyUp,
				'right': self.keyRight
			}, -2)

		self["config"].onSelectionChanged.append(self.updateGUI)

#		self.onClose.append(self._closeScr)
		self.onUpdateGUI.append(self.updateHint)

		if title:
			self.setTitle(title)

	def create_config_list(self, config_entries):
		ret = []

		for entry in config_entries:
			ret.append((entry.title, entry.config_entry, entry.tooltip or '',))

		return ret

	def updateHint(self):
		self["tooltip"].setText( self.config_list_entries[self['config'].getCurrentIndex()][2] )

	def updateGUI(self):
		try:
			for f in self.onUpdateGUI:
				f()
		except:
			log.logError("Action [updateGUI] failed.\n%s"%traceback.format_exc())
			pass

	def changedEntry(self):
		for x in self.onChangedEntry:
			x()

	def keyOk(self):
		v = self["config"].getCurrent() and self["config"].getCurrent()[1]

		if isinstance(v, ConfigMultiSelection):
			v.open_selection(self.session)
		else:
			self.keyOK()

	def keyCancel(self):
		self.close(False)

	def keyBlue(self):
		pass

	def keyGreen(self):
		self.saveAll()
		self.close(True)

	def keyRed(self):
		pass

	def keyYellow(self):
		pass

	def keyLeft(self):
		ConfigListScreen.keyLeft(self)

	def keyRight(self):
		ConfigListScreen.keyRight(self)

	def keyDown(self):
		self['config'].instance.moveSelection(self['config'].instance.moveDown)

	def keyUp(self):
		self['config'].instance.moveSelection(self['config'].instance.moveUp)

	def _closeScr(self):
		pass
