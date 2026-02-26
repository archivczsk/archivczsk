import os, traceback
import shutil
import random
import time
from datetime import datetime
from base64 import b64encode
from hashlib import md5
import json
from functools import partial

from ..engine.tools import util
from ..engine.tools.logger import log
from ..compat import eCompatPicLoad, eCompatTimer
from ..settings import USER_AGENT, PLUGIN_PATH

from twisted.internet import reactor
import requests

from Components.AVSwitch import AVSwitch
from Tools.LoadPixmap import LoadPixmap

from enigma import gPixmapPtr
from Components.config import config


class PosterProcessing(object):
	__instance = None

	@staticmethod
	def get_instance():
		if PosterProcessing.__instance == None:
			PosterProcessing.__instance = PosterProcessing()

		return PosterProcessing.__instance

	@staticmethod
	def stop():
		if PosterProcessing.__instance != None:
			PosterProcessing.__instance.cleanup_poster_dir(True)

		PosterProcessing.__instance = None

	def __init__(self):
		self.poster_limit = int(config.plugins.archivCZSK.posterImageMax.value)
		self.poster_dir = os.path.join(config.plugins.archivCZSK.posterPath.value,'archivczsk_poster')
		self.poster_max_size = int(config.plugins.archivCZSK.posterSizeMax.value) * 1024
		self.poster_files = []
		self.poster_cache = {}
		self.idx = 0
		self._init_poster_dir()

	def _init_poster_dir(self):
		if not os.path.isdir(self.poster_dir):
			try:
				os.makedirs(self.poster_dir)
			except Exception:
				pass
		self.cleanup_poster_dir()

	def cleanup_poster_dir(self, full_clean=False):
		for filename in os.listdir(self.poster_dir):
			file_path = os.path.join(self.poster_dir, filename)
			try:
				if os.path.isfile(file_path) or os.path.islink(file_path):
					os.unlink(file_path)
				elif os.path.isdir(file_path):
					shutil.rmtree(file_path)
			except Exception as e:
				log.error('Failed to delete %s. Reason: %s' % (file_path, e))

		if full_clean:
			try:
				os.rmdir(self.poster_dir)
			except:
				pass

	def _remove_oldest_poster_file(self):
		url, path = self.poster_files.pop(0)
		if url in self.poster_cache:
			del self.poster_cache[url]

#		log.debug("PosterProcessing._remove_oldest_poster_file: {0}".format(path))
		try:
			os.unlink(path)
		except Exception as e:
			log.error("PosterProcessing._remove_oldest_poster_file: {0}".format(str(e)))

	def _create_poster_path(self):
		dt = datetime.now()
		filename = "{:03d}_{}".format(self.idx, datetime.strftime(dt, "%y_%m_%d__%H_%M_%S"))
		self.idx += 1
		if self.idx >= 1000:
			self.idx = 0
		dest = os.path.join(self.poster_dir, filename)
		return dest

	def _check_file_size_limit(self, path):
		if os.path.isfile(path):
			file_size = os.stat(path).st_size
			if self.poster_max_size > 0 and file_size > self.poster_max_size:
				log.debug("PosterProcessing.image over maximum size allowed for processing: {0}".format(path))
				# truncate file to 0, because it is out of limit and can not be processed,
				# but we need to keep it in order not to download it again
				with open(path, 'w') as f:
					f.truncate()

				file_size = 0

			if file_size == 0:
				return None
			else:
				return path
		else:
			return None

	def _image_downloaded(self, url, path, got_image_callback):
		if path is None:
			return

		if len(self.poster_files) == self.poster_limit:
