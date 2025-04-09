# -*- coding: UTF-8 -*-
#### module for addon creators #####

import traceback
import twisted.internet.defer as defer

from Components.config import config
from Components.Input import Input
from Screens.MessageBox import MessageBox
from Screens.VirtualKeyBoard import VirtualKeyBoard
from Screens.ChoiceBox import ChoiceBox
from Screens.InputBox import InputBox

from .tools.logger import log
from .tools.lang import _
from .contentprovider import VideoAddonContentProvider
from .exceptions.addon import AddonInfoError, AddonWarningError, AddonError, AddonThreadException, AddonSilentExit
from .items import PFolder, PVideoResolved, PVideoNotResolved, PPlaylist, PSearch, PSearchItem
from .parental import parental_pin
from .tools.task import callFromThread, Task
from .tools.util import toString, toUnicode, removeDiac
from .license import ArchivCZSKLicense
from .usage import UsageStats
from ..gui.captcha import Captcha
from ..gui.common import LoadingScreen
from ..gui.config import ArchivCZSKSimpleConfigScreen
from ..colors import DeleteColors, ConvertColors
from ..py3compat import *
GItem_lst = VideoAddonContentProvider.get_shared_itemlist()

def abortTask(func):
	def wrapped_func(*args, **kwargs):
		task = Task.getInstance()
		if task and task._aborted:
			raise AddonThreadException()
		return func(*args, **kwargs)
	return wrapped_func


def getVersion():
	return "1.0"

def decode_string(string):
	if isinstance(string, unicode):
		return _(string)
	elif isinstance(string, str):
		string = unicode(string, 'utf-8', 'ignore')
		return _(string)

def getVideoFormats(url):
	'''
	legacy function used to resolve youtube videos - not working anymore - use direct youtube addon call
	'''
	return []

@callFromThread
def openSimpleConfig(session, config_entries, title=None, s=True):
	def simpleConfigCB(result):
		if s and result and not ArchivCZSKLicense.get_instance().check_level(ArchivCZSKLicense.LEVEL_SUPPORTER):
			def mbox_cbk(result):
				if result:
					def close_cbk(result2):
						loading and loading.start()
						d.callback(AddonSilentExit(''))

					from ..gui.icon import ArchivCZSKDonateScreen
					UsageStats.get_instance().update_counter('donate_dialog')
					session.openWithCallback(close_cbk, ArchivCZSKDonateScreen)
				else:
					loading and loading.start()
					d.callback(AddonSilentExit(''))

			UsageStats.get_instance().update_counter('supporter_msg')
			return session.openWithCallback(mbox_cbk, MessageBox, text=toString(_('This is bonus functionality available only for product supporters. Do you want to know, how to get "Supporter" status?')), type=MessageBox.TYPE_YESNO)

		loading and loading.start()
		d.callback(result)

	loading = LoadingScreen.get_running_instance()
	loading and loading.stop()

	d = defer.Deferred()
	session.openWithCallback(simpleConfigCB, ArchivCZSKSimpleConfigScreen, config_entries=config_entries, title=title)
	return d

@callFromThread
def getTextInput(session, title, text=""):
	def getTextInputCB(word):
		loading and loading.start()
		if word is None:
			d.callback('')
		else:
			d.callback(word)

	loading = LoadingScreen.get_running_instance()
	loading and loading.stop()

	d = defer.Deferred()
	#session.openWithCallback(getTextInputCB, VirtualKeyBoard, title=toString(title), text=text)
	session.openWithCallback(getTextInputCB, VirtualKeyBoard, title=DeleteColors(title), text=removeDiac(text))
	return d


@callFromThread
def getNumericInput(session, title, text="", showChars=True):
	def getNumericInputCB(word):
		loading and loading.start()
		if word is None:
			d.callback(None)
		else:
			d.callback(word)

	loading = LoadingScreen.get_running_instance()
	loading and loading.stop()

	d = defer.Deferred()
	session.openWithCallback(getNumericInputCB, InputBox, title=title, text=text, type=Input.NUMBER if showChars else Input.PIN)
	return d


