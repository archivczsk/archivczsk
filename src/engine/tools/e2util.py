import sys, os
from enigma import getDesktop, eConsoleAppContainer, eTimer
from ...compat import eConnectCallback
from ... import log
import traceback
import json

def get_desktop_width_and_height():
	desktop_size = getDesktop(0).size()
	return (desktop_size.width(), desktop_size.height())


class PythonProcess(object):
	def __init__(self, processPath):
		self.toRead = None
		self.pPayload = None
		self.data = ""
		self.data_cached = None
		self.__stopping = False
		self.processPath = processPath
		self.appContainer = eConsoleAppContainer()
		self.stdoutAvail_conn = eConnectCallback(self.appContainer.stdoutAvail, self.dataOutCB)
		self.stderrAvail_conn = eConnectCallback(self.appContainer.stderrAvail, self.dataErrCB)
		self.appContainer_conn = eConnectCallback(self.appContainer.appClosed, self.finishedCB)

	def handleMessage(self, data):
		self.callbacks['messageCB'](data)

	def start(self, callbacks):
		self.callbacks = callbacks
		ext = os.path.splitext( self.processPath )[1]
		
		if ext in ('.py', '.pyo', '.pyc'):
			cmd = "%s %s" % ('python3' if sys.version_info[0] == 3 else "python", self.processPath)
		else:
			cmd = "%s" % self.processPath
			
		self.appContainer.execute(cmd)

	def running(self):
		return self.appContainer.running()

	def stop(self):
		def check_stopped():
			if not self.appContainer.running():
				self.stopTimer.stop()
				del self.stopTimer_conn
				del self.stopTimer
				del self.__i
				return
			if self.__i == 0:
				self.__i += 1
				self.appContainer.kill()
			elif self.__i == 1:
				self.stopTimer.stop()
				del self.stopTimer_conn
				del self.stopTimer
				raise Exception("cannot kill process")

		if self.__stopping:
			return
		self.__stopping = True
		self.__i = 0

		if self.appContainer.running():
			self.appContainer.sendCtrlC()
			self.stopTimer = eTimer()
			self.stopTimer_conn = eConnectCallback(self.stopTimer.timeout, check_stopped)
			self.stopTimer.start(2000, False)

	def write(self, data):
		if self.appContainer.running():
			dump = json.dumps(data) + '\n'
			try:
				self.appContainer.write(dump)
			# DMM image
			except TypeError:
				self.appContainer.write(dump, len(dump))

	def dataErrCB(self, data):
		data = data.decode('utf-8')
		log.error("ERROR from service:\n" + data)
		self.error = data

	def dataOutCB(self, data):
		data = data.decode('utf-8')

		if self.data_cached != None:
			# we have cached data from last run, so use it
			data = self.data_cached + data
			self.data_cached = None

		lines = data.split('\n')
		
		if len(lines[-1]) != 0:
			# last line was not terminated by new line - cache it and do not process it
			self.data_cached = lines[-1]
			del lines[-1]

		for line in lines:

			if len(line) == 0:
				# ignore empty lines
				continue
			
			try:
				message = json.loads(line)
			except:
				if 'exceptionCB' in self.callbacks:
					self.callbacks['exceptionCB'](traceback.format_exc())
				else:
					log.error("Failed to process data from service (%s):\n%s" % (line, traceback.format_exc()))
			else:
				self.handleMessage(message)

	def finishedCB(self, retval):
		self.callbacks['finishedCB'](retval)
		