#			log.debug("PosterProcessing._image_downloaded: download limit reached({0})".format(self.poster_limit))
			self._remove_oldest_poster_file()

		log.debug("PosterProcessing._image_downloaded: {0}".format(path))
		if url not in self.poster_cache:
			self.poster_files.append((url, path))
			self.poster_cache[url] = path

		if self._check_file_size_limit(path) != None:
			got_image_callback(url, path)

	def get_image_file(self, poster_url, use_cache, got_image_callback):
		if os.path.isfile(poster_url):
			log.debug("PosterProcessing.get_image_file: found poster path (local)")
			return got_image_callback(poster_url, poster_url)

		path = self.poster_cache.get(poster_url)

		if path and use_cache:
			log.debug("PosterProcessing.get_image_file: poster found in cache: {}".format(path))
			return got_image_callback(poster_url, self._check_file_size_limit(path))

		reactor.callInThread(self.download_in_thread, util.toString(poster_url), path or self._create_poster_path(), partial(self._image_downloaded, got_image_callback=got_image_callback) )

	def download_in_thread(self, url, dest, callback):
		headers = {"User-Agent": USER_AGENT }
		dest = os.path.splitext(dest)[0]

		try:
			response = requests.get(url, headers=headers, verify=False, timeout=10)
			response.raise_for_status()
		except Exception as e:
			log.error(str(e))
			return reactor.callFromThread(callback, None, None)

		content_type = response.headers.get('content-type')
		data = response.content

		if content_type == 'image/webp':
			# convert to jpeg
			dest += '.jpg'
			if self.convert_to_jpeg('webp', data, dest):
				return reactor.callFromThread(callback, url, dest)
			else:
				# conversion failed
				data = None

		elif content_type == 'image/png':
			dest += '.png'
		elif content_type == 'image/jpeg':
			dest += '.jpg'
		elif content_type == 'image/gif':
			dest += '.gif'
		elif content_type == 'image/bmp':
			dest += '.bmp'
		elif content_type == None:
			# unknown type - save as jpeg and hope, that decoding will success
			dest += '.jpg'
		else:
			# unsupported content type
			log.error("Unsupported image content type: %s" % content_type)
			return reactor.callFromThread(callback, None, None)

		with open(dest, 'wb') as f:
			if data:
				f.write(data)

		return reactor.callFromThread(callback, url, dest)

	def convert_to_jpeg(self, data_type, original_data, dest):
		s = time.time()
		try:
			ret = self._convert_to_jpeg(data_type, original_data, dest)
		except:
			log.error(traceback.format_exc())
			ret = False
		log.debug("Conversion from %s to JPEG took %d ms" % (data_type, int((time.time() - s) * 1000)))
		return ret

	def _convert_to_jpeg(self, data_type, original_data, dest):
		from ..engine.license import ArchivCZSKLicense
		from ..engine.tools.stbinfo import stbinfo

		def calc_data_checksum(req_data):
			req_data = json.dumps(req_data, sort_keys=True, ensure_ascii=True, separators=('','')).encode('ascii')
			return md5(b'svg2png' + req_data).hexdigest()

		if ArchivCZSKLicense.get_instance().is_valid():
			req_data = {
				'version': 1,
				'id': stbinfo.installation_id,
				data_type: b64encode(original_data).decode('ascii')
			}
			req_data['checksum'] = calc_data_checksum(req_data)
			try:
				r = requests.post('http://archivczsk.webredirect.org/tojpeg/' + data_type, json=req_data, timeout=5)
				r.raise_for_status()
			except:
				log.error("Conversion to JPEG failed")
			else:
				with open(dest, 'wb') as f:
					f.write(r.content)

				return True

		# fallback - local slow conversion using ffmpeg
		webp_dest = dest + '.webp'
		with open(webp_dest, 'wb') as f:
			f.write(original_data)

		os.system('ffmpeg -i "{}" -frames:v 1 {}'.format(webp_dest, dest))
		os.remove(webp_dest)

		return os.path.isfile(dest)


