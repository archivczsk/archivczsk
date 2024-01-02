'''
Created on 11.1.2013

@author: marko
'''
#from Plugins.Plugin import PluginDescriptor

import traceback
import re
from .. import _, log, removeDiac
from ..gui.common import showInfoMessage, showErrorMessage
from ..engine.parental import parental_pin
from Components.config import config

from ..py3compat import *


def run_shortcut(session, addon, shortcut_name, params):
	"""
	Runs shortcut with shortcut_name for addon_d
	@param : session - active session
	@param : search_exp - hladany vyraz
	@param : addon_id - addon id that should be used
	@param : shortcut_name name of shortcut to run
	"""

	try:
		if not shortcut_name in addon.get_info('shortcuts'):
			return

		archivCZSKShortcut = ArchivCZSKShortcut.getInstance(session, searchClose)
		if archivCZSKShortcut is not None:
			archivCZSKShortcut.run_shortcut(addon, shortcut_name, params)
	except:
		log.logError("Searching failed.\n%s"%traceback.format_exc())
		showInfoMessage(session, _("Run addon fatal error."))


def searchClose():
	"""
	Uvolni pamat po unkonceni prace s vyhladavacom
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
		self.session = session
		self.cb = cb
		self.archivCZSK, self.contentScreen, self.task = getArchivCZSK()
		self.addon = None
		self.searching = False
		if not isArchivCZSKRunning(session):
			self.task.startWorkerThread()
		ArchivCZSKShortcut.instance = self
		parental_pin.lock_pin()

	def __repr__(self):
		return '[ArchivCZSKShortcut]'

	def _successSearch(self, content):
		(searchItems, command, args) = content
		self.session.openWithCallback(self._contentScreenCB, self.contentScreen, self.addon, searchItems)


	def _errorSearch(self, failure):
		try:
			failure.raiseException()
		except:
			log.error(traceback.format_exc())

		showErrorMessage(self.session, _('Error while trying to retrieve content list'), 5)
		self.addon.provider.stop()
		self.searching = False
		self.addon = None
		if self.cb:
			self.cb()

	def _contentScreenCB(self, cp):
		self.addon.provider.stop()
		self.searching = False
		self.addon = None
		if self.cb:
			self.cb()

	def run_shortcut(self, addon, shortcut_name, params):
		if self.searching:
			showInfoMessage(self.session, _("You cannot run ArchivCZSK again because it is already running"))
			return

		self.addon = addon
		self.searching = True
		addon.provider.start()
		addon.provider.run_shortcut(self.session, shortcut_name, params, self._successSearch, self._errorSearch)

	def close(self):
		if self.searching:
			print('%s cannot close, searching is not finished yet' % self)
			return False
		if not isArchivCZSKRunning(self.session):
			self.task.stopWorkerThread()
		ArchivCZSKShortcut.instance = None
		return True

