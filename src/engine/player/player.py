import traceback, os

from enigma import eServiceReference, iPlayableService, eTimer
from Components.ActionMap import ActionMap, HelpableActionMap
from Components.config import config
from Components.Label import Label
from Components.ServiceEventTracker import InfoBarBase, ServiceEventTracker
from Components.Sources.List import List
from Components.Sources.StaticText import StaticText
from skin import parseColor
from Screens.AudioSelection import AudioSelection
from Screens.ChoiceBox import ChoiceBox
from Screens.HelpMenu import HelpableScreen
from Screens.InfoBarGenerics import (InfoBarShowHide,
		InfoBarSeek, InfoBarAudioSelection, InfoBarNotifications, InfoBarSubtitleSupport)
from Screens.Screen import Screen
from Tools.BoundFunction import boundFunction
from Tools.Notifications import AddNotificationWithID, RemovePopup

try:
	from Plugins.Extensions.SubsSupport import (SubsSupport, SubsSupportStatus, initSubsSettings)
except ImportError:
	# SubsSupport plugin not available, so create fake one
	class SubsSupport(object):
		def __init__(self, *args, **kwargs):
			pass
		def resetSubs(self, rst):
			pass
		def loadSubs(self, fl):
			pass

	class SubsSupportStatus(object):
		pass

	def initSubsSettings():
		pass

from ... import _, log
from ...compat import eConnectCallback, DMM_IMAGE, MessageBox
from ..items import PVideo, PVideoNotResolved, PPlaylist
from ..tools import e2util
from ..tools.util import toString
from ..tools.subtitles import download_subtitles
from ...colors import DeleteColors
from .info import videoPlayerInfo
from ...gui.common import resize

config_archivczsk = config.plugins.archivCZSK

def getPlayPositionPts(session):
	service = session.nav.getCurrentService()
	seek = service and service.seek()
	position = seek and seek.getPlayPosition()
	position = position and not position[0] and position[1] or None
	return position

def getPlayPositionInSeconds(session, position=None):
	if not position:
		position = getPlayPositionPts(session)

	if position is not None:
		position = position // 90000
	return position

def getDurationPts(session):
	service = session.nav.getCurrentService()
	seek = service and service.seek()
	duration = seek and seek.getLength()
	duration = duration and not duration[0] and duration[1] or None
	return duration

def getDurationInSeconds(session, duration=None):
	if not duration:
		duration = getDurationPts(session)

	if duration is not None:
		duration = duration // 90000
	return duration

class ArchivCZSKPlaylist(Screen):
	def __init__(self, session, playlist, title, index=0):
		self.playlist = playlist
		self.index = index
		Screen.__init__(self, session)
		self.skinName = ["ArchivCZSKPlaylistScreen"]
		self["title"] = StaticText(DeleteColors(toString(title)))
		self["list"] = List(self.buildPlaylist())
		self["actions"] = ActionMap(["OkCancelActions"],
				{
					"ok": self.ok,
					"cancel": boundFunction(self.close, None),
				}, -1 )
		self.onLayoutFinish.append(self.setPlaylistIndex)

	def setPlaylistIndex(self):
		self["list"].index = self.index

	def buildPlaylist(self):
		lst = []
		for item in self.playlist:
			lst.append((toString(item.name),))
		return lst

	def ok(self):
		self.close(self["list"].index)


