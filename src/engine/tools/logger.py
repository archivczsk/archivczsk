# -*- coding: utf-8 -*-
import traceback
from ...py3compat import *
fileLogger = None
	
def toString(text):
	if not is_py3 and isinstance(text, unicode):
		return str(text.encode('utf-8'))
	elif isinstance(text, str):
		return text

def create_rotating_log(path):
	try:
		import logging
		from logging.handlers import RotatingFileHandler
	except Exception:
		pass
	else:
		global fileLogger
		fileLogger = logging.getLogger("archivCZSK")
		handler = RotatingFileHandler(path, maxBytes=2 * 1024 * 1024,
									backupCount=2)
		formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
		handler.setFormatter(formatter)
		fileLogger.setLevel(log.DEBUG)
		fileLogger.addHandler(handler)

class log(object):
	ERROR = 0
	INFO = 1
	DEBUG = 2
	mode = INFO

	logEnabled = True
	logToStdout = False
	logDebugEnabled = False

	@staticmethod
	def logDebug(msg, *args):
		if log.logDebugEnabled:
			log.writeLog('DEBUG', msg, *args)

	@staticmethod
	def debug(text, *args):
		log.logDebug(text, *args)

	@staticmethod
	def logInfo(msg, *args):
		log.writeLog('INFO', msg, *args)

	@staticmethod
	def info(text, *args):
		log.logInfo(text, *args)

	@staticmethod
	def logError(msg, *args):
		log.writeLog('ERROR', msg, *args)

	@staticmethod
	def error(text, *args):
		log.logError(text, *args)

	@staticmethod
	def writeLog(log_type, msg, *args):
		try:
			if len(args) == 1 and isinstance(args[0], tuple):
				msg = msg % args[0]
			elif len(args) >= 1:
				msg = msg % args
			msg = toString(msg)

		except Exception as e:
			try:
				print("#####ArchivCZSK#### - problematic message: %s" % msg)
			except:
				pass
			print("#####ArchivCZSK#### - cannot write log message: %s" % str(e))
			traceback.print_exc()
			return

		if not log.logEnabled:
			return
		if fileLogger:
			if log_type == 'INFO':
				fileLogger.info(msg)
			elif log_type == 'ERROR':
				fileLogger.error(msg)
			elif log_type == 'DEBUG':
				fileLogger.debug(msg)

		if not fileLogger or log.logToStdout:
			print("####ArchivCZSK#### ["+log_type+"] "+ msg)

	@staticmethod
	def changeMode(mode):
		log.mode = mode
		if mode == 2:
			log.logDebugEnabled = True
		else:
			log.logDebugEnabled = False

	@staticmethod
	def changePath(path):
		create_rotating_log(path + "/archivCZSK.log")