class PosterPixmapHandler(object):
	def __init__(self, poster_widget, no_image_path=None):
		self.poster_widget = poster_widget
		self.poster_processing = PosterProcessing.get_instance()
		self.no_image_path = no_image_path or os.path.join(PLUGIN_PATH, 'gui', 'icon', 'no_movie_image.png')
		self._decoding_url = None
		self._decoding_path = None
		self.last_decoded_url = None
		self.last_selected_url = None
		self.picload = eCompatPicLoad(self._got_picture_data)
		self.retry_timer = eCompatTimer(self._decode_current_image)
		self._max_retry_times = 3
		self._retry_times = 0
		self.last_picPtr = None
		self.img_idx = 0

	def __del__(self):
		log.debug("PosterImageHandler.__del__")
		self.retry_timer.stop()
		del self.retry_timer
		del self.picload
		del self.last_picPtr

	def _got_image_data(self, url, path, idx):
		if self.img_idx == idx:
			self._start_decode_image(url, path)
		else:
			self.debug("PosterImageHandler._got_image_data: discarting image, because it's outdated")

	def _decode_current_image(self):
		if self._retry_times < self._max_retry_times:
			self._retry_times += 1
			self._start_decode_image(self.last_selected_url, self._decoding_path)
		else:
			self._start_decode_image(None, self.no_image_path)
			self._retry_times = 0
			self.retry_timer.stop()

	def _start_decode_image(self, url, path):
#		log.debug("PosterImageHandler._start_decode_image: {0}".format(path))
		if self._decode_image(path):
#			log.debug("PosterImageHandler._start_decode_image: started...")
			self.retry_timer.stop()
			self._decoding_path = None
			self._decoding_url = url
		else:
			log.debug("PosterImageHandler._start_decode_image: failed...")
			self._decoding_path = path
			self.retry_timer.start(200)

	def _decode_image(self, path):
		try:
			wsize = self.poster_widget.instance.size()
			sc = AVSwitch().getFramebufferScale()
			self.picload.setPara((wsize.width(), wsize.height(),
								  sc[0], sc[1], False, 1, "#ff000000"))
			self.last_decoded_url = None
			return 0 == self.picload.startDecode(util.toString(path))
		except Exception as e:
			log.error("PosterImageHandler._decode_image, exception: %s" % str(e))
			# do not try to decode again ...
			return True

	def _got_picture_data(self, picInfo=None):
		picPtr = self.picload.getData()
		if picPtr is not None:
#			log.debug("PosterImageHandler._got_picture_data, success")
			try:
				self.poster_widget.instance.setPixmap(picPtr)
				self.last_decoded_url = self._decoding_url
				self.last_picPtr = picPtr
			except Exception as e:
				log.error("PosterImageHandler._got_picture_data, exception: %s" % str(e))
				self.last_decoded_url = None
				self.last_picPtr = None
		else:
			log.error("PosterImageHandler._got_picture_data, failed")
			self.last_decoded_url = None
		self._decoding_url = None

	def set_image(self, url, no_image_path=None, use_cache=True):
		log.debug("PosterImageHandler.set_image: {0}".format(url))
		if self.last_selected_url:
			if self.last_selected_url == url:
#				log.debug("PosterImageHandler.set_image: same url as before")
				return
		self.last_selected_url = url
		if self.last_decoded_url:
			if self.last_decoded_url == url and self.last_picPtr != None:
#				log.debug("PosterImageHandler.set_image: same decoded url as before")
				self.poster_widget.instance.setPixmap(self.last_picPtr)
				return

		self.retry_timer.stop()

		if url is None or len(url) == 0:
			imgPtr = LoadPixmap(path=no_image_path if no_image_path else self.no_image_path, cached=True)
			if imgPtr:
				self.poster_widget.instance.setPixmap(imgPtr)
		else:
			self.poster_widget.instance.setPixmap(gPixmapPtr())
			self.last_decoded_url = None
			self.img_idx += 1
			self.poster_processing.get_image_file(url, use_cache, partial(self._got_image_data, idx=self.img_idx))
