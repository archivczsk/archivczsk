# -*- coding: utf-8 -*-

# I don't know why, but this is really needed
# if _ is not defined, then ContentScreenAdvanced (addons content screen) doesn't work
_ = None

class UpdateInfo(object):
	CHECK_UPDATE_TIMESTAMP = None

	@staticmethod
	def resetDates():
		UpdateInfo.CHECK_UPDATE_TIMESTAMP = None
