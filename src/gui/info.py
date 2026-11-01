# -*- coding: UTF-8 -*-
'''
Created on 28.4.2012

@author: marko
'''
import traceback
import re

from Components.Label import Label
from Components.ActionMap import NumberActionMap
from Components.ScrollLabel import ScrollLabel
from Components.Pixmap import Pixmap
from Components.AVSwitch import AVSwitch
from Components.config import config

from .base import BaseArchivCZSKScreen
from .common import showInfoMessage
from .poster import PosterPixmapHandler
from ..engine.parental import parental_pin
from ..engine.usage import UsageStats
from ..engine.tools.util import toUnicode, removeDiac
from ..engine.tools.lang import _
from ..engine.tools.logger import log
from ..colors import DeleteColors
from ..py3compat import *


def openPartialChangelog(session, continue_cb, changelog_title, changelog_path, prev_ver):
	changelog_text = ''
	changelog_data = []
	try:
		with open(changelog_path, 'r') as f:
			for line in f:
				if prev_ver and prev_ver in line:
					break
				changelog_data.append(line)

		changelog_text = ''.join(changelog_data)
	except:
		log.error("Failed to open changelog:\n%s" % traceback.format_exc())

	if len(changelog_text) > 0:
		session.openWithCallback(continue_cb, ArchivCZSKChangelogScreen, changelog_title, changelog_text)
	else:
		continue_cb()


def showChangelog(session, changelog_title, changelog_path):
	changelog_text = ''
	try:
		with open(changelog_path, 'r') as f:
			changelog_text = f.read()
	except:
		pass

	session.open(ArchivCZSKChangelogScreen, changelog_title, changelog_text)

def showItemInfo(session, item):
	session.open(ArchivCZSKItemInfoScreen, item)

def showCSFDInfo(session, item):
	try:
		#name = removeDiacriticsCsfd(item.name)
		name = item.info.get('title', DeleteColors(item.name))
		name = removeDiac(name)
		name = name.replace('.', ' ').replace('_', ' ').replace('*','')

		# remove languages ... "Mother - CZ, EN, KO (2017)"
		name = re.sub("\s-\s[A-Z]{2}(,\s[A-Z]{2})*\s\(", " (", name)

		if item.info.get('year'):
			year = item.info.get('year')
			yearStr = '({})'.format(year)
		else:
			# try to extract year from name
			year = 0
			yearStr = ""
			try:
				mask = re.compile('([0-9]{4})', re.DOTALL)
				yearStr = mask.findall(name)[0]
				year = int(yearStr)
			except:
				year = 0
				yearStr = ""
				pass

		# remove year from name (if provided)
		name = re.sub("\([0-9]{4}\)","", name)

		name = name.strip()
		log.logDebug("Csfd search '%s', year=%s."%(name,year))

		csfdType = int(config.plugins.archivCZSK.csfdMode.getValue())

		if csfdType == 1:
			from ..gui.archivcsfd import ArchivCSFD
			UsageStats.get_instance().update_counter('csfd_i')
			session.open(ArchivCSFD, name, year)
		elif csfdType == 2:
			from Plugins.Extensions.CSFD.plugin import CSFD
			UsageStats.get_instance().update_counter('csfd_e')
			session.open(CSFD, name, EPG=yearStr)
		elif csfdType == 3:
			from Plugins.Extensions.CSFDLite.plugin import CSFDLite
			UsageStats.get_instance().update_counter('csfd_l')
			try:
				session.open(CSFDLite, name, yearStr)
			except:
				log.logDebug("Trying CsfdLite older version compatibility...")
				session.open(CSFDLite, name)
		else:
			raise Exception("CsfdMode '%s' not supported." % csfdType)
	except:
		log.logError("Show CSFD info failed (plugin may not be installed).\n%s"%traceback.format_exc())
		try:
			showInfoMessage(session, _("Show CSFD info failed."), timeout=6)
		except:
			pass


