# -*- coding: UTF-8 -*-

from Components.config import config
from Plugins.Plugin import PluginDescriptor
from ServiceReference import ServiceReference


def get_description():
	from .engine.tools.lang import _
	NAME = _("ArchivCZSK")
	DESCRIPTION = _("Playing CZ/SK archives")
	return NAME, DESCRIPTION


def sessionStart(reason, session):
	from .archivczsk import ArchivCZSK
#	ArchivCZSK.start(session)


def main(session, **kwargs):
	from .archivczsk import ArchivCZSK
	ArchivCZSK.run(session)


def menu(menuid, **kwargs):
	if menuid == "mainmenu":
		NAME, DESCRIPTION = get_description()
		return [(DESCRIPTION, main, NAME, 32)]
	else:
		return []


def eventInfo(session, servicelist, **kwargs):
	from .gui.search import ArchivCZSKSearchClientScreen
	ref = session.nav.getCurrentlyPlayingServiceReference()
	session.open(ArchivCZSKSearchClientScreen, ref)


def autostart(reason, *args, **kwargs):
	if reason == 1:
		from .archivczsk import ArchivCZSK
		# stop command
		ArchivCZSK.stop()


def open_content_by_ref(session, **kwargs):
	from .engine.tools.logger import log
	from .engine.httpserver import ArchivCZSKHttpServer
	from .client.shortcut import run_shortcut

	archivCZSKHttpServer = ArchivCZSKHttpServer.get_instance()

	ref = session.nav.getCurrentlyPlayingServiceReference()
	if not ref:
		return

	ref = ServiceReference(ref)
	ref_str = str(ref)
	log.debug("Called with service reference: %s" % ref_str)

	if 'http%3a//' in ref_str:
		# extract url from service reference (if there's any)
		url = ref_str.split(':')[10].replace('%3a', ':')

		log.debug("Extracted url: %s" % url)

		# extract addon's http endpoint from url
		endpoint = archivCZSKHttpServer.urlToEndpoint(url)
		if not endpoint:
			return None

		log.debug("Addon's endpoint extracted from url: %s" % endpoint)
		addon = archivCZSKHttpServer.getAddonByEndpoint(endpoint)
		if not addon:
			return

		log.debug("Found addon for endpoint: %s" % addon.id)
		path = url[url.find(endpoint) + len(endpoint) + 1:].split('#')[0]
		run_shortcut(session, addon, 'archive', {'path': path})
	else:
		run_shortcut(session, None, 'archive', {'sref': ref})


def Plugins(path, **kwargs):
	NAME, DESCRIPTION = get_description()
	from .engine.tools.lang import _
	from . import settings

	result = [
		PluginDescriptor(where=PluginDescriptor.WHERE_SESSIONSTART, fnc=sessionStart),
		PluginDescriptor(where=PluginDescriptor.WHERE_AUTOSTART, fnc=autostart),
		PluginDescriptor(NAME, description=DESCRIPTION, where=PluginDescriptor.WHERE_PLUGINMENU, fnc=main, icon="czsk.png"),
	]

	if config.plugins.archivCZSK.shortcuts.archive.value:
		result.append(PluginDescriptor(_('Open archive for current channel using ArchivCZSK addon'), description=_('When current channel is managed by ArchivCZSK addon, then it opens archive for it'), where=PluginDescriptor.WHERE_EXTENSIONSMENU, fnc=open_content_by_ref))

	if config.plugins.archivCZSK.extensions_menu.value:
		result.append(PluginDescriptor(NAME, description=DESCRIPTION, where=PluginDescriptor.WHERE_EXTENSIONSMENU, fnc=main))

	if config.plugins.archivCZSK.main_menu.value:
		result.append(PluginDescriptor(NAME, description=DESCRIPTION, where=PluginDescriptor.WHERE_MENU, fnc=menu))

	if config.plugins.archivCZSK.epg_menu.value:
		result.append(PluginDescriptor(_("Search in ArchivCZSK"), where=PluginDescriptor.WHERE_EVENTINFO, fnc=eventInfo))

	return result
