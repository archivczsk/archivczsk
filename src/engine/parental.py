# -*- coding: UTF-8 -*-

from time import time
from .. import log
from .tools.lang import _
from Components.Input import Input
from Screens.InputBox import InputBox
from ..gui.common import showErrorMessage, showInfoMessage
from ..settings import config

# #################################################################################################

class ParentalPin(object):
	def __init__(self):
		self.pin_entered = False
		self.max_pin_tries=3
		self.wait_time=(15*60)
		self.config = config.plugins.archivCZSK.parental

	# #################################################################################################

	def lock_pin(self):
		self.pin_entered = False

	# #################################################################################################

	def unlock_pin(self):
		self.pin_entered = True
		self.config.time.value = 0
		self.config.time.save()
		self.config.pin_tries.value = 0
		self.config.pin_tries.save()

	# #################################################################################################

	def is_locked(self):
		if self.pin_entered:
			return False
		else:
			return True

	# #################################################################################################

	def obfuscate_pin(self, pin):
		pin = int(pin)
		return (pin * 1863) + ((pin * 667934) % 6784) + 783

	# #################################################################################################

	def set_pin(self, pin):
		self.config.pin.value = self.obfuscate_pin(pin)
		self.config.pin.save()

	# #################################################################################################

	def check_pin_validity(self, pin, auto_unlock=True):
		if len(pin) >= 4 and self.obfuscate_pin(pin) == self.config.pin.value:
			if auto_unlock:
				self.unlock_pin()
			return True
		else:
			self.config.pin_tries.value += 1
			self.config.pin_tries.save()
			self.config.time.value = int(time())
			self.config.time.save()
			return False

	# #################################################################################################

	def pin_entering_unlocked(self):
		if self.config.pin_tries.value >= self.max_pin_tries:
			if int(time()) - self.config.time.value > self.wait_time:
				self.unlock_pin()
				return True
			else:
				return False
		else:
			return True

	# #################################################################################################

	def pin_remainig_time(self):
		remaining = self.wait_time + self.config.time.value - int(time())
		if remaining < 0:
			return '0 ' + _('seconds')
		elif remaining <= 60:
			return str(remaining) + ' ' + _('seconds')
		else:
			remaining_min = 1 + (remaining // 60)
			return str(remaining_min) + ' ' + _('minutes')

	# #################################################################################################

	def error_max_tries(self, session, cbk=None):
		showErrorMessage(session, message=_('You entered {max_tries} times wrong PIN. Wait {remaining_time} and try again.').format(max_tries=self.max_pin_tries, remaining_time=self.pin_remainig_time()), timeout=10, cb=cbk)

	# #################################################################################################

	def error_wrong_pin(self, session, cbk=None):
		showErrorMessage(session, message=_('Entered parental PIN code is not correct'), timeout=10, cb=cbk)

	# #################################################################################################

	def error_short_pin(self, session, cbk=None):
		showErrorMessage(session, message=_('Entered PIN code must be at least 4 characters long'), timeout=10, cb=cbk)

	# #################################################################################################

	def check_and_unlock(self, session, cbk=None, msg=None):
		def call_cbk(result):
			if cbk != None:
				cbk(result)

		if self.pin_entered:
			return call_cbk(True)

		def cbk_wrong_entered_pin(result):
			call_cbk(False)

		def cbk_check_entered_pin(pin):
			if pin == None:
				return call_cbk(False)

			if self.check_pin_validity(pin):
				return call_cbk(True)
			else:
				self.error_wrong_pin(session, cbk=cbk_wrong_entered_pin)

		if self.pin_entering_unlocked():
			title=msg or _('To show this content you need to enter parental PIN ({ramaining_tries})')
			session.openWithCallback(cbk_check_entered_pin, InputBox, title=title.format(ramaining_tries=self.max_pin_tries-self.config.pin_tries.value), type=Input.PIN)
		else:
			self.error_max_tries(session, cbk=cbk_wrong_entered_pin)

	# #################################################################################################

	def change(self, session):
		if not self.pin_entering_unlocked():
			self.error_max_tries(session)

		def cbk_check_new_pin2(pin1, pin2):
			if pin2 == None:
				return

			if pin1 != pin2:
				showErrorMessage(session, message=_('Entered PIN codes are different'), timeout=10)
			else:
				self.set_pin(pin2)
				showInfoMessage(session, message=_('PIN code successfuly changed'), timeout=10)

		def cbk_check_new_pin(pin):
			if pin == None:
				return

			if len(pin) < 4:
				return self.error_short_pin(session)

			session.openWithCallback(lambda pin2: cbk_check_new_pin2(pin, pin2), InputBox, title=_('Repeat new PIN'), type=Input.PIN)

		def cbk_check_current_pin(pin):
			if pin == None:
				return

			if self.check_pin_validity(pin, False):
				session.openWithCallback(cbk_check_new_pin, InputBox, title=_('Enter new PIN'), type=Input.PIN)
			else:
				self.error_wrong_pin(session)


		session.openWithCallback(cbk_check_current_pin, InputBox, title=_('Enter current PIN ({ramaining_tries})').format(ramaining_tries=self.max_pin_tries-self.config.pin_tries.value), type=Input.PIN)

	# #################################################################################################

	def get_settings(self, name=None):
		unlocked = self.is_locked() == False or self.config.enable.value == False

		s = {
			'unlocked': unlocked,
			'show_adult': unlocked or self.config.show_adult.value,
			'show_posters': unlocked or self.config.show_posters.value,
		}

		if name != None:
			return s.get(name)
		else:
			return s

# #################################################################################################

parental_pin = ParentalPin()
