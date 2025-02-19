import os
import traceback
from Components.Language import language
from Components.config import config, ConfigSubsection, ConfigSelection, \
	ConfigDirectory, ConfigYesNo, ConfigText, ConfigNumber, ConfigNothing, getConfigListEntry, \
	NoSave, ConfigInteger, ConfigSequence
from Tools.Directories import SCOPE_PLUGINS, resolveFilename

from . import log, UpdateInfo, _
from .compat import DMM_IMAGE, VTI_IMAGE

try:
	from Components.Converter.ACZSKKodiToE2List import colorFixNeeded
except:
	colorFixNeeded = None

if colorFixNeeded == None and VTI_IMAGE:
	# VTi needs color fix
	colorFixNeeded = True

def image_is_openpli():
	try:
		with open('/etc/issue', 'r') as f:
			data = f.read().lower()
			if 'openpli' in data or 'openatv' in data:
				return True
	except:
		pass

	return False


LANGUAGE_SETTINGS_ID = language.getLanguage()[:2]
MENU_SEPARATOR = getConfigListEntry("----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------", NoSave(ConfigNothing()))

######### Plugin Paths ##############
ENIGMA_PLUGIN_PATH = os.path.join(resolveFilename(SCOPE_PLUGINS), 'Extensions')
PLUGIN_PATH = os.path.join(ENIGMA_PLUGIN_PATH, 'archivCZSK')
IMAGE_PATH = os.path.join(PLUGIN_PATH, 'gui/icon')
SKIN_PATH = os.path.join(PLUGIN_PATH, 'gui/skins')
REPOSITORY_PATH = os.path.join(PLUGIN_PATH, 'resources/repositories')
LIBRARIES_PATH = os.path.join(PLUGIN_PATH, 'resources/libraries')

CUSTOM_FONTS_PATH = os.path.join(SKIN_PATH,'font.json')
CUSTOM_COLORS_PATH = os.path.join(SKIN_PATH,'color.json')
CUSTOM_SIZES_PATH = os.path.join(SKIN_PATH,'sizes.json')

############ Updater Paths #############
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/106.0.0.0 Safari/537.36'

config.plugins.archivCZSK = ConfigSubsection()
config.plugins.archivCZSK.archives = ConfigSubsection()
config.plugins.archivCZSK.profiles = ConfigSubsection()

############# SUPPORTED MEDIA #################

VIDEO_EXTENSIONS = ('.3gp', '3g2', '.asf', '.avi', '.flv', '.mp4', '.mkv', '.mpeg', '.mov' '.mpg', '.wmv', '.divx', '.vob', '.iso', '.ts', '.m3u8')
AUDIO_EXTENSIONS = ('.mp2', '.mp3', '.wma', '.ogg', '.dts', '.flac', '.wav')
SUBTITLES_EXTENSIONS = ('.srt',)
PLAYLIST_EXTENSIONS = ('.m3u', 'pls')
ARCHIVE_EXTENSIONS = ('.rar', '.zip', '.7zip')
PLAYABLE_EXTENSIONS = VIDEO_EXTENSIONS + AUDIO_EXTENSIONS
MEDIA_EXTENSIONS = VIDEO_EXTENSIONS + AUDIO_EXTENSIONS + ARCHIVE_EXTENSIONS + PLAYLIST_EXTENSIONS + SUBTITLES_EXTENSIONS

############ Shortcuts config #################

config.plugins.archivCZSK.shortcuts = ConfigSubsection()
config.plugins.archivCZSK.shortcuts.archive = ConfigYesNo(default=True)

########## TRAKT ##############################

config.plugins.archivCZSK.trakt = ConfigSubsection()
config.plugins.archivCZSK.trakt.access_token=ConfigText()
config.plugins.archivCZSK.trakt.refresh_token=ConfigText()
config.plugins.archivCZSK.trakt.expiration=ConfigNumber()

# #################################################################################################
# ########### Main config #########################################################################
# #################################################################################################

def changeAutoUpdate(configElement):
	UpdateInfo.resetDates()

