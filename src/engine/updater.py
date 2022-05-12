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

from Plugins.Extensions.archivCZSK.engine.exceptions.updater import UpdateXMLVersionError
from Plugins.Extensions.archivCZSK import _, log, toString, settings
from Components.Console import Console
from Components.config import config, ConfigSubsection, ConfigText, ConfigYesNo
from Screens.MessageBox import MessageBox

# [0] = user, [1] = branch
github_params=('archivczsk', 'main')

class ArchivUpdater(object):
	def __init__(self, archivInstance):
		self.archiv = archivInstance
		self.tmpPath = config.plugins.archivCZSK.tmpPath.value
		if not self.tmpPath:
			self.tmpPath = "/tmp"
			
		self.tmpPath = "/tmp"
		self.__console = None
		self.__updateDialog = None
		self.remote_version = ""
		self.remote_date = ""
		self.updateXmlFilePath = os.path.join(self.tmpPath, 'archivczskupdate.xml')
		self.updateIpkFilePath = os.path.join(self.tmpPath, 'archivczsk_{version}-{date}.ipk')
		
		self.updateXml = "https://raw.githubusercontent.com/%s/archivczsk/%s/build/ipk/latest.xml" % github_params
		self.updateIpk = "https://raw.githubusercontent.com/%s/archivczsk/%s/build/ipk/archivczsk_{version}-{date}.ipk" % github_params
		
		self.needUpdate = False
		
		if os.path.isfile( '/usr/bin/dpkg' ):
			self.pkgInstallCmd = 'dpkg --install --force-all {update_file} && apt-get -y update && apt-get -f -y install'
			self.updateMode = 'dpkg'
		else: #if os.path.isfile( '/usr/bin/opkg' ):
			self.pkgInstallCmd = 'opkg update; opkg install --force-overwrite --force-depends --force-downgrade --force-reinstall {update_file}'
			self.updateMode = 'opkg'
	
	def checkUpdate(self):
		self.__updateDialog = self.archiv.session.openWithCallback(self.checkUpdateFinished, MessageBox, 
								   _("Checking for updates"), 
								   type=MessageBox.TYPE_INFO, 
								   enable_input=False)

		try:
			if self.downloadUpdateXml():
				from Plugins.Extensions.archivCZSK.version import version
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

		# execution will continue in self.checkUpdateFinished()
		self.archiv.session.close(self.__updateDialog)
		

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
			self.__updateDialog = self.archiv.session.openWithCallback(self.downloadIpkFinished, MessageBox,
					   _("Downloading update package"), 
					   type=MessageBox.TYPE_INFO, 
					   enable_input=False)

			# download update package
			self.downloadSuccess = self.downloadIpk()
			
			# execution will continue in self.downloadIpkFinished()
			self.archiv.session.close(self.__updateDialog)

	def downloadIpkFinished(self):
		if self.downloadSuccess:
			self.__updateDialog = self.archiv.session.openWithCallback(self.updateArchivIpkFinished, MessageBox,
					   _("Updating archivCZSK using package manager"), 
					   type=MessageBox.TYPE_INFO, 
					   enable_input=False)

			if self.updateMode == 'dpkg':
				updateDebFilePath = self.updateIpkFilePath.replace('.ipk', '.deb')
				os.rename( self.updateIpkFilePath, updateDebFilePath )
				self.updateIpkFilePath = updateDebFilePath
			
			log.logInfo("Update command: %s" % self.pkgInstallCmd.replace('{update_file}', self.updateIpkFilePath) )
			self.__console = Console()
			self.__console.ePopen(self.pkgInstallCmd.replace('{update_file}', self.updateIpkFilePath), self.pkgInstallCmdFinished)
		else:
			strMsg = "%s" % _("Failed to download archivCZSK update package")
			self.archiv.session.openWithCallback(self.updateFailed,
					MessageBox,
					strMsg,
					type=MessageBox.TYPE_INFO)

	def pkgInstallCmdFinished(self, data, retval, extra_args):
		self.update_retval = retval
		self.update_data = data
		# close Message box - execution wil continue in updateArchivIpkFinished()
		self.archiv.session.close(self.__updateDialog)
	
	def updateArchivIpkFinished(self):
		if self.update_retval == 0:
			log.logInfo("ArchivUpdater update archivCZSK from ipk/deb success. %s" % self.update_data)
			self.removeTempFiles()

			# restart enigma
			strMsg = "%s" % _("Update archivCZSK complete.")
			self.archiv.session.openWithCallback(self.archiv.ask_restart_e2,
					MessageBox,
					strMsg,
					type=MessageBox.TYPE_INFO)

		else:
			log.logError("ArchivUpdater update archivCZSK from ipk/deb failed. %s ### retval=%s" % (self.update_data, self.update_retval))
			
			strMsg = "%s" % _("Update archivCZSK failed. %s returned error\n%s" % (self.updateMode, self.update_data) )
			
			self.archiv.session.openWithCallback(self.updateFailed,
					MessageBox,
					strMsg,
					type=MessageBox.TYPE_INFO)

	def downloadUpdateXml(self):
		try:
			util.download_to_file(self.updateXml, self.updateXmlFilePath)
			return True
		except Exception:
			log.logError("ArchivUpdater download archiv update xml failed.\n%s" % traceback.format_exc())
			return False
		
	def downloadIpk(self):
		try:
			self.updateIpk = self.updateIpk.replace('{version}', self.remote_version).replace('{date}', self.remote_date)
			self.updateIpkFilePath = self.updateIpkFilePath.replace('{version}', self.remote_version).replace('{date}', self.remote_date)
			log.logDebug("ArchivUpdater downloading ipk %s to %s" % (self.updateIpk, self.updateIpkFilePath))
			util.download_to_file(self.updateIpk, self.updateIpkFilePath)
			return True
		except Exception:
			log.logError("ArchivUpdater download update ipk failed.\n%s" % traceback.format_exc())
			return False
		
	def updateFailed(self, callback=None):
		self.continueToArchiv()

	def continueToArchiv(self):
		self.removeTempFiles()
			
		if config.plugins.archivCZSK.autoUpdate.value and self.archiv.canCheckUpdate(False):
			# check plugin updates
			self.archiv.download_commit()
		else:
			self.archiv.open_archive_screen()

	def removeTempFiles(self):
		try:
			if os.path.isfile(self.updateXmlFilePath):
				os.remove(self.updateXmlFilePath)
			if os.path.isfile(self.updateIpkFilePath):
				os.remove(self.updateIpkFilePath)
		except:
			log.logError("ArchivUpdater remove temp files failed.\n%s" % traceback.format_exc())
			pass

