# -*- coding: utf-8 -*-
import traceback

from Components.config import config
from Screens.MessageBox import MessageBox
from Screens.ChoiceBox import ChoiceBox

from .item import ItemHandler
from ... import _, log
from ...gui.exception import AddonExceptionHandler, DownloadExceptionHandler
from ...engine.items import PExit, PVideoResolved, PVideoNotResolved, PPlaylist
from ...engine.tools.util import toString
from ...gui.common import showInfoMessage, showErrorMessage, showWarningMessage
from ...colors import DeleteColors
from ...engine.player.info import videoPlayerInfo
from ...compat import DMM_IMAGE
from ...engine.trakttv import trakttv


class MediaItemHandler(ItemHandler):
	""" Template class - handles Media Item interaction """

	def __init__(self, session, content_screen, content_provider, info_modes):
		ItemHandler.__init__(self, session, content_screen, info_modes)
		self.content_provider = content_provider

	def _open_item(self, item, mode='play', *args, **kwargs):
		self.play_item(item, mode, args, kwargs)

	def isValidForTrakt(self, item):
		if isinstance(item, PPlaylist):
			item = item.get_current_item()

		if hasattr(item, 'traktItem') and item.traktItem is not None:
			if 'type' in item.traktItem and 'ids' in item.traktItem:
				return True
		return False

	
	# action:
	# 	- play
	# 	- end
	# 	- seek
	# 	- pause
	# 	- unpause
	# 	- watching (every 5minutes)
	def cmdStats(self, item, action, duration=None, position=None, finishCB=None, sendTraktWatchedCmd=False):
		if isinstance(item, PPlaylist):
			item = item.get_current_item()

		def open_item_finish(result):
			log.logDebug("Stats (%s) call finished.\n%s"%(action,result))
			if paused and not sendTraktWatchedCmd:
				self.content_provider.pause()
			if sendTraktWatchedCmd:
				return self.cmdTrakt(item, 'scrobble', finishCB)
			elif finishCB is not None:
				finishCB()
		paused = self.content_provider.isPaused()
		try:
			if paused:
				self.content_provider.resume()
			
			extra_params = {
				'duration': duration,
				'position': position,
			}
				
			# content provider must be in running state (not paused)
			self.content_provider.stats(self.session, item.dataItem, action, extra_params, successCB=open_item_finish, errorCB=open_item_finish)
		except:
			log.logError("Stats call failed.\n%s"%traceback.format_exc())
			if paused:
				self.content_provider.pause()
			if finishCB is not None:
				finishCB()
			
	# action:
	#	- add
	#	- remove
	#	- watched
	#	- unwatched
	#   - scrobble
	def cmdTrakt(self, item, action, finishedCB=None):
		if isinstance(item, PPlaylist):
			item = item.get_current_item()

		def finishCb(result):
			if paused:
				self.content_provider.pause()
			if finishedCB is not None:
				finishedCB()
		def open_item_success_cb(result):
			log.logDebug("Trakt.tv (%s) call success. %s" % (action, result))
			#OK, ERROR
#			list_items, command, args = result
#			if args['isError']:
#				return showErrorMessage(self.session, args['msg'], 10, finishCb)
#			else:
#				return showInfoMessage(self.session, args['msg'], 10, finishCb)
			finishCb(None)
		def open_item_error_cb(failure):
			log.logDebug("Trakt.tv (%s) call failed. %s" % (action,failure))
