import mimetypes
import os.path
import re
import stat
import sys
import socket
import struct
import traceback

from enigma import eConsoleAppContainer

try:
	from urllib2 import urlopen, HTTPError, URLError
	from urllib2 import Request as url_Request
	from urlparse import urlparse
	from urllib import unquote_plus
	from httplib import HTTPConnection, HTTPSConnection
	from htmlentitydefs import name2codepoint as n2cp
	from itertools import izip_longest as zip_longest
except:
	from urllib.request import urlopen
	from urllib.request import Request as url_Request
	from urllib.parse import urlparse, unquote_plus
	from urllib.error import HTTPError, URLError
	from http.client import HTTPConnection, HTTPSConnection
	from html.entities import name2codepoint as n2cp
	from itertools import zip_longest

from xml.etree.cElementTree import ElementTree, fromstring
from ...py3compat import *

from twisted.internet import reactor
from twisted.web.client import Agent, BrowserLikeRedirectAgent, readBody
from twisted.web.http_headers import Headers

try:
	FileExistsError

	def check_EEXIST(e):
		return True
except:
	# py2 workaround
	import errno
	FileExistsError = OSError

	def check_EEXIST(e):
		return e.errno == errno.EEXIST

try:
	from ... import log, removeDiac
except ImportError:
	from .logger import log

supported_video_extensions = ('.avi', '.mp4', '.mkv', '.mpeg', '.mpg')

def is_hls_url(url):
	return url.startswith('http') and urlparse(url).path.endswith('.m3u8')

def load_xml_string(xml_string):
	try:
		root = fromstring(xml_string)
	except Exception as er:
		print("cannot parse xml string %s" % str(er))
		raise
	else:
		return root


def load_xml(xml_file):
	xml = None
	try:
		xml = open(xml_file, "r+")

	# trying to set encoding utf-8 in xml file with not defined encoding
		if 'encoding' not in xml.readline():
			xml.seek(0)
			xml_string = xml.read()
			xml_string = py2_decode_utf8(xml_string)
			xml.seek(0)
			xml.write('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n')
			xml.write(py2_encode_utf8(xml_string))
			xml.flush()
	except IOError as e:
		print("I/O error(%d): %s" % (e.errno, e.strerror))
	finally:
		if xml:xml.close()


	el = ElementTree()
	try:
		el.parse(xml_file)
	except IOError as e:
		print("cannot load %s file I/O error(%d): %s" % (xml_file, e.errno, e.strerror))
		raise
	else:
		return el

# source from xbmc_doplnky
def decode_html(data):
	try:
		if is_py3 == False and not isinstance(data, unicode):
			data = unicode(data, 'utf-8', errors='ignore')
		entity_re = re.compile(r'&(#?)(x?)(\w+);')
		return entity_re.subn(_substitute_entity, data)[0]
	except:
		traceback.print_exc()
		return data

def decode_string(string):
	if is_py3 or isinstance(string, unicode):
		return string
	encodings = ['utf-8', 'windows-1250', 'iso-8859-2']
	for encoding in encodings:
		try:
			return string.decode(encoding)
		except Exception:
			if encoding == encodings[-1]:
				return u'cannot_decode'
			else:
				continue

def toUnicode(text):
	if text == None:
		return None

	if is_py3:
		if isinstance(text, bytes):
			return text.decode('utf-8')
		elif isinstance(text, str):
			return text
		else:
			return str(text)
	else:
		if isinstance(text, basestring):
			if isinstance(text, unicode):
				return text
			elif isinstance(text, str):
				return unicode(text, 'utf-8', 'ignore')
		return unicode(str(text), 'utf-8', 'ignore')

def toString(text):
	if text is None:
		return None
	if is_py3:
		if isinstance(text, bytes):
			return text.decode('utf-8')
		elif isinstance(text, str):
			return text
	else:
		if isinstance(text, basestring):
			if isinstance(text, unicode):
				return text.encode('utf-8')
			return text

	return str(text)

