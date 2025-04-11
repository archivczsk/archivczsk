import os,sys
import shutil
import threading
import traceback
import datetime
import time

from Components.config import config, configfile
from Screens.MessageBox import MessageBox
from skin import loadSkin
from enigma import eTimer, eConsoleAppContainer
from . import settings, UpdateInfo
from .engine.tools.logger import log
from .engine.tools.lang import _
from .engine.tools.util import toString
from .engine.addon import ToolsAddon, VideoAddon, XBMCAddon
from .engine.exceptions.updater import UpdateXMLVersionError, UpdateXMLNoUpdateUrl
from .engine.downloader import DownloadManager
from .engine.tools.task import Task
from .engine.httpserver import ArchivCZSKHttpServer
from .gui.content import ArchivCZSKContentScreen
from .gui.info import openPartialChangelog
from .gui.icon import ArchivCZSKDonateScreen
from .engine.parental import parental_pin
from .compat import DMM_IMAGE, VTI_IMAGE, eConnectCallback
from .engine.updater import ArchivUpdater
from .engine.bgservice import BGServiceTask
from .engine.license import ArchivCZSKLicense
from .engine.usage import UsageStats
from .gsession import GlobalSession

def have_valid_ssl_certificates():
	# outdated images don't have Let's Encrypt CA, so make a simple check here
	import requests

	ret = True
	try:
#		we have options to disable SSL verification, so this is not needed for now
#		requests.get('https://ntp.org', timeout=3)
		pass
	except requests.exceptions.SSLError:
		ret = False
	except:
		pass

	return ret

