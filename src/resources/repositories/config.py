# -*- coding: utf-8 -*-
'''
Created on 11.8.2012

@author: marko
'''
from ...engine.tools.lang import _
from Components.config import config, ConfigSelection, ConfigDirectory, getConfigListEntry, ConfigBoolean

import os

choicelist_timeout = []
for i in range(4, 30, 1):
	choicelist_timeout.append(("%d" % i, "%d s" % i))
choicelist_timeout.append(("0", "∞"))

#define settings which will apply for every addon
global_addon_settings = [
	{
		'label':_('Download'),
		'subentries': [
			{
				'label': _("Download path"),
				'id':'download_path'
			},
		]
	},
	{
		'label':_('Loading'),
		'subentries': [
			{
				'label': _("Timeout"),
				'id':'loading_timeout',
				'entry': ConfigSelection(default="10", choices=choicelist_timeout)
			},
			{
				'label': _("Verify SSL certificates"),
				'id':'verify_ssl',
				'entry': ConfigBoolean(default=False)
			},
		]
	}
]


def add_global_addon_specific_setting(addon, addon_config, setting):
	if setting['id'] == 'download_path':
		download_path = os.path.join(config.plugins.archivCZSK.downloadsPath.getValue(), addon.get_real_id())
		#print '[ArchivCZSK] adding download_path %s to %s' % (download_path, addon.id)
		setattr(addon_config, setting['id'], ConfigDirectory(default=download_path))


#globally adding archivCZSK specific options to addons
def add_global_addon_settings(addon, addon_config):
	for category in global_addon_settings:
		for setting in category['subentries']:
			if 'entry' not in setting:
				add_global_addon_specific_setting(addon, addon_config, setting)
			else:
				if not hasattr( addon_config, setting['id']):
					setattr(addon_config, setting['id'], setting['entry'])
					setting['setting_id'] = getattr(addon_config, setting['id'])


#get addon config entries with global addons settings
def getArchiveConfigList(addon):
	categories = addon.settings.get_configlist_categories()[:]
	for category in global_addon_settings:
		category_init = None

		for cat in categories:
			if category['label'] == cat['label']:
				category_init = cat

		if category_init is None:
			category_init = {
				'label':category['label'],
				'subentries':[]
			}

		for setting in category['subentries']:
			if 'setting_id' not in setting:
				category_init['subentries'].append(getConfigListEntry(setting['label'], getattr(addon.settings.main, setting['id'])))
			else:
				category_init['subentries'].append(getConfigListEntry(setting['label'], setting['setting_id']))
		categories.append(category_init)

	return categories
