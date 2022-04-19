'''
Created on 3.10.2012

@author: marko
'''
import os
import socket
import sys
import operator
import traceback
try:
	from urllib2 import URLError
except:
	from urllib.error import URLError


from shutil import copyfile
from twisted.python import failure
from twisted.internet import defer
from xml.etree.cElementTree import ElementTree


from Screens.LocationBox import LocationBox
from Screens.VirtualKeyBoard import VirtualKeyBoard
from Components.Console import Console
from Components.config import config, ConfigSelection
from Plugins.Extensions.archivCZSK import _, log, settings, version as aczsk, removeDiac
from Plugins.Extensions.archivCZSK.compat import eConnectCallback, MessageBox
from Plugins.Extensions.archivCZSK.engine.downloader import getFilenameAndLength
from Plugins.Extensions.archivCZSK.gui.download import DownloadManagerMessages
from Plugins.Extensions.archivCZSK.settings import VIDEO_EXTENSIONS, SUBTITLES_EXTENSIONS
from Plugins.Extensions.archivCZSK.engine.exceptions.addon import AddonError
from Plugins.Extensions.archivCZSK.engine.player.player import Player 
from Plugins.Extensions.archivCZSK.resources.repositories import repo_modules
from Plugins.Extensions.archivCZSK.engine.tools.util import toString, is_hls_url, url_get_data_async, get_streams_from_manifest, download_web_file
from .downloader import DownloadManager
from .items import PVideo, PFolder, PPlaylist, PDownload, PCategory, PVideoAddon, \
	PCategoryVideoAddon, PUserCategory, Stream, RtmpStream, PVideoResolved
from .serialize import CategoriesIO, FavoritesIO
from .tools import task, util

from ..py3compat import *
from enigma import eTimer
PNG_PATH = settings.IMAGE_PATH

CREATE_DEFAULT_HTTPS_CONTEXT = None
try:
	import ssl
	CREATE_DEFAULT_HTTPS_CONTEXT = ssl._create_default_https_context
except:
	pass


class SysPath(list):
	"""to append sys path only to addon which belongs to"""
	def __init__(self, addons):
		self.addons = addons
	def append(self, val):
		log.debug('[AddonSysPath] append %s'%val)
		for addon in self.addons:
			if val.find(addon.id) != -1:
				addon.loader.add_path(val)

class CustomSysImporter(util.CustomImporter):
	def __init__(self, custom_sys):
		util.CustomImporter.__init__(self, 'custom_sys',  log=log.debug)
		self.add_module('sys', custom_sys)

class AddonOutput:
	def __init__(self):
		pass

	def write(self, data):
		log.info(data)

	def flush(self):
		pass

	def isatty(self):
		return True


class AddonSys():
	def __init__(self):
		self.addons = []
		self.path = SysPath(self.addons)
		self.output = AddonOutput()

	def __setitem__(self, key, val):
		if key == 'path':
			log.error('you cannot replace AddonSysPath!')
		elif key == 'stdout':
			pass
		else:
			dict.__setitem__(self, key, val)

	def __getattr__(self, attr):
		if attr=='path':
			return self.path
		elif attr=='stdout':
			return self.output
		return getattr(sys, attr)

	def add_addon(self, addon):
		self.addons.append(addon)

	def remove_addon(self, addon):
		self.addons.remove(addon)

	def clear_addons(self):
		del self.addons[:]