config.plugins.archivCZSK.developer_mode = ConfigYesNo(default=False)
config.plugins.archivCZSK.main_menu = ConfigYesNo(default=True)
config.plugins.archivCZSK.extensions_menu = ConfigYesNo(default=False)
config.plugins.archivCZSK.epg_menu = ConfigYesNo(default=True)
config.plugins.archivCZSK.epg_viewer = ConfigYesNo(default=True)
choicelist = [ ('-1', _("Don't change"),) ]
for i in range(1, 8):
	choicelist.append( (str(i), str(i),) )

config.plugins.archivCZSK.epg_viewer_history = ConfigSelection(default='7',  choices=choicelist)
config.plugins.archivCZSK.archivAutoUpdate = ConfigYesNo(default=True)
config.plugins.archivCZSK.archivAutoUpdate.addNotifier(changeAutoUpdate)
config.plugins.archivCZSK.allow_custom_update = ConfigYesNo(default=False)
config.plugins.archivCZSK.update_repository=ConfigText(default='archivczsk')
if config.plugins.archivCZSK.allow_custom_update.value:
	# setting this config option allow you to choose custom update repo/branch
	config.plugins.archivCZSK.update_branch=ConfigText(default='main')
else:
	# only official repo is allowed
	config.plugins.archivCZSK.update_branch=ConfigSelection(default='main',  choices=[ ('main', _('Stable')), ('testing', _("Testing"))])
	config.plugins.archivCZSK.update_repository.setValue('archivczsk')
config.plugins.archivCZSK.autoUpdate = ConfigYesNo(default=True)
config.plugins.archivCZSK.autoUpdate.addNotifier(changeAutoUpdate)
config.plugins.archivCZSK.updateTimeout = ConfigInteger(default=8, limits=(0,30))
config.plugins.archivCZSK.preload = ConfigYesNo(default=True)
config.plugins.archivCZSK.lastIconDShowMessage = ConfigInteger(0)
config.plugins.archivCZSK.changelogAfterUpdate = ConfigYesNo(default=True)
config.plugins.archivCZSK.checkAddonsIntegrity = ConfigYesNo(default=True)

def skin_changed(configElement):
	from .archivczsk import ArchivCZSK
	ArchivCZSK.force_skin_reload = True

config.plugins.archivCZSK.skin = ConfigText(default="default")
config.plugins.archivCZSK.skin_from_system = ConfigYesNo(default=False)
config.plugins.archivCZSK.skin_from_system.addNotifier(skin_changed, initial_call=False)
config.plugins.archivCZSK.skin_transparency = ConfigSelection(default="5", choices=[(str(i), str(i),) for i in range(0, 100)])
config.plugins.archivCZSK.skin_transparency.addNotifier(skin_changed, initial_call=False)
config.plugins.archivCZSK.skin_background_color=ConfigSequence(seperator=" ", limits=[(0,255),(0,255),(0,255)], default=[0,0,0])
config.plugins.archivCZSK.skin_background_color.addNotifier(skin_changed, initial_call=False)
config.plugins.archivCZSK.font_size = ConfigSelection(default="100", choices=[(str(i), str(i),) for i in range(50, 151)])
config.plugins.archivCZSK.font_size.addNotifier(skin_changed, initial_call=False)
config.plugins.archivCZSK.colored_items = ConfigYesNo(default=False if colorFixNeeded == None else True)
config.plugins.archivCZSK.downloadPoster = ConfigYesNo(default=True)
choicelist = []
#choicelist.append(("%d" % 0, "%d" % 0))
for i in range(0, 310, 10):
	choicelist.append(("%d" % i, "%d" % i))
config.plugins.archivCZSK.posterImageMax = ConfigSelection(default="20", choices=choicelist)

for i in range(0, 10000, 500):
	choicelist.append(("%d" % i, "%d" % i))
config.plugins.archivCZSK.posterSizeMax = ConfigSelection(default="5000", choices=choicelist)

choicelistCsfd = [('1', _("Internal")), ('2', _("CSFD")), ('3', _("CSFDLite"))]
config.plugins.archivCZSK.csfdMode = ConfigSelection(default='1', choices=choicelistCsfd)

