'''
Created on 22.12.2012

@author: marko
'''
import os
from ... import log
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
			log.logDebug('Found gstreamer 1.0')
			self.type = 'gstreamer'
			self.version = '1.0'
			self.gstPath = GSTREAMER10_PATH
		elif os.path.isdir(GSTREAMER_PATH):
			print('found gstreamer')
			log.logDebug('Found gstreamer 0.10')
			self.type = 'gstreamer'
			self.version = '0.10'
			self.gstPath = GSTREAMER_PATH

		# check, if there is ServiceApp plugin installed
		if os.path.isfile( SERVICEAPP_PATH ) or os.path.isfile( SERVICEAPP_PATH + 'o' ) or os.path.isfile( SERVICEAPP_PATH + 'c'):
			self.serviceappAvailable = True
		else:
			self.serviceappAvailable = False

		# check if there is gstplayer installed
		for bin_name in GSTPLAYER_PATHS:
			if os.path.isfile( bin_name ):
				self.gstplayerAvailable = True
				break
		else:
			self.gstplayerAvailable = False

		# check if there is ExtEplayer3 installed
		if os.path.isfile( EXTEPLAYER3_PATH ):
			self.exteplayer3Available = True
		else:
			self.exteplayer3Available = False

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

######################### Supported protocols ##################################

	def isRTMPSupported(self):
		"""
		@return: True if its 100% supported
		@return: None may be supported
		@return: False not supported
		"""

		if self.type == 'gstreamer':
			rtmplib = os.path.join(self.gstPath, 'libgstrtmp.so')

			librtmp = os.path.join(LIB_PATH, 'librtmp.so.0')
			librtmp2 = os.path.join(LIB_PATH, 'librtmp.so.1')

			# flv is file container used in rtmp
			flvlib = os.path.join(self.gstPath, 'libgstflv.so')
			if os.path.isfile(rtmplib) and (os.path.isfile(librtmp) or os.path.isfile(librtmp2)) and (os.path.isfile(flvlib)):
				log.logDebug("RTMP supported for 100%...")
				return True

			msg = ""
			if not os.path.isfile(rtmplib):
				msg+= "\n'libgstrtmp.so' is missing..."
			if not (os.path.isfile(librtmp) or os.path.isfile(librtmp2)):
				msg+= "\n'%s' or '%s' is missing..."%(librtmp, librtmp2)
			if not os.path.isfile(flvlib):
				msg+= "\n'libgstflv.so' is missing..."

			log.logDebug("RTMP not supported (some file missing '%s')...%s" % (self.gstPath, msg))
			return False

	def isMMSSupported(self):
		"""
		@return: True if its 100% supported
		@return: None may be supported
		@return: False not supported
		"""
		if self.type == 'gstreamer':
			mmslib = os.path.join(self.gstPath, 'libgstmms.so')
			if os.path.isfile(mmslib):
				log.logDebug("MMS supported")
				return True
			log.logDebug("MMS not supported, missing file '%s'" % mmslib)
			return False

	def isRTSPSupported(self):
		"""
		@return: True if its 100% supported
		@return: None may be supported
		@return: False not supported
		"""
		if self.type == 'gstreamer':
			rtsplib = os.path.join(self.gstPath, 'libgstrtsp.so')
			rtplib = os.path.join(self.gstPath, 'libgstrtp.so')
			rtpmanager = os.path.join(self.gstPath, 'libgstrtpmanager.so')
			if os.path.isfile(rtsplib) and os.path.isfile(rtplib) and os.path.isfile(rtpmanager):
				log.logDebug("RTSP supported for 100%...")
				return True

			msg = ""
			if not os.path.isfile(rtsplib):
				msg+= "\n'libgstrtsp.so' is missing..."
			if not os.path.isfile(rtplib):
				msg+= "\n'libgstrtp.so' is missing..."
			if not os.path.isfile(rtpmanager):
				msg+= "\n'libgstrtpmanager.so' is missing..."

			log.logDebug("RTSP may be supported (some file missing '%s')...%s" % (self.gstPath, msg))
			return False

	def isHTTPSupported(self):
		"""
		@return: True if its 100% supported
		@return: None may be supported
		@return: False not supported
		"""
		if self.type == 'gstreamer':
			httplib = os.path.join(self.gstPath, 'libgstsouphttpsrc.so' if self.version == '0.10' else 'libgstsoup.so')
			if os.path.isfile(httplib):
				log.logDebug("HTTP supported")
				return True
			log.logDebug("HTTP not supported, missing file '%s'" % httplib)
			return False

	def isHLSSupported(self):
		"""
		@return: True if its 100% supported
		@return: None may be supported
		@return: False not supported
		"""
		if self.type == 'gstreamer':
			hlslib = os.path.join(self.gstPath, 'libgstfragmented.so' if self.version == '0.10' else 'libgsthls.so' )
			if os.path.isfile(hlslib):
				log.logDebug("HLS supported")
				return True
			log.logDebug("HLS not supported, missing file '%s'" % hlslib)
			return False

##########################################################################

########################### Supported Video Formats ######################

	def isASFSupported(self):
		"""
		@return: True if its 100% supported
		@return: None may be supported
		@return: False not supported
		"""
		if self.type == 'gstreamer':
			asflib = os.path.join(self.gstPath, 'libgstasf.so')
			if os.path.isfile(asflib):
				log.logDebug("ASF supported")
				return True
			log.logDebug("ASF not supported, missing file '%s'" % asflib )
			return False

	def isWMVSupported(self):
		return self.isASFSupported()

	def isFLVSupported(self):
		"""
		@return: True if its 100% supported
		@return: None may be supported
		@return: False not supported
		"""
		if self.type == 'gstreamer':
			flvlib = os.path.join(self.gstPath, 'libgstflv.so')
			if os.path.isfile(flvlib):
				log.logDebug("FLV supported")
				return True
			log.logDebug("FLV not supported, missing file '%s'" % flvlib)
			return False

	def isMKVSupported(self):
		"""
		@return: True if its 100% supported
		@return: None may be supported
		@return: False not supported
		"""
		if self.type == 'gstreamer':
			mkvlib = os.path.join(self.gstPath, 'libgstmatroska.so')
			if os.path.isfile(mkvlib):
				log.logDebug("MKV supported")
				return True
			log.logDebug("MKV not supported, missing file '%s'" % mkvlib)
			return False

	def isAVISupported(self):
		"""
		@return: True if its 100% supported
		@return: None may be supported
		@return: False not supported
		"""
		if self.type == 'gstreamer':
			avilib = os.path.join(self.gstPath, 'libgstavi.so')
			if os.path.isfile(avilib):
				log.logDebug("AVI supported")
				return True
			log.logDebug("AVI not supported, missing file '%s'" % avilib)
			return False

	def isMP4Supported(self):
		"""
		@return: True if its 100% supported
		@return: None may be supported
		@return: False not supported
		"""
		if self.type == 'gstreamer':
			isomp4lib = os.path.join(self.gstPath, 'libgstisomp4.so')
			if os.path.isfile(isomp4lib):
				log.logDebug("MP4 supported")
				return True
			log.logDebug("MP4 not supported, missing file '%s'" % isomp4lib)
			return False

	def is3GPPSupported(self):
		if self.type == 'gstreamer':
			return self.isMP4Supported()

#########################################################################

videoPlayerInfo = VideoPlayerInfo()
