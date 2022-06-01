import traceback
from Screens.MessageBox import MessageBox

from .item import ItemHandler
from Plugins.Extensions.archivCZSK import _, log
from Plugins.Extensions.archivCZSK.gui.exception import AddonExceptionHandler
from Plugins.Extensions.archivCZSK.engine.items import PExit, PFolder, PSearchItem, PSearch
from Plugins.Extensions.archivCZSK.gui.common import showInfoMessage, showErrorMessage, showWarningMessage
from Plugins.Extensions.archivCZSK.engine.trakttv import trakttv

from ...py3compat import *

class FolderItemHandler(ItemHandler):
	handles = (PFolder,)

	def __init__(self, session, content_screen, content_provider):
		info_modes = ['item', 'csfd']
		ItemHandler.__init__(self, session, content_screen, info_modes)
		self.content_provider = content_provider

	def is_search(self, item):
		return isinstance(item, (PSearchItem))

	def _open_item(self, item, *args, **kwargs):
		
		def open_item_success_cb(result):
			def continue_cb(res):
				list_items = []
				args = {}
				list_items.insert(0, PExit())
				self.content_screen.startLoading()
				if not self.content_screen.refreshing:
					self.content_screen.save()
				else:
					self.content_screen.refreshing = False

				if self.is_search(item):
					parent_content = self.content_screen.getParent()
					if parent_content:
						parent_content['refresh'] = True

				content = {'parent_it':item,
						   'lst_items':list_items, 
						   'refresh':False,
						   'index':kwargs.get('position', 0)}
				self.content_screen.load(content)
				self.content_screen.stopLoading()
				self.content_screen.showList()
				self.content_screen.workingFinished()

			def continue_cb_normal(res):
				if not list_items and screen_command is not None:
					self.content_screen.resolveCommand(screen_command, args)
				else:
					list_items.insert(0, PExit())
					if screen_command is not None:
						self.content_screen.resolveCommand(screen_command, args)

					if not self.content_screen.refreshing:
						self.content_screen.save()
					else:
						self.content_screen.refreshing = False

					if self.is_search(item):
						parent_content = self.content_screen.getParent()
						if parent_content:
							parent_content['refresh'] = True

					content = {'parent_it':item,
							'lst_items':list_items, 
							'refresh':False,
							'index':kwargs.get('position', 0)}
					self.content_screen.load(content)
					self.content_screen.stopLoading()
					self.content_screen.showList()
					self.content_screen.workingFinished()

			list_items, screen_command, args = result
			
			try:
				#client.add_operation("SHOW_MSG", {'msg': 'some text'},
				#								   'msgType': 'info|error|warning',		#optional
				#								   'msgTimeout': 10,					#optional
				#								   'canClose': True						#optional
				#								  })

