from twisted.internet import stdio, reactor, defer, task
from twisted.protocols import basic
import json
import traceback

class AddonServiceHelper(basic.LineReceiver):
	def __init__(self):
		self.delimiter=b'\n'
		self.getSettingsCbk = {}
		self.getHttpEndpointCbk = {}
		
	def sendJson(self, data ):
		self.sendLine(json.dumps( data ).encode('utf-8'))
	
	def connectionMade(self):
		data = {'cmd': 'startup_response', 'version': 1 }
		self.sendJson(data)

	def logDebug(self, msg ):
		data = {'cmd': 'show_debug', 'msg': msg}
		self.sendJson(data)

	def logInfo(self, msg ):
		data = {'cmd': 'show_info', 'msg': msg}
		self.sendJson(data)
	
	def logError(self, msg ):
		data = {'cmd': 'show_error', 'msg': msg}
		self.sendJson(data)

	def logException(self, msg ):
		data = {'cmd': 'show_exception', 'msg': msg}
		self.sendJson(data)
		
	def lineReceived(self, data):
		try:
			data = json.loads(data)
	
			cmd = data.get('cmd')
	
			if not cmd:
				return
			
			if hasattr(self, 'handle_' + cmd):
				method = getattr(self, 'handle_' + cmd)
				cmd_data = data.get('cmd_data')
				if cmd_data:
					method(**cmd_data)
				else:
					method()
			else:
				self.logError( "Unknown command received: %s" % cmd )
		except:
			self.logException( traceback.format_exc() )
	
	def handle_settings_response(self, key, settings ):
		if key in self.getSettingsCbk:
			cbk = self.getSettingsCbk[key]['cbk']
			args = self.getSettingsCbk[key]['args']
			kwargs = self.getSettingsCbk[key]['kwargs']
			cbk( settings, *args, **kwargs )
			del self.getSettingsCbk[key]
	
	def handle_stop(self):
		reactor.stop()
	
	def connectionLost(self, reason):
		# stop the reactor, only because this is meant to be run in Stdio.
		if reactor.running:
			reactor.stop()

	def getSetting(self, name, cbk ):
		def extractSingleValue( settings ):
			cbk(name, settings[name])
		
		self.getSettings( [name], extractSingleValue )

	def setSetting(self, name, value ):
		self.setSettings( { name: value } )

	def getSettings(self, names, cbk, *args, **kwargs ):
		key = '#'.join(names)
		data = { 'cmd': 'get_settings', 'key': key, 'names': names }
		self.sendJson(data)
		self.getSettingsCbk[key] = { 'cbk': cbk, 'args': args, 'kwargs': kwargs }

	def setSettings(self, settings ):
		data = { 'cmd': 'set_settings', 'settings': settings }
		self.sendJson(data)

	def getHttpEndpoint(self, addon_id, cbk, *args, **kwargs ):
		data = { 'cmd': 'get_http_endpoint', 'addon_id': addon_id }
		self.sendJson(data)
		self.getHttpEndpointCbk[addon_id] = { 'cbk': cbk, 'args': args, 'kwargs': kwargs }

	def handle_http_endpoint_response(self, addon_id, endpoint ):
		if addon_id in self.getHttpEndpointCbk:
			cbk = self.getHttpEndpointCbk[addon_id]['cbk']
			args = self.getHttpEndpointCbk[addon_id]['args']
			kwargs = self.getHttpEndpointCbk[addon_id]['kwargs']
			cbk( addon_id, endpoint, *args, **kwargs )
			del self.getHttpEndpointCbk[addon_id]
	
	def showInfoMessage(self, msg, timeout=5):
		data = { 'cmd': 'show_info_message', 'msg': msg, 'timeout': timeout }
		self.sendJson(data)

	def showErrorMessage(self, msg, timeout=5):
		data = { 'cmd': 'show_error_message', 'msg': msg, 'timeout': timeout }
		self.sendJson(data)
	
	def runDelayed(self, delay_seconds, cbk, *args, **kwargs ):
		d = defer.Deferred()
		if callable( cbk ):
			d.addCallback(cbk)
		else:
			for x in cbk:
				d.addCallback(x)
				
		reactor.callLater(delay_seconds, d.callback, *args, **kwargs )
		return d
	
	def runLoop(self, seconds_to_loop, cbk, *args, **kwargs ):
		loop = task.LoopingCall(cbk, *args, **kwargs)
		loop.start( seconds_to_loop )
		return loop
	
	def run(self):
		reactor.run()

def StartAddonServiceHelper( helper=None, main=None, *args, **kwargs ):
	if not helper:
		helper = AddonServiceHelper()
	
	stdio.StandardIO(helper)
	
	if main:
		helper.runDelayed(1, main, *args, **kwargs)
		
	return helper
