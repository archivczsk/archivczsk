# -*- coding: utf-8 -*-
'''
Created on 11.8.2012

@author: marko
'''
from ...compat import DMM_IMAGE

# just dummy implementation, for extracting texts - real translation will be done when settings will be shown
def _(s):
	return s

choicelist_timeout = []
for i in range(4, 30, 1):
	choicelist_timeout.append(("%d" % i, "%d s" % i))
choicelist_timeout.append(("0", "∞"))

available_players=[ _('Default'), 'gstplayer', 'exteplayer3' ]

if DMM_IMAGE:
	available_players.extend(['DMM', 'DVB (OE>=2.5)'] )

#define settings which will apply for every addon
global_addon_settings = [
	{
		'label':_('General'),
		'order': 0,
		'subentries': [
			{
				'label': _("Addon order"),
				'id': 'auto_addon_order',
				'type': 'number',
				'default': '99999'
			},
			{
				'label': _("Used player"),
				'id': 'auto_used_player',
				'type': 'enum',
				'lvalues': '|'.join(available_players),
				'default': '0'
			}
		]
	},
	{
		'label':_('Other'),
		'subentries': [
			{
				'label': _("Addon language"),
				'id': 'addon_lang',
				'type': 'keyenum',
				'default': 'auto',
				'values': '|'.join([ '{};{}'.format(x[0], x[1]) for x in [ ('auto', _('Automaticaly')), ('cs', _("Czech")), ('sk', _("Slovak")), ('en', _("English")) ]])
			},
			{
				'label': _("Timeout"),
				'id':'loading_timeout',
				'type': 'keyenum',
				'default': '10',
				'values': '|'.join([ '{};{}'.format(x[0], x[1]) for x in choicelist_timeout])
			},
			{
				'label': _("Verify SSL certificates"),
				'id':'verify_ssl',
				'type': 'bool',
				'default': 'false'
			},
			{
				'label': _("Show addon shortcut in main menu of Enigma"),
				'id':'main_menu_shortcut',
				'type': 'bool',
				'default': 'false'
			},
			{
				'label': _("Download path"),
				'id':'download_path',
				'type':'download_path'
			},
		]
	}
]