def check_version(local, remote, compare_postfix=True):
	'''
	Returns True if local version is lower then remote = update is needed
	Supports tilde (~) at the end of the version string (eg. 1.2.3~4).
	Version with ~ is beta one, so it's value is always considered lower then version without ~
	Examples:
	1.2.3 < 1.2.4
	1.2 < 1.2.1
	1.2 == 1.2.0
	1.2.1 > 1.2
	1.2.3~4 < 1.2.3
	1.2.3~4 > 1.2.4~3
	'''

	# extract postfix from version string
	if '~' in local:
		local, postfix_local = local.split('~')
	else:
		postfix_local = None

	if '~' in remote:
		remote, postfix_remote = remote.split('~')
	else:
		postfix_remote = None

	# split versions by dots, convert to int and compare each other
	local = [int(i) for i in local.split('.')]
	remote = [int(i) for i in remote.split('.')]

	for l, r in zip_longest(local, remote, fillvalue=0):
		if l == r:
			continue
		else:
			return l < r

	# versions are the same, so check for postfix (after ~)
	if compare_postfix:
		if postfix_remote is not None and postfix_local is not None:
			return int(postfix_local) < int(postfix_remote)
		elif postfix_local is not None:
			# local has postfix, so version is lower then remote without postfix
			return True

	# remote has postfix or no versions have them, so locale version is not lower then remote
	return False


def make_path(p):
	'''Makes sure directory components of p exist.'''
	try:
		os.makedirs(p)
	except FileExistsError as e:
		if check_EEXIST(e):
			pass
	try:
		os.makedirs(p)
	except OSError:
		pass

def download_to_file(remote, local, mode='wb', debugfnc=None, timeout=10, headers={}):
	f, localFile = None, None
	try:
		if debugfnc:
			debugfnc("downloading %s to %s", remote, local)
		else:
			print("downloading %s to %s", (remote, local))

		req = url_Request(remote, headers=headers)

		try:
			import ssl
			context = ssl.SSLContext(ssl.PROTOCOL_TLSv1)
			f = urlopen(req, context = context, timeout=timeout)
		except Exception:
			f = urlopen(req, timeout = timeout)
		make_path(os.path.dirname(local))
		localFile = open(local, mode)
		localFile.write(f.read())
	except HTTPError as e:
		if debugfnc:
			debugfnc("HTTP Error: %s %s", e.code, remote)
		else:
			print("HTTP Error: %s %s" % (e.code, remote))
		raise
	except URLError as e:
		if debugfnc:
			debugfnc("URL Error: %s %s", e.reason, remote)
		else:
			print("URL Error: %s %s" % (e.reason, remote))
		raise
	except IOError as e:
		if debugfnc:
			debugfnc("I/O error(%d): %s", (e.errno, e.strerror))
		else:
			print("I/O error(%d): %s" % (e.errno, e.strerror))
		raise
	else:
		if debugfnc:
			debugfnc('%s succesfully downloaded', local)
		else:
			print('%s succesfully downloaded' % local)
	finally:
		if f:f.close()
		if localFile:localFile.close()
	print("download finished")

def download_web_file(remote, local, mode='wb', debugfnc=None, headers={}):
	f, localFile = None, None
	try:
		if debugfnc:
			debugfnc("downloading %s to %s", remote, local)
		else:
			print("downloading %s to %s", (remote, local))
		req = url_Request(remote, headers=headers)
		from ...settings import USER_AGENT
		req.add_header('User-Agent', USER_AGENT)
		f = urlopen(req)
		make_path(os.path.dirname(local))
		localFile = open(local, mode)
		localFile.write(f.read())
	except HTTPError as e:
		if debugfnc:
			debugfnc("HTTP Error: %s %s", e.code, remote)
		else:
			print("HTTP Error: %s %s" % (e.code, remote))
		raise
	except URLError as e:
		if debugfnc:
			debugfnc("URL Error: %s %s", e.reason, remote)
		else:
			print("URL Error: %s %s" % (e.reason, remote))
		raise
	except IOError as e:
		if debugfnc:
			debugfnc("I/O error(%d): %s", (e.errno, e.strerror))
		else:
			print("I/O error(%d): %s" % (e.errno, e.strerror))
		raise
	else:
		if debugfnc:
			debugfnc('%s succesfully downloaded', local)
		else:
			print(local, 'succesfully downloaded')
	finally:
		if f:f.close()
		if localFile:localFile.close()


