'''
Created on 11.1.2013

@author: marko
'''
import traceback
from ..engine.tools.logger import log
from ..gui.common import showInfoMessage, showErrorMessage
from ..engine.tools.lang import _
from ..engine.parental import parental_pin
from ..engine.usage import UsageStats

from ..py3compat import *


def run_shortcut(session, addon, shortcut_name, params, autorun=False):
	"""
	Runs shortcut with shortcut_name for addon
	@param : session - active session
	@param : search_exp - hladany vyraz
	@param : addon_id - addon id that should be used
	@param : shortcut_name name of shortcut to run
	"""

	try:
		archivCZSKShortcut = ArchivCZSKShortcut.getInstance(session, searchClose)
		if archivCZSKShortcut is not None:
			archivCZSKShortcut.run_shortcut(addon, shortcut_name, params, autorun)
	except:
		log.logError("Shortcut run failed.\n%s" % traceback.format_exc())
		showInfoMessage(session, _("Run addon fatal error."))


def searchClose():
	"""
	Uvolni pamat po unkonceni prace so skratkami
	"""
	if ArchivCZSKShortcut.instance is not None:
		ArchivCZSKShortcut.instance.close()


def isArchivCZSKRunning(session):
	for dialog in session.dialog_stack:
		# csfd plugin sa da otvorit len z ContentScreen
		if dialog.__class__.__name__ == 'ContentScreen':
			return True
	return False

def getArchivCZSK():
	from ..archivczsk import ArchivCZSK
	from ..engine.tools.task import Task
	from ..gui.content import ArchivCZSKAddonContentScreenAdvanced
	return ArchivCZSK, ArchivCZSKAddonContentScreenAdvanced, Task

from Components.Label import Label
from ..engine.tools.util import toString
from Screens.Screen import Screen

class ArchivCZSKShortcutRunScreen(Screen):
	def __init__(self, session, text=None, shortcut_name=None):
		Screen.__init__(self, session)
		self["status"] = Label()

		if text:
			self['status'].setText(toString(text))

		if shortcut_name:
			self.setTitle(_("Running shortcut: {shortcut_name}").format(shortcut_name=shortcut_name))

	def set_status(self, text):
		self['status'].setText(toString(text))


class ArchivCZSKShortcut():
	instance = None

	@staticmethod
	def getInstance(session, cb=None):
		if ArchivCZSKShortcut.instance is None:
			try:
				return ArchivCZSKShortcut(session, cb)
			except ImportError:
				log.logError("Cannot run shortcut, archivCZSK is not installed")
				showInfoMessage(session, _('Cannot run shortcut, archivCZSK is not installed'), 5, cb=cb)
				print('cannot found archivCZSK')
				return None
			except Exception:
				log.logError("ArchivCZSKShortcut fatal error.\n%s" % traceback.format_exc())
				traceback.print_exc()
				showErrorMessage(session, _('Unknown error'), 5, cb=cb)
				return None
		return ArchivCZSKShortcut.instance

	def __init__(self, session, cb=None):
		self.autorun = False
		self.session = session
		self.cb = cb
		self.archivCZSK, self.contentScreen, self.task = getArchivCZSK()
		self.status_dialog = None
		self._cleanup()
		if not isArchivCZSKRunning(session):
			self.task.startWorkerThread()
		ArchivCZSKShortcut.instance = self
		parental_pin.lock_pin()

	def __repr__(self):
		return '[ArchivCZSKShortcut]'

	def _cleanup(self):
		self.searching = False
		self.addon = None
		self.addons = []
		self.shortcut_name = None
		self.params = None
		if self.status_dialog:
			self.session.close(self.status_dialog)
			self.status_dialog = None

	def _successSearch(self, content):
		(searchItems, command, args) = content
		if searchItems:
			self.session.openWithCallback(self._contentScreenCB, self.contentScreen, self.addon, searchItems, self.autorun)
		else:
			self.addon.provider.stop()
			self._run_shortcut_internal()

	def _errorSearch(self, failure):
		try:
			failure.raiseException()
		except:
			log.error(traceback.format_exc())

		showErrorMessage(self.session, _('Error while trying to retrieve content list'), 5)
		self.addon.provider.stop()
		self._cleanup()
		if self.cb:
			self.cb()

	def _contentScreenCB(self, cp):
		self.addon.provider.stop()
		self._cleanup()
		if self.cb:
			self.cb()

	def _run_shortcut_internal(self):
		if self.addons:
			self.addon = self.addons.pop()

			status_text = _("Running shortcut using {addon_name} addon ...").format(addon_name=self.addon.name)

			if self.status_dialog:
				self.status_dialog.set_status(status_text)
			else:
				self.status_dialog = self.session.open(ArchivCZSKShortcutRunScreen, text=status_text, shortcut_name=self.shortcut_name)

			UsageStats.get_instance().addon_shortcut(self.addon, self.shortcut_name)
			self.addon.provider.start()
			self.addon.provider.run_shortcut(self.session, self.shortcut_name, self.params, self._successSearch, self._errorSearch)
		else:
			self._cleanup()
			if self.cb:
				self.cb()


	def run_shortcut(self, addon, shortcut_name, params, autorun=False):
		if self.searching:
			showInfoMessage(self.session, _("You cannot run ArchivCZSK again because it is already running"))
			return

		addons = [addon] if addon else self.archivCZSK.get_video_addons()
		self.addons = [a for a in addons if shortcut_name in (a.get_info('shortcuts') or [])]

		try:
			self.addons.sort(key=lambda a: (int(a.get_setting('auto_addon_order')), a.name,), reverse=True)
		except:
			log.error(traceback.format_exc())

		log.debug("Sorted addons for running shortcut: %s" % str(self.addons))

		self.searching = True
		self.shortcut_name = shortcut_name
		self.params = params
		self.autorun = autorun
		self._run_shortcut_internal()


	def close(self):
		if self.searching:
			print('%s cannot close, searching is not finished yet' % self)
			return False
		if not isArchivCZSKRunning(self.session):
			self.task.stopWorkerThread()
		ArchivCZSKShortcut.instance = None
		return True