class Updater(object):
	"""Updater for updating addons in repository, every repository has its own updater"""
	
	def __init__(self, repository, tmp_path):
		self.repository = repository
		self.remote_path = repository.update_datadir_url
		self.local_path = repository.path
		self.tmp_path = tmp_path
		self.update_xml_url = repository.update_xml_url
		self.update_xml_file = os.path.join(self.tmp_path, 'addons.xml')
		self.remote_addons_dict = {}
	
	def check_addon(self, addon, update_xml=True):
		"""
		check if addon needs update and if its broken
		"""
		try:
			log.debug("checking updates for %s", addon.name)
			self._get_server_addon(addon, update_xml)
		
			broken = self.remote_addons_dict[addon.id]['broken']
			remote_version = self.remote_addons_dict[addon.id]['version']
			local_version = addon.version
		
			if util.check_version(local_version, remote_version):
				log.logDebug("Addon '%s' need update (local %s < remote %s)." % (addon.name, local_version, remote_version))
				log.debug("%s local version %s < remote version %s", addon.name, local_version, remote_version)
				log.debug("%s is not up to date", addon.name)
				return True, broken
			else:
				log.logDebug("Addon '%s' (%s) is up to date." % (addon.name, local_version))
				log.debug("%s local version %s >= remote version %s", addon.name, local_version, remote_version)
				log.debug("%s is up to date", addon.name)
			return False, broken
		except:
			log.logError("Check addon '%s' update failed.\n%s" % (addon.name, traceback.format_exc()))
			raise

	def update_addon(self, addon):
		"""updates addon"""
		
		log.debug("updating %s", addon.name)
		self._get_server_addon(addon)
	
		local_base = os.path.join(self.local_path, addon.id)		
		zip_file = self._download(addon)
		
		if zip_file is not None and os.path.isfile(zip_file):
			if os.path.isdir(local_base):
				shutil.rmtree(local_base)
			
			unzip_to_dir(zip_file, self.local_path)
			
			log.debug("%s was successfully updated to version %s", addon.name, self.remote_addons_dict[addon.id]['version'])
			return True
		log.debug("%s failed to update to version %s", addon.name, addon.version)
		return False
	
	
	def check_addons(self, new=True):
		"""checks every addon in repository, and update its state accordingly"""
		log.debug('checking addons')
		update_needed = []
		self._get_server_addons()
		for addon_id in list(self.remote_addons_dict.keys()):
			remote_addon = self.remote_addons_dict[addon_id]
			if remote_addon['id'] in self.repository._addons:
				local_addon = self.repository.get_addon(addon_id)
				if local_addon.check_update(False):
					update_needed.append(local_addon)
			elif new:
				log.debug("%s not in local repository, adding dummy Addon to update", remote_addon['name'])
				log.logDebug("'%s' not in local repository, adding Addon to update"%remote_addon['name'])
				new_addon = DummyAddon(self.repository, remote_addon['id'], remote_addon['name'], remote_addon['version'])
				update_needed.append(new_addon)
			else:
				log.debug("dont want new addons skipping %s", remote_addon['id'])

		for addon_id in self.repository._addons:
			if addon_id not in list(self.remote_addons_dict.keys()):
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
		log.logDebug("pre update xml")
		self._download_update_xml()
		log.logDebug("post update xml")
			
		pars = parser.XBMCMultiAddonXMLParser(self.update_xml_file)
		self.remote_addons_dict = pars.parse_addons()
			

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
		if remote_file.find('{commit}') != -1:
			from Plugins.Extensions.archivCZSK.settings import PLUGIN_PATH
			try:
				commit = open(os.path.join(PLUGIN_PATH, 'commit')).readline()[:-1]
			except Exception:
				commit = '4ff9ac15d461a885f13125125ea501f3b12eb05d'
			remote_file = remote_file.replace('{commit}', commit)

		try:
			util.download_to_file(remote_file, local_file, debugfnc=log.debug)
		except:
			shutil.rmtree(tmp_base)
			return None
		return local_file	   
			
			
	def _download_update_xml(self):
		"""downloads update xml of repository"""
		
		# hack for https github urls
		# since some receivers have have problems with https
		if self.update_xml_url.find('{commit}') != -1:
			try:
				commit = open(os.path.join(settings.PLUGIN_PATH, 'commit')).readline()[:-1]
			except Exception:
				commit = '4ff9ac15d461a885f13125125ea501f3b12eb05d'
			self.update_xml_url = self.update_xml_url.replace('{commit}', commit)
			
		try:
			util.download_to_file(self.update_xml_url, self.update_xml_file)
		except Exception:
			log.error('cannot download %s update xml', self.repository.name)
			raise UpdateXMLVersionError()
		

class DummyAddon(object):
	"""to add new addon to repository"""
	def __init__(self, repository, id, name, version):
		self.repository = repository
		self.name = name
		self.id = id
		self.relative_path = self.id
		self.version = version
		self.path = os.path.normpath(os.path.join(repository.path, self.relative_path))
		self.__need_update = True
		
	def need_update(self):
		return True
	
	def update(self):
		return self.repository._updater.update_addon(self)


