# -*- coding: UTF-8 -*-

from enigma import eTimer
from Components.Label import Label
from Screens.Screen import Screen
from .compat import eConnectCallback
from .engine.tools.util import toString
from .engine.tools.lang import _

class ArchivCZSKReloadInfoScreen(Screen):
	def __init__(self, session, text=None):
		Screen.__init__(self, session)
		self.skinName = ['ArchivCZSKUpdateInfoScreen']
		self["status"] = Label()

		if text:
			self['status'].setText(toString(text))

		self.setTitle(_("Loading ArchivCZSK"))

	def set_status(self, text):
		self['status'].setText(toString(text))


class ArchivCZSKReloader(object):
	def __init__(self, session):
		self.session = session
		self.dialog = None
		self.run_after_reload = False
		self.force_e2_restart = False

	def run_next(self, cbk, msg=None):
		# this is needed to make changes in GUI, because you need to return call to reactor
		def __cbk_wrapper():
			del self.t
			del self.tc
			cbk()

		if msg:
			self.show_dialog(msg)
		else:
			self.close_dialog()
		self.t = eTimer()
		self.tc = eConnectCallback(self.t.timeout, __cbk_wrapper)
		self.t.start(100, True)

	def show_dialog(self, msg):
		if self.dialog:
			self.dialog.set_status(msg)
		else:
			self.dialog = self.session.open(ArchivCZSKReloadInfoScreen, text=msg)

	def close_dialog(self):
		if self.dialog:
			self.session.close(self.dialog)
			self.dialog = None

	def reload_and_run(self):
		self.run_after_reload = True
		self.reload()

	def reload(self):
		self.run_next(self.unload, _("Stopping old version of ArchivCZSK"))

	def unload(self):
		from .archivczsk import ArchivCZSK

		if not ArchivCZSK.isLoaded():
			return self.run_next(self.unload_finished, _("Old version not running"))

		def __unload():
			if not stopped:
				from .engine.tools.logger import log
				log.debug("HTTP server still running ...")

			self.__stop_t.stop()
			del self.__stop_tc
			del self.__stop_t

			if self.force_e2_restart:
				from Screens.Standby import TryQuitMainloop
				self.session.open(TryQuitMainloop, 3)
				return

			ArchivCZSK.unload(addon_modules)
			return self.run_next(self.unload_finished, _("Old version stopped"))

		stopped = False
		def __stop_cbk():
			stopped = True

		try:
			addon_modules = ArchivCZSK.get_addon_modules()
		except:
			addon_modules = []
			# this is needed in order to update version 3.4.0, that has bug in addons reload
			self.force_e2_restart = True

		ArchivCZSK.stop(__stop_cbk)
		# now we need to wait a little bit in order to HTTP server completely stops
		self.__stop_t = eTimer()
		self.__stop_tc = eConnectCallback(self.__stop_t.timeout, __unload)
		self.__stop_t.start(1000)

	def unload_finished(self):
		self.run_next(self.start_archivczsk, _("Initialising new version of ArchivCZSK"))

	def start_archivczsk(self):
		from .archivczsk import ArchivCZSK
		ArchivCZSK.start(self.session)

		if self.run_after_reload:
			self.run_next(self.run_archivczsk)
		else:
			self.close_dialog()

	def run_archivczsk(self):
		from .archivczsk import ArchivCZSK
		ArchivCZSK.run(self.session)
