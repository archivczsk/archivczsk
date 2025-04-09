'''
Created on 11.1.2013

@author: marko
'''
#from Plugins.Plugin import PluginDescriptor

import traceback
import re
from ..engine.tools.logger import log
from ..gui.common import showInfoMessage, showErrorMessage
from ..engine.tools.lang import _
from ..engine.parental import parental_pin
from ..engine.usage import UsageStats
from ..engine.tools.util import removeDiac
from Components.config import config

from ..py3compat import *

def getCapabilities():
	"""
	Vrati zoznam vsetkych moznosti vyhladavania: tuple(nazov_vyhladavania, id_doplnku, mod_vyhladavania)
	"""

	cap_list = []
	from ..archivczsk import ArchivCZSK
	for addon in ArchivCZSK.get_video_addons():
		for seeker in addon.get_info('seekers'):
			# seeker is touple ("Search name", search_id) - it's defined in addon's xml in archivczsk.addon.seeker point
			title = seeker[0]
			if addon.is_virtual():
				if config.plugins.archivCZSK.colored_items.value:
					title = '{} [B][{}][/B]'.format(title, addon.profile_name)
				else:
					title = '{} [{}]'.format(title, addon.profile_name)

			cap_list.append((title, addon.id, seeker[1],))

	cap_list.append(('CSFD', 'csfd', None))
	return cap_list

#	 Napriklad:
#
#	 search_exp = u'Matrix'
#	 search(session, search_exp, 'plugin.video.online-files')

def search(session, search_exp, addon_id, mode=None, cb=None):
	"""
	Vyhlada v archivCZSK hladany vyraz prostrednictvom addonu s addon_id s modom vyhladavania mode
	@param : session - aktivna session
	@param : search_exp - hladany vyraz
	@param : addon_id - id addonu v ktorom chceme vyhladavat
	@param : mode - mod vyhladavania podporovany addonom
	"""

	try:
		if search_exp is None or search_exp == "":
			showInfoMessage(session, _("Empty search expression"))
			return cb()

		archivCZSKSeeker = ArchivCZSKSeeker.getInstance(session, cb)
		if archivCZSKSeeker is not None:
			archivCZSKSeeker.search(search_exp, addon_id, mode)
	except:
		log.logError("Searching failed.\n%s"%traceback.format_exc())
		showInfoMessage(session, _("Search fatal error."))
		return cb()

def searchClose():
	"""
	Uvolni pamat po unkonceni prace s vyhladavacom
	"""
	if ArchivCZSKSeeker.instance is not None:
		ArchivCZSKSeeker.instance.close()


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


class ArchivCZSKSeeker():
	instance = None

	@staticmethod
	def getInstance(session, cb=None):
		if ArchivCZSKSeeker.instance is None:
			try:
				return ArchivCZSKSeeker(session, cb)
			except ImportError:
				log.logError("Cannot search, archivCZSK is not installed")
				showInfoMessage(session, _('Cannot search, archivCZSK is not installed'), 5, cb=cb)
				print('cannot found archivCZSK')
				return None
			except Exception:
				log.logError("ArchivCZSKSeeker fatal error.\n%s" % traceback.format_exc())
				traceback.print_exc()
				showErrorMessage(session, _('Unknown error'), 5, cb=cb)
				return None
		return ArchivCZSKSeeker.instance

	def __init__(self, session, cb=None):
		self.session = session
		self.cb = cb
		self.archivCZSK, self.contentScreen, self.task = getArchivCZSK()
		self.searcher = None
		self.addon = None
		self.searching = False
		if not isArchivCZSKRunning(session):
			self.task.startWorkerThread()
		ArchivCZSKSeeker.instance = self
		parental_pin.lock_pin()

	def __repr__(self):
		return '[ArchivCZSKSeeker]'

	def _successSearch(self, content):
		(searchItems, command, args) = content
		self.session.openWithCallback(self._contentScreenCB, self.contentScreen, self.addon, searchItems)


	def _errorSearch(self, failure):
		try:
			failure.raiseException()
		except:
			log.error(traceback.format_exc())

		showErrorMessage(self.session, _('Error while trying to retrieve search list'), 5)
		if self.searcher is not None:
			self.searcher.close()
			self.searcher = None
		self.searching = False
		self.addon = None
		if self.cb:
			self.cb()

	def _contentScreenCB(self, cp):
		if self.searcher is not None:
			self.searcher.close()
			self.searcher = None
		self.searching = False
		self.addon = None
		if self.cb:
			self.cb()


	def search(self, search_exp, addon_id, mode=None):
		if self.searching:
			showInfoMessage(self.session, _("You cannot search, archivCZSK Search is already running"))
			print("%s cannot search, searching is not finished" % self)
			return
		if addon_id.lower() == 'csfd':
			CsfdSearch().showCSFDInfo(self.session, search_exp)
			return self.cb()
		else:
			searcher = getSearcher(self.session, addon_id, self.archivCZSK, self._successSearch, self._errorSearch)
			if searcher is not None:
				self.searcher = searcher
				self.searching = True
				self.addon = searcher.addon
				searcher.start()
				searcher.search(search_exp, mode)
			else:
				showInfoMessage(self.session, _("Cannot find searcher") + ' ' + addon_id)
				return self.cb()

	def close(self):
		if self.searching:
			print('%s cannot close, searching is not finished yet' % self)
			return False
		if not isArchivCZSKRunning(self.session):
			self.task.stopWorkerThread()
		ArchivCZSKSeeker.instance = None
		return True


