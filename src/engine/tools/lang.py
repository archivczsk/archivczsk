# -*- coding: utf-8 -*-
import os, gettext

from Components.Language import language
from Tools.Directories import resolveFilename, SCOPE_PLUGINS, SCOPE_LANGUAGE
from .logger import log

PluginLanguageDomain = "archivCZSK"
PluginLanguagePath = "Extensions/archivCZSK/locale"

translation = None
lang_requested = None
lang_selected = 'en'

def get_system_lang_id():
	return language.getLanguage()[:2] if language else 'en' # getLanguage returns e.g. "fi_FI" for "language_country"

def localeInit(language_id=None):
	log.debug("Initialising locale to %s" % language_id or 'auto')
	global translation, lang_selected, lang_requested

	lang_requested = language_id

	if not language_id:
		language_id = get_system_lang_id()
		log.debug("System language is set to %s" % language_id)

	if not language_id:
		translation = None
		lang_selected = 'en'
		return

	languages_dir = resolveFilename(SCOPE_PLUGINS, PluginLanguagePath)

	if os.path.isdir( os.path.join(languages_dir, language_id, 'LC_MESSAGES') ):
		lang_selected = language_id
		translation = gettext.translation(PluginLanguageDomain, languages_dir, [language_id])
	else:
		lang_selected = 'en'
		translation = None

	log.debug("Plugin language initialised to %s" % lang_selected)


def _(txt):
	return translation.gettext(txt) if translation else txt

def get_language_id():
	return lang_selected

def systemLangChanged():
	log.debug("System language changed to %s" % get_system_lang_id())
	if lang_requested == None:
		localeInit()

localeInit()
if language:
	language.addCallback(systemLangChanged)
