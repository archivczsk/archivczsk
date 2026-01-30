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

from Components.config import config
from .common import showInfoMessage, showWarningMessage, showErrorMessage, showYesNoDialog, MessageBox
from ..engine.exceptions import addon, download, play
from ..engine.usage import UsageStats
from ..engine.tools.lang import _
from ..engine.tools.logger import log
from ..engine.addon import Addon
from ..engine.trakttv import TraktException
import requests

# this is needed for compatibility with Python 2.7
try:
	ConnectionError
except:
	class ConnectionError(OSError):
		pass

try:
	TimeoutError
except:
	class TimeoutError(OSError):
		pass


class GUIExceptionHandler(object):
	errorName = _("Unknown Error")
	warningName = _("Unknown Warning")
	infoName = _("Unknown Info")

	def __init__(self,session, timeout=6):
		self.timeout = timeout
		self.session = session
		self.messageFormat = "[%s]\n%s"

	def infoMessage(self, text):
		showInfoMessage(self.session, self.messageFormat % (self.__class__.infoName, text), self.timeout)

	def errorMessage(self, text):
		showErrorMessage(self.session, self.messageFormat % (self.__class__.errorName, text), self.timeout)

	def warningMessage(self, text):
		showWarningMessage(self.session, self.messageFormat % (self.__class__.warningName, text), self.timeout)

	def errorMessageAskReport(self, text, **kwargs):
		def check_resp(r):
			if r:
				UsageStats.get_instance().send_bug_report(**kwargs)
				self.infoMessage(_("Bug report was send."))

		showYesNoDialog(self.session, self.messageFormat % (self.__class__.errorName, text), cb=check_resp, default=False, timeout=self.timeout, picon=MessageBox.TYPE_ERROR)

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

	def __init__(self, session, cp_or_addon=None, timeout = 6):
		GUIExceptionHandler.__init__(self, session, timeout)

		if cp_or_addon == None:
			self.addon = None
		elif isinstance(cp_or_addon, Addon):
			self.addon = cp_or_addon
		else:
			self.addon = getattr(cp_or_addon, "video_addon", None)

	def __call__(self, func):
		def wrapped(*args, **kwargs):
			try:
				try:
					func(*args, **kwargs)

				# addon specific exceptions
				except addon.AddonSilentExit as er:
					log.logInfo("Addon (AddonSilentExit) '%s'" % er.value)
				except addon.AddonInfoError as er:
					log.logError("Addon (AddonInfoError) error '%s'.\n%s"%(er.value,traceback.format_exc()))
					self.infoMessage(er.value)
				except addon.AddonWarningError as er:
					log.logError("Addon (AddonWarningError) error '%s'.\n%s"%(er.value,traceback.format_exc()))
					self.warningMessage(er.value)
				except addon.AddonError as er:
					log.logError("Addon (AddonError) error '%s'.\n%s"%(er.value,traceback.format_exc()))
					self.errorMessage(er.value)
				except TraktException as er:
					log.logError("Addon (TraktException) error '%s'.\n%s"%(str(er),traceback.format_exc()))
					self.errorMessage(str(er))

				# loading exceptions
				except HTTPError as e:
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
				except requests.HTTPError as e:
					log.logError("Addon (HTTPError) error '%s'.\n%s"%(e.response.status_code,traceback.format_exc()))
					message = "%s: %s %d" % (_("Error in loading"), _("HTTP Error"), e.response.status_code)
					self.errorMessage(message)
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
				except requests.exceptions.SSLError as e:
					log.logError("Addon (SSLError) error '%s'.\n%s"%(str(e),traceback.format_exc()))
					message = "%s: %s" % (_("Error in loading"), _("Unable to establish SSL connection to server"))
					self.errorMessage(message)
				except requests.RequestException as e:
					log.logError("Addon (RequestException) error '%s'.\n%s"%(str(e),traceback.format_exc()))
					message = "%s: %s\n%s" % (_("Error in loading"), _("Connection to server failed"), str(e))
					self.errorMessage(message)
				except ConnectionError as e:
					log.logError("Addon (ConnectionError) error '%s'.\n%s"%(str(e),traceback.format_exc()))
					message = "%s: %s\n%s" % (_("Error in loading"), _("Connection to server failed"), str(e))
					self.errorMessage(message)
				except TimeoutError as e:
					log.logError("Addon (TimeoutError) error '%s'.\n%s"%(str(e),traceback.format_exc()))
					message = "%s: %s\n%s" % (_("Error in loading"), _("Timeout was exceeded"), str(e))
					self.errorMessage(message)
				except OSError as e:
					log.logError("Addon (OSError) error.\n%s"%traceback.format_exc())
					self.errorMessage(_("System error occured") + ':\n' + str(e))

				# we handle all possible exceptions since we dont want plugin to crash because of addon error...
				except Exception as e:
					if isinstance(e, ValueError) and str(e) == 'filedescriptor out of range in select()':
						log.logError("Addon error.\n%s"%traceback.format_exc())
						self.errorMessage(_("You reached the limit of concurrent connections to remote server. Restart your receiver to solve the problem."))
					else:
						if self.addon:
							UsageStats.get_instance().addon_exception(self.addon)

						log.logError("Unhandled exception in addon %s\n%s" % (self.addon.id if self.addon else "unknown", traceback.format_exc()))

						if config.plugins.archivCZSK.bugReports.value and config.plugins.archivCZSK.archivAutoUpdate.value and (not self.addon or self.addon.bugreport_allowed()):
							self.errorMessageAskReport(_("An unhandled error occurred while calling the addon. Should I send bug report to addon authors?\nReport will contain part of log file, informations about your system and addon settings needed for problem analysis."), addon=self.addon)
						elif (self.addon and self.addon.need_update()):
							self.errorMessage(_("An unhandled error occurred while calling the addon. Update addon to the latest available version."))
						elif not config.plugins.archivCZSK.archivAutoUpdate.value:
							self.errorMessage(_("An unhandled error occurred while calling the addon. Enable addons update in plugin settings to get the latest addon version."))
						else:
							self.errorMessage(_("An unhandled error occurred while calling the addon. Please report a bug so it can be fixed."))
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

