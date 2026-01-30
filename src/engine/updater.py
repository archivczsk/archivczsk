'''
Created on 25.6.2012
Updated on 28.10.2017 by chaoss

@author: marko
'''

import os
import shutil
import traceback
import threading
import json
from datetime import datetime, timedelta
from .tools import util, parser
from .tools.unzip import unzip_to_dir
from .tools.util import toString
from ..compat import eCompatTimer
from .exceptions.updater import UpdateXMLVersionError, UpdateXMLNoUpdateUrl
from .tools.logger import log
from .tools.lang import _
from .bgservice import AddonBackgroundService, callFromService
from ..py3compat import *

from Components.Console import Console
from Components.config import config
from Screens.MessageBox import MessageBox

def canCheckUpdate():
	limitHour = 4

	try:
		from .. import UpdateInfo

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

	return config.plugins.archivCZSK.archivAutoUpdate.value

class RunNext(object):
	def __init__(self, updateDialog):
		self.__updateDialog = updateDialog
		self.__cbk = None
		self.updateCheckTimer = eCompatTimer(self.cbk_wrapper)

	def stop_timers(self):
		log.debug("[RunNext] stopping timers")
		del self.updateCheckTimer

	def cbk_wrapper(self):
		if self.__cbk != None:
			cbk = self.__cbk
			self.__cbk = None
			self.updateCheckTimer.stop()
			log.debug("[RunNext] calling: %s" % str(cbk).split(' ')[2])
			cbk()
		else:
			log.debug("[RunNext] nothing to call - cbk is none")

	def run_next(self, cbk, msg=None):
		if msg:
			self.show_dialog(msg)
		else:
			self.close_dialog()

		self.__cbk = cbk
		log.debug("[RunNext] scheduling: %s" % str(cbk).split(' ')[2])
		self.updateCheckTimer.start(100)

	def show_dialog(self, msg):
		if self.__updateDialog != None:
			self.__updateDialog.set_status(msg)
			self.__updateDialog.show()

	def close_dialog(self):
		if self.__updateDialog != None:
			self.__updateDialog.hide()

class FakeSession(object):
	def openWithCallback(self, cbk, *args, **kwargs):
		def _run_cbk():
			self._t.stop()
			cbk(True)
			del self._t

		self._t = eCompatTimer(_run_cbk)
		self._t.start(100)


