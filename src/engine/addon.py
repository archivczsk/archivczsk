# -*- coding: utf-8 -*-
'''
Created on 21.10.2012

@author: marko
'''
import os, traceback
import gettext
import importlib
from Components.config import config, ConfigSubsection, ConfigSelection, ConfigYesNo, ConfigText, ConfigNumber, ConfigIP, ConfigPassword, getConfigListEntry
import copy
import uuid
from hashlib import md5
from functools import partial

from .tools import util, parser
from .tools.lang import get_language_id
from .tools.logger import log
from .tools.lang import _
from ..resources.repositories import config as addon_config
from ..gui import menu, info, shortcuts, download
from .contentprovider import VideoAddonContentProvider
from .bgservice import AddonBackgroundService
from .httpserver import archivCZSKHttpServer, AddonHttpRequestHandler
from ..compat import DMM_IMAGE

from ..py3compat import *

class Addon(object):

	def __init__(self, info, repository):
		self.repository = repository
		self.info = info

		self.id = info.id
		self.name = info.name
		self.version = info.version
		#self.description = info.get_description(get_language_id())
		self.changelog_path = info.changelog_path
		self.path = info.path
		self.relative_path = os.path.relpath(self.path, repository.path)
		self.supported = True
		self.dependencies_checked = False

		log.info("%s - initializing", self)

		self._updater = repository._updater
		self.__need_update = False
		self.remote_hash = None

		# load languages
		self.language = AddonLanguage(self, os.path.join(self.path, self.repository.addon_languages_relpath))
		archivczsk_lang_id = get_language_id()
		if self.language.has_language(archivczsk_lang_id):
			self.language.set_language(archivczsk_lang_id)
		else:
			#fix to use czech language instead of slovak language when slovak is not available
			if archivczsk_lang_id == 'sk' and self.language.has_language('cs'):
				self.language.set_language('cs')
			else:
				self.language.set_language('en')

		# load settings
		self.settings = AddonSettings(self, os.path.join(self.path, self.repository.addon_settings_relpath))

		# this is the function, that should be called on direct call
		self.entry_point = None

	def __repr__(self):
		return "%s(%s-%s)" % (self.__class__.__name__, self.name, self.version)

	def get_real_id(self):
		# this will return real (physical) addon ID - used to get parent ID on virtual addon
		return getattr(self, 'real_id', self.id)

	def update(self):
		if self.__need_update:
			ret = self._updater.update_addon(self)
			if ret:
				self.__need_update = False
			return ret
		else:
			return False

	def check_update(self, load_xml=True, force_update=False):
		self.__need_update, self.info.broken = self._updater.check_addon(self, load_xml)
		if force_update:
			self.__need_update = True
		return self.__need_update

	def need_update(self):
		return self.__need_update

	def remove(self):
		self._updater.remove_addon(self)

	def get_localized_string(self, id_language):
		return self.language.get_localized_string(id_language)

	def setting_exist(self, setting_id):
		return self.settings.setting_exist(setting_id)

	def get_setting(self, setting_id):
		return self.settings.get_setting(setting_id)

	def set_setting(self, setting_id, value):
		return self.settings.set_setting(setting_id, value)

	def get_info(self, info):
		if info == 'description':
			return self.info.get_description(get_language_id())

		try:
			atr = getattr(self.info, '%s' % info)
		except Exception as e:
			#traceback.print_exc()
			log.error("%s get_info cannot retrieve info - %s" % (self, str(e)))
			return None
		else:
			return atr

	def open_settings(self, session, cb=None):
		def __settings_closed(*args):
			saved = args[0] if len(args) > 0  else False
			self.settings.unpause_change_notifiers(saved)
			if cb:
				cb(*args)

		self.settings.pause_change_notifiers()
		menu.openAddonMenu(session, self, __settings_closed)

	def open_changelog(self, session):
		info.showChangelog(session, self.name, self.changelog_path)

	def close(self):
		self.info = None
		self._updater = None
		self.repository = None

	def is_enabled(self):
		return self.get_setting('enabled')

	def set_enabled(self, enabled):
		self.set_setting('enabled', enabled)
		if enabled:
			if isinstance( self, VideoAddon ):
				self.provider.preload_addon()

	def add_setting_change_notifier(self, setting_ids, cbk):
		self.settings.add_change_notifier(setting_ids, cbk)

	def get_addon_files(self):
		def is_filtered(file):
			if file.startswith('.') or os.path.basename(file).startswith('.'):
				return True

			for ext in ('.pyo', '.pyc', '.so'):
				if file.endswith(ext):
					return True

			return False

		files = []

		for dirpath, _ ,filenames in os.walk(self.path):
			if dirpath.endswith('__pycache__'):
				continue

			for f in filenames:
				if not is_filtered(f):
					files.append(os.path.join(dirpath, f))

		return sorted(files)

	def get_addon_data_hash(self):
		m = md5()
		for file in self.get_addon_files():
			with open(file, 'rb') as f:
				for data in iter(lambda: f.read(8192), b''):
					m.update(data)

		return m.hexdigest()

	def check_addon_integrity(self):
		if not self.remote_hash:
			# remote hash is not known
			return True

		return self.get_addon_data_hash() == self.remote_hash

	def set_remote_hash(self, hash):
		self.remote_hash = hash


