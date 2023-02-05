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
		return entry

	
class XBMCAddonXMLParser(XMLParser):
		
	addon_types = {
		"xbmc.python.pluginsource":"content",
		"xbmc.addon.repository":"repository",
		"xbmc.python.module":"tools",
		
		"archivczsk.addon.repository":"repository",
		"archivczsk.addon.video":"content_video",
		"archivczsk.addon.tools":"tools_simple",
	}
	
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
		author = addon.attrib.get('provider-name', u'')
		version = addon.attrib.get('version')
		if version is None:
			raise Exception("Parse error: Mandatory atrribute 'version' is missing")
		
		addon_type = 'unknown'
		description = {}
		broken = None
		repo_datadir_url = u''
		repo_addons_url = u''
		repo_authorization = u''
		requires = []
		library = 'lib'
		script = None
		import_name = None
		import_entry_point = None
		import_preload = False
		deprecated = False
		
		req = addon.find('requires')
		if req:
			for imp in req.findall('import'):
				requires.append({'addon':imp.attrib.get('addon'),
								 'version':imp.attrib.get('version'),
								 'optional':imp.attrib.get('optional')})
			
			
		for info in addon.findall('extension'):
			if info.attrib.get('point') in self.addon_types:
				ad_type = self.addon_types[info.attrib.get('point')]
				util.log.debug("ad_type: %s" % ad_type )
				if ad_type == 'repository':
					addon_type = ad_type
					repo_datadir_url = info.find('datadir').text
					repo_addons_url = info.find('info').text
					try:
						repo_authorization = info.find('authorization').text
					except:
						pass
				elif ad_type == 'tools':
					addon_type = ad_type
					library = info.attrib.get('library')
					deprecated = True
				elif ad_type == 'tools_simple':
					addon_type = 'tools'
					library = None
				elif ad_type == 'content':
					provides = None
					if info.findtext('provides'):
						provides = info.findtext('provides')
					if info.attrib.get('provides'):
						provides = info.attrib.get('provides')
					if provides is not None and provides == 'video':
						addon_type = 'video'
						script = info.attrib.get('library', 'default.py')
					deprecated = True
				elif ad_type == 'content_video':
					addon_type = 'video'
					import_name = info.attrib.get('import-name', 'addon')
					import_entry_point = info.attrib.get('entry-point', 'main')
					import_preload = info.attrib.get('preload', 'no').lower() in ('yes', 'true')
					
			if info.attrib.get('point') == 'xbmc.addon.metadata' or info.attrib.get('point') == 'archivczsk.addon.metadata':
				if info.findtext('broken'):
					broken = info.findtext('broken')
				for desc in info.findall('description'):
					if desc.attrib.get('lang') is None:
						description['en'] = desc.text
					else:
						description[desc.attrib.get('lang')] = desc.text
						
		return {
			"id":addon_id,
			"name":name,
			"author":author,
			"type":addon_type,
			"version":version,
			"description":description,
			"broken":broken,
			"repo_addons_url":repo_addons_url,
			"repo_datadir_url":repo_datadir_url,
			"repo_authorization":repo_authorization,
			"requires":requires,
			"library":library,
			"script":script,
			"import_name": import_name,
			"import_entry_point": import_entry_point,
			"import_preload": import_preload,
			"deprecated": deprecated,
		}


class XBMCMultiAddonXMLParser(XBMCAddonXMLParser):
	
	def parse_addons(self):
		addons = {}
		for addon in self.xml.findall('addon'):
			addon_dict = self.parse_addon(addon)
			addon_id = addon_dict['id']
			addons[addon_id] = addon_dict
		return addons
	
	def find_addon(self, id):
		for addon in self.xml.findall('addon'):
			if id == self.get_addon_id(addon):
				return self.parse_addon(addon) 
