# -*- coding: UTF-8 -*-
'''
Created on 28.4.2012

@author: marko
'''
import os
import traceback
import re

from twisted.web.client import downloadPage
from Components.Label import Label
from Components.ActionMap import ActionMap, NumberActionMap
from Components.ScrollLabel import ScrollLabel
from Components.Pixmap import Pixmap
from Components.AVSwitch import AVSwitch
from Components.config import config
from enigma import ePicLoad

from .base import BaseArchivCZSKScreen
from .. import _, log, removeDiac, settings
from ..compat import eConnectCallback
from .common import showInfoMessage, PanelColorListEntry, PanelList
from .poster import PosterProcessing, PosterPixmapHandler
from ..engine.player.info import videoPlayerInfo
from ..colors import DeleteColors
from ..py3compat import *


def openPartialChangelog(session, continue_cb, changelog_title, changelog_path, prev_ver):
	changelog_text = ''
	changelog_data = []
	try:
		with open(changelog_path, 'r') as f:
			for line in f:
				if prev_ver in line:
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
	Info(session, item)
	
#def removeDiacriticsCsfd(text):
#	 searchExp = text
#	 try:
#		 import unicodedata
#		 searchExp = ''.join((c for c in unicodedata.normalize('NFD', searchExp) 
#									 if unicodedata.category(c) != 'Mn')).encode('utf-8')
#	 except:
#		 log.logError("CSFD remove diacritics failed.\n%s"%traceback.format_exc())
		
#	 return searchExp

def showCSFDInfo(session, item):
	try:
		#name = removeDiacriticsCsfd(item.name)
		name = item.info.get('title', DeleteColors(item.name))
		name = removeDiac(name)
		name = name.replace('.', ' ').replace('_', ' ').replace('*','')
		
		# remove languages ... "Mother - CZ, EN, KO (2017)"
		name = re.sub("\s-\s[A-Z]{2}(,\s[A-Z]{2})*\s\(", " (", name)
		
		year = 0
		yearStr = ""
		try:
			mask = re.compile('([0-9]{4})', re.DOTALL)
			yearStr = mask.findall(name)[0]
			year = int(yearStr)
		except:
			pass
		# remove year
		name = re.sub("\([0-9]{4}\)","", name)

		name = name.strip()
		log.logDebug("Csfd search '%s', year=%s."%(name,year))

		csfdType = int(config.plugins.archivCZSK.csfdMode.getValue())

		if csfdType == 1:
			from ..gui.archivcsfd import ArchivCSFD
			session.open(ArchivCSFD, name, year)
		elif csfdType == 2:
			from Plugins.Extensions.CSFD.plugin import CSFD
			session.open(CSFD, name)
		elif csfdType == 3:
			from Plugins.Extensions.CSFDLite.plugin import CSFDLite
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

def showVideoPlayerInfo(session, cb=None):
	if cb:
		session.openWithCallback(cb, ArchivCZSKVideoPlayerInfoScreen)
	else:
		session.open(ArchivCZSKVideoPlayerInfoScreen)


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
		}, -2)	
	
	def pageUp(self):
		self["changelog"].pageUp()

	def pageDown(self):
		self["changelog"].pageDown()


class Info(object):
	def __init__(self, session, it):
		self.session = session
		self.it = it
		self.dest = ''
		self.imagelink = ''
		if it.image is not None:
			self.imagelink = py2_encode_utf8( it.image )
			self.dest = os.path.join('/tmp/', self.imagelink.split('/')[-1])

			if os.path.exists(self.dest):
				self.showInfo()
			else:
				self.downloadPicture()
		else:
			self.showInfo()
		
	def downloadPicture(self):
		print('[Info] downloadPicture %s to %s' % (self.imagelink, self.dest) )
		imagelink = self.imagelink
		if isinstance( self.imagelink, str ):
			imagelink = self.imagelink.encode('utf-8')
			
		downloadPage(imagelink, self.dest).addCallback(self.downloadPictureCallback).addErrback(self.downloadPictureErrorCallback)
		
	def downloadPictureCallback(self, txt=""):
		print('[Info] picture was succesfully downloaded')
		self.showInfo()
		
	def downloadPictureErrorCallback(self, err):
		print('[Info] picture was not succesfully downloaded: %s' % str(err))
		self.showInfo()
		
	def closeInfo(self):
		print('[Info] closeInfo')
		
	def showInfo(self):
		print('[Info] showInfo')
		self.session.openWithCallback(self.closeInfo, ArchivCZSKItemInfoScreen, self.it)

class ArchivCZSKItemInfoScreen(BaseArchivCZSKScreen):
	def __init__(self, session, it):
		BaseArchivCZSKScreen.__init__(self, session)
		self.image_link = None
		self.it = it
		self.image_dest = None
		if it.image is not None:
			self.image_link = py2_encode_utf8( it.image )
			self.image_dest = os.path.join('/tmp/', self.image_link.split('/')[-1])
		self.plot = ''
		self.genre = ''
		self.rating = ''
		self.year = ''

		self.title = py2_encode_utf8(DeleteColors(self.it.name))
		
		for key, value in it.info.items():		
			if key == 'plot':
				self.plot = py2_encode_utf8( value )
			elif key == 'genre':
				self.genre = py2_encode_utf8( value )
			elif key == 'rating':
				self.rating = py2_encode_utf8( value )
			elif key == 'year':
				self.year = py2_encode_utf8( value )
			elif key == 'title':
				self.title = py2_encode_utf8(value)
			elif key == 'img':
				self.image_link = py2_encode_utf8(value)
			
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
			"info": self.openCsfd,
		}, -2)	