def getSearch(session):
	return getTextInput(session, _("Please set your search expression"))

@callFromThread
def getCaptcha(session, image):
	def getCaptchaCB(word):
		loading and loading.start()
		if word is None:
			d.callback('')
		else:
			d.callback(word)

	loading = LoadingScreen.get_running_instance()
	loading and loading.stop()
	d = defer.Deferred()
	Captcha(session, image, getCaptchaCB)
	return d

@callFromThread
def openSettings(session, addon):
	def getSettingsCB(word):
		loading and loading.start()
		d.callback(word)

	loading = LoadingScreen.get_running_instance()
	loading and loading.stop()
	d = defer.Deferred()
	addon.open_settings(session, addon, getSettingsCB)
	return d

def showInfo(info, timeout=5):
	raise AddonInfoError(info)

def showError(error, timeout=5):
	raise AddonError(error)

def showWarning(warning, timeout=5):
	raise AddonWarningError(warning)

def silentExit(msg=''):
	raise AddonSilentExit(msg)

@callFromThread
def getYesNoInput(session, text):
	def getYesNoInputCB(callback=None):
		loading and loading.start()
		if callback:
			d.callback(True)
		else:
			d.callback(False)

	loading = LoadingScreen.get_running_instance()
	loading and loading.stop()
	d = defer.Deferred()
	session.openWithCallback(getYesNoInputCB, MessageBox, text=toString(text), type=MessageBox.TYPE_YESNO)
	return d

@callFromThread
def getListInput(session, choices_list, title="", selection=0):
	def getListInputCB(selected=None):
		loading and loading.start()
		if selected is not None:
			d.callback(newlist.index(selected))
		else:
			d.callback(-1)

	loading = LoadingScreen.get_running_instance()
	loading and loading.stop()

	d = defer.Deferred()

	if config.plugins.archivCZSK.colored_items.value:
		newlist = [(ConvertColors(toString(name)),) for name in choices_list]
	else:
		newlist = [(DeleteColors(toString(name)),) for name in choices_list]

	session.openWithCallback(getListInputCB, ChoiceBox, toString(title), newlist, selection=selection, skin_name="ArchivCZSKChoiceBox")
	return d

@callFromThread
def show_message(session, message, msg_type='info', timeout=5):
	def show_message_cb(callback=None):
		loading and loading.start()
		if callback:
			d.callback(True)
		else:
			d.callback(False)

	msg_type_map = {
		'info': MessageBox.TYPE_INFO,
		'error': MessageBox.TYPE_ERROR,
		'warning': MessageBox.TYPE_WARNING,
	}

	loading = LoadingScreen.get_running_instance()
	loading and loading.stop()
	d = defer.Deferred()
	session.openWithCallback(show_message_cb, MessageBox, text=toString(message), type=msg_type_map.get(msg_type, MessageBox.TYPE_YESNO), timeout=timeout, close_on_any_key=True, enable_input=True)
	return d


def set_command(name, **kwargs):
	"""
	Set command for active content screen
	first argument is always name of the command, next arguments are arguments for command

	possible commands for content screen are: refreshafter - refreshes content screen when again loaded
											  refreshnow- refreshes content screen immediately
	"""
	GItem_lst[1] = name
	for arg in kwargs:
		GItem_lst[2][arg] = kwargs[arg]

def refresh_screen(restoreLastPosition=True, parent=False):
	"""
	Refreshesh active screen
	restoreLastPosition = if True, then restores position of cursor
	"""

	if parent:
		set_command('refreshparent')
	elif restoreLastPosition:
		set_command('refreshnow')
	else:
		set_command('refreshnow_resetpos')

