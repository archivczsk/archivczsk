import os,sys
import shutil
import threading
import traceback
import datetime
import time

from Components.config import config, configfile
from Components.Console import Console
from Screens.Console import Console as ConsoleScreen
from Screens.MessageBox import MessageBox
from skin import loadSkin
from enigma import eTimer
from Plugins.Extensions.archivCZSK import _, log, toString, settings, UpdateInfo, create_rotating_log
from Plugins.Extensions.archivCZSK.engine.addon import VideoAddon, XBMCAddon
from Plugins.Extensions.archivCZSK.engine.exceptions.updater import UpdateXMLVersionError
from Plugins.Extensions.archivCZSK.engine.tools.task import Task
from Plugins.Extensions.archivCZSK.gui.common import showInfoMessage
from Plugins.Extensions.archivCZSK.gui.content import ArchivCZSKContentScreen
from Plugins.Extensions.archivCZSK.compat import DMM_IMAGE, eConnectCallback
from Plugins.Extensions.archivCZSK.engine.updater import ArchivUpdater

class ArchivCZSK():

	__loaded = False
	__need_restart = False

	__repositories = {}
	__addons = {}

	@staticmethod
	def isLoaded():
		return ArchivCZSK.__loaded

	@staticmethod
	def load_repositories():
		start = time.time()
		from .engine.repository import Repository
		
		# list directories in settings.REPOSITORY_PATH and search for directory containing addon.xml file = repository
		for repo in [f for f in os.listdir(settings.REPOSITORY_PATH) if os.path.isdir(os.path.join(settings.REPOSITORY_PATH, f))]:
			repo_xml = os.path.join(settings.REPOSITORY_PATH, repo, 'addon.xml')
			if os.path.isfile( repo_xml ):
				try:
					repository = Repository(repo_xml)
				except Exception:
					traceback.print_exc()
				ArchivCZSK.add_repository(repository)
				sys.path.append(repository.path)

			
		ArchivCZSK.__loaded = True
		diff = time.time() - start
		log.info("load repositories in {0}".format(diff))

	@staticmethod
	def start_ydl():
		from Plugins.Extensions.archivCZSK.engine.ydl import ydl
		ydl.init()

	@staticmethod
	def load_skin():
		try:
			from enigma import getDesktop
			desktop_width = getDesktop(0).size().width()
			log.logDebug("Screen width %s px"%desktop_width)
			if	desktop_width >= 1280:
				if DMM_IMAGE:
					if desktop_width == 1920:
						skin_default_path = os.path.join(settings.SKIN_PATH, "default_dmm_fhd.xml")
					elif desktop_width == 3840:
						skin_default_path = os.path.join(settings.SKIN_PATH, "default_dmm_uhd.xml")
					else:
						skin_default_path = os.path.join(settings.SKIN_PATH, "default_dmm_hd.xml")
				else:
					if desktop_width == 1920:
						skin_default_path = os.path.join(settings.SKIN_PATH, "default_fhd.xml")
					elif desktop_width == 3840:
						skin_default_path = os.path.join(settings.SKIN_PATH, "default_uhd.xml")
					else:
						skin_default_path = os.path.join(settings.SKIN_PATH, "default_hd.xml")
			else:
				skin_default_path = os.path.join(settings.SKIN_PATH, "default_sd.xml")
			skin_name = config.plugins.archivCZSK.skin.value
			skin_path = os.path.join(settings.SKIN_PATH, skin_name + ".xml")
			if skin_name == 'auto' or not os.path.isfile(skin_path):
				skin_path = skin_default_path
			log.info("loading skin %s" % skin_path)
			loadSkin(skin_path)
		except:
			log.logError("Load plugin skin failed.\n%s"%traceback.format_exc())

	@staticmethod
	def get_repository(repository_id):
		return ArchivCZSK.__repositories[repository_id]

	@staticmethod
	def get_repositories():
		return list(ArchivCZSK.__repositories.values())

	@staticmethod
	def add_repository(repository):
		ArchivCZSK.__repositories[repository.id] = repository

	@staticmethod
	def get_addon(addon_id):
		return ArchivCZSK.__addons[addon_id]

	@staticmethod
	def get_addons():
		return list(ArchivCZSK.__addons.values())

	@staticmethod
	def get_video_addons():
		return [addon for addon in ArchivCZSK.get_addons() if isinstance(addon, VideoAddon)]

	@staticmethod
	def get_xbmc_addon(addon_id):
		return XBMCAddon(ArchivCZSK.__addons[addon_id])

	@staticmethod
	def has_addon(addon_id):
		return addon_id in ArchivCZSK.__addons

	@staticmethod
	def add_addon(addon):
		ArchivCZSK.__addons[addon.id] = addon

	@staticmethod
	def remove_addon(addon):
		del ArchivCZSK.__addons[addon.id]

	@staticmethod
	def preload_addons():
		for addon in ArchivCZSK.get_video_addons():
			try:
				if addon.is_enabled():
					addon.provider.preload_addon()
			except:
				log.logError("Preload of addon %s failed:\n%s" % (addon, traceback.format_exc()))

	def __init__(self, session):
		self.session = session
		self.to_update_addons = []
		self.updated_addons = []

		if ArchivCZSK.__need_restart:
			self.ask_restart_e2()
		else:
			if config.plugins.archivCZSK.archivAutoUpdate.value and self.canCheckUpdate(True):
				self.checkArchivUpdate()
			elif config.plugins.archivCZSK.autoUpdate.value and self.canCheckUpdate(False):
				self.runAddonsUpdateCheck()
			else:
				self.open_archive_screen()

	def canCheckUpdate(self, archivUpdate):
		limitHour = 4
		try:
			if archivUpdate:
				if UpdateInfo.CHECK_UPDATE_TIMESTAMP is None:
					UpdateInfo.CHECK_UPDATE_TIMESTAMP = datetime.datetime.now()
					return True
				else:
					delta = UpdateInfo.CHECK_UPDATE_TIMESTAMP + datetime.timedelta(hours=limitHour)
					if datetime.datetime.now() > delta:
						UpdateInfo.CHECK_UPDATE_TIMESTAMP = datetime.datetime.now()
						return True
					else:
						return False
			else:
				if UpdateInfo.CHECK_ADDON_UPDATE_TIMESTAMP is None:
					UpdateInfo.CHECK_ADDON_UPDATE_TIMESTAMP = datetime.datetime.now()
					return True
				else:
					delta = UpdateInfo.CHECK_ADDON_UPDATE_TIMESTAMP + datetime.timedelta(hours=limitHour)
					if datetime.datetime.now() > delta:
						UpdateInfo.CHECK_ADDON_UPDATE_TIMESTAMP = datetime.datetime.now()
						return True
					else:
						return False
		except:
			log.logError("canCheckUpdate failed.\n%s"%traceback.format_exc())
			return True

	def checkArchivUpdate(self):
		try:
			log.logInfo("Checking archivCZSK update...")
			upd = ArchivUpdater(self)
			upd.checkUpdate()
		except:
			if config.plugins.archivCZSK.autoUpdate.value and self.canCheckUpdate(False):
				self.runAddonsUpdateCheck()
			else:
				self.open_archive_screen()

	def runAddonsUpdateCheck(self):
		try:
			log.logInfo("Checking addons update...")
			self.__updateDialog = self.session.openWithCallback(self.check_updates_finished, MessageBox, 
											   _("Checking for addons updates"), 
											   type=MessageBox.TYPE_INFO, 
											   enable_input=False)
			
			# this is needed in order to show __updateDialog
			self.updateCheckTimer = eTimer()
			self.updateCheckTimer_conn = eConnectCallback(self.updateCheckTimer.timeout, self.check_addon_updates)
			self.updateCheckTimer.start(200, True)
		except:
			log.logError("Download addons failed.")
			self.open_archive_screen()

	def check_addon_updates(self):
		del self.updateCheckTimer
		del self.updateCheckTimer_conn
		
		lock = threading.Lock()
		threads = []
		def check_repository(repository):
			try:
				to_update = repository.check_updates()
				with lock:
					self.to_update_addons += to_update
			except UpdateXMLVersionError:
				log.error('cannot retrieve update xml for repository %s', repository)
			except Exception:
				traceback.print_exc()
				log.error('error when checking updates for repository %s', repository)
		for repo_key in list(self.__repositories.keys()):
			repository = self.__repositories[repo_key]
			threads.append(threading.Thread(target=check_repository, args=(repository,)))
		for t in threads:
			t.start()
		for t in threads:
			t.join()
		update_string = '\n'.join(addon.name for addon in self.to_update_addons)
		if len(self.to_update_addons) > 5:
			update_string = '\n'.join(addon.name for addon in self.to_update_addons[:6])
			update_string += "\n...\n..."
		self.__update_string = update_string

		self.session.close(self.__updateDialog)

	def check_updates_finished(self, callback=None):
		update_string = self.__update_string
		del self.__update_string
		if update_string != '':
			self.ask_update_addons(update_string)
		else:
			self.open_archive_screen()

	def ask_update_addons(self, update_string):
		self.session.openWithCallback(
				self.update_addons,
				MessageBox,
				"%s %s? (%s)\n\n%s" %(_("Do you want to update"), _("addons"), len(self.to_update_addons), toString(update_string)),
				type = MessageBox.TYPE_YESNO)

	def update_addons(self, callback=None, verbose=True):
		if not callback:
			self.open_archive_screen()
		else:
			updated_string = self._update_addons()
			self.session.openWithCallback(self.ask_restart_e2,
					MessageBox,
					"%s (%s/%s):\n\n%s"%(_("Following addons were updated"), len(self.updated_addons), len(self.to_update_addons), toString(updated_string)),
					type=MessageBox.TYPE_INFO)

	def _update_addons(self):
		for addon in self.to_update_addons:
			updated = False
			try:
				updated = addon.update()
			except Exception:
				traceback.print_exc()
				log.logError("Update addon '%s' failed.\n%s" % (addon.id,traceback.format_exc()))
				continue
			else:
				if updated:
					self.updated_addons.append(addon)

		update_string = '\n'.join(addon_u.name for addon_u in self.updated_addons)
		if len(self.updated_addons) > 5:
			update_string = '\n'.join(addon.name for addon in self.updated_addons[:6])
			update_string += "\n...\n..."

		return update_string


	def ask_restart_e2(self, callback=None):
		ArchivCZSK.__need_restart = True
		self.session.openWithCallback(self.restart_e2, 
				MessageBox, 
				_("You need to restart E2. Do you want to restart it now?"), 
				type=MessageBox.TYPE_YESNO)


	def restart_e2(self, callback=None):
		if callback:
			from Screens.Standby import TryQuitMainloop
			self.session.open(TryQuitMainloop, 3)

	def open_archive_screen(self, callback=None):
		if not ArchivCZSK.__loaded:
			self.load_repositories()

		def first_start_handled(callback=None):
			# first screen to open when starting plugin,
			# so we start worker thread where we can run our tasks(ie. loading archives)
			Task.startWorkerThread()
			self.session.openWithCallback(self.close_archive_screen, ArchivCZSKContentScreen, self)
		
		# check if this is first start after update
		from Plugins.Extensions.archivCZSK.settings import PLUGIN_PATH
		first_start_file = os.path.join( PLUGIN_PATH, '.first_start')
		if os.path.isfile( first_start_file ):
			os.remove( first_start_file )
			
			# check if we have all players installed
			from Plugins.Extensions.archivCZSK.engine.player.info import videoPlayerInfo
			
			if DMM_IMAGE:
				msg = _("Using archivCZSK on DreamBox with original software not supported due missing HW for testing. Due this bugs related to DreamBox will not be fixed. Use at your own risk.")
			elif not videoPlayerInfo.serviceappAvailable:
				msg = _("By system check there was no system plugin with name ServiceApp detected. This means, that your system only supports video player integrated in enigma2. Some addons doesn't work properly with internal player or don't work at all. If you will have problem with playing some videos, try to install ServiceApp system plugin from feed of your distribution. Then you can change in addon settings used video player to gstplayer or exteplayer3 that can handle some video formats better.")
			elif not videoPlayerInfo.exteplayer3Available and not videoPlayerInfo.gstplayerAvailable:
				msg = _("By system check there was system plugin with name ServiceApp detected, but you miss exteplayer3 and gstplayer. These video players are needed to handle some video formats that internal video player build into enigma2 can't. It is recommended to install gstplayer and exteplayer3 from feed of your distribution to be able use all available addons.")
			elif not videoPlayerInfo.exteplayer3Available:
				msg = _("By system check there was system plugin with name ServiceApp detected, but you miss exteplayer3. This video player is needed to handle some video formats that internal video player build into enigma2 can't. It is recommended to install exteplayer3 from feed of your distribution to be able use all available addons.")
			elif not videoPlayerInfo.gstplayerAvailable:
				msg = _("By system check there was system plugin with name ServiceApp detected, but you miss gstplayer. This video player is needed to handle some video formats that internal video player build into enigma2 can't. It is recommended to install gstplayer from feed of your distribution to be able use all available addons.")
			else:
				msg = None
			
			if msg:
				self.session.openWithCallback(first_start_handled, MessageBox, msg, type=MessageBox.TYPE_INFO, enable_input=True)
			else:
				first_start_handled()
		else:
			first_start_handled()

	def close_archive_screen(self):
#		if not config.plugins.archivCZSK.preload.getValue():
#			self.__addons.clear()
#			self.__repositories.clear()
#			ArchivCZSK.__loaded = False

		self.__console = None
		# We dont need worker thread anymore so we stop it
		Task.stopWorkerThread()

		# finally save all cfg changes - edit by shamman
		configfile.save()

		# clear tmp content by shamman
		filelist = [ f for f in os.listdir("/tmp") if f.endswith(".url") ]
		for f in filelist:
			try:
				os.remove(os.path.join('/tmp', f))
			except OSError:
				continue
		filelist = [ f for f in os.listdir("/tmp") if f.endswith(".png") ]
		for f in filelist:
			try:
				os.remove(os.path.join('/tmp', f))
			except OSError:
				continue
		shutil.rmtree("/tmp/archivCZSK", True)

		if config.plugins.archivCZSK.clearMemory.getValue():
			try:
				with open("/proc/sys/vm/drop_caches", "w") as f:
					f.write("1")
			except IOError as e:
				log.error('cannot drop caches : %s' % str(e))
