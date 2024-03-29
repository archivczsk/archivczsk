from .item import ItemHandler
from .folder import FolderItemHandler
from .media import VideoNotResolvedItemHandler
from ..items import PContextMenuItem

class ContextMenuItemHandler(ItemHandler):
	handles = (PContextMenuItem)
	def __init__(self, session, content_screen, content_provider):
		ItemHandler.__init__(self, session, content_screen)
		self.content_provider = content_provider
		self.folder_handler = FolderItemHandler(session, content_screen, content_provider)
		self.media_handler = VideoNotResolvedItemHandler(session, content_screen, content_provider)
	
	def _open_item(self, item, *args, **kwargs):
		if item.can_execute():
			return item.execute()
		elif item.is_media():
			item.params = item.get_params()
			return self.media_handler._open_item(item, *args, **kwargs)
		else:
			item.params = item.get_params()
			return self.folder_handler._open_item(item, *args, **kwargs)