class ContentProvider(object):
	""" Provides item content which can be shown in GUI
	   All item content which can be created is in items module
	"""

	def __init__(self):
		self.capabilities = []
		self.on_start = []
		self.on_stop = []
		self.on_pause = []
		self.on_resume = []
		self.__started = False
		self.__paused = False

	def __repr__(self):
		return "%s"% self.__class__.__name__

	def get_content(self, params={}):
		"""get content with help of params
		  @return: should return list of items created in items module"""
		pass

	def isPaused(self):
		return self.__paused

	def start(self):
		log.logDebug("ContentProvider start")
		if self.__started:
			log.logDebug("[%s] cannot start, provider is already started"%self)
			return
		self.__started = True
		self.__paused = False
		for f in self.on_start:
			f()
		log.debug("[%s] started", self)

	def stop(self):
		log.logDebug("ContentProvider stop")
		if not self.__started:
			log.logDebug("[%s] cannot stop, provider is already stopped"%self)
			return
		self.__started = False
		self.__paused = False
		for f in self.on_stop:
			f()
		log.debug("[%s] stopped", self)

	def resume(self):
		log.logDebug("ContentProvider resume")
		if not self.__started:
			log.logDebug("[%s] cannot resume, provider not started yet"%self)
			return
		if not self.__paused:
			log.logDebug("[%s] cannot resume, provider is already running"%self)
			return
		self.__paused = False
		for f in self.on_resume:
			f()
		log.debug("[%s] resumed", self)

	def pause(self):
		log.logDebug("ContentProvider pause")
		if not self.__started:
			log.logDebug("[%s] cannot pause, provider not started yet"%self)
			return
		if self.__paused:
			log.logDebug("[%s] cannot pause, provider is already paused"%self)
			return
		self.__paused = True
		for f in self.on_pause:
			f()
		log.debug("[%s] paused", self)


class PlayMixin(object):
	def __init__(self, allowed_download=True):
		self.player = None
		self.capabilities.append('play')
		if allowed_download:
			self.capabilities.append('play_and_download')

	def play(self, session, item, mode, player_callback=None):
		self.player = Player(session, player_callback, self)
		if mode in self.capabilities:
			if mode == 'play':
				self.handle_substitles_and_play(item)
				#try:
				#	 self.player.play_item(item)
				#except:
				#	 traceback.print_exc()
			elif mode == 'play_and_download':
				try:
					self.play_and_download(session, item, "auto", player_callback)
				except:
					traceback.print_exc()
		else:
			log.error('Invalid playing mode - %s', str(mode))

	def handle_substitles_and_play(self, item):
		def check_download(self, data, retval, extra_args):
			self.__console = None
			log.logDebug("Handle subs check download finish... retval=%s, fname=%s"%(retval, fname))
			if retval == 0 and os.path.exists(fname):
				item.subs = fname
			self.player.play_item(item)

		try:
			subs = ''
			if not isinstance(item, PPlaylist) and hasattr(item, 'subs'):
				subs = "%s"%item.subs
			if subs.startswith('http'):
				spl = subs.split('/')
				fname = os.path.join(config.plugins.archivCZSK.tmpPath.getValue(), spl[len(spl)-1])
				try:
							
					download_web_file(subs, fname)
					item.subs = fname
					self.player.play_item(item)
				except URLError: #SSL cert problem
					if subs.startswith('https:\\'): # only for https
						log.logDebug("Handle substitle file failed (try download by CURL).\n%s"%traceback.format_exc())
						# download file by CURL
						self.__console = Console()
						self.__console.ePopen('curl -kfo %s %s' % (fname, subs), check_download)
					else:
						log.logError("Handle substitle file failed.\n%s"%traceback.format_exc())
						self.player.play_item(item)
				except:
					log.logError("Handle substitle file failed.\n%s"%traceback.format_exc())
					self.player.play_item(item)
			else:
				self.player.play_item(item)
		except:
			log.logError("Handle substitle file failed.\n%s"%traceback.format_exc())
			self.player.play_item(item)



	def play_and_download(self, session, item, mode, player_callback=None, prefill_buffer=20*1024*1024):

		def stop_etimer():
			if len(etimer):
				etimer[0].stop()
				del etimer[1]
				del etimer[0]

		def play_video_callback(callback=None):
			if callback != "error":
				stop_etimer()
				download_obj[0].onFinishCB.remove(finish_download_callback)
				download_obj[0].onFinishCB.append(DownloadManagerMessages.finishDownloadCB)
				video_item = PVideo()
				video_item.name = item.name
				video_item.url = download_obj[0].local
				# TODO subs should point to local path download to path where is movie
				video_item.subs = item.subs
				self.player.play_item(video_item)

		def check_prefill_state():
			status = download_obj[0].status
			status.update(1)
			size_kb = util.BtoKB(status.currentLength)
			prefill_buffer_kb = util.BtoKB(prefill_buffer)
			percent = size_kb / float(prefill_buffer_kb) * 100
			speed_kbs = util.BtoKB(status.speed)
			if size_kb < prefill_buffer_kb:
				messagebox[0]["text"].setText("%s\n\n%s: %dKB/%dKB (%d%%) %dKB/s\n\n%s"%(
					_("Please wait until enough data is downloaded for fluent playback"),
					_("Bufferring"), size_kb, prefill_buffer_kb, percent, speed_kbs,
					_("You can press any key to stop pre-buffering and start immediately")))
				etimer[0].start(1000, True)
			else:
				messagebox[0].close()

		def start_download_callback(download):
			download_obj.append(download)
			messagebox.append(session.openWithCallback(
					play_video_callback, MessageBox, "",
					MessageBox.TYPE_INFO, close_on_any_key=True))
			etimer.append(eTimer())
			etimer.append(eConnectCallback(etimer[0].timeout, check_prefill_state))
			etimer[0].start(1000, True)

		def finish_download_callback(download):
			stop_etimer()
			if not download.downloaded:
				messagebox[0].close("error")
				DownloadManagerMessages.finishDownloadCB(download)
				player_callback and player_callback()
			else:
				messagebox[0].close()

		def do_play_and_download():
			self.download(session, item,
					start_callback=start_download_callback,
					finish_callback=finish_download_callback,
					player_callback = player_callback,
					mode = mode)

		def ask_if_play_and_download_callback(answer):
			if answer:
				do_play_and_download()
			else:
				player_callback and player_callback()

		download_obj = []
		etimer		 = []
		messagebox	 = []

		message = "%s%s\n\n%s"%(
				_("Play and download mode is not supported by all video formats."),
				_("Player can start to behave unexpectedly or no to play video at all."),
				_("Do yo want to continue?"))
		session.openWithCallback(ask_if_play_and_download_callback, MessageBox,
				message, MessageBox.TYPE_YESNO)