class XBMCAddon(object):
	def __init__(self, addon):
		self._addon = addon

	def __getattr__(self, attr):
		return getattr(self._addon, attr)

	def getLocalizedString(self, id_language):
		return self._addon.get_localized_string(id_language)

	def getAddonInfo(self, info):
		return self._addon.get_info(info)

	def getSetting(self, setting):
			val = self._addon.get_setting(setting)
			if isinstance(val, bool):
				if val:
					return 'true'
				else:
					return 'false'
			return val

	def setSetting(self, setting, value):
		return self._addon.set_setting(setting, value)


class ToolsAddon(Addon):
	def __init__(self, info, repository):
		Addon.__init__(self, info, repository)
		self.import_package = os.path.basename(info.path)
		self.requires = info.requires

	def init(self):
		importlib.import_module(self.import_package)


class VideoAddon(Addon):
	def __init__(self, info, repository):
		Addon.__init__(self, info, repository)
		self.import_name = info.import_name
		self.import_package = os.path.basename(info.path)
		self.import_entry_point = info.import_entry_point
		self.import_preload = info.import_preload
		self.requires = info.requires
		if not self.info.deprecated and not self.import_entry_point:
			raise Exception("%s entry point missing in addon.xml" % self)
		# content provider
		self.downloads_path = self.get_setting('download_path')
		self.shortcuts_path = os.path.join(config.plugins.archivCZSK.dataPath.getValue(), self.id)
		self.provider = VideoAddonContentProvider(self, self.downloads_path, self.shortcuts_path)
		self.bgservice = AddonBackgroundService(self.name)

	def refresh_provider_paths(self, *args, **kwargs):
		self.downloads_path = self.get_setting('download_path')
		self.shortcuts_path = os.path.join(config.plugins.archivCZSK.dataPath.getValue(), self.id)
		self.provider.downloads_path = self.downloads_path
		self.provider.shortcuts_path = self.shortcuts_path

	def open_shortcuts(self, session, cb):
		def callback(*args, **kwargs):
			self.refresh_provider_paths()
			cb and cb(*args, **kwargs)
		shortcuts.openShortcuts(session, self, callback)

	def open_downloads(self, session, cb):
		def callback(*args, **kwargs):
			self.refresh_provider_paths()
			cb and cb(*args, **kwargs)
		download.openAddonDownloads(session, self, callback)

	def close(self):
		self.bgservice.stop_all()
		archivCZSKHttpServer.unregisterRequestHandler(AddonHttpRequestHandler(self))
		Addon.close(self)
		self.provider.close()
		self.provider = None

	def is_virtual(self):
		return False

	def init_profile_settings(self):
		config_addon_id = self.id.replace('.', '_')
		setattr(config.plugins.archivCZSK.profiles, config_addon_id, ConfigText())

	def get_profiles(self):
		ret = {}
		config_addon_id = self.id.replace('.', '_')
		profile_value = getattr(config.plugins.archivCZSK.profiles, config_addon_id).value
		if profile_value:
			for p in profile_value.split(','):
				pinfo = p.strip().split(':')
				if len(pinfo) == 2:
					ret[pinfo[0]] = pinfo[1]

		return ret

	def set_profiles(self, profiles):
		profiles = [pid + ':' + pname.replace(',', '').replace(':', '') for pid, pname in profiles.items()]
		profile_setting = getattr(config.plugins.archivCZSK.profiles, self.id.replace('.', '_'))
		profile_setting.value = ','.join(profiles)
		profile_setting.save()

	def add_profile(self, name):
		profiles = self.get_profiles()
		profile_id = str(uuid.uuid4()).split('-')[4]
		profiles[profile_id] = name
		self.set_profiles(profiles)
		return profile_id