# source from xbmc_doplnky
def _substitute_entity(match):
		ent = match.group(3)
		if match.group(1) == '#':
			# decoding by number
			if match.group(2) == '':
				# number is in decimal
				return unichr(int(ent))
			elif match.group(2) == 'x':
				# number is in hex
				return unichr(int('0x' + ent, 16))
		else:
			# they were using a name
			cp = n2cp.get(ent)
			if cp: return unichr(cp)
			else: return match.group()



def isSupportedVideo(url):
	if url.startswith('rtmp'):
		return True
	if os.path.splitext(url)[1] != '':
		if os.path.splitext(url)[1] in supported_video_extensions:
			return True
		else:
			return False
	else:
		req = url_Request(url)
		resp = urlopen(req)
		exttype = resp.info().get('Content-Type')
		resp.close()
		ext = mimetypes.guess_extension(exttype)
		if ext in supported_video_extensions:
			return True
		else:
			return False
	return True


def BtoKB(byte):
		return int(byte / float(1024))

def BtoMB(byte):
		return int(byte / float(1024 * 1024))

def BtoGB(byte):
	return int(byte / float(1024 * 1024 * 1024))

def sToHMS(self, sec):
	m, s = divmod(sec, 60)
	h, m = divmod(m, 60)
	return h, m, s

def unescapeHTML(s):
	"""
	@param s a string (of type unicode)
	"""
	assert isinstance(s, type(u''))

	result = re.sub(u'(?u)&(.+?);', htmlentity_transform, s)
	return result

def clean_html(html):
	"""Clean an HTML snippet into a readable string"""
	# Newline vs <br />
	html = html.replace('\n', ' ')
	html = re.sub('\s*<\s*br\s*/?\s*>\s*', '\n', html)
	# Strip html tags
	html = re.sub('<.*?>', '', html)
	# Replace html entities
	html = unescapeHTML(html)
	return html

def encodeFilename(s):
	"""
	@param s The name of the file (of type unicode)
	"""

	assert isinstance(s, type(u''))

	if sys.platform == 'win32' and sys.getwindowsversion()[0] >= 5:
		# Pass u'' directly to use Unicode APIs on Windows 2000 and up
		# (Detecting Windows NT 4 is tricky because 'major >= 4' would
		# match Windows 9x series as well. Besides, NT 4 is obsolete.)
		return s
	else:
		return s.encode(sys.getfilesystemencoding(), 'ignore')

def sanitize_filename(value):
	from ... import removeDiac
	tmp = removeDiac(value)
	tmp = tmp.encode('ascii', 'ignore')
	if is_py3:
		tmp = tmp.decode('ascii')
	tmp = unicode(re.sub(r'(?u)[^\w\s.-]', '', tmp).strip().lower())
	return re.sub(r'(?u)[-\s]+', '-', tmp)
	#import unicodedata
	#value = toUnicode(value)
	#value = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore')
	#value = unicode(re.sub(r'(?u)[^\w\s.-]', '', value).strip().lower())
	#value = re.sub(r'(?u)[-\s]+', '-', value)
	#return value

def htmlentity_transform(matchobj):
	"""Transforms an HTML entity to a Unicode character.

	This function receives a match object and is intended to be used with
	the re.sub() function.
	"""
	entity = matchobj.group(1)

	# Known non-numeric HTML entity
	if entity in n2cp:
		return unichr(n2cp[entity])

	# Unicode character
	mobj = re.match(u'(?u)#(x?\d+)', entity)
	if mobj is not None:
		numstr = mobj.group(1)
		if numstr.startswith(u'x'):
			base = 16
			numstr = u'0%s' % numstr
		else:
			base = 10
		return unichr(long(numstr, base))

	# Unknown entity in name, return its literal representation
	return (u'&%s;' % entity)



