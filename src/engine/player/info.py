# -*- coding: utf-8 -*-
'''
Created on 22.12.2012

@author: marko
'''
import os, traceback
from ..tools.logger import log
from ...compat import DMM_IMAGE

GSTREAMER_PATH = '/usr/lib/gstreamer-0.10'
GSTREAMER10_PATH = '/usr/lib/gstreamer-1.0'
LIB_PATH = '/usr/lib'
GSTPLAYER_PATHS = ('/usr/bin/gstplayer', '/usr/bin/gstplayer_gst-1.0')
EXTEPLAYER3_PATH = '/usr/bin/exteplayer3'
SERVICEAPP_PATH = '/usr/lib/enigma2/python/Plugins/SystemPlugins/ServiceApp/__init__.py'

class VideoPlayerInfo(object):
	def __init__(self):
		self.type = 'gstreamer'
		self.version = 0
		if os.path.isdir(GSTREAMER10_PATH):
			print('found gstreamer')
			log.logInfo('Found gstreamer 1.0')
			self.type = 'gstreamer'
			self.version = '1.0'
			self.gstPath = GSTREAMER10_PATH
		elif os.path.isdir(GSTREAMER_PATH):
			print('found gstreamer')
			log.logInfo('Found gstreamer 0.10')
			self.type = 'gstreamer'
			self.version = '0.10'
			self.gstPath = GSTREAMER_PATH

		# check, if there is ServiceApp plugin installed
		if os.path.isfile( SERVICEAPP_PATH ) or os.path.isfile( SERVICEAPP_PATH + 'o' ) or os.path.isfile( SERVICEAPP_PATH + 'c'):
			log.logInfo('Found ServiceApp system plugin')
			self.serviceappAvailable = True
		else:
			log.logInfo('ServiceApp system plugin not found')
			self.serviceappAvailable = False

		# check if there is gstplayer installed
		for bin_name in GSTPLAYER_PATHS:
			if os.path.isfile( bin_name ):
				self.gstplayerAvailable = True
				break
		else:
			self.gstplayerAvailable = False

		# check if there is Exteplayer3 installed
		if os.path.isfile( EXTEPLAYER3_PATH ):
			self.exteplayer3Available = True
			log.logInfo('Found exteplayer3 with version %s' % self.getExteplayer3Version())
		else:
			self.exteplayer3Available = False
			log.logInfo('exteplayer3 not found')

		# check if there is SubsSupport plugin available
		self.subssupport_version = self.getSubsSupportVersion()
		if self.subssupport_version is not None:
			log.logInfo("Found SubsSupport plugin with version %s" % self.subssupport_version)
		else:
			log.logInfo("SubsSupport plugin not found")

	def getExteplayer3Version(self):
		try:
			import subprocess, json

			try:
				data = subprocess.check_output(['exteplayer3'], shell=False, stderr=subprocess.STDOUT)
			except subprocess.CalledProcessError as ex:
				data = ex.output
			data = data.decode('utf-8')
			if data[-1:] == '\n':
				data = data[:-1]

			lines = list(map(lambda x: x.strip(), data.splitlines()))

			return json.loads(lines[0])['EPLAYER3_EXTENDED']['version']
		except:
			log.logError(traceback.format_exc())
			return None

	def getSubsSupportVersion(self):
		try:
			from Plugins.Extensions.SubsSupport import __version__
			return __version__
		except:
			try:
				from Plugins.Extensions.SubsSupport import SubsSupport
				return "?"
			except:
				pass

		return None

	def getName(self):
		if self.type == 'gstreamer':
			if self.version == '1.0':
				return 'Gstreamer 1.0'
			return 'GStreamer 0.10'

	def getAvailablePlayers(self, asString=False):
		ret = [ self.getName() ]

		if self.serviceappAvailable:
			if self.gstplayerAvailable:
				ret.append('GstPlayer')

			if self.exteplayer3Available:
				ret.append('ExtEplayer3')

		if DMM_IMAGE:
			ret.append('DMM')
			ret.append('DVB')

		if asString:
			return ', '.join(ret)
		return ret

	def getAvailablePlayersRefs(self):
		ret = [ 4097 ]

		if self.serviceappAvailable:
			if self.gstplayerAvailable:
				ret.append(5001)

			if self.exteplayer3Available:
				ret.append(5002)

		if DMM_IMAGE:
			ret.append(8193)
			ret.append(1)

		return ret

	def getPlayerNameByStype(self, stype):
		return {
			4097: 'Enigma2 default',
			5001: 'GstPlayer',
			5002: 'Exteplayer3',
			8193: 'DMM Player',
			1: 'DVB',
		}.get(stype, str(stype))


#########################################################################

videoPlayerInfo = VideoPlayerInfo()

#########################################################################

def player2stype( player ):
	# enum: 'Predvolený|gstplayer|exteplayer3|DMM|DVB (OE>=2.5)'
	player_mapping = {
		'0' : 4097, # Default
	}

	# fill only available players - if not available player is choosen then default service 4097 will be used
	if videoPlayerInfo.serviceappAvailable:
		if videoPlayerInfo.gstplayerAvailable:
			player_mapping['1'] = 5001  # gstplayer
		if videoPlayerInfo.exteplayer3Available:
			player_mapping['2'] = 5002  # exteplayer3

	if DMM_IMAGE:
		# this is only available on DreamOS
		player_mapping['3'] = 8193  # DMM player
		player_mapping['4'] = 1     # DVB service

	return player_mapping.get( player, 4097 )

#########################################################################