class Player(object):

	def __init__(self, session, callback=None, event_callback=None, stype=4097, resolve_cbk=None):
		self.session = session
		self.old_service = session.nav.getCurrentlyPlayingServiceReference()
		self.settings = config_archivczsk.videoPlayer
		self.resolve_cbk = resolve_cbk
		self.video_player = None
		self.playlist_dialog = None
		self.playlist = []
		self.auto_resume = False
		self.auto_next = True
		self.curr_idx = 0
		self._play_item = None
		self.callback = callback
		self.lastPlayPositionSeconds = None
		self.duration = None
		self.event_callback = event_callback
		self.stype = stype
		self.available_players = None
		self.current_stype = None
		self.cleanup_files = []

	def player_switch(self):
		if not self._play_item:
			return

		if not self.available_players:
			self.available_players = videoPlayerInfo.getAvailablePlayersRefs()

		self.available_players.remove(self.current_stype)
		self.available_players.append(self.current_stype)
		stype = self.available_players[0]

		log.info("Switching player to %d" % stype)

		play_item = self._play_item
		settings = play_item.settings.copy()
		settings['stype'] = stype
		settings['resume_time_sec'] = getPlayPositionInSeconds(self.session)
		settings['resume_popup'] = False

		status_msg = _("Player switched to {player}").format(player=videoPlayerInfo.getPlayerNameByStype(stype))
		self.play_stream(play_item.url, settings, play_item.subs, play_item.name, play_item, status_msg)

	def play_item(self, item = None, idx = None):
		log.info("play_item(%s, %s)"%(item,toString(idx)))
		play_item = None
		auto_resume = False
		if item is not None:
			idx = idx or 0
			if isinstance(item, PPlaylist):
				if len(item.playlist) == 0:
					return self.player_exit_callback()

				self.playlist_item = item
				self.playlist = item.playlist
				self.auto_next = not item.variant
				self.auto_resume = item.variant
				play_item = item.playlist[idx]
			elif isinstance(item, PVideo):
				if item not in self.playlist:
					self.playlist_item = None
					self.playlist = [item]
				play_item = item
		elif idx is not None and self.playlist and idx >= 0 and idx < len(self.playlist):
			auto_resume = self.auto_resume
			play_item = self.playlist[idx]

		def play_next_item():
			# plays next item from playlist or closes player
			# also handles if player was already started or not
			if idx == len(self.playlist) - 1:
				if self.video_player:
					# player was already started - call standard close
					self.video_player.close()
				else:
					# player was not started yet, so exit without video_player call
					self.player_exit_callback()
			else:
				self.play_item(idx=idx + 1)

		def play_item_continue(play_item):
			if play_item == None:
				# resolving failed
				return play_next_item()

			if self._play_item != play_item:
				self._play_item = play_item
				self.curr_idx = idx

				if self.playlist_item:
					# set current play item - needed for stats and trakt commands
					self.playlist_item.set_current_item(play_item)

				if auto_resume:
					settings = play_item.settings.copy()
					settings['resume_time_sec'] = getPlayPositionInSeconds(self.session)
					settings['resume_popup'] = False
				else:
					settings = play_item.settings

				try:
					self.play_stream(play_item.url, settings, play_item.subs, play_item.name, play_item)
				except:
					log.error(traceback.format_exc())
				else:
					if settings.get('playlist_on_start', False):
						self.player_callback(('playlist', 'show',))

		if isinstance(play_item, PVideoNotResolved):
			if self.resolve_cbk:
				self.resolve_cbk(play_item, play_item_continue)
			else:
				# we can't play this item without resolve callback
				play_next_item()
		else:
			# video sould be already resolved, so start play
			play_item_continue(play_item)

	def play_stream(self, play_url, play_settings=None, subtitles_url=None, title=None, wholeItem=None, status_msg=None):
		log.info("play_stream(%s, %s, %s, %s)"%(play_url, play_settings, subtitles_url, title))

		if play_url.startswith("rtmp"):
			rtmp_timeout = int(self.settings.rtmpTimeout.value)
			rtmp_buffer = int(self.settings.rtmpBuffer.value)
			if ' timeout=' not in play_url:
				play_url = "%s timeout=%d" % (play_url, rtmp_timeout)
			if ' buffer=' not in play_url:
				play_url = "%s buffer=%d" % (play_url, rtmp_buffer)
		headers = {}
		if play_settings.get("user-agent"):
			headers["User-Agent"] = play_settings["user-agent"]
		if play_settings.get("extra-headers"):
			headers.update(play_settings["extra-headers"])
		if headers:
			play_url += "#" + "&".join("%s=%s"%(k,v) for k,v in headers.items())

		self.current_stype = play_settings.get('forced_player', play_settings.get("stype", self.stype))
		service_ref = eServiceReference(self.current_stype, 0, toString(play_url))

		if self.video_player is None:
			self.video_player = self.session.openWithCallback(self.player_exit_callback,
					ArchivCZSKMoviePlayer, self.player_callback)

		# set infobar text
		titleSet = False
		if wholeItem is not None:
			try:
				if 'title' in  wholeItem.info:
					sref_title = DeleteColors(toString(wholeItem.info["title"]))
					service_ref.setName(sref_title)
					self.video_player.setInfoBarText(sref_title)
					titleSet = True
			except:
				log.logError("Set title from item failed (set default).\n%s"%traceback.format_exc())

		if not titleSet:
			sref_title = DeleteColors(toString(title))
			service_ref.setName( sref_title )
			self.video_player.setInfoBarText(sref_title)

		# handle subtitles
		subtitles_file = download_subtitles(subtitles_url)
		if subtitles_url != subtitles_file:
			self.cleanup_files.append(subtitles_file)

		self.video_player.relativeSeekEnabled(play_settings.get('relative_seek_enabled', True))

		tracks_settings = {
			# list of priority langs used for audio and subtitles - audio will be automatically switched to first available language
			'lang_priority': play_settings.get('lang_priority', []),

			# list of fallback langs - audio will be automatically switched to first available language, but subtitles will be enabled also
			'lang_fallback': play_settings.get('lang_fallback', []),

			# allow autostart of subtitles (when subtitle lang will be found in lang_priority)
			'subs_autostart': play_settings.get('subs_autostart', True),

			# always start subtitles, even if audio from lang_priority was found
			'subs_always': play_settings.get('subs_always', False),

			# start subtitles when forced subtitle track is found (this is poorly supported by enigma)
			'subs_forced_autostart': play_settings.get('subs_forced_autostart', True)
		}

		self.video_player.play_service_ref(service_ref,
				subtitles_file, play_settings.get("resume_time_sec"), play_settings.get("resume_popup", True), status_msg, tracks_settings, play_settings.get('skip_times'))

	def player_callback(self, callback):
		log.info("player_callback(%r)" % (callback,))
		if callback is not None:
			if callback[0] == "eof":
				if callback[1] and self.auto_next:
					self.player_callback(("playlist", "next",))
				else:
					self.player_callback(('stop',))
					self.video_player.close()
			elif callback[0] == "exit":
				exit_player = True
				if len(callback) == 2:
					exit_player = callback[1]
				else:
					if self.settings.confirmExit.value:
						self.session.openWithCallback(
								lambda x:self.player_callback(("exit", x)),
								MessageBox, text=_("Stop playing this movie?"),
								type=MessageBox.TYPE_YESNO)
						exit_player = False
				if exit_player:
					self.duration = getDurationInSeconds(self.session)
					self.lastPlayPositionSeconds = getPlayPositionInSeconds(self.session)

					self.player_callback(('stop',))
					self.video_player.close()
			elif callback[0] == "playlist":
				if callback[1] == "show":
					if self.playlist_item is not None:
						title = self.playlist_item.name
					else:
						title = self._play_item.name
					self.playlist_dialog = self.session.openWithCallback(
							lambda x: self.player_callback(("playlist", "idx", x)),
							ArchivCZSKPlaylist, self.playlist, title, self.curr_idx)
				elif callback[1] == "prev":
					self.player_callback(('stop',))
					idx = self.curr_idx
					if idx == 0:
						idx = len(self.playlist) - 1
					else:
						idx -= 1
					self.play_item(idx = idx)
				elif callback[1] == "next":
					self.player_callback(('stop',))
					idx = self.curr_idx
					# maybe ignore/make optional
					if idx == len(self.playlist) -1:
						self.video_player.close()
					else:
						idx += 1
						self.play_item(idx = idx)
				elif callback[1] == "idx":
					if callback[2] is not None:
						self.player_callback(('stop',))
						self.play_item(idx=callback[2])
			elif callback[0] == "player_switch":
				self.player_switch()
			elif callback[0] in ("start", "stop", "pause", "unpause", "seek", "watching"):
				self.event_callback and self.event_callback(callback[0], getDurationInSeconds(self.session), getPlayPositionInSeconds(self.session))

	def player_exit_callback(self, playpos=None):
		log.info("player_exit_callback(%s)", playpos)
		if self.playlist_dialog and self.playlist_dialog.__dict__:
			self.playlist_dialog.close()
			self.playlist_dialog = None
		self._play_item = None
		self.playlist = []
		self.curr_idx = 0
		self.playlist_item = None
		self.available_players = None
		self.current_stype = None

		if self.video_player is not None:
			self.session.nav.playService(self.old_service)
		self.video_player = None
		self.old_service = None
		if self.callback is not None:
			self.callback()
			self.callback = None

		for file in self.cleanup_files:
			try:
				os.remove(file)
			except:
				pass
		self.cleanup_files = []


