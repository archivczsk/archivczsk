# -*- coding: UTF-8 -*-
from twisted.internet import reactor
from twisted.web import server, http, resource
from .. import log
from Components.config import config
from ..py3compat import *
from .usage import usage_stats
import traceback

class AddonHttpRequestHandler(resource.Resource):
	isLeaf = True

	@staticmethod
	def addonIdToEndpoint( addon_id ):
		if addon_id.startswith('plugin.video.'):
			name = addon_id[13:]
		elif addon_id.startswith('script.module.'):
			name = addon_id[14:]
		
		return name.replace('.', '-').replace('_', '-')
	
	def __init__(self, addon):
		self.NOT_DONE_YET = server.NOT_DONE_YET
		self.name = AddonHttpRequestHandler.addonIdToEndpoint(addon.id)
		self.addon = addon
		self.prefix_len = len(self.name)+2

	def __to_bytes(self, data):
		if isinstance(data, unicode):
			return data.encode('utf-8')

		return data

	def get_endpoint(self, request, relative=False):
		if relative:
			return "/%s" % self.name
		else:
			server_name = request.getRequestHostname()
			server_port = request.getHost().port
			return "http://%s:%d/%s" % (server_name, server_port, self.name)

	def reply_error404(self, request):
		request.setHeader("content-type", "text/html")
		request.setResponseCode(http.NOT_FOUND)
		data = "<html><head><title>archivCZSK</title></head><body><h1>Error 404: addon %s has not set any response</h1><br />The requested URL was not found on this server.</body></html>" % self.name
		return self.__to_bytes(data)

	def reply_error500(self, request):
		request.setHeader("content-type", "text/html")
		request.setResponseCode(http.INTERNAL_SERVER_ERROR)
		data = "<html><head><title>archivCZSK</title></head><body><h1>Error 500: addon %s failed</h1><br />Internal server error</body></html>" % self.name
		return self.__to_bytes(data)

	def reply_redirect(self, request, redirect_url ):
		request.redirect( self.__to_bytes(redirect_url) )
		request.setHeader("content-type", "text/plain")
		request.finish()
		return server.NOT_DONE_YET

	def reply_ok(self, request, data, content_type=None, raw=False ):
		if content_type:
			request.setHeader("content-type", content_type )
			
		request.setResponseCode(http.OK)
		if raw:
			return data
		else:
			return self.__to_bytes(data)
	
	def get_relative_path(self, request ):
		return request.path.decode('utf-8')[self.prefix_len:]
		
	def render(self, request):
		usage_stats.addon_http_call(self.addon)
		# if addon wants to handle requests more flexible, then it can override this function
		
		# function for endpoint needs to be named P_endpoint and supports only GET requests (inspired by openwebif)
		
		# info about request API
		# https://twistedmatrix.com/documents/21.2.0/api/twisted.web.http.Request.html
		
		path_full = self.get_relative_path( request )
		path = path_full.split('/')[0]
		if len(path) > 0 and request.method == b'GET':
			func = getattr(self, "P_" + path, None)
			
			if callable(func):
				return self.__to_bytes((func(request, path_full[len(path)+1:])))
		
		return self.__to_bytes(self.default_handler( request, path_full ))
	
	def default_handler(self, request, path_full ):
		# this is default handler, when request is not processed by named endpoint - it mostly prints error message 
		request.setHeader("content-type", "text/plain; charset=utf-8")
		request.setResponseCode(http.NOT_FOUND)
		data = "Error 404: addon %s has no handler for path %s" % (self.name, path_full)
		return self.__to_bytes(data)


class ArchivCZSKHttpServer:
	def __init__(self):
		self.root = resource.Resource()
		self.site = server.Site(self.root)
		self.site.displayTracebacks = True
		self.port = config.plugins.archivCZSK.httpPort.value
		self.running = None
	
	def start_listening(self, only_restart=False):
		def continue_cbk(*args):
			self.port = config.plugins.archivCZSK.httpPort.value

			if only_restart and not was_started:
				# restart requiered, but server is not running - do nothing
				return

			if self.running == None:
				if config.plugins.archivCZSK.httpLocalhost.value:
					listen_address = '127.0.0.1'
				else:
					listen_address = '0.0.0.0'

				try:
					self.running = reactor.listenTCP(self.port, self.site, interface=listen_address)
				except:
					log.error("Failed to start internal HTTP server:\n%s" % traceback.format_exc())

		was_started = self.running != None
		
		if self.running == None:
			continue_cbk()
		elif only_restart:
			self.stop_listening(continue_cbk)

	def stop_listening(self, cbk=None):
		if self.running != None:
			defer = self.running.stopListening()
			self.running = None
			if cbk:
				defer.addBoth(cbk)
		elif cbk:
			cbk()
		
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
		
	def getAddonByEndpoint(self, endpoint):
		handler = self.root.getStaticEntity(endpoint)
		return handler.addon if handler else None

	def urlToEndpoint(self, url):
		server_url = "http://127.0.0.1:%d/" % self.port

		if url.startswith(server_url):
			return url[len(server_url):].split('/')[0]

		return None


archivCZSKHttpServer = ArchivCZSKHttpServer()