class ArchivCZSK():

	__loaded = False
	__need_restart = False
	__reload_needed = False
	force_skin_reload = False

	__repositories = {}
	__addons = {}

	@staticmethod
	def isLoaded():
		return ArchivCZSK.__loaded

	@staticmethod
	def load_repositories():
		log.debug("Loading repositories")
		from .engine.repository import Repository

		# list directories in settings.REPOSITORY_PATH and search for directory containing addon.xml file = repository
		for repo in [f for f in os.listdir(settings.REPOSITORY_PATH) if os.path.isdir(os.path.join(settings.REPOSITORY_PATH, f))]:
			repo_xml = os.path.join(settings.REPOSITORY_PATH, repo, 'addon.xml')
			if os.path.isfile( repo_xml ):
				try:
					repository = Repository(repo_xml)
				except Exception:
					log.error("Failed to load repository: %s\n%s" % (repo, traceback.format_exc()))
				else:
					ArchivCZSK.add_repository(repository)
					if repository.path not in sys.path:
						sys.path.append(repository.path)

	@staticmethod
	def process_skin(skin_path_orig, skin_path_new):
		import re
		from enigma import getDesktop
		desktop_width = getDesktop(0).size().width()
		desktop_height = getDesktop(0).size().height()
		log.logDebug("Screen resolution: {}x{} px".format(desktop_width, desktop_height))

		r = float(desktop_width) / 1920.0 # we assume, that skin is prepared for FullHD resolution

		log.logDebug("Ratio used for skin processing: {:.4f}".format(r))

		def apply_skin_ratio(skin_data):
			# Define the pattern to search for *[-]number*
			pattern = r'\*(-?\d+)\*'

			# Function to replace the matched pattern
			def multiply_and_replace(match):
				number = int(match.group(1))
				result = int(round(number * r))
				return str(result)

			# Use re.sub to replace all occurrences of the pattern
			return re.sub(pattern, multiply_and_replace, skin_data)

		def apply_font_ratio(skin_data):
			f = r * (float(config.plugins.archivCZSK.font_size.value) / 100)
			# Define the pattern to search for *fnumber*
			pattern = r'\*f(\d+)\*'

			# Function to replace the matched pattern
			def multiply_and_replace(match):
				number = int(match.group(1))
				result = int(round(number * f))
				return str(result)

			# Use re.sub to replace all occurrences of the pattern
			return re.sub(pattern, multiply_and_replace, skin_data)

		def fix_dmm_params(match):
			if DMM_IMAGE:
				return ''
			else:
				return match.group(1)

		def btscale_skin_fix(skin_data):
			# flags parameter in MultiContentEntryPixmapAlphaTest is totaly incompatible between images
			# OpenXXX images use flags with BT_* values
			# dreambox uses scale_flags with SCALE_* (default is SCALE_RATIO, which is OK for us)
			# VTi uses options with only mumeric values
			try:
				from Components.MultiContent import MultiContentEntryPixmapAlphaTest

				try:
					from enigma import BT_SCALE
					scale_flags = str(BT_SCALE)
				except:
					scale_flags = "0"

				try:
					# try OpenXXX images, but for sure replace BT_SCALE with numeric value
					MultiContentEntryPixmapAlphaTest(flags=0)
					skin_data = skin_data.replace('flags=BT_SCALE', 'flags='+scale_flags)
				except:
					try:
						# try VTi images and replace BT_SCALE with numeric value
						MultiContentEntryPixmapAlphaTest(options=0)
						skin_data = skin_data.replace('flags=BT_SCALE', 'options='+scale_flags)
					except:
						# other images without flags support + dreambox with SCALE_RATIO default
						skin_data = skin_data.replace(', flags=BT_SCALE', '')
			except:
				log.error(traceback.format_exc())

			return skin_data

		with open(skin_path_orig, 'r') as f:
			skin_data = re.sub(r'!(font=.+?)!', fix_dmm_params, f.read())
			skin_data = apply_skin_ratio(skin_data)
			skin_data = apply_font_ratio(skin_data)
			skin_data = btscale_skin_fix(skin_data)

			if not DMM_IMAGE:
				# values of scale flags are incompatible between images
				skin_data = skin_data.replace('scale="stretch"', 'scale="scale"')

			if config.plugins.archivCZSK.skin_from_system.value:
				log.debug("Setting skin background color to system default")
				skin_data = skin_data.replace('backgroundColor="#0a000000"', '')
			else:
				bgc = '{:02x}{:02x}{:02x}'.format(*config.plugins.archivCZSK.skin_background_color.value)
				if len(bgc) != 6:
					bgc = '000000'
				log.debug("Setting skin background color to: %s" % bgc)
				bgt = '{:02x}'.format(int(float(255 * int(config.plugins.archivCZSK.skin_transparency.value)) / 100.0 ))
				if len(bgt) != 2:
					bgt = '00'
				log.debug("Setting skin background transparency to: %s" % bgt)

				# apply transparency setting - we assume, that default skin transparency is 0a000000 and this value isn't used for anything else
				skin_data = skin_data.replace('"#0a000000"', '"#{}{}"'.format(bgt, bgc))

		with open(skin_path_new, 'w') as f:
			f.write(skin_data)


	@staticmethod
	def load_skin():
		try:
			skin_path = os.path.join(settings.SKIN_PATH, config.plugins.archivCZSK.skin.value + ".xml")

			if (not ArchivCZSKLicense.get_instance().check_level(ArchivCZSKLicense.LEVEL_DEVELOPER)) or (not os.path.isfile(skin_path)):
				skin_path = os.path.join(settings.SKIN_PATH, 'default.xml')

			tmp_skin_path = '/tmp/archivczsk_skin.xml'

			log.info("Processing skin %s" % skin_path)
			ArchivCZSK.process_skin(skin_path, tmp_skin_path)

			log.info("Loading skin %s" % skin_path)
			if VTI_IMAGE or DMM_IMAGE:
				try:
					# workaround for VTi and DMM - allows updating skin without gui restart
					from skin import dom_skins

					for i, s in enumerate(dom_skins):
						if s[0] == '/tmp/' and s[1].find('screen').attrib.get('name','').startswith('ArchivCZSK'):
							log.debug("Removing ArchivCZSK skin from dom_skins")
							dom_skins.pop(i)
							break

					if VTI_IMAGE:
						# for VTi also this is needed ...
						from skin import dom_screens
						for s in list(dom_screens.keys()):
							if s.startswith('ArchivCZSK'):
								log.debug("Removing screen %s from dom cache" % s)
								del dom_screens[s]
				except:
					log.error(traceback.format_exc())

			loadSkin(tmp_skin_path)

			os.remove(tmp_skin_path)
		except:
			log.logError("Load plugin skin failed.\n%s" % traceback.format_exc())

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
	def remove_repository(repository):
		del ArchivCZSK.__repositories[repository.id]

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
	def get_tools_addons():
		return [addon for addon in ArchivCZSK.get_addons() if isinstance(addon, ToolsAddon)]

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
		if config.plugins.archivCZSK.preload.value == False:
			return

		log.info("Starting addons preload")

		for addon in ArchivCZSK.get_video_addons():
			try:
				if addon.is_enabled():
					addon.provider.preload_addon()
			except:
				log.logError("Preload of addon %s failed:\n%s" % (addon, traceback.format_exc()))

	@staticmethod
	def init_addons():
		log.debug("Initialising adddons")

		for addon in ArchivCZSK.get_tools_addons():
			try:
				if addon.is_enabled():
					log.debug("Initialising tools addon: %s" % addon)
					addon.init()
			except:
				log.logError("Init of addon %s failed:\n%s" % (addon, traceback.format_exc()))

	@staticmethod
	def close_addons():
		for a in ArchivCZSK.get_addons():
			log.debug("Closing addon %s" % a.id)
			a.close()
			ArchivCZSK.remove_addon(a)

		ArchivCZSK.__addons = {}

	@staticmethod
	def close_repositories():
		for r in ArchivCZSK.get_repositories():
			log.debug("Closing repository %s" % r.id)
			ArchivCZSK.remove_repository(r)

		ArchivCZSK.__repositories = {}

	@staticmethod
	def check_dependencies(force=False):
		if force or ArchivCZSK.was_upgraded() != None:
			try:
				from .settings import PLUGIN_PATH
				eConsoleAppContainer().execute(os.path.join( PLUGIN_PATH, 'script', 'install_dependencies.sh'))
			except:
				log.error(traceback.format_exc())

	@staticmethod
	def was_upgraded(clear_upgrade_flag=False):
		from .settings import PLUGIN_PATH
		first_start_file = os.path.join( PLUGIN_PATH, '.first_start')
		prev_ver = None

		if os.path.isfile( first_start_file ):
			try:
				prev_ver = open(first_start_file).readline().strip()
			except:
				prev_ver = ''

			if clear_upgrade_flag:
				os.remove( first_start_file )

		return prev_ver

	@staticmethod
	def reload_needed(needed=None):
		if needed != None:
			ArchivCZSK.__reload_needed = needed

		return ArchivCZSK.__reload_needed

	@staticmethod
	def start(session):
		if ArchivCZSK.isLoaded():
			return

		log.info("Starting ArchivCZSK ...")
		start_time = time.time()
		BGServiceTask.startMessagePump()
		BGServiceTask.startServiceThread()
		ArchivCZSKLicense.start()
		ArchivCZSKHttpServer.start()
		ArchivCZSK.load_skin()
		ArchivCZSK.load_repositories()
		ArchivCZSK.init_addons()
		log.debug("Starting stats collection")
		UsageStats.start()
		ArchivCZSK.preload_addons()

		if config.plugins.archivCZSK.epg_viewer.value:
			try:
				log.debug("Injecting ArchivCZSK interface to system's EPG")
				from .engine.epg_integrator import inject_archive_into_epg
				inject_archive_into_epg()
			except:
				log.error(traceback.format_exc())

		log.debug("Initialising downloader")
		GlobalSession.setSession(session)
		# saving active downloads to session
		if not hasattr(session, 'archivCZSKdownloads'):
			session.archivCZSKdownloads = []

		if DownloadManager.getInstance() is None:
			DownloadManager(session.archivCZSKdownloads)

		try:
			log.info("Collecting STB info")
			from .engine.tools.stbinfo import stbinfo
			log.info('STB info:\n%s' % stbinfo.to_string())
		except:
			pass

		ArchivCZSK.__loaded = True
		log.info("ArchivCZSK started in {:.02f} seconds".format(time.time() - start_time))
		return

	@staticmethod
	def stop(stop_cbk=None):
		if not ArchivCZSK.isLoaded():
			return

		log.info("Stopping ArchivCZSK ...")
		ArchivCZSK.close_addons()
		ArchivCZSK.close_repositories()
		UsageStats.stop()
		ArchivCZSKLicense.stop()
		BGServiceTask.stopServiceThread()
		BGServiceTask.stopMessagePump()
		ArchivCZSK.__loaded = False
		DownloadManager.instance = None
		ArchivCZSKHttpServer.stop(stop_cbk)
		log.info("ArchivCZSK stopped")
		return

	@staticmethod
	def unload():
		log.stop()
		modules_to_reload = [k for k, m in sys.modules.items() if 'archivCZSK' in str(m)]
		for m in modules_to_reload:
			del sys.modules[m]

		try:
			from importlib import invalidate_caches
			invalidate_caches()
		except:
			pass

	@staticmethod
	def run(session):
		ArchivCZSK.start(session)
		def runArchivCZSK(callback = None):
			ArchivCZSK(session)

		lastIconDUtcCfg = config.plugins.archivCZSK.lastIconDShowMessage

		monthSeconds = 60 * 60 * 24 * 30

		if ArchivCZSKLicense.get_instance().is_valid() == False and (lastIconDUtcCfg.value == 0 or (int(time.time()) - lastIconDUtcCfg.value > monthSeconds)):
			lastIconDUtcCfg.value = int(time.time())
			lastIconDUtcCfg.save()
			session.openWithCallback(runArchivCZSK, ArchivCZSKDonateScreen, countdown=10)
		else:
			runArchivCZSK()


	def __init__(self, session):
		self.session = session
		self.to_update_addons = []
		self.updated_addons = []

		if ArchivCZSK.__need_restart:
			self.ask_restart_e2()
		else:
			if ArchivCZSK.force_skin_reload:
				ArchivCZSK.load_skin()
				ArchivCZSK.force_skin_reload = False

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
			except UpdateXMLNoUpdateUrl:
				log.info('Repository %s has no update URL set - addons update is for this repository disabled', repository)
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
				"%s %s? (%s)\n\n%s" % (_("Do you want to update"), _("addons"), len(self.to_update_addons), toString(update_string)),
				type = MessageBox.TYPE_YESNO)

	def update_addons(self, callback=None, verbose=True):
		if not callback:
			self.open_archive_screen()
		else:
			updated_string = self._update_addons()
			self._cleanup_addons()
			self.session.openWithCallback(self.ask_restart_e2,
					MessageBox,
					"%s: (%s/%s):\n\n%s" % (_("Following addons were updated"), len(self.updated_addons), len(self.to_update_addons), toString(updated_string)),
					type=MessageBox.TYPE_INFO)

	def _update_addons(self):
		self.updated_addons = []
		for addon in self.to_update_addons:
			updated = False
			try:
				updated = addon.update()
			except Exception:
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

	def _cleanup_addons(self):
		if config.plugins.archivCZSK.cleanupBrokenAddons.value:
			for addon in self.get_addons():
				if addon.info.broken and not addon.supported:
					log.logInfo("Addon %s is broken and not supported - removing" % addon.id)
					addon.remove()

	def ask_restart_e2(self, callback=None):
		if config.plugins.archivCZSK.no_restart.value:
			self.reload_addons(self.updated_addons)
			self.updated_addons = []
			self.open_archive_screen()
		else:
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
		def first_start_handled(callback=None):
			# first screen to open when starting plugin,
			# so we start worker thread where we can run our tasks(ie. loading archives)
			Task.startWorkerThread()
			parental_pin.lock_pin()
			self.session.openWithCallback(self.close_archive_screen, ArchivCZSKContentScreen, self)

		def check_player():
			# check if we have all players installed
			from .engine.player.info import videoPlayerInfo

			if DMM_IMAGE:
				msg = None
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

			return msg

		def check_ssl_certificates():
			if have_valid_ssl_certificates() == False:
				msg = _("You are using outdated image in your receiver without updated SSL certificates used for HTTPS communication. This can cause problems connecting to some sites or services. Outdated images are not supported and errors related to SSL communication will not be fixed. Update your image to latest version or switch to other image if current one doesn't get updates anymore.")
			else:
				msg = None

			return msg

		def fix_serviceapp_settings():
			try:
				for p in ('serviceexteplayer3', 'servicegstplayer'):
					c = config.plugins.serviceapp.options[p].hls_explorer

					if c.value:
						c.value = False
						c.save()
						log.info("Disabling HLS explorer for %s in ServiceApp settings" % p)
			except:
				pass

			return None

		def run_first_start_actions(actions, prev_ver):
			if len(actions) > 0:
				a = actions[0]
				next_a = actions[1:]

				msg = a()
				if msg:
					self.session.openWithCallback(lambda x: run_first_start_actions(next_a, prev_ver), MessageBox, msg, type=MessageBox.TYPE_INFO, enable_input=True)
				else:
					run_first_start_actions(next_a, prev_ver)
			else:
				changelog_path = os.path.join(settings.PLUGIN_PATH, 'changelog.txt')
				openPartialChangelog(self.session, first_start_handled, "ArchivCZSK", changelog_path, prev_ver)

		# check if this is first start after update
		prev_ver = self.was_upgraded(True)

		if prev_ver != None:
			self.check_dependencies(True)
			run_first_start_actions( [check_player, check_ssl_certificates, fix_serviceapp_settings], prev_ver )
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

	@staticmethod
	def reload_addons(addons):
		log.info("Starting addons reload")
		start_time = time.time()

		modules_to_reload = []
		for addon in addons:
			modules_to_reload.extend( [k for k, m in sys.modules.items() if addon.path in str(m)] )

		ArchivCZSK.close_addons()
		ArchivCZSK.close_repositories()

		for m in modules_to_reload:
			log.debug("Unloading module %s" % m)
			del sys.modules[m]

		ArchivCZSK.load_repositories()
		ArchivCZSK.init_addons()
		ArchivCZSK.preload_addons()

		log.info("Addons reloaded in {:.02f} seconds".format(time.time() - start_time))