class SkipNotificationScreen(Screen):

	def __init__(self, session):
		Screen.__init__(self, session)
		self.stand_alone = True
		width, height = e2util.get_desktop_width_and_height()
		skin = '<screen position="%d,%d" size="%d,%d" backgroundColor="#20000000" flags="wfNoBorder">' % (
				0.82 * width, 0.9 * height, 0.14 * width, 0.07 * height)
		skin += '<widget name="status" position="5,5" size="%d,%d" zPosition="1" valign="center" halign="center" font="Regular;%d" foregroundColor="white" backgroundColor="#5f606060" shadowColor="black" shadowOffset="-2,-2" />' % (
				(0.14 * width) - 10, (0.07 * height) - 10, resize(17))
		skin += '</screen>'
		self.skin = skin
		self["status"] = Label()

		self.timer = eTimer()
		self.timer_conn = eConnectCallback(self.timer.timeout, self.hide)
		self.onClose.append(self.__on_close)
		self.onShow.append(self.__on_show)
		self.onHide.append(self.__on_hide)
		self.is_shown = False
		self.timeout = 5000

	def run_skip(self):
		self.hide()
		if self.skip_cbk:
			self.skip_cbk()

	def __on_close(self):
		self.timer.stop()
		del self.timer_conn
		del self.timer

	def __on_show(self):
		if self.timer.isActive():
			self.timer.stop()

		self.is_shown = True
		self.timer.start(self.timeout, True)
		log.debug("Notification window shown")

	def __on_hide(self):
		if self.timer.isActive():
			self.timer.stop()

		self.is_shown = False
		log.debug("Notification window hidden")

	def show_skip(self, text, cbk=None, timeout=5):
		self.skip_cbk = cbk
		self.timeout = timeout * 1000
		self['status'].setText(toString(text))
		self.show()


class StatusScreen(Screen):
	def __init__(self, session):
		Screen.__init__(self, session)
		self.stand_alone = True
		width, height = e2util.get_desktop_width_and_height()
		skin = '<screen position="%d,%d" size="%d,%d" backgroundColor="transparent" flags="wfNoBorder">'%(
				0.05 * width, 0.05 * height, 0.9 * width, 0.1 * height)
		skin+= '<widget name="status" position="0,0" size="%d,%d" valign="center" halign="left" font="Regular;22" transparent="1" shadowColor="#40101010" shadowOffset="3,3" />'%(
				0.9 * width, 0.1 * height)
		skin+= '</screen>'
		self.skin = skin
		self["status"] = Label()
		self.timer = eTimer()
		self.timer_conn = eConnectCallback(self.timer.timeout, self.hide)
		self.onClose.append(self.__on_close)

	def __on_close(self):
		self.timer.stop()
		del self.timer_conn
		del self.timer

	def set_status(self, text, color="yellow", timeout=1500):
		self['status'].setText(toString(text))
		self['status'].instance.setForegroundColor(parseColor(color))
		self.show()
		self.timer.start(timeout, True)

