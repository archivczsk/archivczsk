'''
Created on 30.10.2012

@author: marko
'''
from . import util

class XMLParser():
	def __init__(self, xml_file):
		xml = util.load_xml(xml_file)
		self.xml = xml.getroot()

	def parse(self):
		pass

class XBMCSettingsXMLParser(XMLParser):

	def parse(self):
		categories = []
		settings = self.xml

		main_category = {'label':'general', 'subentries':[]}
		for setting in settings.findall('setting'):
			main_category['subentries'].append(self.get_setting_entry(setting))
		categories.append(main_category)

		for category in settings.findall('category'):
			category_entry = self.get_category_entry(category)
			categories.append(category_entry)

		return categories


	def get_category_entry(self, category):
		entry = {'label':category.attrib.get('label'), 'subentries':[]}
		for setting in category.findall('setting'):
			entry['subentries'].append(self.get_setting_entry(setting))
		return entry


	def get_setting_entry(self, setting):
		entry = {}
		entry['label'] = setting.attrib.get('label')
		entry['id'] = setting.attrib.get('id')
		entry['type'] = setting.attrib.get('type')
		entry['default'] = setting.attrib.get('default')
		entry['visible'] = setting.attrib.get('visible') or 'true'
		if entry['type'] == 'text':
			entry['option'] = setting.attrib.get('option') or 'false'
		if entry['type'] == 'enum':
			entry['lvalues'] = setting.attrib.get('lvalues')
		elif entry['type'] == 'labelenum':
			entry['values'] = setting.attrib.get('values')
		elif entry['type'] == 'keyenum':
			entry['values'] = setting.attrib.get('values')
		return entry


class XBMCAddonXMLParser(XMLParser):

	def get_addon_id(self, addon):
		id_addon = addon.attrib.get('id')#.replace('-', '')
		#id_addon = id_addon.split('.')[-2] if id_addon.split('.')[-1] == 'cz' else id_addon.split('.')[-1]
		return id_addon

	def parse(self):
		return self.parse_addon(self.xml)

	def parse_addon(self, addon):

		addon_id = self.get_addon_id(addon)
		if addon_id is None:
			raise Exception("Parse error: Mandatory atrribute 'id' is missing")
		name = addon.attrib.get('name')
		if name is None:
			raise Exception("Parse error: Mandatory atrribute 'name' is missing")
		version = addon.attrib.get('version')
		if version is None:
			raise Exception("Parse error: Mandatory atrribute 'version' is missing")

		hash = addon.attrib.get('rhash')
		supported = addon.attrib.get('supported') != 'no'

		addon_type = 'unknown'
		description = {}
		broken = None
		repo_datadir_url = None
		repo_addons_url = None
		repo_authorization = None
		requires = []
		import_name = None
		import_entry_point = None
		import_preload = False
		deprecated = False
		seekers = []
		shortcuts = []

		req = addon.find('requires')
		if req:
			for imp in req.findall('import'):
				requires.append({
					'addon': imp.attrib.get('addon'),
					'version':imp.attrib.get('version'),
					'optional':imp.attrib.get('optional')
				})

		for info in addon.findall('extension'):
			point = info.attrib.get('point')

			if point == 'archivczsk.addon.video':
				addon_type = 'video'
				import_name = info.attrib.get('import-name', 'addon')
				import_entry_point = info.attrib.get('entry-point', 'main')
				import_preload = info.attrib.get('preload', 'no').lower() in ('yes', 'true')

			elif point == 'archivczsk.addon.tools':
				addon_type = 'tools'

			elif point == 'xbmc.python.pluginsource':
				addon_type = 'video'
				deprecated = True

			elif point == 'xbmc.addon.tools':
				addon_type = 'tools'
				deprecated = True

			elif point in ('archivczsk.addon.repository', 'xbmc.addon.repository'):
				addon_type = 'repository'
				repo_datadir_url = info.findtext('datadir')
				repo_addons_url = info.findtext('info')
				repo_authorization = info.findtext('authorization')

			elif point in ('archivczsk.addon.metadata', 'xbmc.addon.metadata'):
				broken = info.findtext('broken')

				for desc in info.findall('description'):
					description[desc.attrib.get('lang', 'en')] = desc.text

			elif point == 'archivczsk.addon.seeker':
				seekers.append((info.attrib.get('name', name), info.attrib.get('id'),))

			elif point == 'archivczsk.addon.shortcut':
				shortcuts.append(info.attrib.get('name'))

		return {
			"id":addon_id,
			"name":name,
			"type":addon_type,
			"version":version,
			"description":description,
			"broken":broken,
			"repo_addons_url":repo_addons_url,
			"repo_datadir_url":repo_datadir_url,
			"repo_authorization":repo_authorization,
			"requires":requires,
			"import_name": import_name,
			"import_entry_point": import_entry_point,
			"import_preload": import_preload,
			"deprecated": deprecated,
			"seekers": seekers,
			"shortcuts": shortcuts,
			"hash": hash,
			"supported": supported,
		}


class XBMCMultiAddonXMLParser(XBMCAddonXMLParser):

	def parse_addons(self):
		addons = {}
		for addon in self.xml.findall('addon'):
			addon_dict = self.parse_addon(addon)
			addon_id = addon_dict['id']
			addons[addon_id] = addon_dict
		return addons

	def find_addon(self, addon_id):
		for addon in self.xml.findall('addon'):
			if addon_id == self.get_addon_id(addon):
				return self.parse_addon(addon)