def get_main_settings():
	list = []
	from .engine.license import license

	if license.check_level(license.LEVEL_DEVELOPER):
		list.append(getConfigListEntry(_("Enable developer mode (use only for developing addons)"), config.plugins.archivCZSK.developer_mode))

	list.append(getConfigListEntry(_("Use background color and transparency from system"), config.plugins.archivCZSK.skin_from_system))
	if not config.plugins.archivCZSK.skin_from_system.value:
		list.append(getConfigListEntry(_("Background transparency (in %)"), config.plugins.archivCZSK.skin_transparency))
		list.append(getConfigListEntry(_("Background color (RGB format)"), config.plugins.archivCZSK.skin_background_color))
	list.append(getConfigListEntry(_("Font size in lists (in %)"), config.plugins.archivCZSK.font_size))
	list.append(getConfigListEntry(_("Enable colored items"), config.plugins.archivCZSK.colored_items))
	list.append(getConfigListEntry(_("Default category"), config.plugins.archivCZSK.defaultCategory))
	list.append(getConfigListEntry(_("Allow archivCZSK auto update"), config.plugins.archivCZSK.archivAutoUpdate))
	list.append(getConfigListEntry(_("Allow addons auto update"), config.plugins.archivCZSK.autoUpdate))
	if config.plugins.archivCZSK.archivAutoUpdate.value or config.plugins.archivCZSK.autoUpdate.value:
		list.append(getConfigListEntry(_("Update timeout"), config.plugins.archivCZSK.updateTimeout))
		if config.plugins.archivCZSK.allow_custom_update.value:
			list.append(getConfigListEntry(_("Update repository"), config.plugins.archivCZSK.update_repository))
		list.append(getConfigListEntry(_("Update channel"), config.plugins.archivCZSK.update_branch))
	list.append(getConfigListEntry(_("Show changelog after update"), config.plugins.archivCZSK.changelogAfterUpdate))
	list.append(getConfigListEntry(_("Check addons integrity"), config.plugins.archivCZSK.checkAddonsIntegrity))

	list.append(MENU_SEPARATOR)

	list.append(getConfigListEntry(_("Show movie poster"), config.plugins.archivCZSK.downloadPoster))
	if config.plugins.archivCZSK.downloadPoster.value:
		list.append(getConfigListEntry(_("Poster maximum processing size (in kB)"), config.plugins.archivCZSK.posterSizeMax))
		list.append(getConfigListEntry(_("Max posters on HDD"), config.plugins.archivCZSK.posterImageMax))

	list.append(MENU_SEPARATOR)

	list.append(getConfigListEntry(_("Add to extensions menu"), config.plugins.archivCZSK.extensions_menu))
	list.append(getConfigListEntry(_("Add to main menu"), config.plugins.archivCZSK.main_menu))
	list.append(getConfigListEntry(_("Add archive enter shortcut to extensions menu"), config.plugins.archivCZSK.shortcuts.archive))
	list.append(getConfigListEntry(_("Add search option in epg menu"), config.plugins.archivCZSK.epg_menu))
	list.append(getConfigListEntry(_("Integrate into EPG viewer (need restart)"), config.plugins.archivCZSK.epg_viewer))
	if (not DMM_IMAGE) and config.plugins.archivCZSK.epg_viewer.value:
		list.append(getConfigListEntry(_("Number of history days in EPG viewer (need restart)"), config.plugins.archivCZSK.epg_viewer_history))

	list.append(MENU_SEPARATOR)

	list.append(getConfigListEntry(_("CSFD plugin"), config.plugins.archivCZSK.csfdMode))

	return list

# #################################################################################################
# ################# Player config #################################################################
# #################################################################################################

config.plugins.archivCZSK.videoPlayer = ConfigSubsection()
config.plugins.archivCZSK.videoPlayer.info = NoSave(ConfigNothing())

choicelist = [('standard', _('standard player')),
			  ('custom', _('custom player (subtitle support)'))]
config.plugins.archivCZSK.videoPlayer.type = ConfigSelection(default="custom", choices=choicelist)
config.plugins.archivCZSK.videoPlayer.autoPlay = ConfigYesNo(default=True)
config.plugins.archivCZSK.videoPlayer.confirmExit = ConfigYesNo(default=False)
config.plugins.archivCZSK.videoPlayer.subtitlesInAudioSelection = ConfigYesNo(default=True if image_is_openpli() else False)
config.plugins.archivCZSK.videoPlayer.autoChangeAudio = ConfigYesNo(default=True)

