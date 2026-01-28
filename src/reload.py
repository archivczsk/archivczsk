# -*- coding: UTF-8 -*-

from enigma import eTimer
from Components.Label import Label
from Screens.Screen import Screen
from .engine.tools.util import toString
from .engine.tools.lang import _
import traceback

class eCompatTimer(object):
	def __init__(self, callbackFun):
		self.t = eTimer()
		self.callbackFun = callbackFun

		obj = self.t.timeout

		if 'connect' in dir(obj):
			self.conn_obj = obj.connect(callbackFun)
		elif 'get' in dir(obj):
			obj.get().append(callbackFun)
		else:
			obj.append(callbackFun)

	def __del__(self):
		obj = self.t.timeout
		if 'connect' in dir(obj):
			try:
				del self.conn_obj
			except:
				pass
		elif 'get' in dir(obj):
			obj.get().remove(self.callbackFun)
		else:
			obj.remove(self.callbackFun)

		self.callbackFun = None
		del self.t

	def __getattr__(self, name):
		return getattr(self.t, name)

class ArchivCZSKReloadInfoScreen(Screen):
	def __init__(self, session, text=None):
		Screen.__init__(self, session)
		self.toString = toString
		self._ = _
		self.skinName = ['ArchivCZSKUpdateInfoScreen']
		self["status"] = Label()

		if text:
			self['status'].setText(self.toString(text))

		self.setTitle(self._("Loading ArchivCZSK"))

	def set_status(self, text):
		self['status'].setText(self.toString(text))


class ArchivCZSKReloader(object):
	def __init__(self, session, autorun_addon=None):
		self.session = session
		self.autorun_addon = autorun_addon
		self.dialog = None
		self.run_after_reload = False
		self.force_e2_restart = False
		self._ = _
		self.__cbk = None
		self.t = eCompatTimer(self.cbk_wrapper)

	def cbk_wrapper(self):
		if self.__cbk != None:
			cbk = self.__cbk
			self.__cbk = None
			self.t.stop()
			cbk()

	def stop_timers(self):
		del self.t

	def run_next(self, cbk, msg=None):
		if msg:
			self.show_dialog(msg)
		else:
			self.close_dialog()

		self.__cbk = cbk
		self.t.start(100)

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
		self.run_next(self.unload, self._("Stopping old version of ArchivCZSK"))

	def unload(self):
		from .archivczsk import ArchivCZSK

		if not ArchivCZSK.isLoaded():
			return self.run_next(self.unload_finished, self._("Old version not running"))

		try:
			addon_modules = ArchivCZSK.get_addon_modules()
		except:
			addon_modules = []
			# this is needed in order to update version 3.4.0, that has bug in addons reload
			self.force_e2_restart = True

		try:
			ArchivCZSK.stop(True)
		except:
			from .engine.tools.logger import log
			log.error("Failed to stop ArchivCZSK\n%s" % traceback.format_exc())
			# if something failed, then restart enigma
			self.force_e2_restart = True

		if self.force_e2_restart:
			self.stop_timers()
			from Screens.Standby import TryQuitMainloop
			self.session.open(TryQuitMainloop, 3)
			return

		ArchivCZSK.unload(addon_modules)
		return self.run_next(self.unload_finished, self._("Old version stopped"))

	def unload_finished(self):
		self.run_next(self.start_archivczsk, self._("Initialising new version of ArchivCZSK"))

	def start_archivczsk(self):
		from .archivczsk import ArchivCZSK
		ArchivCZSK.start(self.session)

		if self.run_after_reload:
			self.run_next(self.run_archivczsk)
		else:
			self.stop_timers()
			self.close_dialog()

	def run_archivczsk(self):
		self.stop_timers()
		from .archivczsk import ArchivCZSK
		ArchivCZSK.run(self.session, self.autorun_addon)
