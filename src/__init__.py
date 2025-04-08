# -*- coding: utf-8 -*-

from .engine.tools.logger import log, create_rotating_log, toString
from .py3compat import *

# I don't know why, but this is really needed
# if _ is not defined, then ContentScreenAdvanced (addons content screen) doesn't work
_ = None

class UpdateInfo(object):
	CHECK_UPDATE_TIMESTAMP = None
	CHECK_ADDON_UPDATE_TIMESTAMP = None

	@staticmethod
	def resetDates():
		UpdateInfo.CHECK_UPDATE_TIMESTAMP = None
		UpdateInfo.CHECK_ADDON_UPDATE_TIMESTAMP = None