@callFromThread
def open_donate_dialog(session):
	from ..gui.icon import ArchivCZSKDonateScreen
	UsageStats.get_instance().update_counter('donate_dialog')
	def close_cbk(result):
		loading and loading.start()
		d.callback(None)

	loading = LoadingScreen.get_running_instance()
	loading and loading.stop()
	d = defer.Deferred()
	session.openWithCallback(close_cbk, ArchivCZSKDonateScreen)
	return d

def ensure_supporter(session, msg=None):
	if ArchivCZSKLicense.get_instance().check_level(ArchivCZSKLicense.LEVEL_SUPPORTER):
		return

	if msg:
		msg = msg + '\n'
	else:
		msg = ''

	UsageStats.get_instance().update_counter('supporter_msg')
	if getYesNoInput(session, msg + _('This is bonus functionality available only for product supporters. Do you want to know, how to get "Supporter" status?')) == True:
		open_donate_dialog(session)

	raise AddonSilentExit('')

def is_supporter():
	return ArchivCZSKLicense.get_instance().check_level(ArchivCZSKLicense.LEVEL_SUPPORTER)

def __process_info_labels(item, info_labels):
	# this is really hacky implementation ...
	def set_info_labels(info_labels, cbk_continue=None):
		infolabel_uni = {}

		for key, value in info_labels.items():
			if value != None:
				if isinstance(value, (dict, list, set)):
					if value:
						infolabel_uni[key.lower()] = value
				elif isinstance(value, bool):
					infolabel_uni[key.lower()] = value
				else:
					infolabel_uni[key.lower()] = toUnicode(value)

		if not 'title' in infolabel_uni:
			infolabel_uni["title"] = DeleteColors(item.name)

		item.info = infolabel_uni
		if cbk_continue:
			cbk_continue()

	def load_info(cbk_load_info_labels, cbk_continue=None):
		if cbk_continue:
			# call cbk_load_info_labels() in worker thread
			def handle_result(success, result):
				if not success:
					log.error(result.getTraceback())
					result = {}
				set_info_labels(result, cbk_continue)

			Task(handle_result, cbk_load_info_labels).run()
		else:
			try:
				# cbk_continue - call cbk_load_info_labels() directly
				set_info_labels(cbk_load_info_labels())
			except:
				log.error(traceback.format_exc())

	if callable(info_labels):
		# info_labels as callable, that will return real info_labels dictionary
		item.load_info_cbk = lambda cbk_continue: load_info(info_labels, cbk_continue)
	else:
		# info_labels as dictionary - just call function to set it ...
		set_info_labels(info_labels)


def create_directory_it(name, params={}, image=None, infoLabels={}, menuItems={}, search_folder=False, search_item=False, video_item=False, dataItem=None, traktItem=None, download=True):
	'''
	Creates new directory item. It can be:
	search_item, search_folder, video_item if any of these are set to True or folder otherwise

	@param name : name of the directory
	@param params: dictationary of parameters for next resolving
	@param image: image to show in directories info
	@param infoLabels: dictationary of informations{'title':title,'plot':plot,'rating':rating,''}"
	@param menuItems: dictationary with menu items
	@param dataItem: data item that will be forwarded to stats() callback
	@param traktItem: trakt item that holds informations for trakt scrobling
	@param download: Enables or disables downloading of this item
	'''

	if search_item:
		it = PSearchItem()
	elif search_folder:
		it = PSearch()
	elif video_item:
		it = PVideoNotResolved()
	else:
		it = PFolder()

	name = toUnicode(name)
	if not config.plugins.archivCZSK.colored_items.value:
		name = DeleteColors(name)

	it.name = name
	it.params = params
	it.image = toUnicode(image)

	__process_info_labels(it, infoLabels)

	for key, value in menuItems.items():
		item_name = decode_string(key)
		thumb = None
		is_media = False
		if isinstance(value, dict):
			params = value
			thumb = None
		elif isinstance(value, list):
			thumb = value[0]
			params = value[1]
			if len(value) == 3:
				is_media = value[2]
		it.add_context_menu_item(item_name, thumb=thumb, params=params, is_media=is_media)

	if hasattr(it, 'dataItem'):
		it.dataItem = dataItem

	if hasattr(it, 'traktItem'):
		it.traktItem=traktItem

	if hasattr(it, 'download'):
		it.download = download

	return it