class VirtualVideoAddon(VideoAddon):
	def __init__(self, info, repository, profile_id, profile_name):
		self.real_id = info.id
		self.profile_id = profile_id
		self.profile_name = profile_name

		# modify info dictionary
		info = copy.copy(info)
		info.id = info.id + '_' + profile_id
		info.data_path = info.data_path + '_' + profile_id
		util.make_path(info.data_path)
		info.name = info.name + ' - ' + profile_name

		VideoAddon.__init__(self, info, repository)

	def is_virtual(self):
		return True

	def rename_profile(self, name):
		addon = self.repository.get_addon(self.real_id)
		profiles = addon.get_profiles()
		if self.profile_id in profiles:
			profiles[self.profile_id] = name
			addon.set_profiles(profiles)
			self.profile_name = name
			self.info.name = addon.name + ' - ' + name
			self.name = self.info.name

	def remove_profile(self):
		# get parent addon
		addon = self.repository.get_addon(self.real_id)
		profiles = addon.get_profiles()
		if self.profile_id in profiles:
			del profiles[self.profile_id]
			addon.set_profiles(profiles)


class DummyGettext(object):
	def __init__(self):
		pass

	def gettext(self, s):
		return s


class AddonLanguage(object):
	"""Loading xml language file"""
	language_map = {
		'en':'English',
		'sk':'Slovak',
		'cs':'Czech',
	}

	def __init__(self, addon, languages_dir):

		self.addon = addon
		self._languages_dir = languages_dir
		self._language_filename = 'strings.xml'
		self.dummy_gettext = DummyGettext()
		self.current_language = {}
		self.default_language_id = 'en'
		self.current_language_id = 'en'
		self.languages = {}
		self.use_gettext = False
		log.debug("initializing %s - languages", addon)

		if not os.path.isdir(languages_dir):
			log.error("%s cannot load languages, missing %s directory", self, os.path.basename(languages_dir))
			return

		for language_dir in os.listdir(languages_dir):
			if language_dir in self.language_map and os.path.isdir( os.path.join(languages_dir, language_dir, 'LC_MESSAGES') ):
				# directory for gettext localisation exists
				self.use_gettext = True
				self.languages[language_dir] = None
			else:
				language_id = self.get_language_id(language_dir)
				if language_id is None:
					log.error("%s unknown language %s, you need to update Language map to use it, skipping..", self, language_dir)
					continue
				language_dir_path = os.path.join(languages_dir, language_dir)
				language_file_path = os.path.join(language_dir_path, self._language_filename)
				if os.path.isfile(language_file_path):
					self.languages[language_id] = None
				else:
					log.error("%s cannot find language file %s, skipping %s language..", self, language_file_path, language_dir)

		if self.use_gettext:
			# always init EN lang if using gettext localisation
			self.languages['en'] = None
			self.current_language = self.dummy_gettext

	def __repr__(self):
		return "%s[language]" % self.addon


	def load_language(self, language_id):
		if self.use_gettext:
			if os.path.isdir( os.path.join(self._languages_dir, language_id, 'LC_MESSAGES') ):
				self.languages[language_id] = gettext.translation(self.addon.get_real_id(), self._languages_dir, [language_id])
				log.debug("%s gettext language %s was successfully loaded", (self, language_id))
			else:
				log.debug("%s gettext language %s not found - using dummy EN as backup", (self, language_id))
				self.languages[language_id] = self.dummy_gettext
			return

		language_dir_path = os.path.join(self._languages_dir, self.get_language_name(language_id))
		language_file_path = os.path.join(language_dir_path, self._language_filename)
		try:
			el = util.load_xml(language_file_path)
		except Exception:
			log.error("%s skipping language %s"%(self, language_id))
		else:
			language = {}
			strings = el.getroot()
			for string in strings.findall('string'):
				string_id = string.attrib.get('id')
				language[string_id] = string.text
			self.languages[language_id] = language
			log.debug("%s language %s was successfully loaded", (self, language_id))


	def get_language_id(self, language_name):
		revert_langs = dict([(item[1], item[0]) for item in list(self.language_map.items())])
		if language_name in revert_langs:
			return revert_langs[language_name]
		else:
			return None

	def get_language_name(self, language_id):
		if language_id in self.language_map:
			return self.language_map[language_id]
		else:
			return None

	def get_localized_string(self, string_id):
		string_id = str(string_id)
		if self.use_gettext:
			return self.current_language.gettext(string_id)
		if string_id in self.current_language:
			return self.current_language[string_id]
		else:
#			log.error("%s cannot find language id %s in %s language, returning id of language", self, string_id, self.current_language_id)
			return string_id

	def has_language(self, language_id):
		return language_id in self.languages

	def set_language(self, language_id):
		if self.has_language(language_id):
			if self.languages[language_id] is None:
				self.load_language(language_id)
			log.info("%s setting current language %s to %s", self, self.current_language_id, language_id)
			self.current_language_id = language_id
			self.current_language = self.languages[language_id]
		else:
			log.error("%s cannot set language %s, language is not available", self, language_id)

	def get_language(self):
		return self.current_language_id

	def close(self):
		self.addon = None



class AddonSettings(object):

	def __init__(self, addon, settings_file):
		log.debug("%s - initializing settings", addon)

		# remove dots from addon.id to resolve issue with load/save config of addon
		addon_id = addon.id.replace('.', '_')

		setattr(config.plugins.archivCZSK.archives, addon_id, ConfigSubsection())
		self.main = getattr(config.plugins.archivCZSK.archives, addon_id)

		addon_config.add_global_addon_settings(addon, self.main)

		self.main.enabled = ConfigYesNo(default=True)
		self.notifiers_enabled = True
		self.old_settings = {}

		self.addon = addon
		# not every addon has settings
		try:
			settings_parser = parser.XBMCSettingsXMLParser(settings_file)
		except IOError:
			pass
		else:
			self.category_entries = settings_parser.parse()
			self.initialize_settings()


	def __repr__(self):
		return "%s[settings]" % self.addon


	def initialize_settings(self):
		for entry in self.category_entries:
			for subentry in entry['subentries']:
				self.initialize_entry(self.main, subentry)


	def get_configlist_categories(self):
		def __load_subcategory(idx):
			se = []
			for subentry in self.category_entries[idx]['subentries']:
				if subentry['visible'] == 'true':
					se.append(getConfigListEntry(py2_encode_utf8( self._get_label(subentry['label']) ), subentry['setting_id']))
			return se

		categories = []
		for i, entry in enumerate(self.category_entries):
			if entry['label'] == 'general':
				if len(entry['subentries']) == 0 :
					continue
				else:
					category = {'label':_('General'), 'subentries': partial(__load_subcategory, i)}
			else:
				category = {'label':self._get_label(entry['label']), 'subentries': partial( __load_subcategory, i)}

			categories.append(category)

		return categories

	def setting_exist(self, setting_id):
		try:
			getattr(self.main, '%s' % setting_id)
			return True
		except:
			return False

	def get_setting(self, setting_id):
		try:
			if self.setting_exist(setting_id):
				setting = getattr(self.main, '%s' % setting_id)
				if isinstance(setting, ConfigIP):
					return setting.getText()
				return setting.getValue()
			else:
				log.logDebug("Cannot retrieve setting '%s' - %s" % (setting_id, self.addon))
		except:
			log.logError("Cannot retrieve setting '%s' - %s\n%s" % (setting_id, self.addon, traceback.format_exc()))

		return ""

	def set_setting(self, setting_id, value):
		try:
			setting = getattr(self.main, '%s' % setting_id)
		except ValueError:
			log.error('%s cannot retrieve setting %s,  Invalid setting id', self, setting_id)
			return False
		else:
			setting.setValue(value)
			setting.save()
			return True

	def dict(self, filter_sensitive=False):
		ret = {}
		for s in self.main.dict().keys():
			if filter_sensitive and isinstance(s, ConfigPassword):
				continue

			ret[s] = self.get_setting(s)

		return ret

	def _get_label(self, label):
		return self.addon.get_localized_string(label)

	def initialize_entry(self, setting, entry):
		# fix dotted id
		entry['id'] = entry['id'].replace('.', '_')

		if entry['type'] == 'bool':
			setattr(setting, entry['id'], ConfigYesNo(default=(entry['default'] == 'true')))

		elif entry['type'] == 'text':
			if entry['option'] == 'true':
				setattr(setting, entry['id'], ConfigPassword(default=entry['default'], fixed_size=False))
			else:
				setattr(setting, entry['id'], ConfigText(default=entry['default'], fixed_size=False))

		elif entry['type'] == 'password':
			setattr(setting, entry['id'], ConfigPassword(default=entry['default'], fixed_size=False))

		elif entry['type'] == 'enum':
			choicelist = [(str(idx), py2_encode_utf8( self._get_label(e)) ) for idx, e in enumerate(entry['lvalues'].split("|"))]
			setattr(setting, entry['id'], ConfigSelection(default=entry['default'], choices=choicelist))

		elif entry['type'] == 'labelenum':
			choicelist = [(py2_encode_utf8(e), py2_encode_utf8(self._get_label(e))) for e in entry['values'].split("|")]
			setattr(setting, entry['id'], ConfigSelection(default=entry['default'], choices=choicelist))

		elif entry['type'] == 'keyenum':
			choicelist = [(py2_encode_utf8(e.split(';')[0]), py2_encode_utf8(self._get_label(e.split(';')[1]))) for e in entry['values'].split("|")]
			setattr(setting, entry['id'], ConfigSelection(default=entry['default'], choices=choicelist))

		elif entry['type'] == 'ipaddress':
			setattr(setting, entry['id'], ConfigIP(default=list(map(int, entry['default'].split('.'))), auto_jump=True))

		elif entry['type'] == 'number':
			setattr(setting, entry['id'], ConfigNumber(default=int(entry['default'])))

		else:
			log.error('%s cannot initialize unknown entry %s', self, entry['type'])
			return

		entry['setting_id'] = getattr(setting, entry['id'])

	def close(self):
		self.addon = None

	def pause_change_notifiers(self):
		self.notifiers_enabled = False
		self.delayed_notifiers = {}

	def unpause_change_notifiers(self, fire_delayed=True):
		if fire_delayed:
			log.debug("Settings closed - searching notifiers to call")
			for name in self.delayed_notifiers:
				cbk, value = self.delayed_notifiers[name]

				if self.old_settings[name] != value:
					log.debug("Setting %s changed - calling notifier" % name)
					try:
						cbk(name, value)
					except:
						log.error('Error by calling delayed setting change notification for option "%s"' % name)
						log.error(traceback.format_exc())
				else:
					log.debug("Value of setting %s not changed - not calling notifier" % name)
				self.old_settings[name] = value
		else:
			log.debug("Settings closed without save")
		del self.delayed_notifiers
		self.notifiers_enabled = True

	def __call_change_notifier(self, cbk, name, value ):
		if self.old_settings.get(name) == None:
			# store first value to compare it if it's realy changed
			log.debug("First value for setting %s succesfuly stored" % name)
			self.old_settings[name] = value
			return


		if self.notifiers_enabled:
			if self.old_settings[name] != value:
				try:
					cbk(name, value)
				except:
					log.error('Error by calling setting change notification for option "%s"' % name)
					log.error(traceback.format_exc())

				self.old_settings[name] = value
		else:
			# store notification for later
			self.delayed_notifiers[name] = (cbk, value)

	def __add_change_notifier(self, setting_id, cbk):
		try:
			setting = getattr(self.main, '%s' % setting_id)
		except ValueError:
			log.error('%s cannot retrieve setting %s,  Invalid setting id', self, setting_id)
		else:
			setting.addNotifier(lambda c: self.__call_change_notifier(cbk, setting_id, c.value), immediate_feedback=True)

	def add_change_notifier(self, setting_ids, cbk):
		if isinstance(setting_ids, (type(()), type([]))):
			for setting_id in setting_ids:
				self.__add_change_notifier(setting_id, cbk)
		else:
			self.__add_change_notifier(setting_ids, cbk)


