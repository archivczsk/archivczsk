# -*- coding: UTF-8 -*-
import os

from Components.ActionMap import ActionMap
from Components.Label import Label
from .base import BaseArchivCZSKListSourceScreen
from .common import toString
from ..engine.tools.lang import _
from ..engine.tools.logger import log

class ArchivCZSKMultiLineChoiceBox(BaseArchivCZSKListSourceScreen):
	def __init__(self, session, title="", choices_list=[], selection=0):
		BaseArchivCZSKListSourceScreen.__init__(self, session)
		self.session = session
		self.choices_list = choices_list
		self.selection_idx = selection
		self.title = _("Choice")

		self["text"] = Label(title)

		self["actions"] = ActionMap(["archivCZSKActions"],
				{
				"ok": self.ok,
				"cancel": self.cancel,
				"up": self.up,
				"down": self.down,
				"left": self.home,
				"right": self.end,
				}, -2)

	def updateMenuList(self, index=0):
		self["menu"].list = [
			(
				'{:02d}.'.format(i+1),
				toString(item[0]),
				toString(' '.join(item[1:])),
			) for i, item in enumerate(self.choices_list)
		]

		self["menu"].index = self.selection_idx or index
		self.selection_idx = None

	def ok(self):
		result = self.choices_list[self["menu"].index]
		self.close(result)

	def cancel(self):
		self.close(None)