class Language(object):
	language_map = {
				'en':'English',
				'sk':'Slovak',
				'cz':'Czech',
				}
	@staticmethod
	def get_language_id(language_name):
		revert_langs = dict([(item[1], item[0]) for item in list(Language.language_map.items())])
		if language_name in revert_langs:
			return revert_langs[language_name]
		else:
			return None

	@staticmethod
	def get_language_name(language_id):
		if language_id in Language.language_map:
			return Language.language_map[language_id]
		else:
			return None

def get_streams_from_manifest(url, manifest_data):
	manifest_data_str = toString(manifest_data)
	for m in re.finditer(r'^#EXT-X-STREAM-INF:(?P<info>.+)\n(?P<chunk>.+)', manifest_data_str, re.MULTILINE):
		stream_info = {}
		for info in re.split(r''',(?=(?:[^'"]|'[^']*'|"[^"]*")*$)''', m.group('info')):
			key, val = info.split('=', 1)
			stream_info[key.lower()] = val

		stream_url = m.group('chunk')

		if not stream_url.startswith('http'):
			if stream_url.startswith('/'):
				# stream is relative path to base domain
				stream_url = url[:url[9:].find('/') + 9] + stream_url
			else:
				# stream is relative path to last element
				stream_url = url[:url.rfind('/') + 1] + stream_url

		stream_info['url'] = stream_url
		yield stream_info

def url_get_data_async(url, callback=None, data=None, headers=None, timeout=60):
	def handle_failure(failure):
		failure.printTraceback()
		callback(None)
	def handle_result(data):
		callback(data)

	assert data is None, "sorry data is currently not supported"
	if headers is not None:
		headers = {k:[v] for k,v in list(headers.items())}
	agent = BrowserLikeRedirectAgent(Agent(reactor, connectTimeout=timeout))
	if isinstance( url, str ):
		url = url.encode('utf-8')
	d = agent.request(b'GET', url, Headers(headers))
	d.addCallback(readBody)
	if callback is not None:
		d.addCallbacks(handle_result, handle_failure)
	return d

def url_get_data(url, data=None, headers=None, timeout=30):
	if headers is None:
		headers = {}
	request = url_Request(url, data, headers)
	try:
		response = urlopen(request, timeout=timeout)
		return response.read()
	except (URLError, HTTPError, socket.timeout):
		traceback.print_exc()

def url_get_response_headers(url, headers=None, timeout=5, max_redirects=3):
	purl = urlparse(url)
	if	headers is None:
		headers = {}
	if purl.scheme.startswith("http"):
		if purl.path:
			if purl.query:
				path = purl.path + "?" + purl.query
			else:
				path = purl.path
		else:
			path = "/"
		conn = None
		try:
			if purl.scheme == "http":
				conn = HTTPConnection(purl.netloc, timeout=timeout)
			if purl.scheme == "https":
				conn = HTTPSConnection(purl.netloc, timeout=timeout)
			if conn is not None:
				if isinstance( path, str ):
					path = path.encode('utf-8')
				conn.request(b"HEAD", path, headers=headers)
				response = conn.getresponse()
				if response.status == 200:
					return dict(response.getheaders())
				if (response.status in range(300, 309) and max_redirects):
					max_redirects -= 1
					return url_get_response_headers(
							response.getheader("Location"), headers,
							timeout, max_redirects)
		except Exception:
			traceback.print_exc()
		finally:
			conn and conn.close()

def url_get_content_length(url, headers=None, timeout=5, max_redirects=5):
	resp_headers = url_get_response_headers(url, headers, timeout, max_redirects)
	if resp_headers:
		length = resp_headers.get('content-length')
		if length: return int(length)

