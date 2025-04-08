from ..tools.logger import log
from ...gui import info
from ..parental import parental_pin

INFO_HANDLERS= {
				"item":info.showItemInfo,
				"csfd":info.showCSFDInfo,
			   }

class ItemHandler(object):
	""" Template class - handles item interaction """
	handles = ()
	def __init__(self, session, content_screen, info_modes=None):
		self.session = session
		self.content_screen = content_screen
		self.info_modes = info_modes or []

		#current item
		self.item = None

	def __repr__(self):
		return "[" + self.__class__.__name__ + "]"

	def open_item(self, item, *args, **kwargs):
		self.item = item
		log.debug("%s opening %s", repr(self), repr(item))
		self._open_item(item, *args, **kwargs)

	def _open_item(self, item, *args, **kwargs):
		"""
		define how to open item in subclass
		"""
		pass

	def _init_menu(self, item):
		""" hook - you can add here your init code"""
		pass

	def _init_info(self, item):
		""" hook - you can add here your init code"""
		pass

	def info_item(self, item, mode=None, *args, **kwargs):
		"""opens info about item according to defined mode"""
		self.item = item
		if mode in INFO_HANDLERS and mode in self.info_modes:
			self._init_info(item)
			log.debug("%s opening info of %s", repr(self), repr(item))
			INFO_HANDLERS[mode](self.session, item)

	def can_handle(self, item):
		"""
		@return: True if can handle item
		@return: False if cannot handle item
		"""
		return isinstance(item, self.handles)

	def check_pin(self, item, cbk):
		"""
		Checks if there is parental PIN needed for this item and if yes, then asks for it
		@return: Returns True/False result of pin check
		"""

		if parental_pin.get_settings('unlocked'):
			# parental control is not enabled or unlocked
			return cbk(True)

		try:
			is_adult = getattr(item, 'info', {}).get('adult', False)
		except:
			is_adult = False

		if is_adult:
			return parental_pin.check_and_unlock(self.session, cbk)

		return cbk(True)
