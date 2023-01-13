# -*- coding: UTF-8 -*-
from twisted.internet import reactor
from twisted.web import server, http, resource
from twisted.internet import defer
from Plugins.Extensions.archivCZSK import _, log
from Components.config import config

class AddonHttpRequestHandler(resource.Resource):
	isLeaf = True

	@staticmethod
	def addonIdToEndpoint( addon_id ):
		if addon_id.startswith('plugin.video.'):
			name = addon_id[13:]
		elif addon_id.startswith('script.module.'):
			name = addon_id[14:]
		
		return name.replace('.', '-')
	
	def __init__(self, addon_id):
		self.NOT_DONE_YET = server.NOT_DONE_YET
		self.name = AddonHttpRequestHandler.addonIdToEndpoint(addon_id)
		self.prefix_len = len(self.name)+2
	
	def reply_error404(self, request):
		request.setHeader("content-type", "text/html")
		request.setResponseCode(http.NOT_FOUND)
		data = "<html><head><title>archivCZSK</title></head><body><h1>Error 404: addon %s has not set any response</h1><br />The requested URL was not found on this server.</body></html>" % self.name
		return data.encode('utf-8')

	def reply_error500(self, request):
		request.setHeader("content-type", "text/html")
		request.setResponseCode(http.INTERNAL_SERVER_ERROR)
		data = "<html><head><title>archivCZSK</title></head><body><h1>Error 500: addon %s failed</h1><br />Internal server error</body></html>" % self.name
		return data.encode('utf-8')

	def reply_redirect(self, request, redirect_url ):
		request.redirect( redirect_url )
		request.setHeader("content-type", "text/plain")
		request.finish()
		return server.NOT_DONE_YET

	def reply_ok(self, request, data, content_type=None ):
		if content_type:
			request.setHeader("content-type", content_type )
			
		request.setResponseCode(http.OK)
		return data
	
	def get_relative_path(self, request ):
		return request.path[self.prefix_len:]
		
	def render(self, request):
		# if addon wants to handle requests more flexible, then it can override this function
		
		# function for endpoint needs to be named P_endpoint and supports only GET requests (inspired by openwebif)
		
		# info about request API
		# https://twistedmatrix.com/documents/21.2.0/api/twisted.web.http.Request.html
		
		path_full = self.get_relative_path( request )
		path = path_full.split(b'/')[0]
		if len(path) > 0 and request.method == b'GET':
			func = getattr(self, "P_" + path.decode('utf-8'), None)
			
			if callable(func):
				return func(request, path_full[len(path)+1:])
		
		return self.default_handler( request, path_full )
	
	def default_handler(self, request, path_full ):
		# this is default handler, when request is not processed by named endpoint - it mostly prints error message 
		request.setHeader("content-type", "text/plain; charset=utf-8")
		request.setResponseCode(http.NOT_FOUND)
		data = "Error 404: addon %s has no handler for path %s" % (self.name, path_full)
		return data.encode('utf-8')


class ArchivCZSKHttpServer:
	def __init__(self):
		self.root = resource.Resource()
		self.site = server.Site(self.root)
		self.site.displayTracebacks = True
		self.port = config.plugins.archivCZSK.httpPort.value
		self.running = None
	
	def start_listening(self, only_restart=False):
		if only_restart:
			if self.running:
				self.stop_listening()
			else:
				self.port = config.plugins.archivCZSK.httpPort.value
				# restart requiered, but server is not running - no nothing
				return
			
		if not self.running:
			# server not running - start it
			self.port = config.plugins.archivCZSK.httpPort.value
			if config.plugins.archivCZSK.httpLocalhost.value:
				listen_address = '127.0.0.1'
			else:
				listen_address = '0.0.0.0'
			self.running = reactor.listenTCP(self.port, self.site, interface=listen_address)

	def stop_listening(self):
		if self.running:
			self.running.stopListening()
			self.running = None
		
	def getAddonEndpoint(self, handler_or_id, base_url=None, relative=False):
		if isinstance( handler_or_id, AddonHttpRequestHandler ):
			endpoint = handler_or_id.name
		else:
			endpoint = AddonHttpRequestHandler.addonIdToEndpoint(handler_or_id)

		if relative:
			return "/%s" % endpoint
		else:
			if not base_url:
				base_url = '127.0.0.1'

			return "http://%s:%d/%s" % (base_url, self.port, endpoint)
	
	def registerRequestHandler(self, requestHandler ):
		self.start_listening()
		log.logInfo( "Adding HTTP request handler for endpoint: %s" % requestHandler.name)
		self.root.putChild(requestHandler.name.encode('utf-8'), requestHandler)


archivCZSKHttpServer = None	

if archivCZSKHttpServer == None:
	archivCZSKHttpServer = ArchivCZSKHttpServer()