class FavoritesMixin(object):
	def __init__(self, shortcuts_path):
		self.shortcuts = FavoritesIO(os.path.join(shortcuts_path, 'shortcuts'))
		self.capabilities.append('favorites')
		self.on_stop.append(self.save_shortcuts)

	def create_shortcut(self, favorite):
		return self.shortcuts.add_favorite(favorite)

	def remove_shortcut(self, favorite):
		return self.shortcuts.remove_favorite(favorite)

	def get_shortcuts(self):
		return self.shortcuts.get_favorites()

	def save_shortcuts(self):
		self.shortcuts.save()


class DownloadsMixin(object):
	def __init__(self, downloads_path, allowed_download):
		self.downloads_path = downloads_path
		if allowed_download:
			self.capabilities.append('download')

	def get_downloads(self):
		video_lst = []
		if not os.path.isdir(self.downloads_path):
			util.make_path(self.downloads_path)

		downloads = os.listdir(self.downloads_path)
		for download in downloads:
			download_path = os.path.join(self.downloads_path, download)

			if os.path.isdir(download_path):
				continue

			if os.path.splitext(download_path)[1] in VIDEO_EXTENSIONS:
				filename = os.path.basename(os.path.splitext(download_path)[0])
				url = download_path
				subs = None
				if filename in [os.path.splitext(x)[0] for x in downloads if os.path.splitext(x)[1] in SUBTITLES_EXTENSIONS]:
					subs = filename + ".srt"

				it = PDownload(download_path)
				it.name = filename
				it.url = url
				it.subs = subs

				downloadManager = DownloadManager.getInstance()
				download = downloadManager.findDownloadByIT(it)

				if download is not None:
					it.finish_time = download.finish_time
					it.start_time = download.start_time
					it.state = download.state
					it.textState = download.textState
				video_lst.append(it)

		return video_lst

	def download(self, session, item, start_callback=None, finish_callback=None,
			player_callback = None, play_download=False, mode=""):
		#closure fun :)
		def do_download():
			try:
				# have to rename to start_cb otherwise python
				# doesnt see start_callback
				start_cb = start_callback
				finish_cb = finish_callback
				if start_cb is None:
					start_cb = DownloadManagerMessages.startDownloadCB
				if finish_cb is None:
					finish_cb = DownloadManagerMessages.finishDownloadCB
				override_cb = DownloadManagerMessages.overrideDownloadCB

				downloadManager = DownloadManager.getInstance()
				d = downloadManager.createDownload(
					name=item.name, url=item.url, 
					stream=item.stream, filename=filename[0],
					live=item.live, destination=destination[0],
					startCB=start_cb, finishCB=finish_cb, quiet=False,
					playDownload=play_download, headers=headers, mode=mode)

				if item.subs:
					remote = item.subs
					local = os.path.splitext(d.local)[0] + '.srt'
					if os.path.isfile(remote):
						copyfile(remote, local)
					elif remote.startswith('http'):
						util.download_to_file(remote, local)
				downloadManager.addDownload(d, override_cb)
			except:
				log.logError("Download '%s' failed.\n%s"%(item.name, traceback.format_exc()))
				session.openWithCallback(ask_if_download_callback, MessageBox, text=_("Download error, look into the log file."), timeout=10, type=MessageBox.TYPE_ERROR)
				pass

		def change_filename_callback(answer):
			if answer:
				filename[0] = answer
			ask_if_download()

		def change_download_path_callback(answer):
			if answer:
				destination[0] = answer
			ask_if_download()

		def ask_if_download_callback(answer):
			if not answer or answer == "no":
				player_callback and player_callback()
			else:
				if answer == "yes":
					do_download()
				if answer == "change":
					downloads_path = (self.downloads_path.endswith("/") and 
							self.downloads_path or self.downloads_path + "/")
					session.openWithCallback(change_download_path_callback,
							LocationBox, _("Select new location"),
							currDir=downloads_path)
				if answer == "filename":
					session.openWithCallback(change_filename_callback,
							VirtualKeyBoard, title = removeDiac(_("Edit filename")),
							text = filename[0])
							#text = toString(filename[0]))

		def ask_if_download():
			filename[0], size_bytes = getFilenameAndLength(item.url, headers, filename[0])
			size_mbytes = size_bytes and util.BtoMB(size_bytes) or "???"
			free_bytes = util.get_free_space(destination[0])
			free_mbytes = free_bytes and util.BtoMB(free_bytes) or "???"

			message = "%s:\n\n%s:\n%s - %sMB\n\n%s:\n%s - %sMB %s\n\n%s:\n%s"%(
					_("Do you want to download"),
					_("Source"), toString(item.name), str(size_mbytes),
					_("Destination"), toString(destination[0]), str(free_mbytes), _("free"),
					_("Filename"), toString(filename[0]))
			choices = [ (_("yes"), "yes"), (_("no"), "no"), 
					(_("Change location"), "change"), (_("Edit filename"), "filename") ]

			session.openWithCallback(ask_if_download_callback,
					MessageBox, message, MessageBox.TYPE_YESNO, list=choices)

		headers = item.settings['extra-headers']
		destination = [self.downloads_path]
		filename = [item.filename or item.name]
		filename[0] = removeDiac(filename[0])
		ask_if_download()

	def remove_download(self, item):
		if item is not None:
			log.debug('removing item %s from disk' % item.name)
			os.remove(toString(item.path))