class InfoBarAspectChange(object):

	V_DICT = {'16_9_letterbox'	: {'aspect' : '16:9', 'policy2' : 'letterbox', 'title'	 : '16:9 ' + _("Letterbox")},
		   '16_9_panscan'		: {'aspect' : '16:9', 'policy2' : 'panscan', 'title'	 : '16:9 ' + _("Pan&scan")},
		   '16_9_nonlinear'		: {'aspect' : '16:9', 'policy2' : 'panscan', 'title'	 : '16:9 ' + _("Nonlinear")},
		   '16_9_bestfit'		: {'aspect' : '16:9', 'policy2' : 'bestfit', 'title'	 : '16:9 ' + _("Just scale")},
		   '16_9_4_3_pillarbox' : {'aspect' : '16:9', 'policy'	: 'pillarbox', 'title'	 : '4:3 ' + _("PillarBox")},
		   '16_9_4_3_panscan'	: {'aspect' : '16:9', 'policy'	: 'panscan', 'title'	 : '4:3 ' + _("Pan&scan")},
		   '16_9_4_3_nonlinear' : {'aspect' : '16:9', 'policy'	: 'nonlinear', 'title'	 : '4:3 ' + _("Nonlinear")},
		   '16_9_4_3_bestfit'	: {'aspect' : '16:9', 'policy'	: 'bestfit', 'title'	 : _("Just scale")},
		   '4_3_letterbox'		: {'aspect' : '4:3',  'policy'	: 'letterbox', 'policy2' : 'policy', 'title' : _("Letterbox")},
		   '4_3_panscan'		: {'aspect' : '4:3',  'policy'	: 'panscan', 'policy2'	 : 'policy', 'title' : _("Pan&scan")},
		   '4_3_bestfit'		: {'aspect' : '4:3',  'policy'	: 'bestfit', 'policy2'	 : 'policy', 'title' : _("Just scale")}}

	V_MODES = ['16_9_letterbox', '16_9_panscan', '16_9_nonlinear', '16_9_bestfit',
			'16_9_4_3_pillarbox', '16_9_4_3_panscan', '16_9_4_3_nonlinear',
			'16_9_4_3_bestfit','4_3_letterbox', '4_3_panscan', '4_3_bestfit']

	def __init__(self):
		self.aspectChanged = False
		try:
			self.defaultAspect = open("/proc/stb/video/aspect", "r").read().strip()
		except IOError:
			self.defaultAspect = None
		try:
			self.defaultPolicy = open("/proc/stb/video/policy", "r").read().strip()
		except IOError:
			self.defaultPolicy = None
		try:
			self.defaultPolicy2 = open("/proc/stb/video/policy2", "r").read().strip()
		except IOError:
			self.defaultPolicy2 = None
		self.currentVMode = self.V_MODES[0]

		self["aspectChangeActions"] = HelpableActionMap(self, "InfobarAspectChangeActions",
			{
			 "aspectChange":(self.aspectChange, ("Change aspect ratio"))
			  }, -3)
		self.onClose.append(self.__onClose)
		self.postAspectChange = []

	def __onClose(self):
		if self.aspectChanged:
			self.setAspect(self.defaultAspect, self.defaultPolicy, self.defaultPolicy2)

	def getAspectString(self):
		mode = self.V_DICT[self.currentVMode]
		return "%s: %s\n%s: %s" % (
				_("Aspect"), mode['aspect'],
				_("Policy"), mode['title'])

	def setAspect(self, aspect, policy, policy2):
		log.info('aspect: %s policy: %s policy2: %s' % (str(aspect), str(policy), str(policy2)))
		log.logDebug('aspect: %s policy: %s policy2: %s' % (str(aspect), str(policy), str(policy2)))
		if aspect:
			try:
				open("/proc/stb/video/aspect", "w").write(aspect)
			except IOError as e:
				print(e)
		if policy:
			try:
				open("/proc/stb/video/policy", "w").write(policy)
			except IOError as e:
				print(e)
		if policy2:
			try:
				open("/proc/stb/video/policy2", "w").write(policy2)
			except IOError as e:
				print(e)

	def aspectChange(self):
		self.aspectChanged = True
		modeIdx = self.V_MODES.index(self.currentVMode)
		if modeIdx == len(self.V_MODES) - 1:
			modeIdx = 0
		else:
			modeIdx += 1
		self.currentVMode = self.V_MODES[modeIdx]
		mode = self.V_DICT[self.currentVMode]
		self.setAspect(mode['aspect'], mode.get('policy'), mode.get('policy2'))
		for f in self.postAspectChange:
			f()

