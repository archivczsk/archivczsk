import os

from Plugins.Extensions.archivCZSK import settings
from Plugins.Extensions.archivCZSK import log
from Plugins.Extensions.archivCZSK.engine.tools.e2util import PythonProcess
from Screens.MessageBox import MessageBox
from ..py3compat import *

class AddonService(PythonProcess):
	def __init__(self, addon ):
		self.available = None
		self.initialized = False
		self.version = None
		self.addon = addon

		if not addon.info.service_lib:
			self.name = "%s:dummy" % addon.info.name
			self.available = False
			return
		
		script_path = os.path.join(addon.info.path, addon.info.service_lib)
		
		PythonProcess.__init__(self, script_path)

		self.name = "%s:%s" % (addon.info.name, os.path.splitext(addon.info.service_lib)[0])
		log.info("Service %s initialised" % self)

	def __repr__(self):
		return self.name
		
	def init(self):
		if self.available == False:
			return
		
		if not self.initialized:
			callbacks = {}
			callbacks['messageCB'] = self.messageReceived
			callbacks['finishedCB'] = self.processExited
			callbacks['exceptionCB'] = self.processException
			self.start(callbacks)

	def stop(self, ):
		if self.available == False:
			return

		log.info("Sending stop command to service %s" % self)

		if not self.initialized:
			log.info("Service %s not initialized...")
		else:
			self.write({'cmd': 'stop'})

	def sendCommand(self, cmd, **kwargs ):
		if self.initialized:
			self.write({'cmd': cmd, 'cmd_data': kwargs })
		
	def messageReceived(self, data):
#		log.debug("%s - got data: %s" % (self, data) )
		
		if data['cmd'] == 'startup_response':
			self.version = data['version']
			self.initialized = True
			self.available = True
			log.info("Service %s successfuly started" % self)
		elif data['cmd'] == 'show_exception':
			log.error("Service[%s]: EXCEPTION: %s" % (self, data.get('msg', 'unknown exception') ))
		elif data['cmd'] == 'show_error':
			log.error("Service[%s] %s" % (self, data.get('msg') ))
		elif data['cmd'] == 'show_info':
			log.info("Service[%s]: %s" % (self, data.get('msg') ))
		elif data['cmd'] == 'show_debug':
			log.debug("Service[%s]: %s" % (self, data.get('msg') ))
		elif data['cmd'] == 'get_settings':
			settings = {}
			for name in data['names']:
				settings[name] = self.addon.settings.get_setting( name )
			
			self.write( {'cmd': 'settings_response', 'cmd_data': { 'key': data['key'], 'settings': settings } } )
			
		elif data['cmd'] == 'set_settings':
			settings = {}
			for k,v in data['settings'].items():
				self.addon.settings.set_setting( k, v )
		elif data['cmd'] == 'get_http_endpoint':
			from Plugins.Extensions.archivCZSK.engine.httpserver import archivCZSKHttpServer
			self.write( {'cmd': 'http_endpoint_response', 'cmd_data': { 'addon_id': data['addon_id'], 'endpoint': archivCZSKHttpServer.getAddonEndpoint( data['addon_id'] ) } } )
		elif data['cmd'] == 'show_info_message':
			from Plugins.Extensions.archivCZSK.gsession import GlobalSession
			GlobalSession.getSession().open(MessageBox, py2_encode_utf8(data['msg']), MessageBox.TYPE_INFO, timeout=data.get('timeout', 5))
		elif data['cmd'] == 'show_error_message':
			from Plugins.Extensions.archivCZSK.gsession import GlobalSession
			GlobalSession.getSession().open(MessageBox, py2_encode_utf8(data['msg']), MessageBox.TYPE_ERROR, timeout=data.get('timeout', 5))
	
	def getVersion(self):
		return self.version

	def isInitialized(self):
		return self.initialized

	def isAvailable(self):
		return self.available

	def processExited(self, retval):
		log.info("Service[%s] exited with return code %d" % (self, retval))
		self.initialized = False
		self.available = None
		
	def processException(self, tb):
		log.error("Service[%s]: exception by processing data\n%s" % (self, tb))
#		PythonProcess.stop(self)