def create_video_it(name, url, subs=None, image=None, infoLabels={}, menuItems={}, filename=None, live=False, settings=None, dataItem=None, traktItem=None, download=True):
	'''
	Creates new video item:

	@param url: play url
	@param subs: subtitles url
	@param image: image of video item
	@param infoLabels: dictationary of informations{'title':title,'plot':plot,'rating':rating,''}"
	@param menuItems: dictationary with menu items
	@param filename: set this filename when downloading
	@param live: is video live stream (for rtmp)
	@param settings: dictationary of player/download settings{"user-agent",:"","extra-headers":{}}
	@param dataItem: data item that will be forwarded to stats() callback
	@param traktItem: trakt item that holds informations for trakt scrobling
	@param download: Enables or disables downloading of this item
	'''

	it = PVideoResolved()

	name = toUnicode(name)
	if not config.plugins.archivCZSK.colored_items.value:
		name = DeleteColors(name)

	it.name = name
	it.url = toUnicode(url)
	if subs is not None and subs != "":
		it.subs = toUnicode(subs)
	it.image = toUnicode(image)

	__process_info_labels(it, infoLabels)

	for key, value in menuItems.items():
		item_name = decode_string(key)
		thumb = None
		if isinstance(value, dict):
			params = value
			thumb = None
			is_media = False
		elif isinstance(value, list):
			thumb = value[0]
			params = value[1]
			if len(value) == 3:
				is_media = value[2]
		it.add_context_menu_item(item_name, thumb=thumb, params=params, is_media=is_media)

	if filename is not None:
		it.filename = toUnicode(filename)

	it.live = live

	if settings is not None:
		if not isinstance(settings, dict):
			log.error("Cannot load settings %s class, it has to be dict class" , settings.__class__.__name__)
		else:
			if 'user-agent' not in settings:
				settings['user-agent'] = ""
			if 'extra-headers' not in settings:
				settings['extra-headers'] = {}
			if not isinstance(settings['extra-headers'], dict):
				log.error("extra headers is not a dict type!")
				settings['extra-headers'] = {}
			log.debug("Settings: %s", settings)
			it.settings = settings
	it.resolved = True

	it.dataItem = dataItem
	it.traktItem = traktItem
	it.download = download

	return it

@abortTask
def add_item(item):
	'''
	Adds new item to current screen. Item needs to be created using create_video_it() or create_directory_it()
	'''
	if getattr(item, 'info', {}).get('adult', False) == False or parental_pin.get_settings('show_adult'):
		GItem_lst[0].append(item)

def add_dir(*args, **kwargs):
	'''
	Creates new directory item and adds it to current screen. For parameters see create_directory_it()
	'''
	add_item(create_directory_it(*args, **kwargs))

def add_video(*args, **kwargs):
	'''
	Creates new resolved video item and adds it to current screen. For parameters see create_video_it()
	'''
	add_item(create_video_it(*args, **kwargs))

@abortTask
def sort_items(reverse=False, use_diacritics=True, ignore_case=False):
	def key_fn(item):
		if use_diacritics:
			key = item.name
		else:
			key = removeDiac(item.name)

		if ignore_case:
			key = key.lower()
		return key

	GItem_lst[0].sort(key=key_fn, reverse=reverse)


@abortTask
def add_playlist(name, media_list=[], variant=False):
	playlist = PPlaylist()
	playlist.name = toUnicode(name)
	playlist.variant = variant
	for media in media_list:
		playlist.add(media)
	GItem_lst[0].append(playlist)
	return playlist

@abortTask
def clear_items():
	del GItem_lst[0][:]
