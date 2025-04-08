# -*- coding: utf-8 -*-
import os, gettext, sys, datetime, traceback

from Components.Language import language
from Components.config import config
from Tools.Directories import resolveFilename, SCOPE_PLUGINS, SCOPE_LANGUAGE

from .engine.tools.logger import log, create_rotating_log, toString
from .py3compat import *

PluginLanguageDomain = "archivCZSK"
PluginLanguagePath = "Extensions/archivCZSK/locale"

def localeInit():
	lang = language.getLanguage()[:2] # getLanguage returns e.g. "fi_FI" for "language_country"
	os.environ["LANGUAGE"] = lang # Enigma doesn't set this (or LC_ALL, LC_MESSAGES, LANG). gettext needs it!
	print("[WebInterface] set language to %s" % lang )
	gettext.bindtextdomain(PluginLanguageDomain, resolveFilename(SCOPE_PLUGINS, PluginLanguagePath))

def _(txt):
	return gettext.dgettext(PluginLanguageDomain, txt)

if language:
	localeInit()
	language.addCallback(localeInit)

class UpdateInfo(object):
	CHECK_UPDATE_TIMESTAMP = None
	CHECK_ADDON_UPDATE_TIMESTAMP = None

	@staticmethod
	def resetDates():
		UpdateInfo.CHECK_UPDATE_TIMESTAMP = None
		UpdateInfo.CHECK_ADDON_UPDATE_TIMESTAMP = None