#			return showErrorMessage(self.session, "Operation failed.", 10, finishCb)
			finishCb(None)

		def eval_trakt_pairing( result ):
			if result:
				self.cmdTrakt( item, 'reload', finishedCB )
			else:
				finishCb(None)
				
		paused = self.content_provider.isPaused()
		try:
			if action == 'open_action_choicebox':
				trakttv.open_trakt_action_choicebox(self.session, item, self.cmdTrakt )
			elif action == 'pair':
				trakttv.handle_trakt_pairing(self.session, eval_trakt_pairing )
			else:
				success, msg = trakttv.handle_trakt_action( action, item.traktItem )

				if paused:
					self.content_provider.resume()

				# content provider must be in running state (not paused)
				self.content_provider.trakt(self.session, item.traktItem, action, { 'success': success, 'msg': msg }, successCB=open_item_success_cb, errorCB=open_item_error_cb)
		except:
			log.logError("Trakt.tv call failed.\n%s" % traceback.format_exc())
			if paused:
				self.content_provider.pause()
			if finishedCB is not None:
				finishedCB()

	def play_item(self, item, mode='play', *args, **kwargs):
		# This horrible code is needed to sync player end with calling of stats and trakt commands
		# Without it endPlayFinish() will be called before stats command finishes and this will
		# end in lock, because content provider will not be running
		sync_info = {
			'stats_command_running': False,
			'endPlayFinish_delayed': False
		}
		
		def endPlayFinish():
			if sync_info['stats_command_running']:
				sync_info['endPlayFinish_delayed'] = True
			else:
				self.content_screen.workingFinished()
				if self.content_provider.isPaused():
					self.content_provider.resume()

		def end_play():
			sync_info['stats_command_running'] = False

			if sync_info['endPlayFinish_delayed']:
				sync_info['endPlayFinish_delayed'] = False
				endPlayFinish()

		def handle_trakt_scrobble(command, duration, position):
			notify_scrobble = False

			if duration != None and position != None:
				position_percentage = int((position * 100) // duration)
			else:
				position_percentage = None

			if position_percentage != None and 'trakt' in self.content_provider.capabilities and self.isValidForTrakt(item):
				position_percentage = int((position * 100) // duration)
				log.logInfo("Trakt.tv scrobble command %s received with position %d" % (command, position_percentage))

				try:
					if command in ('start', 'seek', 'unpause'):
						trakttv.scrobble('start', item.traktItem, position_percentage)
					elif command == 'pause':
						trakttv.scrobble('pause', item.traktItem, position_percentage)
					elif command == 'stop':
						ret = trakttv.scrobble('stop', item.traktItem, position_percentage)
						if ret == 'scrobble':
							notify_scrobble = True
							
				except:
					log.logError("Trakt.tv scrobble command failed.\n%s" % traceback.format_exc())

			return notify_scrobble

		def player_event_handler(command, duration, position):
			log.logDebug("Media event callback called: command=%s, duration=%s, position=%s" % (command, str(duration), str(position)))
			notify_scrobble = handle_trakt_scrobble(command, duration, position)

			sync_info['stats_command_running'] = True
			if command == 'start':
				self.cmdStats(item, 'play', duration, position)
			elif command == 'stop':
				self.cmdStats(item, 'end', duration, position, finishCB=end_play, sendTraktWatchedCmd=notify_scrobble)
			elif command in ('seek', 'pause', 'unpause', 'watching'):
				self.cmdStats(item, command, duration, position)
			else:
				sync_info['stats_command_running'] = False

		def player2stype( player ):
			# enum: 'Predvolený|gstplayer|exteplayer3|DMM|DVB (OE>=2.5)'
			player_mapping = {
				'0' : 4097, # Default
			}

			# fill only available players - if not available player is choosen then default service 4097 will be used
			if videoPlayerInfo.serviceappAvailable:
				if videoPlayerInfo.gstplayerAvailable:
					player_mapping['1'] = 5001  # gstplayer
				if videoPlayerInfo.exteplayer3Available:
					player_mapping['2'] = 5002  # exteplayer3
			
			if DMM_IMAGE:
				# this is only available on DreamOS
				player_mapping['3'] = 8193  # DMM player
				player_mapping['4'] = 1     # DVB service
				
			return player_mapping.get( player, 4097 )
		
		stype = None
		if 'forced_player' in kwargs:
			stype = kwargs['forced_player']
		else:
			stype = player2stype( self.content_provider.video_addon.settings.get_setting('auto_used_player') )
		
		self.content_screen.workingStarted()
		self.content_provider.pause()
		self.content_provider.play(self.session, item, mode, endPlayFinish, player_event_handler, stype)

	def download_item(self, item, mode="", *args, **kwargs):
		@DownloadExceptionHandler(self.session)
		def start_download(mode):
			try:
				self.content_provider.download(self.session, item, mode=mode)
			except Exception:
				self.content_screen.workingFinished()
				raise
		start_download(mode)

	def _init_menu(self, item):
		provider = self.content_provider
		# TRAKT menu (show only if item got data to handle trakt)
		if 'trakt' in provider.capabilities and self.isValidForTrakt(item):
			if trakttv.valid():
				item.add_context_menu_item(_("Trakt.tv action"), action=self.cmdTrakt, params={'item':item, 'action':'open_action_choicebox'})
			else:
				item.add_context_menu_item(_('Pair device with Trakt.tv'), action=self.cmdTrakt, params={'item':item, 'action':'pair'})

		download_enabled = item.download if hasattr(item, 'download') else False

		if 'download' in provider.capabilities and download_enabled:
			item.add_context_menu_item(_("Download"), action=self.download_item, params={'item':item, 'mode':'auto'})
		if 'play' in provider.capabilities:
			item.add_context_menu_item(_("Play"), action=self.play_item, params={'item':item, 'mode':'play'})
			if videoPlayerInfo.serviceappAvailable:
				if videoPlayerInfo.gstplayerAvailable:
					item.add_context_menu_item(_("Play using gstplayer"), action=self.play_item, params={'item':item, 'mode':'play', 'forced_player':5001})
				
				if videoPlayerInfo.exteplayer3Available:
					item.add_context_menu_item(_("Play using exteplayer3"), action=self.play_item, params={'item':item, 'mode':'play', 'forced_player':5002})
		if 'play_and_download' in provider.capabilities and download_enabled:
			item.add_context_menu_item(_("Play and Download"), action=self.play_item, params={'item':item, 'mode':'play_and_download'})

class VideoResolvedItemHandler(MediaItemHandler):
	handles = (PVideoResolved, )
	def __init__(self, session, content_screen, content_provider):
		info_handlers = ['csfd','item']
		MediaItemHandler.__init__(self, session, content_screen, content_provider, info_handlers)



class VideoNotResolvedItemHandler(MediaItemHandler):
	handles = (PVideoNotResolved, )
	def __init__(self, session, content_screen, content_provider):
		MediaItemHandler.__init__(self, session, content_screen, content_provider, ['item','csfd'])
		self.known_commands = ('show_msg',)

	def _init_menu(self, item):
		MediaItemHandler._init_menu(self, item)
		item.add_context_menu_item(_("Resolve videos"),
									   action=self._resolve_videos,
									   params={'item':item})
		if 'favorites' in self.content_provider.capabilities:
			item.add_context_menu_item(_("Add Shortcut"), 
					action=self.ask_add_shortcut, 
					params={'item':item})
		else:
			item.remove_context_menu_item(_("Add Shortcut"), 
					action=self.ask_add_shortcut, 
					params={'item':item})

	def ask_add_shortcut(self, item):
		self.item = item
		self.session.openWithCallback(self.add_shortcut_cb, MessageBox,
				text="%s %s %s"%(_("Do you want to add"), toString(item.name),	_("shortcut?")),
				type=MessageBox.TYPE_YESNO)

	def add_shortcut_cb(self, cb):
		if cb:
			self.content_provider.create_shortcut(self.item)

	def play_item(self, item, mode='play', *args, **kwargs):

		def video_selected_callback(res_item):
			MediaItemHandler.play_item(self, res_item, mode, *args, **kwargs)

		if mode != 'play' or config.plugins.archivCZSK.showVideoSourceSelection.value:
			# if mode == 'play' then result is redirected to player which suppports playlists
			# in other modes (like play_and_download) playlists are not supported and result
			# can be exactly one PVideoResolved item
			self._resolve_video(item, video_selected_callback, keep_playlists=(mode == 'play'))
		else:
			self._resolve_videos(item)

	def download_item(self, item, mode="", *args, **kwargs):
		def wrapped(res_item):
			MediaItemHandler.download_item(self, res_item, mode)
			self.content_screen.workingFinished()

		self._resolve_video(item, wrapped, keep_playlists=False)

	def handle_known_command(self, cmd, args, continue_cb):
		if cmd == "show_msg":
			self.content_screen.stopLoading()
			msgType = args.get('msgType', 'info').lower()
			msgTimeout = int(args.get('msgTimeout', 15))
			canClose = args.get('canClose', True)

			if msgType == 'error':
				return showErrorMessage(self.session, args['msg'], msgTimeout, continue_cb, enableInput=canClose)
			elif msgType == 'warning':
				return showWarningMessage(self.session, args['msg'], msgTimeout, continue_cb, enableInput=canClose)
			else:
				return showInfoMessage(self.session, args['msg'], msgTimeout, continue_cb, enableInput=canClose)

	def _filter_by_quality(self, items):
		pass

	def unpack_playlist(self, items):
		for item in list(items):
			if isinstance(item, PPlaylist):
				items.remove(item)
				items.extend(item.playlist)

	def _resolve_video(self, item, callback, keep_playlists=True):

		def selected_source(answer):
			if answer is not None:
				# entry point of play video source
				callback(answer[1])
			else:
				self.content_screen.workingFinished()

		def open_item_success_cb(result):
			def continue_cb(res):
				if not keep_playlists:
					self.unpack_playlist(list_items)

				self._filter_by_quality(list_items)
				if len(list_items) > 1:
					choices = []
					for i in list_items:
						name = i.name
						# TODO remove workaround of embedding
						# quality in title in addons
						if i.quality and i.quality not in i.name:
							if "[???]" in i.name:
								name = i.name.replace("[???]", "[%s]" % (i.quality))
							else:
								name = "[%s] %s" % (i.quality, i.name)
						choices.append((DeleteColors(toString(name)), i))
					self.session.openWithCallback(selected_source,
							ChoiceBox, _("Please select source"),
							list=choices,
							skin_name=["ArchivCZSKVideoSourceSelection"])
				elif len(list_items) == 1:
					item = list_items[0]
					callback(item)
				else: # no video
					self.content_screen.workingFinished()

			self.content_screen.stopLoading()
			self.content_screen.showList()
			list_items, command, args = result
			
			command = command.lower() if command else None
			#client.add_operation("SHOW_MSG", {'msg': 'some text'},
			#								   'msgType': 'info|error|warning',		#optional
			#								   'msgTimeout': 10,					#optional
			#								   'canClose': True						#optional
			#								  })
			if command in self.known_commands:
				return self.handle_known_command(command, args, continue_cb)
			elif command:
				log.logError("Unknown media handler command %s - ignoring" % command)
				command = None
				args = {}

			continue_cb(None)

		@AddonExceptionHandler(self.session)
		def open_item_error_cb(failure):
			self.content_screen.stopLoading()
			self.content_screen.showList()
			self.content_screen.workingFinished()
			failure.raiseException()

		self.content_screen.hideList()
		self.content_screen.startLoading()
		self.content_screen.workingStarted()
		self.content_provider.get_content(self.session, item.params, open_item_success_cb, open_item_error_cb)


	def _resolve_videos(self, item):
		def open_item_success_cb(result):
			def continue_cb(res):
				self.content_screen.save()
				content = {'parent_it':item, 'lst_items':list_items, 'refresh':False}
				self.content_screen.stopLoading()
				self.content_screen.load(content)
				self.content_screen.showList()
				self.content_screen.workingFinished()

			list_items, screen_command, args = result
			list_items.insert(0, PExit())
			if screen_command is not None:
				if screen_command.lower() in self.known_commands:
					return self.handle_known_command(screen_command.lower(), args, continue_cb)
				else:
					self.content_screen.resolveCommand(screen_command, args)
			else:
				continue_cb(None)

		@AddonExceptionHandler(self.session)
		def open_item_error_cb(failure):
			self.content_screen.stopLoading()
			self.content_screen.showList()
			self.content_screen.workingFinished()
			failure.raiseException()

		self.content_screen.workingStarted()
		self.content_screen.hideList()
		self.content_screen.startLoading()
		self.content_provider.get_content(self.session, item.params, open_item_success_cb, open_item_error_cb)



class PlaylistItemHandler(MediaItemHandler):
	handles = (PPlaylist, )
	def __init__(self, session, content_screen, content_provider, info_modes=None):
		if not info_modes:
			info_modes = ['item','csfd']
		MediaItemHandler.__init__(self, session, content_screen, content_provider, info_modes)

	def show_playlist(self, item):
		self.content_screen.save()
		list_items = [PExit()]
		list_items.extend(item.playlist[:])
		content = {'parent_it':item,
						  'lst_items':list_items,
						  'refresh':False}
		self.content_screen.load(content)

	def _init_menu(self, item, *args, **kwargs):
		provider = self.content_provider
		if 'play' in provider.capabilities:
			item.add_context_menu_item(_("Play"),
														action=self.play_item,
														params={'item':item,
														'mode':'play'})
		item.add_context_menu_item(_("Show playlist"),
								   action=self.show_playlist,
								   params={'item':item})
