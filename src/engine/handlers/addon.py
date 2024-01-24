from Screens.MessageBox import MessageBox
import shutil
import traceback
import os

from .item import ItemHandler
from .content import ContentHandler
from .context import ContextMenuItemHandler
from .folder import FolderItemHandler
from .category import CategoryItemHandler, UserCategoryItemHandler
from .media import VideoResolvedItemHandler, VideoNotResolvedItemHandler, PlaylistItemHandler

from ... import _, log
from ..tools import util
from ...gui.context import ArchivCZSKSelectCategoryScreen
from ..contentprovider import VideoAddonContentProvider
from ..items import PExit, PRoot, PVideoAddon, PCategoryVideoAddon
from ...gui.exception import AddonExceptionHandler
from ...gui.common import showInfoMessage, showWarningMessage, showErrorMessage
from Components.config import config

from ...py3compat import *

class VideoAddonItemHandlerTemplate(ItemHandler):
	def __init__(self, session, content_screen, content_provider):
		ItemHandler.__init__(self, session, content_screen)
		self.content_provider = content_provider

	def _open_item(self, item, *args, **kwargs):

		def open_item_success_cb(result):
			list_items, command, args = result

			list_items.insert(0, PExit())
			self.content_screen.resolveCommand(command, args)
			self.content_screen.stopLoading()
			self.open_video_addon(item.addon, list_items)

		@AddonExceptionHandler(self.session, self.content_provider)
		def open_item_error_cb(failure):
			log.logError("Addon get_content error cb.\n%s"%failure)
			self.open_video_addon_cb(item.addon.provider)
			self.content_screen.stopLoading()
			self.content_screen.workingFinished()
			failure.raiseException()

		@AddonExceptionHandler(self.session, self.content_provider)
		def get_content(addon, params):
			try:
				content_provider = addon.provider
				content_provider.start()
				content_provider.get_content(self.session, params, open_item_success_cb, open_item_error_cb)
			except Exception:
				content_provider.stop()
				self.content_screen.stopLoading()
				self.content_screen.workingFinished()
				raise

		def continue_to_addon():
			params = 'params' in kwargs and kwargs['params'] or {}
			self.content_screen.workingStarted()
			self.content_screen.startLoading()
			get_content(addon, params)

		def get_addon_previous_version(addon_path):
			# check if
			previous_version = None
			prev_ver_file = os.path.join(addon_path, '.update_ver')
			if os.path.isfile(prev_ver_file):
				with open(prev_ver_file, 'r') as f:
					previous_version = f.readline().strip()

				os.remove(prev_ver_file)
			return previous_version

		addon = item.addon
		if addon.get_info('broken'):
			self._handle_broken_addon(addon)
		elif addon.get_info('deprecated'):
			self._handle_deprecated_addon(addon)
		else:
			# check if update from previous version was done
			prev_ver = get_addon_previous_version(addon.path)
			log.debug("Addon's previous version: %s" % prev_ver)
			if config.plugins.archivCZSK.changelogAfterUpdate.value and prev_ver:
				from ...gui.info import openPartialChangelog
				openPartialChangelog(self.session, continue_to_addon, addon.name, addon.changelog_path, prev_ver)
			else:
				continue_to_addon()

	def open_video_addon(self, addon, list_items):
		from ...gui.content import ArchivCZSKAddonContentScreenAdvanced
		self.session.openWithCallback(self.open_video_addon_cb, ArchivCZSKAddonContentScreenAdvanced, addon, list_items)

	def open_video_addon_cb(self, content_provider):
		if isinstance(content_provider, VideoAddonContentProvider):
			content_provider.stop()
		self.content_screen.workingFinished()

	def open_shortcuts_cb(self, sc_item):
		if sc_item:
			self.open_item(self.item, params=sc_item.params)

	def _handle_broken_addon(self, addon):
		def disable_addon(cb):
			if cb:
				addon.set_enabled(False)
				self.content_screen.workingStarted()
				self.content_screen.refreshList()
				self.content_screen.workingFinished()

		reason = py2_encode_utf8( addon.get_info('broken') )
		message = _("Addon is broken") + '\n'
		message += _("Reason") + ' : ' + reason +'\n\n'
		message += _("Do you want to disable this addon?")
		self.session.openWithCallback(disable_addon,MessageBox, message, type=MessageBox.TYPE_YESNO)

	def _handle_deprecated_addon(self, addon):
		def disable_addon(cb):
			if cb:
				addon.set_enabled(False)
				self.content_screen.workingStarted()
				self.content_screen.refreshList()
				self.content_screen.workingFinished()

		def remove_addon(cb):
			if cb:
				log.info("removing addon: %s" % addon.id)
				try:
					shutil.rmtree(addon.path)
				except Exception as e:
					log.error("cannot remove addon: %s" % str(e))
					message = ("Unable to remove addon")
					self.session.open(MessageBox, message, type=MessageBox.TYPE_WARNING)

				log.info("addon was removed: %s" % addon.id)

				from ...archivczsk import ArchivCZSK
				ArchivCZSK.remove_addon(addon)

				self.content_screen.workingStarted()
				self.content_screen.refreshList()
				self.content_screen.workingFinished()

		message = _("Addon is created for archivCZSK 1.x.x version and will not work anymore in this version. Author of the addon need to adopt it for this version.") + '\n'
		if addon.supported:
			message += _("Do you want to disable this addon?")
			self.session.openWithCallback(disable_addon, MessageBox, message, type=MessageBox.TYPE_YESNO)
		else:
			message += _("Do you want to remove this addon?")
			self.session.openWithCallback(remove_addon, MessageBox, message, type=MessageBox.TYPE_YESNO)

	def resolve_command(self):
		pass

	def _init_menu(self, item):
		self.item = item
		addon = item.addon
		# item.add_context_menu_item(_("Update"), action=item.addon.update)
		item.add_context_menu_item(_("Settings"),
								   action=addon.open_settings,
								   params={'session':self.session})
		item.add_context_menu_item(_("Changelog"),
								   action=addon.open_changelog,
								   params={'session':self.session})
		item.add_context_menu_item(_("Downloads"),
								   action=addon.open_downloads,
								   params={'session':self.session,
										   'cb':self.content_screen.workingFinished})
		item.add_context_menu_item(_("Shortcuts"),
								   action=addon.open_shortcuts,
								   params={'session':self.session,
										   'cb':self.open_shortcuts_cb})

	def can_handle(self, item):
		return item.__class__ in self.handles