# pretty much openpli's one but simplified
class InfoBarSubservicesSupport(object):
	def __init__(self):
		self["InfoBarSubservicesActions"] = HelpableActionMap(self,
				"ColorActions", { "green": (self.showSubservices, _("Show subservices"))}, -2)
		self.__timer = eTimer()
		self.__timer_conn = (self.__timer.timeout, self.__seekToCurrentPosition)
		self.onClose.append(self.__onClose)

	def __onClose(self):
		self.__timer.stop()
		del self.__timer_conn
		del self.__timer

	def showSubservices(self):
		service = self.session.nav.getCurrentService()
		service_ref = self.session.nav.getCurrentlyPlayingServiceReference()
		subservices = service and service.subServices()
		numsubservices = subservices and subservices.getNumberOfSubservices() or 0

		selection = 0
		choice_list = []
		for idx in range(0, numsubservices):
			subservice_ref = subservices.getSubservice(idx)
			if service_ref.toString() == subservice_ref.toString():
				selection = idx
			choice_list.append((subservice_ref.getName(), subservice_ref))
		if numsubservices > 1:
			self.session.openWithCallback(self.subserviceSelected, ChoiceBox,
				title = _("Please select subservice..."), list = choice_list,
				selection = selection, skin_name="SubserviceSelection")

	def subserviceSelected(self, service_ref):
		if service_ref:
			self.__timer.stop()
			self.__playpos = getPlayPositionPts(self.session) or 0
			duration = getDurationPts(self.session) or 0
			if (self.__playpos > 0 and duration > 0
					and self.__playpos < duration):
				self.__timer.start(500, True)
			self.session.nav.playService(service_ref[1])

	def __seekToCurrentPosition(self):
		if getPlayPositionPts(self.session) is None:
			self.__timer.start(500, True)
		else:
			self.seekToPts(self.session, self.__playpos)
			del self.__playpos

class ArchivCZSKMoviePlayer(InfoBarBase, SubsSupport, SubsSupportStatus, InfoBarSubtitleSupport, InfoBarSeek,
		InfoBarAudioSelection, InfoBarSubservicesSupport, InfoBarNotifications,
		InfoBarShowHide, InfoBarAspectChange, HelpableScreen, Screen):

	RESUME_POPUP_ID = "aczsk_resume_popup"

	def __init__(self, session, player_callback):
		Screen.__init__(self, session)
		self.skinName = ["ArchivCZSKMoviePlayer", "MoviePlayer"]
		InfoBarBase.__init__(self)
		InfoBarShowHide.__init__(self)
		InfoBarSeek.__init__(self)
		# disable slowmotion/fastforward
		self.seekFwd = self.seekFwdManual
		self.seekBack = self.seekBackManual
		self.relative_seek_enabled = True
		self.start_pts = None
		initSubsSettings()

		InfoBarSubtitleSupport.__init__(self)
		SubsSupport.__init__(self,
			defaultPath = config_archivczsk.tmpPath.value,
			forceDefaultPath = True,
			searchSupport = True,
			embeddedSupport = True,
			preferEmbedded = True)
		SubsSupportStatus.__init__(self)

		InfoBarAudioSelection.__init__(self)
		InfoBarNotifications.__init__(self)
		InfoBarSubservicesSupport.__init__(self)
		InfoBarAspectChange.__init__(self)
		self.postAspectChange.append(self.__aspect_changed)
		HelpableScreen.__init__(self)
		self.status_dialog = self.session.instantiateDialog(StatusScreen)
		self.skip_dialog = self.session.instantiateDialog(SkipNotificationScreen)
		self.player_callback = player_callback
		self.__timer = eTimer()
		self.__timer_conn = eConnectCallback(self.__timer.timeout, self.__pts_available)
		self.__timer_seek = eTimer()
		self.__timer_seek_conn = eConnectCallback(self.__timer_seek.timeout, self.__check_seek_position)
		self.__timer_seek_notification = eTimer()
		self.__timer_seek_notification_conn = eConnectCallback(self.__timer_seek_notification.timeout, self.setup_skip_notification)
		self.__timer_watching = eTimer()
		self.__timer_watching_conn = eConnectCallback(self.__timer_watching.timeout, self.__watching)
		self.__timer_tracks_setup = eTimer()
		self.__timer_tracks_setup_conn = eConnectCallback(self.__timer_tracks_setup.timeout, self.setup_tracks)
		self.__timer_skip_notification = eTimer()
		self.__timer_skip_notification_conn = eConnectCallback(self.__timer_skip_notification.timeout, self.show_skip_notification)
		self.only_future_skip_notifications = False
		self.__subtitles_url = None
		self.__resume_time_sec = None
		self.__resume_popup = True
		self.duration_sec = None
		self.skip_times = None #[(5, 30), (35, 70), (120, 300)]
		self.skip_running = None
		self.old_position = -1
		self.auto_skip = {}

		self["actions"] = HelpableActionMap(self, "ArchivCZSKMoviePlayerActions", {
			"showPlaylist": (boundFunction(self.player_callback, ("playlist", "show",)), _("Show playlist")),
			"nextEntry": (boundFunction(self.player_callback, ("playlist", "next",)), _("Play next entry in playlist")),
			"prevEntry": (boundFunction(self.player_callback, ("playlist", "prev",)), _("Play previous entry in playlist")),
			"cancel": (self.__my_cancel, _("Exit player")),
			"toggleShow": (boundFunction(self.toggleShow, aczsk=True), _("Show/hide infobar")),
			"switchPlayer": (boundFunction(self.player_callback, ("player_switch",)), _("Switch player type")),
		}, -2)

		self.__event_tracker = ServiceEventTracker(screen=self, eventmap=
		{
			iPlayableService.evStart: self.__service_started,
		})
		self.onClose.append(self.__on_close)

	def __my_cancel(self):
		if self.skip_dialog.is_shown:
			log.debug("Hiding notification window")
			self.skip_dialog.hide()
		else:
			self.player_callback(("exit",))

	def toggleShow(self, aczsk=False):
		if aczsk == False:
			# this is hack to filter out double run on OpenATV images ...
			return

		if self.skip_dialog.is_shown:
			self.skip_dialog.run_skip()
		else:
			# tries to call infobar's toggleShow() - this should be implemented in InfoBarShowHide, but nobody knows ...

			try:
#				InfoBarShowHide.toggleShow(self)
				super(ArchivCZSKMoviePlayer, self).toggleShow()
			except:
				pass

	def __on_close(self):
		self.__timer.stop()
		self.__timer_watching.stop()
		del self.__timer_conn
		del self.__timer
		del self.__timer_seek_conn
		del self.__timer_seek
		del self.__timer_seek_notification_conn
		del self.__timer_seek_notification
		del self.__timer_watching_conn
		del self.__timer_watching
		del self.__timer_tracks_setup_conn
		del self.__timer_tracks_setup
		del self.__timer_skip_notification_conn
		del self.__timer_skip_notification
		RemovePopup(self.RESUME_POPUP_ID)
		self.session.deleteDialog(self.status_dialog)
		self.session.deleteDialog(self.skip_dialog)

	def show_skip_notification(self):
		def do_skip(skip_id, position):
			self.auto_skip[skip_id] = True
			self.skip_running = skip_id
			self.doSeek(position * 90000)

		# show window with skip notifiction
		cur_position = getPlayPositionInSeconds(self.session)
		log.debug("Going to show skip notification - current position is %d" % cur_position)

		for i, st in enumerate(self.skip_times):
			st_end = st[1]
			if not st_end:
				st_end = self.duration_sec + 60

			if cur_position >= st[0] and cur_position < st_end:
				if i != 2 and self.auto_skip.get(i, False):
					if self.skip_running == i:
						self.skip_running = None
					else:
						self.doSeek(st_end * 90000)
				else:
					if i == 0:
						text = _("Skip intro")
					elif i == len(self.skip_times)-1:
						text = _("Skip credits")
					else:
						text = _("Skip this part")

					log.debug("Showing skip notification to seek to position: %d" % st_end)
					self.skip_dialog.show_skip(text + ' >>>', cbk=lambda: do_skip(i, st_end), timeout=(st_end - cur_position))
				break

		self.only_future_skip_notifications = True
		self.setup_skip_notification()

	def setup_skip_notification(self):
		if self.__timer_skip_notification.isActive():
			self.__timer_skip_notification.stop()

		if self.__timer_seek_notification.isActive():
			self.__timer_seek_notification.stop()

		if not self.skip_times:
			log.debug("No skip times configured")
			return

		if not self.duration_sec:
			log.debug("Movie duration is unknown - not setting up skip times")
			# showing skip notification is only available, when we know total play length
			return

		cur_position = getPlayPositionInSeconds(self.session)
		if cur_position == self.old_position:
			# seek still in progress, try again later
			log.debug("Seek not finished yet - planing new setup in a while")
			self.__timer_seek_notification.start(1000, True)
			return

		for st in self.skip_times:
			if cur_position < st[0]:
				# plan to show skip notification
				log.debug("Planing skip notification in %ds" % (st[0] - cur_position))
				self.__timer_skip_notification.start((1 + st[0] - cur_position) * 1000, True)
				break

			st_end = st[1]
			if not st_end:
				st_end = self.duration_sec

			if not self.skip_dialog.is_shown and not self.only_future_skip_notifications and cur_position >= st[0] and cur_position < st_end and (st_end - cur_position) > 3:
				# show notification now (using timer)
				log.debug("Showing skip notification now")
				self.__timer_skip_notification.start(10, True)
				break

		self.__timer_seek_notification.start(10000, True)

	def __aspect_changed(self):
		self.status_dialog.set_status(self.getAspectString(), "#00ff00")

	def __check_seek_position(self):
		self.player_callback(("seek",))

	def __watching(self):
		self.player_callback(("watching",))

	def __pts_available(self):
		self.start_pts = getPlayPositionPts(self.session)
		if self.start_pts is None:
			self.__timer.start(500, True)
		else:
			self.player_callback(("start",))
			self.duration_sec = getDurationInSeconds(self.session)
			self.setup_skip_notification()
			if self.__resume_time_sec is not None:
				if self.__resume_time_sec > 0 and self.duration_sec and self.duration_sec > 0 and self.__resume_time_sec < self.duration_sec:
					self.doSeek(self.__resume_time_sec * 90000)

				self.__resume_time_sec = None
				if self.__resume_popup:
					RemovePopup(self.RESUME_POPUP_ID)
			if self.__subtitles_url:
				self.loadSubs(toString(self.__subtitles_url))

			self.__timer_tracks_setup.start(500, True)

	def __service_started(self):
		self.__timer.stop()
		self.__timer_watching.stop()
		self.resetSubs(True)

		def service_started_continue(result):
			if result == True:
				AddNotificationWithID(self.RESUME_POPUP_ID,
						MessageBox, _("Resuming playback"), timeout=0,
						type=MessageBox.TYPE_INFO, enable_input=False)
			elif result == False:
				self.__resume_time_sec = None

			# always run pts detection to get video length (if available)
			self.__timer.start(500, True)

		if self.__resume_time_sec is not None and self.__resume_popup:
			self.session.openWithCallback(service_started_continue, MessageBox, text=_("Resume playback from last play position?"), type=MessageBox.TYPE_YESNO, timeout=10, timeout_default=False)
		else:
			service_started_continue(None)

		self.__timer_watching.start(5 * 60 * 1000) # 5 min.

	# inspiration from InforBarGenerics,py and AudioSelection.py
	def get_audio_track_list(self):
		service = self.session.nav.getCurrentService()
		audio_list = []

		audio_service = service and service.audioTracks()
		audio_count = audio_service.getNumberOfTracks()
		for i in range(audio_count):
			ti = audio_service.getTrackInfo(i)
			audio_list.append((i, ti.getLanguage(), ti.getDescription(),))
		return audio_service, audio_list

	# inspiration from InforBarGenerics,py and AudioSelection.py
	def get_subtitles_track_list(self):
		service = self.session.nav.getCurrentService()

		subs_list = []

		if DMM_IMAGE:
			subs_service = service and service.subtitleTracks()
			subs_count = subs_service and subs_service.getNumberOfSubtitleTracks() or 0
			for i in range(subs_count):
				ti = subs_service.getSubtitleTrackInfo(i)