class AddonInfo(object):

	def __init__(self, info_file):
		log.info("AddonInfo(%s) initializing.." , '/'.join(info_file.split('/')[-3:]))

		addon_dict = parser.XBMCAddonXMLParser(info_file).parse()

		self.id = addon_dict['id']
		self.name = addon_dict['name']
		self.version = addon_dict['version']
		self.type = addon_dict['type']
		self.broken = addon_dict['broken']
		self.path = os.path.dirname(info_file)
		self.deprecated = addon_dict['deprecated']
		self.import_name = addon_dict['import_name']
		self.import_entry_point = addon_dict['import_entry_point']
		self.import_preload = addon_dict['import_preload']
		self.seekers = addon_dict['seekers']
		self.shortcuts = addon_dict['shortcuts']
		self.tmp_path = config.plugins.archivCZSK.tmpPath.value
		self.data_path = os.path.join(config.plugins.archivCZSK.dataPath.getValue(), self.id)
		self.description = addon_dict['description']

		# create data_path(profile folder)
		util.make_path(self.data_path)

		self.requires = addon_dict['requires']
		self.image = os.path.join(self.path, 'icon.png')

		#changelog
		if os.path.isfile(os.path.join(self.path, 'changelog.txt')):
			self.changelog_path = os.path.join(self.path, 'changelog.txt')
		elif os.path.isfile(os.path.join(self.path, 'Changelog.txt')):
			self.changelog_path = os.path.join(self.path, 'Changelog.txt')
		else:
			self.changelog_path = None

	def get_description(self, lang_id):
		if lang_id in self.description:
			return self.description[lang_id]
		elif lang_id == 'sk' and 'cs' in self.description:
			return self.description['cs']
		elif lang_id == 'cs' and 'sk' in self.description:
			return self.description['sk']
		else:
			return self.description.get('en', u'')


	def __repr__(self):
		return "AddonInfo(%s)" % ('/'.join(self.path.split('/')[-2:]))


	def close(self):
		self.addon = None