class ArchivUpdater(RunNext):
	def __init__(self, finish_cbk, update_dialog=None):
		super(ArchivUpdater, self).__init__(update_dialog)
		self.session = update_dialog.session if update_dialog else FakeSession()
		self.finish_cbk = finish_cbk
		self.tmpPath = config.plugins.archivCZSK.tmpPath.value
		if not self.tmpPath:
			self.tmpPath = "/tmp"

		self.tmpPath = "/tmp"
		self.__console = None
		self.remote_version = ""
		self.remote_date = ""
		self.updateXmlFilePath = os.path.join(self.tmpPath, 'archivczskupdate.xml')
		self.updateIpkFilePathTemplate = os.path.join(self.tmpPath, 'archivczsk_{version}-{date}.ipk')
		self.updateIpkFilePath = None

		self.updateXml = "https://raw.githubusercontent.com/{update_repository}/archivczsk/{update_branch}/build/ipk/latest.xml"
		self.updateIpk = "https://raw.githubusercontent.com/{update_repository}/archivczsk/{update_branch}/build/ipk/archivczsk_{version}-{date}.ipk"

		self.needUpdate = False

		if os.path.isfile( '/usr/bin/dpkg' ):
			self.pkgInstallCmd = 'dpkg --install --force-all {update_file}'
			self.updateMode = 'dpkg'
		else: #if os.path.isfile( '/usr/bin/opkg' ):
			self.pkgInstallCmd = 'opkg install --force-overwrite --force-depends --force-downgrade --force-reinstall {update_file}'
			self.updateMode = 'opkg'

	def checkUpdate(self):
		self.run_next(self.checkUpdateStarted, _("Checking for updates"))

	def checkUpdateStarted(self):
		try:
			if self.downloadUpdateXml():
				from ..version import version
				local_version = version
				xmlroot = util.load_xml(self.updateXmlFilePath).getroot()
				self.remote_version = xmlroot.attrib.get('version')
				self.remote_date = xmlroot.attrib.get('date')

				log.logDebug("ArchivUpdater remote date: '%s'" % self.remote_date )
				log.logDebug("ArchivUpdater version local/remote: %s/%s" % (local_version, self.remote_version))

				if util.check_version(local_version, self.remote_version):
					self.needUpdate = True
				else:
					self.needUpdate = False
			else:
				self.needUpdate = False


		except:
			log.logError("ArchivUpdater update failed.\n%s" % traceback.format_exc())

		self.run_next(self.checkUpdateFinished, _("New version found") if self.needUpdate else _("No update found"))

	def checkUpdateFinished(self):
		if self.needUpdate:
			log.logInfo("ArchivUpdater update found...%s"%self.remote_version)
			strMsg = "%s %s?" %(_("Do you want to update ArchivCZSK to version"), toString(self.remote_version))
			self.session.openWithCallback(
				self.processUpdateArchivYesNoAnswer,
				MessageBox,
				strMsg,
				type = MessageBox.TYPE_YESNO)
		else:
			self.continueToArchiv()

	def processUpdateArchivYesNoAnswer(self, callback=None):
		if not callback:
			log.logDebug("ArchivUpdater update canceled.")
			self.continueToArchiv()
		else:
			self.run_next(self.processDownloadIpk, _("Downloading update package"))

	def processDownloadIpk(self):
		# download update package
		self.downloadSuccess = self.downloadIpk()

		if self.downloadSuccess:
			self.run_next(self.downloadIpkFinished, _("Updating ArchivCZSK using package manager"))
		else:
			self.run_next(self.downloadIpkFailed, _("Failed to download update package"))

	def downloadIpkFinished(self):
		if self.updateMode == 'dpkg':
			updateDebFilePath = self.updateIpkFilePath.replace('.ipk', '.deb')
			os.rename( self.updateIpkFilePath, updateDebFilePath )
			self.updateIpkFilePath = updateDebFilePath

		log.logInfo("Update command: %s" % self.pkgInstallCmd.replace('{update_file}', self.updateIpkFilePath) )
		try:
			self.__console = Console()
			self.__console.ePopen(self.pkgInstallCmd.replace('{update_file}', self.updateIpkFilePath), self.pkgInstallCmdFinished)
		except:
			log.error(traceback.format_exc())
			self.update_data = 'ePopen Failed'
			self.update_retval = -1
			self.updateArchivIpkFailed()

	def downloadIpkFailed(self):
		log.debug("[Updater] downloadIpkFailed - opening message box")
		self.session.openWithCallback(self.updateFailed,
				MessageBox,
				_("Failed to download ArchivCZSK update package"),
				type=MessageBox.TYPE_ERROR)


	def pkgInstallCmdFinished(self, data, retval, extra_args):
		log.debug("[Updater] pkgInstallCmdFinished with return code %s" % retval)
		self.update_retval = retval
		self.update_data = data

		if self.update_retval == 0:
			self.run_next(self.updateArchivIpkFinished, _("Update finished successfuly"))
		else:
			self.run_next(self.updateArchivIpkFailed, _("Update finished with error"))

	def updateArchivIpkFinished(self):
		log.logInfo("ArchivUpdater update ArchivCZSK from ipk/deb success. %s" % self.update_data)
		self.removeTempFiles()

		# restart enigma
		if config.plugins.archivCZSK.no_restart.value and self.check_api_level():
			self.session.openWithCallback(self.reloadArchiv, MessageBox, _("Update complete. Please start ArchivCZSK again."), type=MessageBox.TYPE_INFO)
		else:
			self.session.openWithCallback(self.restartArchiv, MessageBox, _("Update ArchivCZSK complete."), type=MessageBox.TYPE_INFO)

	def restartArchiv(self, *args):
		self.stop_timers()
		self.finish_cbk('restart')

	def reloadArchiv(self, *args):
		self.close_dialog()
		self.stop_timers()
		# don't continue - reload is needed, so user needs to run ArchivCZSK again
		self.finish_cbk('reload')

	def updateArchivIpkFailed(self):
		log.logError("ArchivUpdater update ArchivCZSK from ipk/deb failed. %s ### retval=%s" % (self.update_data, self.update_retval))

		self.session.openWithCallback(self.updateFailed,
				MessageBox,
				_("Update ArchivCZSK failed. {cmd} returned error\n{msg}".format(cmd=self.updateMode, msg=self.update_data) ),
				type=MessageBox.TYPE_ERROR)

	def downloadUpdateXml(self):
		updateXml = self.updateXml.replace('{update_repository}', config.plugins.archivCZSK.update_repository.value ).replace('{update_branch}', config.plugins.archivCZSK.update_branch.value)
		log.debug("Checking ArchivCZSK update from: %s" % updateXml)

		try:
			util.download_to_file(updateXml, self.updateXmlFilePath, timeout=config.plugins.archivCZSK.updateTimeout.value)
			return True
		except Exception:
			log.logError("ArchivUpdater download archiv update xml failed.\n%s" % traceback.format_exc())
			return False

	def downloadIpk(self):
		try:
			updateIpk = self.updateIpk.replace('{update_repository}', config.plugins.archivCZSK.update_repository.value ).replace('{update_branch}', config.plugins.archivCZSK.update_branch.value)
			updateIpk = updateIpk.replace('{version}', self.remote_version).replace('{date}', self.remote_date)
			self.updateIpkFilePath = self.updateIpkFilePathTemplate.replace('{version}', self.remote_version).replace('{date}', self.remote_date)
			log.logDebug("ArchivUpdater downloading ipk %s to %s" % (updateIpk, self.updateIpkFilePath))
			util.download_to_file(updateIpk, self.updateIpkFilePath, timeout=config.plugins.archivCZSK.updateTimeout.value)
			return True
		except Exception:
			log.logError("ArchivUpdater download update ipk failed.\n%s" % traceback.format_exc())
			return False

	def updateFailed(self, callback=None):
		self.continueToArchiv()

	def continueToArchiv(self):
		self.removeTempFiles()
		self.stop_timers()
		self.finish_cbk('continue')

	def removeTempFiles(self):
		try:
			if os.path.isfile(self.updateXmlFilePath):
				os.remove(self.updateXmlFilePath)
			if self.updateIpkFilePath and os.path.isfile(self.updateIpkFilePath):
				os.remove(self.updateIpkFilePath)
		except:
			log.logError("ArchivUpdater remove temp files failed.\n%s" % traceback.format_exc())
			pass

	def check_api_level(self):
		from .. import version
		try:
			old_api_level = version.reload_api_level
		except:
			old_api_level = 1

		if is_py3:
			import importlib
			version = importlib.reload(version)
		else:
			version = reload(version)

		new_api_level = version.reload_api_level
		log.info("Old API level: %d" % old_api_level)
		log.info("New API level: %d" % new_api_level)
		return old_api_level == new_api_level