def url_get_file_info(url, headers=None, timeout=3):
	purl = urlparse(url)
	filename = purl.path.split('/')[-1]
	length = None
	is_hls = False
	if url.startswith('rtmp'):
		url_split = url.split()
		if len(url_split) > 1:
			for i in url_split:
				if i.find('playpath=') == 0:
					filename = urlparse(i[len('playpath='):]).path.split('/')[-1]

	elif url.startswith('http') and purl.path.endswith('.m3u8'):
		is_hls = True
		filename = purl.path.split('/')[-2]
		if not filename:
			filename = purl.path.split('/')[-1]

	elif url.startswith('http'):
		if headers is None:
			headers = {}
		resp_headers = url_get_response_headers(url, headers, timeout=timeout)
		if resp_headers:
			content_length = resp_headers.get('content-length')
			if content_length is not None:
				length = int(content_length)
			content_disposition = resp_headers.get('content-disposition')
			if content_disposition is not None:
				filename_match = re.search(r'''filename=(?:\*=UTF-8'')?['"]?([^'"]+)''', content_disposition)
				if filename_match is not None:
					filename = toString(unquote_plus(filename_match.group(1)))
			content_type = resp_headers.get('content-type')
			if content_type is not None:
				extension = mimetypes.guess_extension(content_type, False)
				if extension is not None:
					if not os.path.splitext(filename)[1]:
						filename += extension
	return {'filename':sanitize_filename(filename), 'length':length, 'is_hls': is_hls}

def download_to_file_async(url, dest, callback=None, data=None, headers=None, timeout=60):
	def got_data(data):
		if data:
			try:
				with open(dest, "wb") as f:
					f.write(data)
			except Exception as e:
				log.logError("download_to_file_async: %s"% toString(e))
				callback(None, None)
			else:
				callback(url, dest)
		else:
			callback(None, None)
	log.logDebug("download_to_file_async: %s -> %s"% (toString(url), toString(dest)))
	return url_get_data_async(url, got_data, data, headers, timeout)

def get_free_space(location):
	try:
		s = os.statvfs(location)
		return s.f_bavail * s.f_bsize
	except Exception:
		traceback.print_exc()

def check_program(program):

	def is_file(fpath):
		return os.path.isfile(fpath)

	def is_exe(fpath):
		return os.access(fpath, os.X_OK)

	def set_executable(program):
		mode = os.stat(program).st_mode
		os.chmod(program, mode | stat.S_IXUSR)

	fpath, fname = os.path.split(program)
	if fpath:
		if is_file(program):
			if not is_exe(program):
				set_executable(program)
			return program
	else:
		for path in os.environ["PATH"].split(os.pathsep):
			exe_file = os.path.join(path, program)
			if is_file(exe_file):
				if not is_exe(exe_file):
					set_executable(exe_file)
				return exe_file
	return None


def convert_png_to_8bit(png_path, pngquant_path='pngquant'):
	pngquant = check_program(pngquant_path)
	if pngquant is None:
		print('cannot decode png %s, pngquant not found' % png_path)
		return png_path

	png_path_8bit = os.path.splitext(png_path)[0] + '-fs8.png'
	cmd = '%s --force 32 %s' % (pngquant, png_path)
	cmd = cmd.split()

	if os.path.isfile(png_path_8bit):
		os.remove(png_path_8bit)

	eConsoleAppContainer().execute(*cmd)
	if os.path.isfile(png_path_8bit):
		print('png %s was successfully converted' % os.path.basename(png_path))
		return png_path_8bit
	return png_path


def set_thread_name(name):
	try:
		import ctypes
		libcap = ctypes.CDLL('libcap.so.2')
		libcap.prctl(15, name.encode())
	except:
		pass


def get_ntp_timestamp():
	# simple implementation of getting timestamp from external NTP server with without dependency on non standard libraries
	t = None
	client = None

	try:
		client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
		client.settimeout(2)
		client.sendto(b'\x1b' + 47 * b'\0', ('pool.ntp.org', 123))
		data, _ = client.recvfrom(1024)

		if data:
			t = struct.unpack('!12I', data)[10]
			t -= 2208988800  # Reference time (1.1.1970)
	except:
		t = None
	finally:
		if client != None:
			client.close()

	return t

def get_http_timestamp():
	try:
		import requests
		from datetime import datetime
		import time

		resp = requests.get('http://google.com', timeout=3, allow_redirects=False)
		t = int( time.mktime(datetime.strptime(resp.headers['date'], '%a, %d %b %Y %H:%M:%S %Z').timetuple()) )
		offset = datetime.fromtimestamp(t) - datetime.utcfromtimestamp(t)
		t = t + offset.total_seconds()
	except:
		t = None

	return t