#		self.title = py2_encode_utf8(DeleteColors(self.it.name))
		self.Scale = AVSwitch().getFramebufferScale()
		self.onLayoutFinish.append(self.showPicture)
		self.onClose.append(self.__onClose)

		poster_processing = PosterProcessing(1, os.path.join(config.plugins.archivCZSK.posterPath.getValue(), 'archivczsk_poster2'))
		self.poster = PosterPixmapHandler(self["img"], poster_processing, os.path.join(settings.PLUGIN_PATH, 'gui', 'icon', 'no_movie_image.png'))

	def pageUp(self):
		self["plot"].pageUp()

	def pageDown(self):
		self["plot"].pageDown()

	def openCsfd(self):
		showCSFDInfo(self.session, self.it)

	def showPicture(self):
		if self.image_link is not None:
			self.poster.set_image(self.image_link)

	def __onClose(self):
		del self.poster


class ArchivCZSKVideoPlayerInfoScreen(BaseArchivCZSKScreen):
	def __init__(self, session):
		BaseArchivCZSKScreen.__init__(self, session)
		self.__settings = config.plugins.archivCZSK.videoPlayer
		
		self["key_red"] = Label("")
		self["key_green"] = Label("")
		self["key_yellow"] = Label("")
		self["key_blue"] = Label(_("Refresh"))
		self["detected player"] = Label(_("Detected player:"))
		self["detected player_val"] = Label("")
		self["protocol"] = Label(_("Supported protocols:"))
		self["protocol_list"] = PanelList([], 24)
		self["container"] = Label(_("Supported containers:"))
		self["container_list"] = PanelList([], 24)
		self["info_scrolllabel"] = ScrollLabel()
			
		self["actions"] = ActionMap(["archivCZSKActions"],
		{
			"up": self.pageUp,
			"down": self.pageDown,
			"right": self.pageDown,
			"left": self.pageUp,
			"cancel":self.cancel,
			"blue": self.updateGUI,
		}, -2)
		
		self.onShown.append(self.setWindowTitle)
		self.onLayoutFinish.append(self.disableSelection)
		self.onLayoutFinish.append(self.setPlayer)
		self.onLayoutFinish.append(self.setInfo)
		self.onLayoutFinish.append(self.updateGUI)
	
	def setWindowTitle(self):
		self.title = _("VideoPlayer Info")
		
	def disableSelection(self):
		self["container_list"].selectionEnabled(False)
		self["protocol_list"].selectionEnabled(False)
		
	def updateGUI(self):
		containerWidth = self["container_list"].instance.size().width()
		protocolWidth = self["protocol_list"].instance.size().width()
		self.updateProtocolList(containerWidth)
		self.updateContainerList(protocolWidth)
		
	def setPlayer(self):
		self["detected player_val"].setText(videoPlayerInfo.getName())
		
	def setInfo(self):
		infoText=''
		infoText += _("These informations are valid only for internal enigma2 player based on gstreamer") + "."
		infoText += _("If you use other player like exteplayer3, then this check is not valid to you.")
		infoText += "\n\n"
		infoText += _("* Status UNKNOWN means, that I dont know how to get info,")
		infoText += " " + _("it doesnt mean that protocol or container isn't supported") + "."
		infoText += "\n\n"
		infoText += _("* Videos are encoded by various codecs")
		infoText += ", " + _("to play them you need to have HW support of your receiver to decode them") + "."
		infoText += "\n" + _("For example if you have ASF(WMV) - OK state")
		infoText += ", " + _("it doesnt already mean that you can play WMV file")
		infoText += ", " + _("it just means that player can open WMV container and get ENCODED video out of it") + "."
		infoText += " " + _("In WMV container is used VC1 encoded video") + "."
		infoText += " " + _("If your player cannot decode VC1 codec, than you cannot play this video.")
		self["info_scrolllabel"].setText(infoText)
		
	def updateProtocolList(self,width):
		menuList = []
		menuList.append(self.buildEntry(_("HTTP Protocol"), videoPlayerInfo.isHTTPSupported(), width))
		menuList.append(self.buildEntry(_("HLS Protocol"), videoPlayerInfo.isHLSSupported(), width))
		menuList.append(self.buildEntry(_("MMS Protocol"), videoPlayerInfo.isMMSSupported(), width))
		menuList.append(self.buildEntry(_("RTMP Protocol"), videoPlayerInfo.isRTMPSupported(), width))
		menuList.append(self.buildEntry(_("RTSP Protocol"), videoPlayerInfo.isRTSPSupported(), width))
		self["protocol_list"].setList(menuList)
		
	def updateContainerList(self,width):
		menuList = []
		menuList.append(self.buildEntry(_("3GP container"), videoPlayerInfo.isMP4Supported(), width))
		menuList.append(self.buildEntry(_("ASF(WMV) Container"), videoPlayerInfo.isASFSupported(), width))
		menuList.append(self.buildEntry(_("AVI Container"), videoPlayerInfo.isAVISupported(), width))
		menuList.append(self.buildEntry(_("FLV Container"), videoPlayerInfo.isFLVSupported(), width))
		menuList.append(self.buildEntry(_("MKV Container"), videoPlayerInfo.isMKVSupported(), width))
		menuList.append(self.buildEntry(_("MP4 Container"), videoPlayerInfo.isMP4Supported(), width))
		self["container_list"].setList(menuList)

		
	def buildEntry(self, name, res, width):
		if res is None:
			return PanelColorListEntry(name, _("UNKNOWN"), 0xffff00, width)
		elif res:
			return PanelColorListEntry(name, _("OK"), 0x00ff00, width)
		else:
			return PanelColorListEntry(name, _("FAIL"), 0xff0000, width)
		
	def pageUp(self):
		self["info_scrolllabel"].pageUp()

	def pageDown(self):
		self["info_scrolllabel"].pageDown()
		
		
	def cancel(self):
		self.close()