class AddonsUpdater(RunNext):
	def __init__(self, finish_cbk, update_dialog=None):
		super(AddonsUpdater, self).__init__(update_dialog)
		self.session = update_dialog.session if update_dialog else FakeSession()
		self.finish_cbk = finish_cbk
		self.updated_addons = []
		self.to_update_addons = []

	def checkUpdate(self):
		log.info("Checking addons update...")
		self.run_next(self.check_addon_updates, _("Checking for addons update"))

	def check_addon_updates(self, check_only=False):
		from ..archivczsk import ArchivCZSK
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
				log.error('error when checking updates for repository %s\n%s', (repository, traceback.format_exc()))
		for repository in ArchivCZSK.get_repositories():
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

		if not check_only:
			self.run_next(self.check_updates_finished, _("Some addons need update") if self.__update_string else _("All addons are up to date"))

	def check_updates_finished(self):
		update_string = self.__update_string
		del self.__update_string
		if update_string != '':
			self.ask_update_addons(update_string)
		else:
			self.continueToArchiv()

	def ask_update_addons(self, update_string):
		self.session.openWithCallback(
				self.ask_update_answer,
				MessageBox,
				"%s %s? (%s)\n\n%s" % (_("Do you want to update"), _("addons"), len(self.to_update_addons), toString(update_string)),
				type = MessageBox.TYPE_YESNO)

	def ask_update_answer(self, callback=None):
		if not callback:
			return self.continueToArchiv()

		self.updated_addons = []
		self.to_update_addons_len = len(self.to_update_addons)
		return self.run_addons_update()

	def run_addons_update(self):
		if self.to_update_addons:
			self.__addon = self.to_update_addons.pop()
			self.run_next(self.process_addon_update, _('Updating addon: {name}').format(name=self.__addon.name))
		else:
			update_string = '\n'.join(addon_u.name for addon_u in self.updated_addons)
			if len(self.updated_addons) > 5:
				update_string = '\n'.join(addon.name for addon in self.updated_addons[:6])
				update_string += "\n...\n..."

			self.__update_string = update_string
			self.run_next(self.cleanup_addons, _("Removing old broken and unsupported addons"))

	def process_addon_update(self):
		updated = False
		addon = self.__addon
		try:
			updated = addon.update()
		except Exception:
			log.logError("Update addon '%s' failed.\n%s" % (addon.id,traceback.format_exc()))
		else:
			if updated:
				self.updated_addons.append(addon)

		self.run_addons_update()

	def cleanup_addons(self):
		if config.plugins.archivCZSK.cleanupBrokenAddons.value:
			from ..archivczsk import ArchivCZSK
			for addon in ArchivCZSK.get_addons():
				if addon.info.broken and not addon.supported:
					log.logInfo("Addon %s is broken and not supported - removing" % addon.id)
					addon.remove()

		self.run_next(self.update_finished, _("Addons update finished"))

	def update_finished(self):
		updated_string = self.__update_string
		del self.__update_string

		self.session.openWithCallback(self.update_finished2,
				MessageBox,
				"%s: (%s/%s):\n\n%s" % (_("Following addons were updated"), len(self.updated_addons), self.to_update_addons_len, toString(updated_string)),
				type=MessageBox.TYPE_INFO)

	def update_finished2(self, *args):
		if config.plugins.archivCZSK.no_restart.value:
			self.run_next(self.reload_addons, _("Reloading addons. Please wait ..."))
		else:
			self.stop_timers()
			self.close_dialog()
			self.finish_cbk('restart')

	def reload_addons(self):
		from ..archivczsk import ArchivCZSK
		ArchivCZSK.reload_addons()
		self.updated_addons = []
		self.run_next(self.reread_remote_repositories, _("Addons were reloaded"))

	def reread_remote_repositories(self):
		self.check_addon_updates(True)
		self.continueToArchiv()

	def continueToArchiv(self):
		self.stop_timers()
		self.finish_cbk('continue')


