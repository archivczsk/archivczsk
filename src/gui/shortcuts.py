# -*- coding: UTF-8 -*-
'''
Created on 28.4.2012

@author: marko
'''
from Components.config import config
from Components.ActionMap import ActionMap
from Components.Label import Label
from Screens.MessageBox import MessageBox
from Tools.LoadPixmap import LoadPixmap

from .. import _
from .common import toString
from .base import BaseArchivCZSKListSourceScreen
from ..colors import DeleteColors


def openShortcuts(session, addon, cb):
	session.openWithCallback(cb, ArchivCZSKShortcutsScreen, addon)

class ArchivCZSKShortcutsScreen(BaseArchivCZSKListSourceScreen):
	def __init__(self, session, addon):
		BaseArchivCZSKListSourceScreen.__init__(self, session)
		self.provider = addon.provider
		self.lst_items = self.provider.get_shortcuts()
		self.title = "%s - %s"% (toString(addon.name), _("Shortcuts"))
		self["key_red"] = Label(_("Remove shortcut"))
		self["key_green"] = Label()
		self["key_yellow"] = Label()
		self["key_blue"] = Label()
		self["actions"] = ActionMap(["archivCZSKActions"],
			{
				"ok": self.ok,
				"cancel": self.cancel,
				"red": self.askRemoveShortcut,
			})

		self.onShown.append(self.setWindowTitle)

	def setWindowTitle(self):
		self.setTitle(self.title)

	def askRemoveShortcut(self):
		item = self.getSelectedItem()
		if item:
			message = '%s %s?' % (_('Do you want to delete'), toString(DeleteColors(item.name)))
			self.session.openWithCallback(self.removeShortcut, 
								MessageBox, message, type=MessageBox.TYPE_YESNO)

	def removeShortcut(self, callback):
		if callback:
			self.provider.remove_shortcut(self.getSelectedItem())
			self.lst_items = self.provider.get_shortcuts()
			self.updateMenuList()
	
	def updateMenuList(self, index=0):
		if config.plugins.archivCZSK.colored_items.value:
			def handle_colors(s):
				return s
		else:
			def handle_colors(s):
				return DeleteColors(s)

		self["menu"].list = [(LoadPixmap(toString(item.thumb)), toString(handle_colors(item.name)))
						for item in self.lst_items]
		self["menu"].index = index

	def ok(self):
		self.close(self.getSelectedItem())

	def cancel(self):
		self.close(None)

