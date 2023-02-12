# -*- coding: UTF-8 -*-
import time

from Components.config import config
from Plugins.Plugin import PluginDescriptor

from . import _
from .archivczsk import ArchivCZSK
from .gsession import GlobalSession
from .gui.search import ArchivCZSKSearchClientScreen
from .gui.icon import IconD
from .engine.downloader import DownloadManager

NAME = _("ArchivCZSK")
DESCRIPTION = _("Playing CZ/SK archives")

def sessionStart(reason, session):
	GlobalSession.setSession(session)
	# saving active downloads to session
	if not hasattr(session, 'archivCZSKdownloads'):
		session.archivCZSKdownloads = []
	if DownloadManager.getInstance() is None:
		DownloadManager(session.archivCZSKdownloads)

def main(session, **kwargs):
	def runArchivCZSK(callback = None):
		ArchivCZSK(session)

	lastIconDUtcCfg = config.plugins.archivCZSK.lastIconDShowMessage

	monthSeconds = 60 * 60 * 24 * 30
	if lastIconDUtcCfg.value == 0 or (int(time.time()) - lastIconDUtcCfg.value > monthSeconds):
		lastIconDUtcCfg.value = int(time.time())
		lastIconDUtcCfg.save()
		session.openWithCallback(runArchivCZSK, IconD)
	else:
		runArchivCZSK()

def menu(menuid, **kwargs):
	if menuid == "mainmenu":
		return [(DESCRIPTION, main, "archivy_czsk", 32)]
	else:
		return []

def eventInfo(session, servicelist, **kwargs):
	ref = session.nav.getCurrentlyPlayingServiceReference()
	session.open(ArchivCZSKSearchClientScreen, ref)

def autostart(reason, *args, **kwargs):
	print('autostart called with reason: %s' % (str(reason)))
	if reason == 1:
		# stop command
		ArchivCZSK.stop()


def Plugins(path, **kwargs):
	result = [
		PluginDescriptor(where=[PluginDescriptor.WHERE_SESSIONSTART], fnc=sessionStart),
		PluginDescriptor(where=[PluginDescriptor.WHERE_AUTOSTART], fnc=autostart),
		PluginDescriptor(NAME, description=DESCRIPTION, where=PluginDescriptor.WHERE_PLUGINMENU, fnc=main, icon="czsk.png")
	]

	if config.plugins.archivCZSK.extensions_menu.value:
		#result.append(PluginDescriptor(NAME, where=PluginDescriptor.WHERE_EXTENSIONSMENU, fnc=main))
		result.append(PluginDescriptor(NAME, description=DESCRIPTION, where=PluginDescriptor.WHERE_EXTENSIONSMENU, fnc=main))
	
	if config.plugins.archivCZSK.main_menu.value:
		#result.append(PluginDescriptor(NAME, where=PluginDescriptor.WHERE_MENU, fnc=menu))
		result.append(PluginDescriptor(NAME, description=DESCRIPTION, where=PluginDescriptor.WHERE_MENU, fnc=menu))
		
	if config.plugins.archivCZSK.epg_menu.value:
		result.append(PluginDescriptor(_("Search in ArchivCZSK"), where=PluginDescriptor.WHERE_EVENTINFO, fnc=eventInfo))

	return result


ArchivCZSK.load_skin()
ArchivCZSK.load_repositories()

if config.plugins.archivCZSK.preload.value:
	ArchivCZSK.preload_addons()
	
if config.plugins.archivCZSK.videoPlayer.ydl.value == 'preload':
	ArchivCZSK.start_ydl()