class Updater(object):
	"""Updater for updating addons in repository, every repository has its own updater"""

	def __init__(self, repository, tmp_path):
		self.repository = repository
		self.remote_path = repository.update_datadir_url
		self.local_path = repository.path
		self.tmp_path = tmp_path
		self.update_xml_url = repository.update_xml_url
		self.update_xml_file = os.path.join(self.tmp_path, repository.id + 'addons.xml')
		self.update_authorization = repository.update_authorization
		self.remote_addons_dict = {}

	def check_addon(self, addon, update_xml=True):
		"""
		check if addon needs update and if its broken
		"""
		try:
			log.debug("[%s] checking updates" % addon.name)
			self._get_server_addon(addon, update_xml)

			broken = self.remote_addons_dict[addon.id]['broken']
			remote_version = self.remote_addons_dict[addon.id]['version']
			local_version = addon.version

			if util.check_version(local_version, remote_version):
				log.debug("[%s] update needed: local %s < remote %s" % (addon.name, local_version, remote_version))
				return True, broken
			else:
				log.debug("[%s] update not needed: local %s >= remote %s" % (addon.name, local_version, remote_version))
			return False, broken
		except:
			log.logError("[%s] update failed\n%s" % (addon.name, traceback.format_exc()))
			raise

	def update_addon(self, addon):
		"""updates addon"""

		log.debug("[%s] starting update" % addon.name)
		self._get_server_addon(addon)

		# real path where addon is installed
		local_base = os.path.join(self.local_path, addon.relative_path)

		# path created by addon.id - legacy (addon.id and directory where addon is installed can be different)
		local_base_id = os.path.join(self.local_path, addon.id)
		zip_file = self._download(addon)

		if zip_file is not None and os.path.isfile(zip_file):
			# remove directory based on dir where addon is installed
			if os.path.isdir(local_base):
				shutil.rmtree(local_base)

			# remove directory based od addon id
			if os.path.isdir(local_base_id):
				shutil.rmtree(local_base_id)

			unzip_to_dir(zip_file, self.local_path)

			# store addon's previous version - used to show changelog on first run
			if os.path.isdir(local_base):
				# this check is needed, because if we install new addon (not already installed) we only guess addon.relative_path
				with open(os.path.join(local_base, '.update_ver'), 'w') as f:
					f.write(addon.version)

			log.debug("[%s] successfully updated to version %s" % (addon.name, self.remote_addons_dict[addon.id]['version']))
			os.remove(zip_file)
			return True
		log.debug("[%s] failed to update to version %s" % (addon.name, addon.version))
		return False

	def remove_addon(self, addon):
		"""removes addon"""

		log.debug("[%s] removing addon" % addon.name)

		# real path where addon is installed
		local_base = os.path.join(self.local_path, addon.relative_path)

		if os.path.isdir(local_base):
			# remove directory based on dir where addon is installed
			shutil.rmtree(local_base)
			log.debug("[%s] removed" % addon.name)
		else:
			log.error("[%s] addons local directory not found" % addon.name)

	def check_addons(self, new=True):
		"""checks every addon in repository, and update its state accordingly"""
		log.debug('checking addons')
		update_needed = []
		self._get_server_addons()
		for addon_id in list(self.remote_addons_dict.keys()):
			remote_addon = self.remote_addons_dict[addon_id]
			if remote_addon['id'] in self.repository._addons:
				local_addon = self.repository.get_addon(addon_id)
				local_addon.supported = remote_addon.get('supported', True)

				if local_addon.supported and local_addon.version == remote_addon['version']:
					local_addon.set_remote_hash(remote_addon.get('hash'))

				# we need to always call check_addon(), because it sets broken message from remote repository
				if local_addon.check_update(False) and local_addon.supported:
					update_needed.append(local_addon)

			elif new:
				if not remote_addon['broken']:
					log.debug("[%s] not in local repository, adding dummy Addon to update" % remote_addon['name'])
					new_addon = DummyAddon(self.repository, remote_addon['id'], remote_addon['name'], remote_addon['version'], remote_addon.get('hash'))
					update_needed.append(new_addon)
			else:
				log.debug("[%s] downloading of new addons disabled - skipping" % remote_addon['id'])

		for addon_id in self.repository._addons:
			if addon_id not in list(self.remote_addons_dict.keys()):
				log.debug("[%s] not found in remote repository - marking as not supported" % addon_id)
				local_addon = self.repository.get_addon(addon_id)
				local_addon.supported = False

		return update_needed


	def update_addons(self, addons):
		"""update addons in repository, according to their state"""
		log.debug('updating addons')
		update_success = []
		for addon in addons:
			if addon.need_update():
				if addon.update():
					update_success.append(update_success)
		return update_success



	def _get_server_addons(self):
		"""loads info about addons from remote repository to remote_addons_dict"""
		self._download_update_xml()

		pars = parser.XBMCMultiAddonXMLParser(self.update_xml_file)
		self.remote_addons_dict = pars.parse_addons()
		os.remove(self.update_xml_file)


	def _get_server_addon(self, addon, load_again=False):
		"""load info about addon from remote repository"""

		if load_again:
			self._get_server_addons()

		if addon.id not in self.remote_addons_dict:
			pars = parser.XBMCMultiAddonXMLParser(self.update_xml_url)
			addon_el = pars.find_addon(addon.id)
			self.remote_addons_dict[addon.id] = pars.parse(addon_el)


	def _download(self, addon):
		"""downloads addon zipfile to tmp"""
		zip_filename = "%s-%s.zip" % (addon.id, self.remote_addons_dict[addon.id]['version'])

		remote_base = self.remote_path + '/' + addon.id
		tmp_base = os.path.normpath(os.path.join(self.tmp_path, addon.relative_path))

		local_file = os.path.join(tmp_base, zip_filename)
		remote_file = remote_base + '/' + zip_filename

		# if update data path contains variables configurable by user, then set it here
		remote_file = remote_file.replace('{update_repository}', config.plugins.archivCZSK.update_repository.value ).replace('{update_branch}', config.plugins.archivCZSK.update_branch.value)

		headers = {}
		if self.update_authorization:
			headers['Authorization'] = self.update_authorization

		try:
			util.download_to_file(remote_file, local_file, debugfnc=log.debug, timeout=config.plugins.archivCZSK.updateTimeout.value, headers=headers)
		except:
			shutil.rmtree(tmp_base)
			return None
		return local_file


	def _download_update_xml(self):
		"""downloads update xml of repository"""

		if not self.update_xml_url:
			raise UpdateXMLNoUpdateUrl()

		# if update xml path contains variables configurable by user, then set it here
		update_xml_url = self.update_xml_url.replace('{update_repository}', config.plugins.archivCZSK.update_repository.value ).replace('{update_branch}', config.plugins.archivCZSK.update_branch.value)

		log.debug("[%s] checking addons updates from: %s" % (self.repository.name, update_xml_url))

		headers = {}
		if self.update_authorization:
			headers['Authorization'] = self.update_authorization

		try:
			util.download_to_file(update_xml_url, self.update_xml_file, debugfnc=log.debug, timeout=config.plugins.archivCZSK.updateTimeout.value, headers=headers)
		except Exception:
			log.error('[%s] download update xml failed' % self.repository.name)
			log.logError( traceback.format_exc())
			raise UpdateXMLVersionError()