class ArchivCZSKContentProvider(ContentProvider):
	def __init__(self, archivczsk, path):
		ContentProvider.__init__(self)
		self._archivczsk = archivczsk
		self._categories_io = CategoriesIO(path)
		self.on_start.append(self.__create_config)
		self.on_pause.append(self.__create_config)
		self.on_stop.append(self.__save_categories)

		all_addons_category = PCategory()
		all_addons_category.name = _("All addons")
		all_addons_category.params = {'category_addons':'all_addons'}
		all_addons_category.image = PNG_PATH + '/category_all.png'
		tv_addons_category = PCategory()
		tv_addons_category.name = _("TV addons")
		tv_addons_category.image = PNG_PATH+'/category_tv.png'
		tv_addons_category.params = {'category_addons':'tv_addons'}
		video_addons_category = PCategory()
		video_addons_category.name = _("Video addons")
		video_addons_category.image = PNG_PATH+'/category_video.png'
		video_addons_category.params = {'category_addons':'video_addons'}
		self.default_categories={
								 'all_addons':{'item':all_addons_category
											   ,'title':_("All addons"),
											   'call':self._get_all_addons
											   },
								 'tv_addons':{
											  'item':tv_addons_category,
											  'title':_("TV addons"),
											  'call':self._get_tv_addons
											  },
								  'video_addons':{
												  'item':video_addons_category,
												  'title':_("Video addons"),
												  'call':self._get_video_addons
												  }
								  }
		self.default_categories_order = ['all_addons','tv_addons','video_addons']

	def __create_config(self):
		choicelist = [('categories', _("Category list"))]
		choicelist.extend([(category_key,self.default_categories[category_key]['title']) for category_key in self.default_categories_order])
		choicelist.extend([(category.id, category.name) for category in self._get_categories(user_only=True)])
		config.plugins.archivCZSK.defaultCategory = ConfigSelection(default='categories', choices=choicelist)

	def __save_categories(self):
		self._categories_io.save()

	def get_content(self, params=None):
		f = open("/tmp/archivCZSK.last", "w")
		f.write('%s - params: %s' % (self, str(params)))
		f.close()
		log.info('%s get_content - params: %s' % (self, str(params)))
		if not params or 'categories' in params:
			return self._get_categories()
		if 'category' in params:
			return self._get_category(params['category'])
		if 'category_addons' in params:
			return self._get_category_addons(params['category_addons'], params)
		if 'categories_user' in params:
			return self._get_categories(user_only=True)

	def add_category(self, category_title):
		pcategory = PCategory()
		pcategory.name = category_title
		self._categories_io.add_category(pcategory)
		# update params
		pcategory.params = {'category_addons':pcategory.id}
		self._categories_io.update_category(pcategory)

	def rename_category(self, pcategory, new_title):
		# sync category
		pcategory = self._get_category(pcategory.id)
		pcategory.name = new_title
		self._categories_io.update_category(pcategory)
		# update params
		pcategory.params = {'category_addons':pcategory.id}
		self._categories_io.update_category(pcategory)

	def remove_category(self, pcategory):
		self._categories_io.remove_category(pcategory)

	def add_to_category(self, pcategory, paddon):
		# sync category
		pcategory = self._get_category(pcategory.id)
		pcategory.add_addon(paddon)
		self._categories_io.update_category(pcategory)

	def remove_from_category(self, pcategory, paddon):
		# sync category
		pcategory = self._get_category(pcategory.id)
		pcategory.remove_addon(paddon)
		self._categories_io.update_category(pcategory)

	def _get_category(self, category_id):
		if category_id in self.default_categories:
			return self.default_categories[category_id]['item']
		pcategory = self._categories_io.get_category(category_id)
		return pcategory

	def _get_categories(self, user_only=False):
		category_list = self._categories_io.get_categories()
		if not user_only:
			category_list.extend( [self.default_categories[category_key]['item'] for category_key in self.default_categories_order])
		return category_list

	def _filter_addons(self, addons, params):
		def filter_enabled_addons(paddon):
			return paddon.addon.get_setting('enabled')

		def filter_supported_addons(paddon):
			return paddon.addon.supported

		if params.get('filter_enabled', True):
			addons = list(filter(filter_enabled_addons, addons))

		if params.get('filter_supported', config.plugins.archivCZSK.showNotSupportedAddons.value):
			addons = list(filter(filter_supported_addons, addons))
		return addons

	def _sort_addons(self, addons):
		try:
			addons = sorted(addons, key=lambda x: x.order)
		except:
			pass
		return addons


	def _get_category_addons(self, category_id, params = None):
		if category_id in self.default_categories:
			return self.default_categories[category_id]['call'](params)
		addons = [PCategoryVideoAddon(self._archivczsk.get_addon(addon_id)) for addon_id in self._categories_io.get_category(category_id)]
		addons = self._sort_addons(addons)
		return addons

	def _get_all_addons(self, params):
		addons = [PVideoAddon(addon) for addon in self._archivczsk.get_video_addons()]
		addons = self._filter_addons(addons, params)
		addons = self._sort_addons(addons)
		return addons

	def _get_video_addons(self, params):
		addons = [paddon for paddon in self._get_all_addons(params) if not paddon.addon.setting_exist('tv_addon') or not paddon.addon.get_setting('tv_addon')]
		addons = self._sort_addons(addons)
		return addons

	def _get_tv_addons(self, params):
		addons = [paddon for paddon in self._get_all_addons(params) if paddon.addon.setting_exist('tv_addon') and paddon.addon.get_setting('tv_addon')]
		addons = self._sort_addons(addons)
		return addons


