# -*- coding: utf-8 -*-

import traceback
from Components.Label import Label
from Components.ActionMap import ActionMap
from Screens.Screen import Screen
from Components.config import config
from datetime import datetime, timedelta
from ..engine.tools.logger import log
from .. import UpdateInfo
from ..engine.tools.lang import _
from ..engine.tools.util import toString

from ..engine.updater import ArchivUpdater, AddonsUpdater

class ArchivCZSKUpdateInfoScreen(Screen):
	def __init__(self, session, archivInstance):
		Screen.__init__(self, session)
		self.archiv = archivInstance
		self.__update_started = False
		self.__upd = None

		self["status"] = Label(_("Looking for updates. Please wait ..."))

		self["actions"] = ActionMap(["archivCZSKActions"],
		{
			"ok": self.ok,
			"cancel": self.cancel,
		})

		self.setTitle(_("Updating ArchivCZSK"))
		self.onShown.append(self.start_updater)

	def set_status(self, text):
		self['status'].setText(toString(text))

	def ok(self):
		log.info("OK pressed during update ...")
		try:
			self.__upd.cbk_wrapper()
		except:
			log.error(traceback.format_exc())

	def cancel(self):
		log.info("CANCEL pressed during update ...")
		try:
			self.__upd.cbk_wrapper()
		except:
			log.error(traceback.format_exc())

	@staticmethod
	def canCheckUpdate():
		limitHour = 4

		try:
			if UpdateInfo.CHECK_UPDATE_TIMESTAMP is None:
				UpdateInfo.CHECK_UPDATE_TIMESTAMP = datetime.now()
			else:
				delta = UpdateInfo.CHECK_UPDATE_TIMESTAMP + timedelta(hours=limitHour)
				if datetime.now() > delta:
					UpdateInfo.CHECK_UPDATE_TIMESTAMP = datetime.now()
				else:
					return False
		except:
			log.logError("canCheckUpdate failed.\n%s"%traceback.format_exc())

		return config.plugins.archivCZSK.archivAutoUpdate.value or config.plugins.archivCZSK.autoUpdate.value

	def checkArchivUpdate(self):
		try:
			log.info("Checking ArchivCZSK update ...")
			self.__upd = ArchivUpdater(self.archiv, self.archiv_update_finished, self)
			self.__upd.checkUpdate()
		except:
			log.error(traceback.format_exc())
			self.archiv_update_finished()


	def archiv_update_finished(self, result='continue'):
		self.__upd = None
		if result == 'continue' and config.plugins.archivCZSK.autoUpdate.value:
			self.checkAddonsUpdate()
		else:
			self.close(result)

	def checkAddonsUpdate(self):
		try:
			log.info("Checking addons update ...")
			self.__upd = AddonsUpdater(self.archiv, self.addons_update_finished, self)
			self.__upd.checkUpdate()
		except:
			log.error(traceback.format_exc())
			self.addons_update_finished()

	def addons_update_finished(self, result='continue'):
		self.__upd = None
		self.close(result)

	def start_updater(self):
		if self.__update_started:
			return

		self.__update_started = True

		if config.plugins.archivCZSK.archivAutoUpdate.value:
			self.checkArchivUpdate()
		elif config.plugins.archivCZSK.autoUpdate.value:
			self.checkAddonsUpdate()
		else:
			self.close('continue')