choicelist = []
for i in range(10, 240, 5):
	choicelist.append(("%d" % i, "%d s" % i))
config.plugins.archivCZSK.videoPlayer.rtmpTimeout = ConfigSelection(default="20", choices=choicelist)

choicelist = []
for i in range(1000, 50000, 1000):
	choicelist.append(("%d" % i, "%d ms" % i))
config.plugins.archivCZSK.videoPlayer.rtmpBuffer = ConfigSelection(default="10000", choices=choicelist)

def get_player_settings():
	list = []
	list.append(getConfigListEntry(_("Show more info about player"), config.plugins.archivCZSK.videoPlayer.info))
	list.append(getConfigListEntry(_("RTMP Timeout"), config.plugins.archivCZSK.videoPlayer.rtmpTimeout))
	list.append(getConfigListEntry(_("RTMP Buffer"), config.plugins.archivCZSK.videoPlayer.rtmpBuffer))
	list.append(getConfigListEntry(_("Confirm exit when closing player"), config.plugins.archivCZSK.videoPlayer.confirmExit))
	list.append(getConfigListEntry(_("Allow automatically changing audio track"), config.plugins.archivCZSK.videoPlayer.autoChangeAudio))

	return list

# #################################################################################################
# ########### Parental config #####################################################################
# #################################################################################################

config.plugins.archivCZSK.parental = ConfigSubsection()
config.plugins.archivCZSK.parental.change_settings = NoSave(ConfigNothing())
config.plugins.archivCZSK.parental.pin_default = NoSave(ConfigNothing())
config.plugins.archivCZSK.parental.enable = ConfigYesNo(default=False)
config.plugins.archivCZSK.parental.show_adult = ConfigYesNo(default=True)
config.plugins.archivCZSK.parental.show_posters = ConfigYesNo(default=False)
config.plugins.archivCZSK.parental.pin_setup = NoSave(ConfigNothing())
config.plugins.archivCZSK.parental.pin = ConfigInteger(default=783)
config.plugins.archivCZSK.parental.pin_tries = ConfigInteger(default=0)
config.plugins.archivCZSK.parental.time = ConfigInteger(default=0)

def get_parental_settings(locked=False):
	list = []

	if locked:
		list.append(getConfigListEntry(_("Change parental control settings"), config.plugins.archivCZSK.parental.change_settings))
		if config.plugins.archivCZSK.parental.pin.value == 783:
			list.append(getConfigListEntry(_("Your PIN code is set to default 0000. Please change it to your own value."), config.plugins.archivCZSK.parental.pin_default))
	else:
		list.append(getConfigListEntry(_("Enable parental control"), config.plugins.archivCZSK.parental.enable))
		list.append(getConfigListEntry(_("Change parental control PIN"), config.plugins.archivCZSK.parental.pin_setup))
		list.append(getConfigListEntry(_("Show adult content"), config.plugins.archivCZSK.parental.show_adult))
		list.append(getConfigListEntry(_("Show posters for adult content"), config.plugins.archivCZSK.parental.show_posters))

	return list

# #################################################################################################
# ############ Paths ##############################################################################
# #################################################################################################

def changeLogPath(configElement):
	log.changePath(configElement.value)

config.plugins.archivCZSK.dataPath = ConfigDirectory(default=os.path.join(PLUGIN_PATH, "resources/data"))
config.plugins.archivCZSK.downloadsPath = ConfigDirectory(default="/media/hdd")
config.plugins.archivCZSK.posterPath = ConfigDirectory(default="/tmp")
config.plugins.archivCZSK.tmpPath = ConfigDirectory(default="/tmp")
config.plugins.archivCZSK.logPath = ConfigDirectory(default="/tmp")
config.plugins.archivCZSK.logPath.addNotifier(changeLogPath)

