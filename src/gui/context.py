# -*- coding: UTF-8 -*-
'''
Created on 28.4.2012

@author: marko
'''

from enigma import (loadPNG, RT_VALIGN_TOP, RT_HALIGN_LEFT, RT_HALIGN_RIGHT, RT_HALIGN_CENTER, RT_VALIGN_CENTER, eListboxPythonMultiContent, gFont, getDesktop, gPixmapPtr)

from Components.ActionMap import ActionMap
from Components.Label import Label
from Components.MenuList import MenuList
from Components.MultiContent import MultiContentEntryText, MultiContentEntryPixmapAlphaTest
from Components.Pixmap import Pixmap
from Components.config import config
from Tools.Directories import fileExists
from Tools.LoadPixmap import LoadPixmap

from ..engine.tools.lang import _
from ..py3compat import *

RATIO = 1
try:
	width = getDesktop(0).size().width()
	if width >= 3840:
		RATIO = 3
	elif width >= 2560:
		RATIO = 2
	elif width >= 1920:
		RATIO = 1.5
except:
	pass

def resize(t):
	return int(t*RATIO)

def fresize(t):
	return int(t * RATIO * (float(config.plugins.archivCZSK.font_size.value) / 100))


from .base import  BaseArchivCZSKScreen
def showContextMenu(session, name, img, items, globalItems, cb):
	session.openWithCallback(cb, ArchivCZSKContextMenuScreen, name, img, items, globalItems)


class ContextMenuList(MenuList):
	def __init__(self):
		MenuList.__init__(self, [], False, eListboxPythonMultiContent)
		self.l.setItemHeight(fresize(24))
		self.l.setFont(0, gFont("Regular", fresize(19)))


def ContextEntry(name, idx, png=''):
	res = [(name, idx)]
	if fileExists(png):
		res.append(MultiContentEntryPixmapAlphaTest(pos=(resize(5), 0), size=(resize(24), fresize(24)), png=loadPNG(png)))
		res.append(MultiContentEntryText(pos=(resize(40), 0), size=(resize(455), fresize(24)), font=0, flags=RT_VALIGN_CENTER, text=name))
	else:
		res.append(MultiContentEntryText(pos=(resize(5), 0), size=(resize(490), fresize(24)), font=0, flags=RT_VALIGN_CENTER, text=name))
	return res

def ContextEntryDisabled(name, idx, png='', separator=False):
	res = [(name, idx)]
	if separator:
		res.append(MultiContentEntryText(pos=(resize(5), resize(12)), size=(resize(490), resize(1)), font=0, flags=RT_VALIGN_CENTER, text=name, backcolor=0xffffff))
	elif fileExists(png):
		res.append(MultiContentEntryPixmapAlphaTest(pos=(resize(5), 0), size=(resize(24), fresize(24)), png=loadPNG(png)))
		res.append(MultiContentEntryText(pos=(resize(40), 0), size=(resize(455), fresize(24)), font=0, flags=RT_VALIGN_CENTER, text=name, color=0x696969))
	else:
		res.append(MultiContentEntryText(pos=(resize(5), 0), size=(resize(490), fresize(24)), font=0, flags=RT_VALIGN_CENTER, text=name, color=0x696969))
	return res



class ArchivCZSKContextMenuScreen(BaseArchivCZSKScreen):
	def __init__(self, session, name, img, items=None, globalItems=None):
		BaseArchivCZSKScreen.__init__(self, session)
		self.ctxItems = items or []
		self.globalCtxItems = globalItems or []
		self.disabledItemsIdx = []
		name = is_py3 == False and isinstance(name, unicode) and str(name.encode('utf-8')) or name
		img = img and img.endswith(('.jpg', '.png')) and img
		img = img and LoadPixmap(cached=True, path=img)
		self.img = img or gPixmapPtr()
		self.itemListDisabled = not (items and len(items) > 0)
		self.globalListDisabled = not (globalItems and len(globalItems) > 0)
		self.useSeparator = not	 self.globalListDisabled
		self["item_pixmap"] = Pixmap()
		self["item_label"] = Label(name)
		self.isFHD = False
		try:
			if getDesktop(0).size().width() > 1280:
				self.isFHD = True
		except:
			pass
		self['list'] = ContextMenuList()
		self["actions"] = ActionMap(["archivCZSKActions"],
			{"ok": self.ok,
			 "cancel": self.cancel,
			  "up": self.up,
			  "down": self.down,
			}, -2)
		self.onLayoutFinish.append(self.updateMenuList)
		self.onLayoutFinish.append(self.updateSelection)
		self.onLayoutFinish.append(self.checkList)
		self.onShown.append(self.__onShown)

	def __onShown(self):
		self["item_pixmap"].instance.setPixmap(self.img)

	def updateSelection(self):
		selectionIdx = 0
		while selectionIdx in self.disabledItemsIdx:
			selectionIdx += 1
		if selectionIdx == len(self["list"].list):
			selectionIdx = None
		if selectionIdx is not None:
			self["list"].moveToIndex(selectionIdx)

	def checkList(self):
		if self.itemListDisabled and self.globalListDisabled or len(self.disabledItemsIdx) == len(self["list"].list):
			self['list'].selectionEnabled(False)

	def updateMenuList(self):
		list = []
		idx = 0
		for item in self.ctxItems:
			png = item.thumb or ""
			name = item.name
			name = is_py3 == False and isinstance(name, unicode) and str(name.encode('utf-8')) or name
			if item.enabled:
				list.append(ContextEntry(name, idx, png))
			else:
				self.disabledItemsIdx.append(idx)
				list.append(ContextEntryDisabled(name, idx, png))
			idx += 1
		if self.useSeparator:
			self.disabledItemsIdx.append(idx)
			list.append(ContextEntryDisabled("", idx, None, True))
		# global context items should be standardized
		for item in self.globalCtxItems:
			png = item[1] or ""
			name = item[0]
			name = is_py3 == False and isinstance(name, unicode) and str(name.encode('utf-8')) or name
			list.append(ContextEntry(name, idx, png))
			idx += 1
		self["list"].setList(list)

	def up(self):
		if self.globalListDisabled and self.itemListDisabled:
			return
		listIdx = self["list"].getSelectedIndex()
		nextIdx = listIdx - 1
		if nextIdx in self.disabledItemsIdx:
			while nextIdx in self.disabledItemsIdx:
				nextIdx -= 1
				if nextIdx == -1:
					nextIdx = None
					break
			if nextIdx is not None:
				self["list"].moveToIndex(nextIdx)
		else:
			self["list"].up()

	def down(self):
		if self.globalListDisabled and self.itemListDisabled:
			return
		listIdx = self["list"].getSelectedIndex()
		nextIdx = listIdx + 1
		if nextIdx in self.disabledItemsIdx:
			while nextIdx in self.disabledItemsIdx:
				nextIdx += 1
				if nextIdx == len(self["list"].list):
					nextIdx = None
					break
			if nextIdx is not None:
				self["list"].moveToIndex(nextIdx)
		else:
			self["list"].down()

	def ok(self):
		if not self.globalListDisabled or not self.itemListDisabled:
			if not self["list"].getSelectedIndex() in self.disabledItemsIdx:
				idx = self["list"].getCurrent()[0][1]
				self.close(idx)
		else:
			self.close(None)

	def cancel(self):
		self.close(None)

class ArchivCZSKSelectCategoryScreen(ArchivCZSKContextMenuScreen):
	def __init__(self, session, categories):
		ArchivCZSKContextMenuScreen.__init__(self, session, _("Select category"), None, categories, None)
		self.skinName = "ArchivCZSKSelectSourceScreen"


