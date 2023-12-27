'''
Created on 10.3.2013

@author: marko

GUI Exception handling
'''
import traceback
try:
	from urllib2 import HTTPError, URLError
except:
	from urllib.error import HTTPError, URLError

from .common import showInfoMessage, showWarningMessage, showErrorMessage
from ..engine.exceptions import addon, download, play
from ..gsession import GlobalSession
from .. import _, log
import requests

class GUIExceptionHandler(object):
	errorName = _("Unknown Error")
	warningName = _("Unknown Warning")
	infoName = _("Unknown Info")

	def __init__(self,session, timeout=6):
		self.timeout = timeout
		self.session = session
		#self.session = GlobalSession.getSession()
		self.messageFormat = "[%s]\n%s"

	def infoMessage(self, text):
		showInfoMessage(self.session, self.messageFormat % (self.__class__.infoName, text), self.timeout)

	def errorMessage(self, text):
		showErrorMessage(self.session, self.messageFormat % (self.__class__.errorName, text), self.timeout)

	def warningMessage(self, text):
		showWarningMessage(self.session, self.messageFormat % (self.__class__.warningName, text), self.timeout)

	def customMessage(self, messageType, text):
		if messageType == 'info':
			showInfoMessage(self.session, text, self.timeout)
		elif messageType == 'warning':
			showWarningMessage(self.session, text, self.timeout)
		elif messageType == 'error':
			showErrorMessage(self.session, text, self.timeout)


class AddonExceptionHandler(GUIExceptionHandler):
	errorName = _("Addon error")
	warningName = _("Addon warning")
	infoName = _("Addon info")

	def __call__(self, func):
		def wrapped(*args, **kwargs):
			try:
				try:
					func(*args, **kwargs)
				# addon specific exceptions
				except addon.AddonInfoError as er:
					log.logError("Addon (AddonInfoError) error '%s'.\n%s"%(er.value,traceback.format_exc()))
					self.infoMessage(er.value)
				except addon.AddonWarningError as er:
					log.logError("Addon (AddonWarningError) error '%s'.\n%s"%(er.value,traceback.format_exc()))
					self.warningMessage(er.value)
				except addon.AddonError as er:
					log.logError("Addon (AddonError) error '%s'.\n%s"%(er.value,traceback.format_exc()))
					self.errorMessage(er.value)
				# loading exceptions
				except (requests.HTTPError, HTTPError) as e:
					log.logError("Addon (HTTPError) error '%s'.\n%s"%(e.code,traceback.format_exc()))
					message = "%s: %s %d" % (_("Error in loading"), _("HTTP Error"), e.code)
					self.errorMessage(message)
				except URLError as e:
					log.logError("Addon (URLError) error '%s'.\n%s"%(e.reason,traceback.format_exc()))
					message = "%s: %s\n%s" % (_("Error in loading"), _("URL Error"), str(e.reason))
					self.errorMessage(message)
				except addon.AddonThreadException as er:
					log.logError("Addon (AddonThreadException) error.\n%s"%(traceback.format_exc()))
					pass
				except requests.ConnectTimeout as e:
					log.logError("Addon (ConnectTimeout) error '%s'.\n%s"%(str(e),traceback.format_exc()))
					message = "%s: %s" % (_("Error in loading"), _("Connection to server timed out"))
					self.errorMessage(message)
				except requests.ReadTimeout as e:
					log.logError("Addon (ReadTimeout) error '%s'.\n%s"%(str(e),traceback.format_exc()))
					message = "%s: %s" % (_("Error in loading"), _("Waiting for data from server timed out"))
					self.errorMessage(message)
				except requests.ConnectionError as e:
					log.logError("Addon (ConnectionError) error '%s'.\n%s"%(str(e),traceback.format_exc()))
					message = "%s: %s" % (_("Error in loading"), _("Connection to server failed"))
					self.errorMessage(message)
				except requests.RequestException as e:
					log.logError("Addon (RequestException) error '%s'.\n%s"%(str(e),traceback.format_exc()))
					message = "%s: %s\n%s" % (_("Error in loading"), _("Connection to server failed"), str(e))
					self.errorMessage(message)
				# we handle all possible exceptions since we dont want plugin to crash because of addon error...
				except Exception as e:
					log.logError("Addon error.\n%s"%traceback.format_exc())
					self.errorMessage(_("An unhandled error occurred while calling the addon. Please report a bug so it can be fixed."))
					traceback.print_exc()
			except:
				log.logError("Addon (LOG) error.\n%s"%traceback.format_exc())
				# this can go to crash because want show modal from screen which is not modal
				# but this can got to fck
				#self.errorMessage("ADDON ERROR")
				pass
		return wrapped


class DownloadExceptionHandler(GUIExceptionHandler):
	errorName = _("Download error")
	warningName = _("Download warning")
	infoName = _("Download info")

	def __call__(self, func):
		def wrapped(*args, **kwargs):
			try:
				func(*args, **kwargs)
			except download.NotSupportedProtocolError as e:
				message = "%s %s" % (e.message, _("protocol is not supported"))
				self.errorMessage(message)
			except HTTPError as e:
				message = "%s %s:%d" % (_("Error in loading"), _("HTTP Error"), e.code)
				self.errorMessage(message)
			except URLError as e:
				message = "%s %s:%s" % (_("Error in loading"), _("URL Error"), str(e.reason))
				self.errorMessage(message)
		return wrapped


class UpdaterExceptionHandler(GUIExceptionHandler):
	errorName = _("Updater error")
	warningName = _("Updater warning")
	infoName = _("Updater info")
	def __call__(self, func):
		def wrapped(*args, **kwargs):
			try:
				func(*args, **kwargs)
			except HTTPError as e:
				message = "%s %s:%d" % (_("Error in loading"), _("HTTP Error"), e.code)
				self.errorMessage(message)
			except URLError as e:
				message = "%s %s:%s" % (_("Error in loading"), _("URL Error"), str(e.reason))
				self.errorMessage(message)
		return wrapped


class PlayExceptionHandler(GUIExceptionHandler):
	errorName = _("Play error")
	warningName = _("Play warning")
	infoName = _("Play info")

	def __call__(self, func):
		def wrapped(*args, **kwargs):
			try:
				func(*args, **kwargs)
			except play.UrlNotExistError:
				self.errorMessage((_("Video url doesnt exist")))
		return wrapped

