# -*- coding: UTF-8 -*-
import os
from . import info

from Components.ActionMap import ActionMap
from Components.ConfigList import ConfigListScreen
from Components.Label import Label
from Components.config import config, ConfigDirectory, ConfigText, ConfigNumber
from Screens.LocationBox import LocationBox
from Screens.VirtualKeyBoard import VirtualKeyBoard

from .. import _, settings, log, removeDiac
from ..resources.repositories import config as addon_config
from .base import BaseArchivCZSKScreen
from .common import Tabs

from ..compat import DMM_IMAGE
from ..py3compat import *

def openArchivCZSKMenu(session):
	session.open(ArchivCZSKConfigScreen)

def openAddonMenu(session, addon, cb):
	if cb is None:
		session.open(ArchivCZSKAddonConfigScreen, addon)
	else:
		session.openWithCallback(cb, ArchivCZSKAddonConfigScreen, addon)


class BaseArchivCZSKConfigScreen(BaseArchivCZSKScreen, ConfigListScreen):

	def __init__(self, session, categories=[]):
		BaseArchivCZSKScreen.__init__(self, session)
		ConfigListScreen.__init__(self, [], session=session, on_change=self.changedEntry)
		self.onChangedEntry = [ ]

		self.categories = categories
		self.selected_category = 0
		self.config_list_entries = []

		self["key_yellow"] = Label(_("Changelog"))
		self["key_green"] = Label(_("Save"))
		self["key_red"] = Label(_("Cancel"))
		self["key_blue"] = Label(_("Next"))
		self["categories"] = Tabs([c['label'] for c in categories])

		self["actions"] = ActionMap(["SetupActions", "ColorActions", "DirectionActions"],
			{
				"cancel": self.keyCancel,
				"green": self.keySave,
				"ok": self.keyOk,
				"red": self.keyCancel,
				"blue": self.nextCategory,
				"yellow": self.changelog,
				'left': self.keyLeft,
				'down': self.keyDown,
				'up': self.keyUp,
				'right': self.keyRight
			}, -2)

	def changedEntry(self):
		for x in self.onChangedEntry:
			x()

	def nextCategory(self):
		if len(self.categories) > 0:
			self.changeCategory()

	def refreshConfigList(self):
		if len(self.categories) > 0:
			config_list = self.categories[self.selected_category]['subentries']
			if hasattr(config_list, '__call__'):
				config_list = config_list()

			self.config_list_entries = config_list

		self["config"].list = self.config_list_entries
		self["config"].setList(self.config_list_entries)

	def changeCategory(self):
		if self.selected_category == len(self.categories) - 1:
			self.selected_category = 0
		else:
			self.selected_category += 1

		config_list = self.categories[self.selected_category]['subentries']

		# for dynamic menus we can use functions to retrieve config list
		if hasattr(config_list, '__call__'):
			config_list = config_list()

		self.config_list_entries = config_list

		self["categories"].setActiveTab(self.selected_category)
		self["config"].list = self.config_list_entries
		self["config"].setList(self.config_list_entries)


	def changelog(self):
		clog = u''
		changelog_path = os.path.join(settings.PLUGIN_PATH, 'changelog.txt')
		if os.path.isfile(changelog_path):
			with open(changelog_path, 'r') as f:
				text = f.read()
			try:
				clog = text
			except Exception:
				log.logError('ArchivCZSK changelog cannot be decoded')
				pass
		info.showChangelog(self.session, "ArchivCZSK", clog)

	def keyOk(self):
		current = self["config"].getCurrent()[1]
		if isinstance(current, ConfigDirectory):
			self.session.openWithCallback(self.pathSelected, LocationBox, "", "", current.value)
		elif isinstance(current, ConfigNumber):
			pass
		elif isinstance(current, ConfigText):
			entryName = self["config"].getCurrent()[0]
			self.session.openWithCallback(self.virtualKBCB, VirtualKeyBoard, title=removeDiac(entryName), text=removeDiac(current.getValue()))

	def keySave(self):
		self.saveAll()
		self.close(True)

	def keyCancel(self):
		for x in self["config"].list:
			x[1].cancel()
		self.close()

	def keyLeft(self):
		ConfigListScreen.keyLeft(self)

	def keyRight(self):
		ConfigListScreen.keyRight(self)

	def keyDown(self):
		self['config'].instance.moveSelection(self['config'].instance.moveDown)

	def keyUp(self):
		self['config'].instance.moveSelection(self['config'].instance.moveUp)

	def pathSelected(self, path):
		if path is not None:
			self["config"].getCurrent()[1].value = path

	def virtualKBCB(self, res=None):
		if res is not None:
			current = self["config"].getCurrent()[1]
			try:
				if 'XcursorX' in res:
					res = res.replace('XcursorX','')
			except:
				pass
			current.setValue(res)


class ArchivCZSKConfigScreen(BaseArchivCZSKConfigScreen):
	def __init__(self, session):

		categories = [
			{ 'label':_("Main"), 'subentries': settings.get_main_settings },
			{ 'label':_("Player"), 'subentries': settings.get_player_settings },
			{ 'label':_("Path"), 'subentries': settings.get_path_settings },
			{ 'label':_("Misc"), 'subentries': settings.get_misc_settings }
		]

		BaseArchivCZSKConfigScreen.__init__(self, session, categories=categories)

		if DMM_IMAGE:
			# DMM needs specific skin for config screen
			self.skinName = ["ArchivCZSKConfigScreenDMM", "ArchivCZSKConfigScreen"]

		self.onLayoutFinish.append(self.layoutFinished)
		self.onShown.append(self.buildMenu)

	def layoutFinished(self):
		self.setTitle("ArchivCZSK" + " - " + _("Configuration"))


	def buildMenu(self):
		self.refreshConfigList()

	def keyOk(self):
		current = self["config"].getCurrent()[1]
		if current == config.plugins.archivCZSK.videoPlayer.info:
			info.showVideoPlayerInfo(self.session)
		else:
			super(ArchivCZSKConfigScreen, self).keyOk()


class ArchivCZSKAddonConfigScreen(BaseArchivCZSKConfigScreen):
	def __init__(self, session, addon):
		self.session = session
		self.addon = addon

		# to get addon config including global settings
		categories = addon_config.getArchiveConfigList(addon)

		BaseArchivCZSKConfigScreen.__init__(self, session, categories=categories)

		if DMM_IMAGE:
			self.skinName = ["ArchivCZSKConfigScreenDMM", "ArchivCZSKConfigScreen"]
		else:
			self.skinName = "ArchivCZSKConfigScreen"

		self.onShown.append(self.buildMenu)
		self.onLayoutFinish.append(self.layoutFinished)

	def layoutFinished(self):
		name = py2_encode_utf8( self.addon.name )
		self.setTitle( name + " - " + _("Settings"))

	def changelog(self):
		info.showChangelog(self.session, self.addon.name, self.addon.changelog)

	def buildMenu(self):
		self.refreshConfigList()
		