class VideoAddonItemHandler(VideoAddonItemHandlerTemplate):
	handles = (PVideoAddon,)

	def _init_menu(self, item):
		item.add_context_menu_item(_("Add to category"),
								   action=self._choose_category,
								   params={'item':item})
		VideoAddonItemHandlerTemplate._init_menu(self, item)


	def _choose_category(self, item):
		self.categories = self.content_provider.get_content({'categories_user':''})
		for category in self.categories:
			if item.addon_id in category:
				category.enabled = False
		self.session.openWithCallback(self._choose_category_cb, ArchivCZSKSelectCategoryScreen, self.categories)

	def _choose_category_cb(self, idx):
		if idx is not None:
			self.content_screen.workingStarted()
			category_item = self.categories[idx]
			del self.categories
			self.content_provider.add_to_category(category_item, self.item)
			self.content_screen.workingFinished()


class CategoryVideoAddonItemHandler(VideoAddonItemHandlerTemplate):
	handles = (PCategoryVideoAddon,)

	def _init_menu(self, item):
		item.add_context_menu_item(_("Remove from category"),
								   action=self._remove_from_category,
								   params={'item':item})
		VideoAddonItemHandlerTemplate._init_menu(self, item)

	def _remove_from_category(self, item):
		category_item = self.content_screen.parent_it
		self.content_screen.workingStarted()
		self.content_provider.remove_from_category(category_item, item)
		self.content_screen.refreshList()
		self.content_screen.workingFinished()


class VideoAddonManagement(ItemHandler):
	handles = (PVideoAddon,)

	def __init__(self, session, content_screen, content_provider):
		ItemHandler.__init__(self, session, content_screen)
		self.content_provider = content_provider

	def _init_menu(self, item):
		addon = item.addon
		item.add_context_menu_item(_("Enable"),
								   enabled=not addon.is_enabled(),
								   action=self._enable_addon,
								   params={'addon':addon})
		item.add_context_menu_item(_("Disable"),
								   enabled=addon.is_enabled(),
								   action=self._disable_addon,
								   params={'addon':addon})
		item.add_context_menu_item(_("Settings"),
								   action=addon.open_settings,
								   params={'session':self.session})
		item.add_context_menu_item(_("Changelog"),
								   action=addon.open_changelog,
								   params={'session':self.session})

		item.add_context_menu_item(_("Remove"),
								enabled=not addon.supported,
								action=self._remove_addon,
								params={'addon':addon})
		ItemHandler._init_menu(self, item)

	def _enable_addon(self, addon):
		self.content_screen.workingStarted()
		addon.set_enabled(True)
		self.content_screen.refreshList()
		self.content_screen.workingFinished()

	def _disable_addon(self, addon):
		self.content_screen.workingStarted()
		addon.set_enabled(False)
		self.content_screen.refreshList()
		self.content_screen.workingFinished()

	def _remove_addon(self, addon):

		def remove_addon_callback(remove):
			if (remove):
				log.info("removing addon: %s" % addon.id)
				try:
					shutil.rmtree(addon.path)
				except Exception as e:
					log.error("cannot remove addon: %s" % str(e))
					message = ("Unable to remove addon")
					self.session.open(MessageBox, message, type=MessageBox.TYPE_WARNING)

				log.info("addon was removed: %s" % addon.id)

				from ...archivczsk import ArchivCZSK
				ArchivCZSK.remove_addon(addon)
				self.content_screen.workingStarted()
				self.content_screen.refreshList()
				self.content_screen.workingFinished()

		message = _("Do you want to remove") + " " + util.toString(addon.name)
		self.session.openWithCallback(remove_addon_callback, MessageBox, message, type=MessageBox.TYPE_YESNO,)