#				ti.isForced()
#				subs_list.append( (2, i, 1, 0, ti.getLanguage(), ))
				subs_list.append({
					'idx': i,
					'forced': ti.isForced(),
					'lang': ti.getLanguage()
				})
		else:
			# the rest of the world
			subs_service = service and service.subtitle()
			for s in subs_service.getSubtitleList():
				subs_list.append({
					'idx': s[1],
					'forced': None,
					'lang': s[4]
				})

		return subs_list

	def lang_to_lang_list(self, lang):
		# get all possible ISO639 lang codes
		if lang == 'cs':
			return ['cs', 'ces', 'cze']
		elif lang == 'sk':
			return ['sk', 'slk', 'slo']
		elif lang == 'en':
			return ['en', 'eng']
		else:
			return [lang]

	def setup_tracks(self):
		try:
			self.__setup_tracks()
		except:
			log.error("Failed to setup audio/subtitles tracks:\n%s" % traceback.format_exc())

	def __setup_tracks(self):
		if not self.tracks_settings:
			return

		audio_service, audio_list = self.get_audio_track_list()
		log.debug("Available audio tracks: %s" % str(audio_list))

		subs_list = self.get_subtitles_track_list()
		log.debug("Available subtitle tracks: %s" % str(subs_list))

		def get_audio_index(setting_name):
			a_idx = []
			for l in self.tracks_settings.get(setting_name):
				lang_list = self.lang_to_lang_list(l)
				for idx, alang, codec in audio_list:
					if alang in lang_list:
						log.debug("Found %s audio on index %d" % (l, idx))
						a_idx.append((idx, codec.lower().replace('-', ''),))
				if len(a_idx) > 0:
					break
			return a_idx

		def get_subtitle_index(setting_name):
			s_idx = []
			for l in self.tracks_settings.get(setting_name):
				lang_list = self.lang_to_lang_list(l)
				for item in subs_list:
					if item['lang'].lower() in lang_list:
						log.debug("Found %s subtitle on index %d" % (l, item['idx']))
						s_idx.append(item)
				if len(s_idx) > 0:
					break
			return s_idx

		def run_subtitles(idx, lang):
			log.debug("Enabling subtitles on index %d" % idx)
			try:
				self.enableSubtitle((2, idx, 1, 0, lang,))
			except:
				# compatibility with durinov's oe25,26 subssupport patch
				class FakeIdx():
					def __init__(self, idx):
						self.idx = idx

				self.enableSubtitle(FakeIdx(idx))

		a_idx = get_audio_index('lang_priority')
		if len(a_idx) > 0:
			audio_fallback = False
		else:
			audio_fallback = True
			a_idx = get_audio_index('lang_fallback')

		audio_selected = None
		if len(a_idx) > 0:
			# search for multichannel codec (if available)
			for idx, codec in a_idx:
				if 'ac3' in codec or 'dts' in codec:
					audio_selected = idx
					break
			else:
				audio_selected = a_idx[0][0]

			# set new audio track
			if audio_selected != audio_service.getCurrentTrack():
				# if new audio track is not actually selected
				if config.plugins.archivCZSK.videoPlayer.autoChangeAudio.value:
					log.info("Setting audio track to index %d" % audio_selected)
					audio_service.selectTrack(audio_selected)
				else:
					log.info("Not setting audio track to index %d - changing audio track is disabled in settings" % audio_selected)
			else:
				log.info("Audio track already set to index %d" % audio_selected)

		# external subtitles have priority, so don't setup embedded when external are available
		if not self.__subtitles_url:
			s_idx = get_subtitle_index('lang_priority')

			if len(s_idx) > 0:
				# on other then DMM enigma's there is no info about forced subtitles
				# we consider forced subtitles when there is only one audio track and one subtitle track with the same language and no forced info is available
				if len(audio_list) == 1 and len(subs_list) == 1 and audio_list[0][1].lower() == subs_list[0]['lang'].lower() and s_idx[0]['forced'] == None:
					log.debug("Setting fake forced subtitles to index 0 - have only one audio and subtitles track with the same language")
					s_idx[0]['forced'] = True
				else:
					# or we will fake the first one as forced if there are more subtitles with the same lang
					i = 0
					for s in s_idx:
						if s['forced'] == None:
							s['forced'] = (i == 0) and len(s_idx) > 1 # no info about forced subtitles from enigma, so use this fake one
							if s['forced']:
								log.debug("Setting fake forced subtitles to index %d" % s['idx'])
						i += 1

				if self.tracks_settings['subs_autostart']:
					log.debug("Subtitles found and autostart is enabled")

					if self.tracks_settings['subs_always'] or audio_fallback:
						log.debug("Always run subtitles is enabled or no lang found in audio list")
						# no dubbed movie - run the first not forced subtitle
						for s in s_idx:
							if not s['forced']:
								subs_info = s
								break
						else:
							subs_info = s_idx[0]

						run_subtitles(subs_info['idx'], subs_info['lang'])
					elif self.tracks_settings['subs_forced_autostart']:
						log.debug("Forced subtitles are enabled")
						# run forced subtitle
						for subs_info in s_idx:
							if subs_info['forced']:
								run_subtitles(subs_info['idx'], subs_info['lang'])
								break
						else:
							log.debug("No forced subtitles found")

	def play_service_ref(self, service_ref, subtitles_url=None, resume_time_sec=None, resume_popup=True, status_msg=None, tracks_settings=None, skip_times=None):
		self.duration_sec = None
		self.__subtitles_url = subtitles_url
		self.__resume_time_sec = resume_time_sec
		self.__resume_popup = resume_popup
		self.tracks_settings = tracks_settings
		self.skip_times = skip_times

		self.session.nav.stopService()
		self.session.nav.playService(service_ref)

		if status_msg:
			self.status_dialog.set_status(status_msg)

	def doEofInternal(self, playing):
		log.info("doEofInternal(%s)"%playing)
		self.player_callback(("eof", playing,))

	def setInfoBarText(self, title):
		try:
			self.setTitle(toString(title))
		except:
			log.logError("Set info bar text failed.\n%s"%traceback.format_exc())
			pass

	def relativeSeekEnabled(self, enabled):
		if enabled:
			log.info("Enabling relative seek")
		else:
			log.info("Disabling relative seek. I will use absolute seek instead.")
		self.relative_seek_enabled = enabled

	def pauseService(self):
		seekstate = self.seekstate
		InfoBarSeek.pauseService(self)
		if seekstate != self.seekstate and self.seekstate == self.SEEK_STATE_PAUSE:
			# call player callback only if seekstate changed and current one is set to pause
			self.player_callback(("pause",))

	def unPauseService(self):
		seekstate = self.seekstate
		InfoBarSeek.unPauseService(self)
		if seekstate != self.seekstate and self.seekstate == self.SEEK_STATE_PLAY:
			# call player callback only if seekstate changed and current one is set to play
			self.player_callback(("unpause",))

	def doSeek(self, pts ):
		current_pts = getPlayPositionPts(self.session)
		log.debug("do seek absolute: %s, current position: %s" % (pts, current_pts))
		self.old_position = getPlayPositionInSeconds(self.session, current_pts)
		InfoBarSeek.doSeek(self, pts )
		if self.__timer_seek.isActive():
			self.__timer_seek.stop()

		self.__timer_seek.start(5000, True)

		if self.skip_times:
			self.only_future_skip_notifications = False
			if self.__timer_seek_notification.isActive():
				self.__timer_seek_notification.stop()

			self.__timer_seek_notification.start(1000, True)

	def doSeekRelative(self, pts ):
		current_pts = getPlayPositionPts(self.session)
		log.debug("do seek relative: %s, current position: %s" % (pts, current_pts))
		if self.relative_seek_enabled == False:
			if self.start_pts == None or current_pts == None:
				log.error("No start pts or current pts available - can't do absolute seek!")
			else:
				return self.doSeek(current_pts - self.start_pts + pts)

		self.old_position = getPlayPositionInSeconds(self.session, current_pts)
		InfoBarSeek.doSeekRelative(self, pts )
		if self.__timer_seek.isActive():
			self.__timer_seek.stop()

		# start timer to notify addon about seek state
		self.__timer_seek.start(5000, True)

		if self.skip_times:
			self.only_future_skip_notifications = False
			if self.__timer_seek_notification.isActive():
				self.__timer_seek_notification.stop()

			# start timer to for handling skip notifications
			self.__timer_seek_notification.start(1000, True)
