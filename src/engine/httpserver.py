# -*- coding: UTF-8 -*-
import threading
from .tools.logger import log
from Components.config import config
from ..py3compat import *
from .usage import UsageStats
import traceback
import time
from .license import ArchivCZSKLicense
from .tools.util import set_thread_name
from .bgservice import run_in_reactor

try:
	from socketserver import ThreadingMixIn
	from http.server import HTTPServer, BaseHTTPRequestHandler
except:
	from SocketServer import ThreadingMixIn
	from BaseHTTPServer import HTTPServer, BaseHTTPRequestHandler

class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
	def __init__(self, root, *args, **kwargs):
		if issubclass(ThreadedHTTPServer, object):
			super(ThreadedHTTPServer, self).__init__(*args, **kwargs)
		else:
			# ThreadingMixIn doesn't have __init__ in python2, so skip calling it
			# ThreadingMixIn.__init__(self)
			HTTPServer.__init__(self, *args, **kwargs)

		self.root = root
		self.developer_mode = ArchivCZSKLicense.get_instance().check_level(ArchivCZSKLicense.LEVEL_DEVELOPER)

	def handle_error(self, request, client_address):
		if self.developer_mode:
			tb = traceback.format_exc()
			if not tb.endswith( ('Connection reset by peer\n', 'Broken pipe\n',) ):
				log.error("Failed to process request from %s\n%s" % (client_address, tb))


class AddonHttpRequestHandler(object):

	@staticmethod
	def addonIdToEndpoint( addon_id ):
		if addon_id.startswith('plugin.video.'):
			name = addon_id[13:]
		elif addon_id.startswith('script.module.'):
			name = addon_id[14:]
		elif addon_id.startswith('tools.'):
			name = addon_id[6:]
		else:
			name = addon_id

		return name.replace('.', '-').replace('_', '-')

	def __init__(self, addon):
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
			host = request.headers.get('Host').split(':')
			server_name = host[0]
			server_port = host[1] if len(host) > 1 else request.server.server_port
			return "http://%s:%d/%s" % (server_name, server_port, self.name)

	def reply_error404(self, request):
		request.send_response(404)
		request.send_header("content-type", "text/html")
		data = "<html><head><title>archivCZSK</title></head><body><h1>Error 404: addon %s has not set any response</h1><br />The requested URL was not found on this server.</body></html>" % self.name
		return self.__to_bytes(data)

	def reply_error500(self, request):
		request.send_response(500)
		request.send_header("content-type", "text/html")
		data = "<html><head><title>archivCZSK</title></head><body><h1>Error 500: addon %s failed</h1><br />Internal server error</body></html>" % self.name
		return self.__to_bytes(data)

	def reply_redirect(self, request, redirect_url ):
		request.send_response(302)
		request.send_header("Location", redirect_url)
		request.send_header("content-type", "text/plain")
		return None

	def reply_ok(self, request, data, content_type=None, raw=False ):
		request.send_response(200)
		if content_type:
			request.send_header("content-type", content_type )

		if raw:
			return data
		else:
			return self.__to_bytes(data)

	def get_relative_path(self, request ):
		return request.path[self.prefix_len:]

	def render(self, request):
		UsageStats.get_instance().addon_http_call(self.addon)
		# if addon wants to handle requests more flexible, then it can override this function
		# function for endpoint needs to be named P_endpoint and supports only GET requests (inspired by openwebif)

		path_full = self.get_relative_path( request )
		path = path_full.split('/')[0]
		if len(path):
			func = getattr(self, "P_" + path, None)

			if callable(func):
				try:
					return self.__to_bytes((func(request, path_full[len(path)+1:])))
				except:
					log.error("Error by handling HTTP request for path %s:\n%s" % (path_full, traceback.format_exc()))
					return self.reply_error500(request)

		return self.__to_bytes(self.default_handler( request, path_full ))

	def default_handler(self, request, path_full ):
		# this is default handler, when request is not processed by named endpoint - it mostly prints error message
		request.send_response(404)
		request.send_header("content-type", "text/plain; charset=utf-8")
		data = "Error 404: addon %s has no handler for path %s\n" % (self.name, path_full)
		return self.__to_bytes(data)

	def run_in_reactor(self, fn, *args, **kwargs):
		run_in_reactor(fn, *args, **kwargs)

archivCZSKHttpServer = None

class ArchivCZSKReloadHandler(object):
	def render(self, request):
		from ..archivczsk import ArchivCZSK
		ArchivCZSK.reload_needed(True)
		request.send_response(200)
		request.send_header("content-type", "text/plain; charset=utf-8")
		return b'Reload activated\n'

class ArchivCZSKE2ReloadHandler(object):
	def render(self, request):
		from Components.PluginComponent import plugins
		from Tools.Directories import resolveFilename, SCOPE_PLUGINS
		plugins.readPluginList(resolveFilename(SCOPE_PLUGINS))
		request.send_response(200)
		request.send_header("content-type", "text/plain; charset=utf-8")

		return b'E2 reload activated\n'

class ArchivCZSKUpdateHandler(object):
	def render(self, request):
		from .updater import HeadlessUpdater
		HeadlessUpdater.get_instance().check_updates(True)
		request.send_response(200)
		request.send_header("content-type", "text/plain; charset=utf-8")

		return b'Update finished\n'


