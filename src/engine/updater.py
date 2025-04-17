'''
Created on 25.6.2012
Updated on 28.10.2017 by chaoss

@author: marko
'''

import os
import shutil
import traceback
import threading
from .tools import util, parser
from .tools.unzip import unzip_to_dir
from .tools.util import toString
from enigma import eTimer
from ..compat import eConnectCallback
from .exceptions.updater import UpdateXMLVersionError, UpdateXMLNoUpdateUrl
from .tools.logger import log
from .tools.lang import _

from Components.Console import Console
from Components.config import config
from Screens.MessageBox import MessageBox

class RunNext(object):
	def __init__(self, updateDialog):
		self.__updateDialog = updateDialog

	def run_next(self, cbk, msg=None):
		# this is needed to make changes in GUI, because you need to return call to reactor
		def __cbk_wrapper():
			del self.updateCheckTimer
			del self.updateCheckTimer_conn
			cbk()

		if msg:
			self.show_dialog(msg)
		else:
			self.close_dialog()
		self.updateCheckTimer = eTimer()
		self.updateCheckTimer_conn = eConnectCallback(self.updateCheckTimer.timeout, __cbk_wrapper)
		self.updateCheckTimer.start(10, True)

	def show_dialog(self, msg):
		if self.__updateDialog != None:
			self.__updateDialog.set_status(msg)
			self.__updateDialog.show()

	def close_dialog(self):
		if self.__updateDialog != None:
			self.__updateDialog.hide()


class ArchivUpdater(RunNext):
	def __init__(self, archivInstance, finish_cbk, update_dialog=None):
		super(ArchivUpdater, self).__init__(update_dialog)
		self.archiv = archivInstance
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
			strMsg = "%s %s?" %(_("Do you want to update archivCZSK to version"), toString(self.remote_version))
			self.archiv.session.openWithCallback(
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
			self.run_next(self.downloadIpkFinished, _("Updating archivCZSK using package manager"))
		else:
			self.run_next(self.downloadIpkFailed, _("Failed to download update package"))

	def downloadIpkFinished(self):
		if self.updateMode == 'dpkg':
			updateDebFilePath = self.updateIpkFilePath.replace('.ipk', '.deb')
			os.rename( self.updateIpkFilePath, updateDebFilePath )
			self.updateIpkFilePath = updateDebFilePath

		log.logInfo("Update command: %s" % self.pkgInstallCmd.replace('{update_file}', self.updateIpkFilePath) )
		self.__console = Console()

		self.__console.ePopen(self.pkgInstallCmd.replace('{update_file}', self.updateIpkFilePath), self.pkgInstallCmdFinished)

	def downloadIpkFailed(self):
		self.archiv.session.openWithCallback(self.updateFailed,
				MessageBox,
				_("Failed to download archivCZSK update package"),
				type=MessageBox.TYPE_ERROR)


	def pkgInstallCmdFinished(self, data, retval, extra_args):
		self.update_retval = retval
		self.update_data = data

		if self.update_retval == 0:
			self.run_next(self.updateArchivIpkFinished, _("Update finished successfuly"))
		else:
			self.run_next(self.updateArchivIpkFailed, _("Update finished with error"))

	def updateArchivIpkFinished(self):
		log.logInfo("ArchivUpdater update archivCZSK from ipk/deb success. %s" % self.update_data)
		self.removeTempFiles()

		# restart enigma
		if config.plugins.archivCZSK.no_restart.value:
			self.archiv.session.openWithCallback(self.reloadArchiv, MessageBox, _("Update complete. Please start ArchivCZSK again."), type=MessageBox.TYPE_INFO)
		else:
			self.archiv.session.openWithCallback(self.restartArchiv, MessageBox, _("Update archivCZSK complete."), type=MessageBox.TYPE_INFO)

	def restartArchiv(self, *args):
		self.finish_cbk('restart')

	def reloadArchiv(self, *args):
		self.close_dialog()
		# don't continue - reload is needed, so user needs to run ArchivCZSK again
		self.finish_cbk('reload')

	def updateArchivIpkFailed(self):
		log.logError("ArchivUpdater update archivCZSK from ipk/deb failed. %s ### retval=%s" % (self.update_data, self.update_retval))

		self.archiv.session.openWithCallback(self.updateFailed,
				MessageBox,
				_("Update archivCZSK failed. {cmd} returned error\n{msg}".format(cmd=self.updateMode, msg=self.update_data) ),
				type=MessageBox.TYPE_ERROR)

	def downloadUpdateXml(self):
		updateXml = self.updateXml.replace('{update_repository}', config.plugins.archivCZSK.update_repository.value ).replace('{update_branch}', config.plugins.archivCZSK.update_branch.value)
		log.debug("Checking archivCZSK update from: %s" % updateXml)

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

class AddonsUpdater(RunNext):
	def __init__(self, archivInstance, finish_cbk, update_dialog=None):
		super(AddonsUpdater, self).__init__(update_dialog)
		self.archiv = archivInstance
		self.finish_cbk = finish_cbk
		self.updated_addons = []
		self.to_update_addons = []

	def checkUpdate(self):
		log.info("Checking addons update...")
		self.run_next(self.check_addon_updates, _("Checking for addons update"))

	def check_addon_updates(self):
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
		for repository in self.archiv.get_repositories():
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

		self.run_next(self.check_updates_finished, _("Some addons need update") if self.__update_string else _("All addons are up to date"))

	def check_updates_finished(self, callback=None):
		update_string = self.__update_string
		del self.__update_string
		if update_string != '':
			self.ask_update_addons(update_string)
		else:
			self.continueToArchiv()

	def ask_update_addons(self, update_string):
		self.archiv.session.openWithCallback(
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
			for addon in self.archiv.get_addons():
				if addon.info.broken and not addon.supported:
					log.logInfo("Addon %s is broken and not supported - removing" % addon.id)
					addon.remove()

		self.run_next(self.update_finished, _("Addons update finished"))

	def update_finished(self):
		updated_string = self.__update_string
		del self.__update_string

		self.archiv.session.openWithCallback(self.update_finished2,
				MessageBox,
				"%s: (%s/%s):\n\n%s" % (_("Following addons were updated"), len(self.updated_addons), self.to_update_addons_len, toString(updated_string)),
				type=MessageBox.TYPE_INFO)

	def update_finished2(self, *args):
		if config.plugins.archivCZSK.no_restart.value:
			self.run_next(self.reload_addons, _("Reloading addons. Please wait ..."))
		else:
			self.close_dialog()
			self.finish_cbk('restart')

	def reload_addons(self):
		self.archiv.reload_addons()
		self.updated_addons = []
		self.run_next(self.continueToArchiv, _("Addons were reloaded"))

	def continueToArchiv(self):
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
				if local_addon.version == remote_addon['version']:
					local_addon.set_remote_hash(remote_addon.get('hash'))
				if local_addon.check_update(False):
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