def get_path_settings():
	list = []
	list.append(getConfigListEntry(_("Data path"), config.plugins.archivCZSK.dataPath))
	list.append(getConfigListEntry(_("Temp path"), config.plugins.archivCZSK.tmpPath))
	list.append(getConfigListEntry(_("Downloads path"), config.plugins.archivCZSK.downloadsPath))
	list.append(getConfigListEntry(_("Posters path"), config.plugins.archivCZSK.posterPath))

	list.append(getConfigListEntry(_("Log path"), config.plugins.archivCZSK.logPath))
	return list

# #################################################################################################
# ########## Misc #################################################################################
# #################################################################################################

def changeLogMode(configElement):
	log.changeMode(int(configElement.value))

def restartHttpServer(configElement):
	from .engine.httpserver import archivCZSKHttpServer
	try:
		archivCZSKHttpServer.start_listening(True)
	except:
		log.error( "Failed to restart internal HTTP server\n%s" % traceback.format_exc() )

choicelist = [('1', _("info")), ('2', _("debug"))]
config.plugins.archivCZSK.debugMode = ConfigSelection(default='1', choices=choicelist)
config.plugins.archivCZSK.bugReports = ConfigYesNo(default=True)
config.plugins.archivCZSK.debugMode.addNotifier(changeLogMode)
config.plugins.archivCZSK.showBrokenAddons = ConfigYesNo(default=True)
config.plugins.archivCZSK.showNotSupportedAddons = ConfigYesNo(default=True)
config.plugins.archivCZSK.cleanupBrokenAddons = ConfigYesNo(default=True)
config.plugins.archivCZSK.showVideoSourceSelection = ConfigYesNo(default=True)
config.plugins.archivCZSK.convertPNG = ConfigYesNo(default=True)
config.plugins.archivCZSK.clearMemory = ConfigYesNo(default=False)
config.plugins.archivCZSK.confirmExit = ConfigYesNo(default=False)
config.plugins.archivCZSK.httpPort = ConfigInteger(default=18888, limits=(1,65535))
config.plugins.archivCZSK.httpPort.addNotifier(restartHttpServer, initial_call=False)
config.plugins.archivCZSK.httpLocalhost = ConfigYesNo(default=True)
config.plugins.archivCZSK.httpLocalhost.addNotifier(restartHttpServer, initial_call=False)
config.plugins.archivCZSK.send_usage_stats = ConfigYesNo(default=True)

def get_misc_settings():
	list = []
	list.append(getConfigListEntry(_("Debug mode"), config.plugins.archivCZSK.debugMode))
	list.append(getConfigListEntry(_("Allow sending bug reports on addon error"), config.plugins.archivCZSK.bugReports))
	list.append(getConfigListEntry(_("Allow preloading of addons on start"), config.plugins.archivCZSK.preload))
	list.append(getConfigListEntry(_("Confirm exit when closing plugin"), config.plugins.archivCZSK.confirmExit))
	list.append(getConfigListEntry(_("Show broken addons"), config.plugins.archivCZSK.showBrokenAddons))
	list.append(getConfigListEntry(_("Show not supported addons"), config.plugins.archivCZSK.showNotSupportedAddons))
	list.append(getConfigListEntry(_("On update remove broken and not supported addons"), config.plugins.archivCZSK.cleanupBrokenAddons))
	list.append(getConfigListEntry(_("Show video source selection"), config.plugins.archivCZSK.showVideoSourceSelection))
	list.append(getConfigListEntry(_("Convert captcha images to 8bit"), config.plugins.archivCZSK.convertPNG))
	list.append(getConfigListEntry(_("Drop caches on exit"), config.plugins.archivCZSK.clearMemory))
	list.append(getConfigListEntry(_("Internal HTTP server listen port"), config.plugins.archivCZSK.httpPort ))
	list.append(getConfigListEntry(_("Run HTTP only for internal addons usage"), config.plugins.archivCZSK.httpLocalhost ))
	if config.plugins.archivCZSK.update_branch.value == 'testing':
		config.plugins.archivCZSK.send_usage_stats.setValue(True)
	else:
		list.append(getConfigListEntry(_("Allow sending anonymous usage statistics"), config.plugins.archivCZSK.send_usage_stats))
		pass

	return list

# #################################################################################################