class Handler(BaseHTTPRequestHandler):
	protocol_version = 'HTTP/1.1'

	def __init__(self, *args, **kwargs):
		set_thread_name('ArchivCZSK-htcli')
		BaseHTTPRequestHandler.__init__(self, *args, **kwargs)
		self.__eoh_called = False
		self.rtime = 0

	def do_GET(self):
		request_start = time.time()
		self.__eoh_called = False
		resource = self.path.split('/')[1]

		handler = self.server.root.get(resource)
		if handler is not None:
			try:
				body = handler.render(self)
			except:
				log.error(traceback.format_exc())
				self.send_error(500)
				return

			body_len = len(body) if body else 0
			if not self.__eoh_called:
				self.send_header('Content-Length', body_len)
				self.end_headers()

				if body:
					self.wfile.write(body)
			else:
				self.write(body)
				self.wfile.write(b'0\r\n\r\n')

		else:
			self.send_error( 404 )

		if self.server.developer_mode:
			rtime = (time.time() - request_start) * 1000
			log.debug("Request %s took %dms" % (self.path, int(rtime)))

	def write(self, data):
		if not self.__eoh_called:
			self.send_header('Transfer-Encoding', 'chunked')
			self.end_headers()
			self.__eoh_called = True

		if data:
			self.wfile.write('{:X}\r\n'.format(len(data)).encode('ascii'))
			self.wfile.write(data)
			self.wfile.write(b'\r\n')
			self.wfile.flush()

	def get_header(self, name, default_value=None):
		self.headers.get(name, default_value)

	def log_request(self, *args, **kwargs):
		return

	def log_error(self, format, *args):
		log.debug('HTTP request error: ' + format, *args)

	def log_message(self, format, *args):
		return

class ArchivCZSKHttpServer(object):
	__instance = None

	@staticmethod
	def start():
		if ArchivCZSKHttpServer.__instance == None:
			log.debug("Starting HTTP server")
			ArchivCZSKHttpServer.__instance = ArchivCZSKHttpServer()
			ArchivCZSKHttpServer.__instance.start_listening()
			global archivCZSKHttpServer
			archivCZSKHttpServer = ArchivCZSKHttpServer.__instance

	@staticmethod
	def stop(stop_cbk=None):
		if ArchivCZSKHttpServer.__instance != None:
			log.debug("Stopping HTTP server")
			ArchivCZSKHttpServer.__instance.stop_listening()
			ArchivCZSKHttpServer.__instance = None
			global archivCZSKHttpServer
			archivCZSKHttpServer = None

			if stop_cbk:
				stop_cbk()

	@staticmethod
	def get_instance():
		return ArchivCZSKHttpServer.__instance

	def __init__(self):
		self.root = {}
		self.port = config.plugins.archivCZSK.httpPort.value
		self.running = None
		self.server = None
		self.root['update'] = ArchivCZSKUpdateHandler()

		if ArchivCZSKLicense.get_instance().check_level(ArchivCZSKLicense.LEVEL_DEVELOPER):
			log.info("Adding RELOAD endpoint to HTTP server")
			self.root['reload'] = ArchivCZSKReloadHandler()
			self.root['e2reload'] = ArchivCZSKE2ReloadHandler()

	def start_listening(self, only_restart=False):
		was_started = self.running != None

		if self.running:
			if only_restart:
				self.stop_listening()
			else:
				return

		self.port = config.plugins.archivCZSK.httpPort.value

		if only_restart and not was_started:
			# restart requiered, but server is not running - do nothing
			return

		if self.running == None:
			if config.plugins.archivCZSK.httpLocalhost.value:
				listen_address = '127.0.0.1'
			else:
				listen_address = '0.0.0.0'

			log.info("Starting HTTP server on %s:%s" % (listen_address, self.port))
			try:
				self.running = threading.Thread(target=self.httpd_run,args=(listen_address,))
				self.running.start()
			except:
				log.error("Failed to start internal HTTP server:\n%s" % traceback.format_exc())


	def httpd_run(self, listen_address):
		try:
			set_thread_name('ArchivCZSK-httpd')
			self.server = ThreadedHTTPServer( self.root, (listen_address, self.port), Handler)
			log.debug("HTTP Accept thread started")
		except:
			log.error("FATAL: Failed to start HTTP server\n:%s" % traceback.format_exc())
		else:
			self.server.serve_forever(2)


	def stop_listening(self):
		if self.running != None:
			if not self.server:
				log.error("FATAL: HTTP server accept thread was started, but server itself is not running")
			else:
				self.server.shutdown()
				self.server.server_close()

			self.running.join()
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
		self.root[requestHandler.name] = requestHandler

	def unregisterRequestHandler(self, requestHandler ):
		try:
			del self.root[requestHandler.name]
			log.info( "HTTP request handler for endpoint %s removed" % requestHandler.name)
		except:
			log.debug( "HTTP request handler for endpoint %s not found" % requestHandler.name)

	def getAddonByEndpoint(self, endpoint):
		handler = self.root.get(endpoint)
		return handler.addon if handler else None

	def urlToEndpoint(self, url):
		server_url = "http://127.0.0.1:%d/" % self.port

		if url.startswith(server_url):
			return url[len(server_url):].split('/')[0]

		return None