def getSearcher(session, addon_id, archivczsk, succ_cb, err_cb):
	try:
		return Search(session, addon_id, archivczsk, succ_cb, err_cb)
	except:
		log.logError("ArchivCZSKSeeker: failed to init search\n%s" % traceback.format_exc())
		return None


class Search(object):
	def __init__(self, session, addon_id, archivczsk, succ_cb, err_cb):
		self.session = session
		self.addon = archivczsk.get_addon(addon_id)
		self.provider = self.addon.provider
		self.succ_cb = succ_cb
		self.err_cb = err_cb

	def start(self):
		self.provider.start()

	def search(self, search_exp, mode=None):
		UsageStats.get_instance().addon_ext_search(self.addon)
		self.provider.search(self.session, search_exp, mode, self.succ_cb, self.err_cb)

	def close(self):
		"""releases resources"""
		self.provider.stop()


class CsfdSearch():
	def showCSFDInfo(self, session, searchExp):
		try:
			name = removeDiac(searchExp)
			name = name.replace('.', ' ').replace('_', ' ').replace('*','')

			# remove languages ... "Mother - CZ, EN, KO (2017)"
			name = re.sub("\s-\s[A-Z]{2}(,\s[A-Z]{2})*\s\(", " (", name)

			year = 0
			yearStr = ""
			try:
				mask = re.compile('([0-9]{4})', re.DOTALL)
				yearStr = mask.findall(name)[0]
				year = int(yearStr)
			except:
				pass
			# remove year
			name = re.sub("\([0-9]{4}\)","", name)

			name = name.strip()
			log.logDebug("Csfd search '%s', year=%s."%(name,year))

			csfdType = int(config.plugins.archivCZSK.csfdMode.getValue())

			if csfdType == 1:
				from ..gui.archivcsfd import ArchivCSFD
				session.open(ArchivCSFD, name, year)
			elif csfdType == 2:
				from Plugins.Extensions.CSFD.plugin import CSFD
				session.open(CSFD, name)
			elif csfdType == 3:
				from Plugins.Extensions.CSFDLite.plugin import CSFDLite
				try:
					session.open(CSFDLite, name, yearStr)
				except:
					log.logDebug("Trying CsfdLite older version compatibility...")
					session.open(CSFDLite, name)
			else:
				raise Exception("CsfdMode '%s' not supported." % csfdType)
		except:
			log.logError("Show CSFD info failed (plugin may not be installed).\n%s"%traceback.format_exc())
			try:
				showInfoMessage(session, _("Show CSFD info failed."), timeout=6)
			except:
				pass

#def main(session, **kwargs):
#	 search_exp = u'Matrix'
#	 search(session, search_exp, 'plugin.video.online-files')

#def Plugins(**kwargs):
#	 return [PluginDescriptor(name='Test_Plugin', description='', where=PluginDescriptor.WHERE_PLUGINMENU, icon="plugin.png", fnc=main)]