class ArchivCZSKContentHandler(ContentHandler):
	def __init__(self, session, content_screen, content_provider):
		handlers = []
		handlers.append(VideoAddonItemHandler(session, content_screen, content_provider))
		handlers.append(CategoryVideoAddonItemHandler(session, content_screen, content_provider))
		handlers.append(CategoryItemHandler(session, content_screen, content_provider))
		handlers.append(UserCategoryItemHandler(session, content_screen, content_provider))
		ContentHandler.__init__(self, session, content_screen, handlers=handlers)
		self.content_provider = content_provider

	def _render_content(self, content):
		if not self.content_screen.refreshing:
			self.content_screen.save()
		else:
			self.content_screen.refreshing = False
		self.content_screen.load(content)

	def exit_item(self):
		parent_content = self.content_screen.popParent()
		if parent_content is not None:
			self.content_screen.load(parent_content)
		else:
			self.content_screen.close()


class VideoAddonContentHandler(ContentHandler):

	def __init__(self, session, content_screen, content_provider):
		handlers = []
		handlers.append(FolderItemHandler(session, content_screen, content_provider))
		handlers.append(VideoResolvedItemHandler(session, content_screen, content_provider))
		handlers.append(VideoNotResolvedItemHandler(session, content_screen, content_provider))
		handlers.append(PlaylistItemHandler(session, content_screen, content_provider))
		handlers.append(ContextMenuItemHandler(session, content_screen, content_provider))
		ContentHandler.__init__(self, session, content_screen, content_provider, handlers)

	def exit_item(self):
		parent_content = self.content_screen.popParent()
		if parent_content is not None:
			self.content_screen.load(parent_content)
		else:
			self.content_screen.close(self.content_provider)


class VideoAddonManagementScreenContentHandler(ContentHandler):
	def __init__(self, session, content_screen, content_provider):
		handlers = []
		handlers.append(VideoAddonManagement(session, content_screen, content_provider))
		ContentHandler.__init__(self, session, content_screen, handlers=handlers)
		self.content_provider = content_provider

	def _get_root_content(self):
		content_provider = self.content_provider
		content_screen = self.content_screen
		if content_provider:
			parent_item = PRoot()
			index = content_screen.getSelectedIndex()
			list_items = content_provider.get_content({'category_addons':'all_addons', 'filter_enabled':False, 'filter_supported': False})
			return {'lst_items':list_items, 'parent_it':parent_item, 'index':index, 'refresh':False}

	def _render_content(self, content):
		if not self.content_screen.refreshing:
			self.content_screen.save()
		else:
			self.content_screen.refreshing = False
		self.content_screen.load(content)

	def exit_item(self):
		parent_content = self.content_screen.popParent()
		if parent_content is not None:
			self.content_screen.load(parent_content)
		else:
			self.content_screen.close()


class ShortcutsContentHandler(ContentHandler):

	def __init__(self, session, content_screen, content_provider):
		handlers = []
		handlers.append(FolderItemHandler(session, content_screen, content_provider))
		handlers.append(VideoNotResolvedItemHandler(session, content_screen, content_provider))
		ContentHandler.__init__(self, session, content_screen, content_provider, handlers)

	def exit_item(self):
		parent_content = self.content_screen.popParent()
		if parent_content is not None:
			self.content_screen.load(parent_content)
		else:
			self.content_screen.close(self.content_provider)

	def _render_content(self, content):
		if not self.content_screen.refreshing:
			self.content_screen.save()
		else:
			self.content_screen.refreshing = False
		self.content_screen.load(content)

	def remove_shortcut(self):
		pass