class ArchivCZSKChangelogScreen(BaseArchivCZSKScreen):
	def __init__(self, session, title, text=None):
		BaseArchivCZSKScreen.__init__(self, session)
		self.changelog = ""

		try:
			from ..engine.tools.util import toString
			if text is not None:
				self.changelog = toString(text)
			self.title = toString(title) + ' - ' + _('changelog')
		except:
			self.changelog = "failed"
			log.logError("Convert log file text failed.\n%s"%traceback.format_exc())
			pass
		self["changelog"] = ScrollLabel(self.changelog)

		self["actions"] = NumberActionMap(["archivCZSKActions"],
		{
			"cancel": self.close,
			"ok": self.close,
			"up": self.pageUp,
			"down": self.pageDown,
			"left": self.pageUp,
			"right": self.pageDown,
			"channelUp": self.homePage,
			"channelDown": self.endPage
		}, -2)

	def pageUp(self):
		self["changelog"].pageUp()

	def pageDown(self):
		self["changelog"].pageDown()

	def homePage(self):
		self["changelog"].homePage()

	def endPage(self):
		self["changelog"].endPage()


class ArchivCZSKItemInfoScreen(BaseArchivCZSKScreen):
	def __init__(self, session, it):
		BaseArchivCZSKScreen.__init__(self, session)
		self.image_link = None
		self.it = it
#		self.image_dest = None
		if it.image is not None:
			self.image_link = py2_encode_utf8( it.image )
#			self.image_dest = os.path.join('/tmp/', self.image_link.split('/')[-1])
		self.plot = ''
		self.genre = ''
		self.rating = ''
		self.year = ''

		self.title = py2_encode_utf8(DeleteColors(self.it.name))
		it.load_info()

		try:
			for key, value in it.info.items():
				if key == 'plot':
					self.plot = py2_encode_utf8( value )
				elif key == 'genre':
					self.genre = self.convert_genre(value)
				elif key == 'rating':
					self.rating = self.convert_rating(value)
				elif key == 'year':
					self.year = py2_encode_utf8( value )
				elif key == 'title':
					self.title = py2_encode_utf8(DeleteColors(value))
				elif key == 'img':
					self.image_link = py2_encode_utf8(value)
		except:
			log.error(traceback.format_exc())

		self["img"] = Pixmap()
		self["genre"] = Label(_("Genre: ") + self.genre)
		self["year"] = Label(_("Year: ") + self.year)
		self["rating"] = Label(_("Rating: ") + self.rating)
		self["plot"] = ScrollLabel(self.plot)

		self["actions"] = NumberActionMap(["archivCZSKActions"],
		{
			"cancel": self.close,
			"up": self.pageUp,
			"down": self.pageDown,
			"left": self.pageUp,
			"right": self.pageDown,
			"channelUp": self.homePage,
			"channelDown": self.endPage,
			"info": self.openCsfd,
		}, -2)
#		self.title = py2_encode_utf8(DeleteColors(self.it.name))
		self.Scale = AVSwitch().getFramebufferScale()
		self.onLayoutFinish.append(self.showPicture)
		self.onClose.append(self.__onClose)

		self.poster = PosterPixmapHandler(self["img"])

	def convert_genre(self, genre):
		if isinstance(genre, list):
			genre = ', '.join(toUnicode(g) for g in genre)

		return py2_encode_utf8( genre )

	def convert_rating(self, rating):
		if isinstance(rating, dict):
			r = ['']
			for k, v in rating.items():
				if isinstance(v, (list, set)):
					v = ' '.join(toUnicode(x) for x in v)
				r.append('{}: {}'.format(toUnicode(k), toUnicode(v)))

			rating = '\n'.join(r)

		return py2_encode_utf8( rating )

	def pageUp(self):
		self["plot"].pageUp()

	def pageDown(self):
		self["plot"].pageDown()

	def homePage(self):
		self["plot"].homePage()

	def endPage(self):
		self["plot"].endPage()

	def openCsfd(self):
		showCSFDInfo(self.session, self.it)

	def showPicture(self):
		if self.image_link is not None and (self.it.info.get('adult', False) == False or parental_pin.get_settings('show_posters')):
			self.poster.set_image(self.image_link)

	def __onClose(self):
		self.poster.cleanup()

