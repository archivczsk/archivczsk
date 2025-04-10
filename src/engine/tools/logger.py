# -*- coding: utf-8 -*-
import traceback
from ...py3compat import *
from collections import deque
import logging
from logging.handlers import RotatingFileHandler
from logging import StreamHandler

class MemRingBuff(object):
	def __init__(self, maxlen=200):
		self.queue = deque(maxlen=maxlen)

	def write(self, msg):
		self.queue.append(msg)

	def flush(self):
		pass

	def dump(self):
		return ''.join(self.queue)


def toString(text):
	if not is_py3 and isinstance(text, unicode):
		return str(text.encode('utf-8'))
	elif isinstance(text, str):
		return text


class log(object):
	__file_handler = None
	__mem_handler = None
	__file_instance = None
	__mem_instance = None
	mem_ringbuff = None

	@staticmethod
	def start(path):
		log.__file_instance = logging.getLogger("archivCZSK")
		log.__mem_instance = logging.getLogger("archivCZSK-mem")
		log.mem_ringbuff = MemRingBuff(200)
		formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

		log.__file_handler = RotatingFileHandler(path, maxBytes=2 * 1024 * 1024, backupCount=2)
		log.__file_handler.setFormatter(formatter)
		log.__file_instance.setLevel(log.DEBUG)
		log.__file_instance.addHandler(log.__file_handler)

		log.__mem_handler = StreamHandler(stream=log.mem_ringbuff)
		log.__mem_handler.setFormatter(formatter)
		log.__mem_instance.setLevel(log.DEBUG)
		log.__mem_instance.addHandler(log.__mem_handler)

	@staticmethod
	def stop():
		if log.__file_instance != None and log.__file_handler != None:
			log.__file_instance.removeHandler(log.__file_handler)
			log.__file_handler = None

		if log.__mem_instance != None and log.__mem_handler != None:
			log.__mem_instance.removeHandler(log.__mem_handler)
			log.__mem_handler = None


	ERROR = 0
	INFO = 1
	DEBUG = 2

	LOG_LEVEL_MAPPING = {
		ERROR: 'ERROR',
		INFO: 'INFO',
		DEBUG: 'DEBUG',
	}

	mode = INFO

	logEnabled = True
	logToStdout = False
	logDebugEnabled = False

	@staticmethod
	def logDebug(msg, *args):
		log.writeLog(log.DEBUG, msg, *args)

	@staticmethod
	def debug(text, *args):
		log.logDebug(text, *args)

	@staticmethod
	def logInfo(msg, *args):
		log.writeLog(log.INFO, msg, *args)

	@staticmethod
	def info(text, *args):
		log.logInfo(text, *args)

	@staticmethod
	def logError(msg, *args):
		log.writeLog(log.ERROR, msg, *args)

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

		if log.__file_instance:
			if log_type == log.INFO:
				log.__file_instance.info(msg)
			elif log_type == log.ERROR:
				log.__file_instance.error(msg)
			elif log_type == log.DEBUG:
				if log.logDebugEnabled:
					log.__file_instance.debug(msg)

		if log.__mem_instance:
			if log_type == log.INFO:
				log.__mem_instance.info(msg)
			elif log_type == log.ERROR:
				log.__mem_instance.error(msg)
			elif log_type == log.DEBUG:
				log.__mem_instance.debug(msg)

		if log.__file_instance == None or log.logToStdout:
			print("####ArchivCZSK#### [{}] {}".format(log.LOG_LEVEL_MAPPING.get(log_type, "?"), msg))

	@staticmethod
	def changeMode(mode):
		log.mode = mode
		if mode == 2:
			log.logDebugEnabled = True
		else:
			log.logDebugEnabled = False

	@staticmethod
	def changePath(path):
		import os
		log.start(os.path.join(path, "archivCZSK.log"))

	@staticmethod
	def dump_ringbuff():
		if log.mem_ringbuff:
			return log.mem_ringbuff.dump()
		else:
			return ''
