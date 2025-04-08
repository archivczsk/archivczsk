'''
Created on 21.10.2012

@author: marko
'''
import os, traceback
from Components.config import config, ConfigSubsection, ConfigText

from .. import archivczsk
from .addon import AddonInfo, ToolsAddon, VideoAddon, VirtualVideoAddon
from .tools import parser
from .tools.logger import log
from . import updater

class Repository():

	"""
		Loads installed repository and its addons,
		can check and retrieve updates/downloads for addons in local repository
		from remote repository

	"""
	SUPPORTED_ADDONS = ['video', 'tools']

	def __init__(self, config_file):
		log.debug("initializing repository from %s" , config_file)
		pars = parser.XBMCAddonXMLParser(config_file)
		repo_dict = pars.parse()

		self.id = repo_dict['id']
		self.name = repo_dict['name']
		self.version = repo_dict['version']
		self.description = repo_dict['description']
		# every repository should have its update xml, to check versions and update/download addons
		self.update_xml_url = repo_dict['repo_addons_url']

		self.update_datadir_url = repo_dict['repo_datadir_url']
		self.update_authorization = repo_dict['repo_authorization']

		self.path = os.path.dirname(config_file)
		self.addons_path = self.path#os.path.join(self.path, "addons")

		# addon.xml which describes addon
		self.addon_xml_relpath = 'addon.xml'

		# icon for addon size 256x256
		self.addon_icon_relpath = 'icon.png'

		self.addon_resources_relpath = 'resources'

		# default language,settings and libraries path of addon
		self.addon_languages_relpath = self.addon_resources_relpath + '/language'
		self.addon_settings_relpath = self.addon_resources_relpath + '/settings.xml'

		self._addons = {}

		#create updater for repository
		self._updater = updater.Updater(self, os.path.join(config.plugins.archivCZSK.tmpPath.value, self.id))

		# load installed addons in repository
		for addon_dir in os.listdir(self.addons_path):
			addon_path = os.path.join(self.addons_path, addon_dir)
			if os.path.isfile(addon_path):
				continue

			try:
				addon_info = AddonInfo(os.path.join(addon_path, self.addon_xml_relpath))
			except Exception:
				log.logError("Failed to get addon info from dir %s\n" % addon_dir )
				log.logError(traceback.format_exc())
				continue

			if addon_info.type not in Repository.SUPPORTED_ADDONS:
				log.logError("Load not supported type of addon %s failed, skipping...\n" % (addon_dir,) )
				continue
			if addon_info.type == 'video':
				try:
					if not addon_info.deprecated and not addon_info.broken:
						# chceck if there exitst a script file described in addon.xml
						for ext in ('.py', '.pyc', '.pyo'):
							tmp = os.path.join(addon_path, addon_info.import_name + ext)
							if os.path.isfile(tmp):
								break
						else:
							raise Exception("Invalid addon %s. No script file '%s.py[oc]' found" % (addon_info.name, addon_info.import_name))

					addon = VideoAddon(addon_info, self)
					addon.init_profile_settings()
				except Exception:
					traceback.print_exc()
					log.logError("Load video addon %s failed, skipping...\n%s" % (addon_dir, traceback.format_exc()))
					#log.error("%s cannot load video addon %s, skipping.." , self, addon_dir)
					continue
				else:
					archivczsk.ArchivCZSK.add_addon(addon)
					self.add_addon(addon)

					# create virtual addons based on configured profiles
					for profile_id, profile_name in addon.get_profiles().items():
						log.debug("[%s] Loaded virtual profile %s with id %s" % (addon.id, profile_name, profile_id))
						self.add_virtual_addon(addon, profile_id, profile_name)


			elif addon_info.type == 'tools':
				# load tools addons
				try:
					tools = ToolsAddon(addon_info, self)
				except Exception:
					traceback.print_exc()
					log.error("%s cannot load tools addon %s, skipping.." , self, addon_dir)
					continue
				else:
					archivczsk.ArchivCZSK.add_addon(tools)
					self.add_addon(tools)
		log.debug("%s successfully loaded" , self)

	def add_virtual_addon(self, addon, profile_id, profile_name):
		addon = VirtualVideoAddon(addon.info, self, profile_id, profile_name)
		archivczsk.ArchivCZSK.add_addon(addon)

	def remove_virtual_addon(self, addon):
		archivczsk.ArchivCZSK.remove_addon(addon)

	def __repr__(self):
		return "%s" % self.name

	def get_addon(self, addon_id):
		return self._addons[addon_id]

	def add_addon(self, addon):
		if self.is_supported_addon(addon):
			self._addons[addon.id] = addon
		else:
			log.debug("%s cannot add %s, not supported addon" , str(addon))

	def is_supported_addon(self, addon):
		if isinstance(addon, VideoAddon):
			return True
		if isinstance(addon, ToolsAddon):
			return True
		return False

	def check_updates(self):
		return self._updater.check_addons()