class VideoAddonContentProvider(ContentProvider, PlayMixin, DownloadsMixin, FavoritesMixin):

	__resolving_provider = None
	__gui_item_list = [[], None, {}] #[0] for items, [1] for command to GUI [2] arguments for command
	__addon_sys = AddonSys()

	@classmethod
	def get_shared_itemlist(cls):
		return cls.__gui_item_list

	@classmethod
	def get_resolving_provider(cls):
		return cls.__resolving_provider

	@classmethod
	def get_resolving_addon(cls):
		return cls.__resolving_provider.video_addon

	def __init__(self, video_addon, downloads_path, shortcuts_path):
		allowed_download = True 
		if video_addon.setting_exist('!download'):
			allowed_download = not video_addon.get_setting('!download')
		self.video_addon = video_addon
		ContentProvider.__init__(self)
		PlayMixin.__init__(self, allowed_download)
		DownloadsMixin.__init__(self, downloads_path, allowed_download)
		FavoritesMixin.__init__(self, shortcuts_path)
		self._dependencies = []
		
		self._sys_importer = CustomSysImporter(self.__addon_sys)
		self.on_start.append(self.__clean_sys_modules)
		self.on_start.append(self.__set_resolving_provider)
		self.on_stop.append(self.__unset_resolving_provider)
		self.on_stop.append(self.__restore_sys_modules)
		self.on_pause.append(self.__pause_resolving_provider)
		self.on_resume.append(self.__resume_resolving_provider)

	def __repr__(self):
		return "%s(%s)"%(self.__class__.__name__, self.video_addon)

	def __clean_sys_modules(self):
		self.saved_modules = {}
		for mod_name in repo_modules:
			if mod_name in sys.modules:
				mod = sys.modules[mod_name]
				del sys.modules[mod_name]
				self.saved_modules[mod_name] = mod
		del sys.modules['sys']

	def __restore_sys_modules(self):
		sys.modules['sys'] = sys
		sys.modules.update(self.saved_modules)
		del self.saved_modules

	def __set_resolving_provider(self):
		VideoAddonContentProvider.__resolving_provider = self
		VideoAddonContentProvider.__addon_sys.add_addon(self.video_addon)
		self.video_addon.include()
		self.resolve_dependencies()
		self.include_dependencies()
		sys.meta_path.insert(0, self._sys_importer)

	def __unset_resolving_provider(self):
		VideoAddonContentProvider.__resolving_provider = None
		VideoAddonContentProvider.__addon_sys.clear_addons()
		self.video_addon.deinclude()
		self.release_dependencies()
		sys.meta_path.remove(self._sys_importer)

	def __pause_resolving_provider(self):
		self.video_addon.deinclude()
		for addon in self._dependencies:
			addon.deinclude()
		sys.meta_path.remove(self._sys_importer)

	def __resume_resolving_provider(self):
		self.video_addon.include()
		for addon in self._dependencies:
			addon.include()
		sys.meta_path.insert(0, self._sys_importer)

	def __clear_list(self):
		del VideoAddonContentProvider.__gui_item_list[0][:]
		VideoAddonContentProvider.__gui_item_list[1] = None
		VideoAddonContentProvider.__gui_item_list[2].clear()

	def resolve_dependencies(self):
		from Plugins.Extensions.archivCZSK.archivczsk import ArchivCZSK
		log.info("%s trying to resolve dependencies for %s" , self, self.video_addon)
		for dependency in self.video_addon.requires:
			addon_id, version, optional = dependency['addon'], dependency['version'], dependency['optional']

			# checking if archivCZSK version is compatible with this plugin
			if addon_id == 'enigma2.archivczsk':
				if	not util.check_version(aczsk.version, version):
					log.debug("%s archivCZSK version %s>=%s" , self, aczsk.version, version)
				else:
					log.debug("%s archivCZSK version %s<=%s" , self, aczsk.version, version)
					raise AddonError(_("You need to update archivCZSK at least to") + " " + version + " " + _("version"))

			log.info("%s requires %s addon, version %s" , self, addon_id, version)
			if ArchivCZSK.has_addon(addon_id):
				tools_addon = ArchivCZSK.get_addon(addon_id)
				log.debug("%s required %s founded" , self, tools_addon)
				if	not util.check_version(tools_addon.version, version):
					log.debug("%s version %s>=%s" , self, tools_addon.version, version)
					self._dependencies.append(tools_addon)
				else:
					log.debug("%s version %s<=%s" , self, tools_addon.version, version)
					if not optional:
						log.error("%s cannot execute", self)
						raise AddonError("Cannot execute addon %s, dependency %s version %s needs to be at least version %s"
										% (self.video_addon, tools_addon.id, tools_addon.version, version))
					else:
						log.debug("%s skipping")
						continue
			else:
				log.error("%s required %s addon not founded" ,self, addon_id)
				if not optional:
					log.error("%s cannot execute %s addon" ,self, self.video_addon)
					raise Exception("Cannot execute %s, missing dependency %s" % (self.video_addon, addon_id))
				else:
					log.debug("skipping")

	def include_dependencies(self):
		for addon in self._dependencies:
			addon.include()
			self.__addon_sys.add_addon(addon)

	def release_dependencies(self):
		log.debug("%s trying to release dependencies for %s" ,self , self.video_addon)
		for addon in self._dependencies:
			addon.deinclude()
		del self._dependencies[:]

	def get_content(self, session, params, successCB, errorCB):
		f = open("/tmp/archivCZSK.last", "w")
		f.write('%s - params: %s' % (self, str(params)))
		f.close()
		log.info('%s get_content - params: %s' % (self, str(params)))
		# add/remove trakt compatibility on every content request
		if self.video_addon.setting_exist('trakt_enabled'):
			if self.video_addon.get_setting('trakt_enabled'):
				if 'trakt' not in self.capabilities:
					self.capabilities.append('trakt')
			else:
				if 'trakt' in self.capabilities:
					self.capabilities.remove('trakt')

		self.__clear_list()
		self.content_deferred = defer.Deferred()
		self.content_deferred.addCallback(self._resolve_video_items)
		self.content_deferred.addCallbacks(successCB, errorCB)
		# setting timeout for resolving content
		loading_timeout = int(self.video_addon.get_setting('loading_timeout'))
		if loading_timeout > 0:
			socket.setdefaulttimeout(loading_timeout)

		try:
			ssl._create_default_https_context = ssl._create_unverified_context
		except:
			pass
		thread_task = task.Task(self._get_content_cb, self.run_script, session, params)
		thread_task.run()
		return self.content_deferred

	def run_script(self, session, params):
		script_path = os.path.join(self.video_addon.path, self.video_addon.script)
		
		global_vars = {
			'session':session,
			'params':params,
			'__file__':script_path,
			'sys':self.__addon_sys,
			'os':os
		}

		with open( script_path, "rb") as f:
			exec( compile(f.read(), script_path, 'exec'), global_vars)

	def _get_content_cb(self, success, result):
		log.info('%s get_content_cb - success: %s, items: %d, guicmd: %r - %r' % (
			self, success, len(self.__gui_item_list[0]), self.__gui_item_list[1], self.__gui_item_list[2]))

		# resetting timeout for resolving content
		socket.setdefaulttimeout(socket.getdefaulttimeout())

		try:
			ssl._create_default_https_context = CREATE_DEFAULT_HTTPS_CONTEXT
		except:
			pass
		if success:
			lst_itemscp = [[], None, {}]
			lst_itemscp[0] = self.__gui_item_list[0][:]
			lst_itemscp[1] = self.__gui_item_list[1]
			lst_itemscp[2] = self.__gui_item_list[2].copy()
			self.content_deferred.callback(lst_itemscp)
		else:
			self.content_deferred.errback(result)

	def _resolve_video_items(self, result):

		def all_done(result_list):
			for __, (data, item) in result_list:
				tmp_list = []
				for stream_dict in get_streams_from_manifest(item.url, data):
					video_item = PVideoResolved()
					video_item.subs = item.subs
					video_item.settings = item.settings.copy()
					video_item.url = stream_dict['url']
					video_item.quality = "%s b/s"%stream_dict['bandwidth']
					video_item.bandwidth = int(stream_dict['bandwidth'])
					if 'resolution' in stream_dict:
						video_item.quality = stream_dict['resolution'].split('x')[1] + "p"
					# TODO remove workaround of embedding
					# quality in title in addons
					video_item.name = name = item.name
					quality = video_item.quality
					if quality and quality not in name:
						if "[???]" in name:
							video_item.name = name.replace("[???]","[%s]"%(quality))
						else:
							video_item.name = "[%s] %s"%(quality, name)
					tmp_list.append(video_item)
				tmp_list.sort(key=operator.attrgetter('bandwidth'), reverse=True)
				if tmp_list:
					log.info("%s __resolve_video_items: found %d streams"%(self, len(tmp_list)))
					item_list.remove(item)
					item_list.extend(tmp_list)
			return result

		def get_result(res, item):
			if isinstance(res, failure.Failure):
				log.error("%s _resolve_video_items: %s - %s"%(
					self, item.url, res.value))
			else:
				log.debug("%s _resolve_video_items: %s - %dB"%(
					self, item.url, len(res)))
			return res, item

		item_list,__,__ = result
		video_list = [i for i in item_list if isinstance(i, PVideoResolved) and is_hls_url(i.url)]
		log.debug("%s _resolve_video_items: found %d resolvable video items"%(self, len(video_list)))
		d_list = []
		for item in video_list:
			d = url_get_data_async(toString(item.url),
					headers=item.settings["extra-headers"], timeout=5)
			d.addBoth(get_result, item)
			d_list.append(d)
		return defer.DeferredList(d_list, consumeErrors=True).addCallback(all_done)

	def close(self):
		self.video_addon = None
