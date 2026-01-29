# -*- coding: utf-8 -*-
'''
Created on 11.8.2012

@author: marko
'''
from Components.config import config, ConfigSelection, ConfigDirectory, getConfigListEntry, ConfigBoolean, ConfigNumber
from ...settings import ConfigSelectionTr
from functools import partial
from ...compat import DMM_IMAGE
from ...engine.tools.logger import log
from ...engine.tools.lang import _ as tr
import os


# just dummy implementation, for extracting texts - real translation will be done when settings will be shown
def _(s):
	return s

choicelist_timeout = []
for i in range(4, 30, 1):
	choicelist_timeout.append(("%d" % i, "%d s" % i))
choicelist_timeout.append(("0", "∞"))

available_players=[ ('0', _('Default')), ('1', 'gstplayer'), ('2', 'exteplayer3') ]

if DMM_IMAGE:
	available_players.extend([ ('3', 'DMM'), ('4', 'DVB (OE>=2.5)')] )

#define settings which will apply for every addon
global_addon_settings = [
	{
		'label':_('General'),
		'order': 0,
		'subentries': [
			{
				'label': _("Addon order"),
				'id': 'auto_addon_order',
				'entry': lambda: ConfigNumber(default=99999)
			},
			{
				'label': _("Used player"),
				'id': 'auto_used_player',
				'entry': lambda: ConfigSelectionTr(tr, default='0', choices=available_players)
			}
		]
	},
	{
		'label':_('Other'),
		'subentries': [
			{
				'label': _("Addon language"),
				'id': 'addon_lang',
				'entry': lambda: ConfigSelectionTr(tr, default='auto', choices=[ ('auto', _('Automaticaly')), ('cs', _("Czech")), ('sk', _("Slovak")), ('en', _("English")) ])
			},
			{
				'label': _("Timeout"),
				'id':'loading_timeout',
				'entry': lambda: ConfigSelectionTr(tr, default="10", choices=choicelist_timeout)
			},
			{
				'label': _("Verify SSL certificates"),
				'id':'verify_ssl',
				'entry': lambda: ConfigBoolean(default=False)
			},
			{
				'label': _("Show addon shortcut in main menu of Enigma"),
				'id':'main_menu_shortcut',
				'entry': lambda: ConfigBoolean(default=False)
			},
			{
				'label': _("Download path"),
				'id':'download_path'
			},
		]
	}
]


def add_global_addon_specific_setting(addon, addon_config, setting):
	if setting['id'] == 'download_path':
		download_path = os.path.join(config.plugins.archivCZSK.downloadsPath.getValue(), addon.get_real_id())
		#print '[ArchivCZSK] adding download_path %s to %s' % (download_path, addon.id)
		setattr(addon_config, setting['id'], ConfigDirectory(default=download_path))


#globally adding ArchivCZSK specific options to addons
def add_global_addon_settings(addon, addon_config):
	for category in global_addon_settings:
		for setting in category['subentries']:
			if 'entry' not in setting:
				add_global_addon_specific_setting(addon, addon_config, setting)
			else:
				if not hasattr( addon_config, setting['id']):
					setattr(addon_config, setting['id'], setting['entry']())
#					setting['setting_id'] = getattr(addon_config, setting['id'])


#get addon config entries with global addons settings
def getArchiveConfigList(addon):
	categories = addon.settings.get_configlist_categories()

	def __load_subentries(idx, gidx):
		if idx != None:
			se = categories[idx]['subentries']()
		else:
			se = []

		for setting in global_addon_settings[gidx]['subentries']:
			if 'setting_id' not in setting:
				set_component = getattr(addon.settings.main, setting['id'])
			else:
				set_component = setting['setting_id']

			if isinstance(set_component, ConfigSelectionTr):
				set_component.translate()

			se.append(getConfigListEntry(tr(setting['label']), set_component))

		return se

	ret = []
	gi_added = []

	for i, cat in enumerate(categories):
		category_init = None
		for gi, category in enumerate(global_addon_settings):
			if category['label'] == cat['label'] or category.get('order') == i:
				category_init = cat
				gi_added.append(gi)
				break

		if category_init is None:
			ret.append(cat)
		else:
			ret.append({
				'label': category_init['label'],
				'subentries': partial( __load_subentries, i, gi)
			})

	for gi, category in enumerate(global_addon_settings):
		if gi not in gi_added:
			ret.append({
				'label': tr(category['label']),
				'subentries': partial( __load_subentries, None, gi)
			})

	return ret
