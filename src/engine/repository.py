'''
Created on 21.10.2012

@author: marko
'''
import os, traceback
from Components.config import config, ConfigSubsection, ConfigText, ConfigYesNo
from hashlib import md5

from .. import archivczsk
from .addon import AddonInfo, ToolsAddon, VideoAddon, VirtualVideoAddon, UnsupportedArchException
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
		log.debug("Initializing repository from %s" , config_file)
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
		self.hash = repo_dict['hash']

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
		self._updater = updater.Updater(self)
		self.init_settings()

	def init_settings(self):
		repository_id = self.id.replace('.', '_')

		setattr(config.plugins.archivCZSK.repositories, repository_id, ConfigSubsection())
		self.settings = getattr(config.plugins.archivCZSK.repositories, repository_id)
		self.settings.enabled = ConfigYesNo(default=True if self.is_signed() else False)

	def is_signed(self):
		# yes I know, that this has nothing to do with security, but I'm lazy to implement proper signing and verification using PKI
		if self.hash == None:
			return False

		m = md5()
		for x in ('archivczsk_', self.__class__.__name__.lower(), self.id, self.version, self.update_xml_url, self.update_datadir_url, self.update_authorization):
			if x:
				m.update(x.encode('utf-8'))

		return self.hash == m.hexdigest()

	def is_third_party(self):
		return self.id != 'archivczsk_doplnky'

	def enabled(self, new_value=None):
		if new_value is not None:
			self.settings.enabled.value = new_value
			self.settings.enabled.save()

		return self.settings.enabled.value

	def load_addons(self):
		log.debug("[%s] Loading addons" % self)

		# load installed addons in repository
		for addon_dir in os.listdir(self.addons_path):
			addon_path = os.path.join(self.addons_path, addon_dir)
			if os.path.isfile(addon_path):
				continue

			try:
				addon_info = AddonInfo(os.path.join(addon_path, self.addon_xml_relpath))
			except UnsupportedArchException as e:
				log.logInfo("[%s] Skipping addon %s: %s" % (self, addon_dir, str(e)))
				continue
			except Exception:
				log.logError("[%s] Failed to get addon info from dir %s\n" % (self, addon_dir) )
				log.logError(traceback.format_exc())
				continue

			if addon_info.type not in Repository.SUPPORTED_ADDONS:
				log.logError("Load not supported type of addon %s failed, skipping...\n" % addon_dir )
				continue
			if addon_info.type == 'video':
				try:
					if not addon_info.deprecated and not addon_info.broken:
						# check if there exitst a script file described in addon.xml
						for ext in ('.py', '.pyc', '.pyo'):
							tmp = os.path.join(addon_path, addon_info.import_name + ext)
							if os.path.isfile(tmp):
								break
						else:
							raise Exception("[%s] Invalid addon %s. No script file '%s.py[oc]' found" % (self, addon_info.name, addon_info.import_name))

					addon = VideoAddon(addon_info, self)
					addon.init_profile_settings()
				except Exception:
					traceback.print_exc()
					log.logError("[%s] Load video addon %s failed, skipping...\n%s" % (self, addon_dir, traceback.format_exc()))
					#log.error("%s cannot load video addon %s, skipping.." , self, addon_dir)
					continue
				else:
					if not archivczsk.ArchivCZSK.has_addon(addon.id):
						archivczsk.ArchivCZSK.add_addon(addon)
						self.add_addon(addon)

						# create virtual addons based on configured profiles
						for profile_id, profile_name in addon.get_profiles().items():
							log.debug("[%s] Loaded virtual profile %s with id %s" % (addon.id, profile_name, profile_id))
							self.add_virtual_addon(addon, profile_id, profile_name)
					else:
						log.error("[%s] Addon with ID %s already loaded, skipping ..." % (self, addon.id))
						addon.close()


			elif addon_info.type == 'tools':
				# load tools addons
				try:
					tools = ToolsAddon(addon_info, self)
				except Exception:
					traceback.print_exc()
					log.error("[%s] cannot load tools addon %s, skipping ..." % (self, addon_dir))
					continue
				else:
					if not archivczsk.ArchivCZSK.has_addon(tools.id):
						archivczsk.ArchivCZSK.add_addon(tools)
						self.add_addon(tools)
					else:
						log.error("[%s] Addon with ID %s already loaded, skipping ..." % (self, tools.id))
						tools.close()

		log.debug("[%s] addons successfully loaded" % self)

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

	def get_description(self, lang_id):
		if lang_id in self.description:
			return self.description[lang_id]
		elif lang_id == 'sk' and 'cs' in self.description:
			return self.description['cs']
		elif lang_id == 'cs' and 'sk' in self.description:
			return self.description['sk']
		else:
			return self.description.get('en', u'')
