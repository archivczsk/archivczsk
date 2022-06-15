import os
from twisted.internet.defer import Deferred

from Plugins.Extensions.archivCZSK import settings
from Plugins.Extensions.archivCZSK import log
from Plugins.Extensions.archivCZSK.engine.tools.e2util import PythonProcess

class AddonService(PythonProcess):
	def __init__(self, info ):
		if not info.service_lib:
			self.initialized = False
			self.available = False
			return
		
		script_path = os.path.join(info.path, info.service_lib)
		
		PythonProcess.__init__(self, script_path)

		self.name = "%s:%s" % (info.name,  os.path.splitext(info.service_lib)[0])
		self.version = ""
		self.initialized = False
		self.available = None
		log.info("Service %s initialised" % self)

	def __repr__(self):
		return self.name
		
	def init(self):
		if self.available == False:
			return
		
		if self.initialized:
			d = Deferred()
			d.callback(True)
			return d

		callbacks = {}
		callbacks['messageCB'] = self.messageReceived
		callbacks['finishedCB'] = self.processExited
		self.start(callbacks)

		self.d = Deferred()
		return self.d

	def stop(self, ):
		log.info("Sending stop command to service %s" % self)

		if not self.initialized:
			log.info("Service %s not initialized...")
			d = Deferred()
			d.callback(None)
			return d
		
		self.write({'request': 'stop'})

		self.d = Deferred()
		return self.d

	def messageReceived(self, response):
		log.debug("%s - gotResponse: %s" % (self, response) )
		
		if response['type'] == 'info':
			if response['status']:
				self.initialized = True
				self.available = True
				self.version = response.get('version','')
				log.info("Service %s initialised" % self)
				self.d.callback(True)
			else:
				log.info("Service %s: failed to initialize: %s" % (self, response.get('exception'), 'unknown exception' ))
				self.available = False
				self.d.callback(False)

	def getVersion(self):
		return self.version

	def isInitialized(self):
		return self.initialized

	def isAvailable(self):
		return self.available

	def processExited(self, retval):
		log.info("Service %s exited with return code %d" % (self, retval))