class DummyAddon(object):
	"""to add new addon to repository"""
	def __init__(self, repository, addon_id, name, version, hash=None):
		self.repository = repository
		self.name = name
		self.id = addon_id
		self.relative_path = self.id.replace('.','_')
		self.version = version
		self.path = os.path.normpath(os.path.join(repository.path, self.relative_path))
		self.__need_update = True
		self.remote_hash = hash

	def need_update(self):
		return True

	def update(self):
		return self.repository._updater.update_addon(self)

class HeadlessUpdater(object):
	__instance = None

	@staticmethod
	def start():
		if HeadlessUpdater.__instance == None:
			log.debug("Starting headless updater")
			HeadlessUpdater.__instance = HeadlessUpdater()

	@staticmethod
	def stop():
		if HeadlessUpdater.__instance != None:
			log.debug("Stopping headless updater")
			HeadlessUpdater.__instance.bgservice.stop_all()
			HeadlessUpdater.__instance = None

	@staticmethod
	def get_instance():
		return HeadlessUpdater.__instance

	def __init__(self):
		self.bgservice = AddonBackgroundService('HeadlessUpdater')
		self.bgservice.run_delayed('HeadlessUpdateStart', 10, None, self.start_loop)
		self.standby_flag = False
		self.archiv_updated = False
		self.addons_updated = False
		self.archiv_update_skipped = False
		self.load_settings()

	def start_loop(self):
		if self.standby_flag:
			self.switch_to_standby()

		self.bgservice.run_in_loop('HeadlessUpdate', 3637, self.check_updates)

	def check_updates(self, force=False):
		@callFromService
		def _check_updates_in_reactor_thread():
			self.check_archiv_update()

		if force:
			_check_updates_in_reactor_thread()
			return

		if not config.plugins.archivCZSK.archivAutoUpdate.value:
			log.debug("ArchivCZSK update is disabled - giving up ...")
			return

		if not config.plugins.archivCZSK.headless_update.value:
			log.debug("Headless update is disabled - giving up ...")
			return

		# check if enigma is in standby mode
		from Screens.Standby import inStandby
		if not inStandby:
			log.info("Not checking for updates - Enigma is not in standby")
			return

		# check, if we can run update now
		if canCheckUpdate():
			_check_updates_in_reactor_thread()

	def check_archiv_update(self):
		if self.archiv_updated:
			# disable archiv update check on first run after update, because if update failed for some reason, then without this update will end up in endless loop
			self.archiv_updated = False
			self.archiv_update_skipped = True
			return self.archiv_update_finished()

		self.archiv_update_skipped = False

		try:
			log.info("Checking ArchivCZSK update ...")
			self.__upd = ArchivUpdater(self.archiv_update_finished)
			self.__upd.checkUpdate()
		except:
			log.error(traceback.format_exc())
			self.archiv_update_finished()


	def archiv_update_finished(self, result='continue'):
		self.__upd = None
		if result == 'continue':
			self.check_addons_update()
		else:
			self.process_result(result, archiv_updated=True)

	def check_addons_update(self):
		if self.addons_updated:
			# disable addons update check on first run after update, because if update failed for some reason, then without this update will end up in endless loop
			self.addons_updated = False
			self.addons_update_finished()

		try:
			log.info("Checking addons update ...")
			self.__upd = AddonsUpdater(self.addons_update_finished)
			self.__upd.checkUpdate()
		except:
			log.error(traceback.format_exc())
			self.addons_update_finished()

	def addons_update_finished(self, result='continue'):
		self.__upd = None
		self.process_result(result, addons_updated=True)

	def process_result(self, result, archiv_updated=False, addons_updated=False):
		if result == 'continue':
			pass
		elif result in ('restart', 'reload'):
			self.save_settings(archiv_updated, addons_updated)
			log.info("Scheduling enigma restart ...")
			self.restart_enigma()

		else:
			log.error('FATAL: Unknown update result: "%s" - don\'t know how to continue' % result )

	def disable_tv_wakeup(self):
		file_name = '/tmp/powerup_without_waking_tv.txt'
		# disable TV wakeup (works for OpenATV)
		if os.path.isfile(file_name):
			with open(file_name, 'w') as f:
				f.write('True')

	def save_settings(self, archiv_updated=False, addons_updated=False):
		from Screens.Standby import inStandby

		file_name = '/tmp/archivczsk_update.json'
		s = {
			'switch_to_standby': inStandby is not None,
			'archiv_updated': archiv_updated or self.archiv_update_skipped,
			'addons_updated': addons_updated
		}

		with open(file_name, 'w') as f:
			json.dump(s, f)

	def load_settings(self):
		file_name = '/tmp/archivczsk_update.json'

		try:
			with open(file_name, 'r') as f:
				s = json.load(f)

			self.standby_flag = s.get('switch_to_standby', False)
			self.archiv_updated = s.get('archiv_updated', False)
			self.addons_updated = s.get('addons_updated', False)

			os.remove(file_name)
		except:
			pass


	def restart_enigma(self):
		from Screens.Standby import TryQuitMainloop
		from ..gsession import GlobalSession

		self.disable_tv_wakeup()

		log.info("Restarting enigma ...")
		GlobalSession.getSession().open(TryQuitMainloop, 3)

	def switch_to_standby(self):
		log.info("Switching enigma into standby ...")

		@callFromService
		def _switch_to_standby_in_reactor_thread():
			from Screens.Standby import Standby, inStandby
			if not inStandby:
				from ..gsession import GlobalSession
				GlobalSession.getSession().open(Standby)

		_switch_to_standby_in_reactor_thread()