#				client.add_operation("TRAKT_PAIR_NEW", { 'client_id' : client_id, 'client_secret' : client_secret } )

				if screen_command is not None:
					cmd = ("%s"%screen_command).lower()
					ams = args
					if cmd == "show_msg":
						#dialogStart = datetime.datetime.now()
						self.content_screen.stopLoading()
						msgType = 'info'
						if 'msgType' in args:
							msgType = ("%s"%args['msgType']).lower()
						msgTimeout = 15
						if 'msgTimeout' in args:
							msgTimeout = int(args['msgTimeout'])
						canClose = True
						if 'canClose' in args:
							canClose = args['canClose']
						if msgType == 'error':
							return showErrorMessage(self.session, args['msg'], msgTimeout, continue_cb_normal, enableInput=canClose)
						if msgType == 'warning':
							return showWarningMessage(self.session, args['msg'], msgTimeout, continue_cb_normal, enableInput=canClose)
						return showInfoMessage(self.session, args['msg'], msgTimeout, continue_cb_normal, enableInput=canClose)
			except:
				log.logError("Execute HACK command failed.\n%s"%traceback.format_exc())
				screen_command = None
				args = {}

			
			if not list_items and screen_command is not None:
				self.content_screen.resolveCommand(screen_command, args)
			else:
				list_items.insert(0, PExit())
				if screen_command is not None:
					self.content_screen.resolveCommand(screen_command, args)

				if not self.content_screen.refreshing:
					self.content_screen.save()
				else:
					self.content_screen.refreshing = False

				if self.is_search(item):
					parent_content = self.content_screen.getParent()
					if parent_content:
						parent_content['refresh'] = True

				content = {'parent_it':item,
						'lst_items':list_items, 
						'refresh':False,
						'index':kwargs.get('position', 0)}
				self.content_screen.load(content)
				self.content_screen.stopLoading()
				self.content_screen.showList()
				self.content_screen.workingFinished()

		@AddonExceptionHandler(self.session)
		def open_item_error_cb(failure):
			log.logError("Folder get_content error cb.\n%s"%failure)
			self.content_screen.stopLoading()
			self.content_screen.showList()
			self.content_screen.workingFinished()
			failure.raiseException()

		self.content_screen.workingStarted()
		self.content_screen.startLoading()
		self.content_screen.hideList()
		self.content_provider.get_content(self.session, item.params, open_item_success_cb, open_item_error_cb)


	def isValidForTrakt(self, item):
		if hasattr(item, 'traktItem') and item.traktItem is not None:
			if 'ids' in item.traktItem and 'type' in item.traktItem:
				return True
		return False

	# action:
	#	- add
	#	- remove
	#	- watched
	#	- unwatched
	def cmdTrakt(self, item, action):
		def finishCb(result):
			if paused:
				self.content_provider.pause()
		def open_item_success_cb(result):
			log.logDebug("Trakt (%s) call success. %s"%(action, result))
			list_items, command, args = result
			if command is not None and command.lower()=='result_msg':
				#{'msg':msg, 'isError':isError}
				if args['isError']:
					showErrorMessage(self.session, args['msg'], 10, finishCb)
				else:
					showInfoMessage(self.session, args['msg'], 10, finishCb)
			else:
				finishCb(None)

		def open_item_error_cb(failure):
			log.logDebug("Trakt (%s) call failed. %s"%(action,failure))
			showErrorMessage(self.session, "Operation failed.", 5, finishCb)

		paused = self.content_provider.isPaused()
		try:
			if action == 'open_action_choicebox':
				trakttv.open_trakt_action_choicebox(self.session, item, self.cmdTrakt)
			elif action == 'pair':
				trakttv.handle_trakt_pairing(self.session, finishCb )
			else:
				if paused:
					self.content_provider.resume()
				
				if hasattr(item, 'traktItem'): # do it only on item which have trakt data
					# handle trakt action localy and after that forward it to addon
					result, msg = trakttv.handle_trakt_action( action, item.traktItem )
					
					ppp = { 'cp': 'czsklib', 'trakt':action, 'item': item.traktItem, 'result': result, 'msg': msg }
					# content provider must be in running state (not paused)
					self.content_provider.get_content(self.session, params=ppp, successCB=open_item_success_cb, errorCB=open_item_error_cb)
				else:
					log.logDebug("Trakt action not supported for this item %s"%item.name);
		except:
			log.logError("Trakt call failed.\n%s"%traceback.format_exc())
			if paused:
				self.content_provider.pause()
				
	def _init_menu(self, item, *args, **kwargs):
		# TRAKT menu (show only if item got data to handle trakt)
		if 'trakt' in self.content_provider.capabilities and self.isValidForTrakt(item):
			if trakttv.valid():
				item.add_context_menu_item(_("Trakt.tv action"), action=self.cmdTrakt, params={'item':item, 'action':'open_action_choicebox'})
			else:
				item.add_context_menu_item(_('Pair device with Trakt.tv'), action=self.cmdTrakt, params={'item':item, 'action':'pair'})

		item.add_context_menu_item(_("Open"), action=self.open_item, params={'item':item})
		if not self.is_search(item) and 'favorites' in self.content_provider.capabilities:
			item.add_context_menu_item(_("Add Shortcut"), action=self.ask_add_shortcut, params={'item':item})
		else:
			item.remove_context_menu_item(_("Add Shortcut"), action=self.ask_add_shortcut, params={'item':item})

	def ask_add_shortcut(self, item):
		self.item = item
		self.session.openWithCallback(self.add_shortcut_cb, MessageBox,
									  text=_("Do you want to add") + " " + py2_encode_utf8( item.name ) + " " + _("shortcut?"),
									  type=MessageBox.TYPE_YESNO)

	def add_shortcut_cb(self, cb):
		if cb:
			self.content_provider.create_shortcut(self.item)
