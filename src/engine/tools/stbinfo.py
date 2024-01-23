# -*- coding: utf-8 -*-

import uuid
import socket
import platform

class StbInfo:
	def __init__(self):
		try:
			from Plugins.Extensions.OpenWebif.controllers.models.info import getInfo
			self.boxinfo = getInfo()
		except:
			self.boxinfo = {}
			pass

		self.hw_vendor = self.get_info_value('brand')
		self.hw_model = self.get_info_value('model')
		self.hw_chipset =  self.get_info_value('chipset')
		self.hw_arch = self._get_arch()

		self.sw_distro_ver = self.get_info_value('imagever')
		self.sw_distro = self.get_info_value('friendlyimagedistro')
		self.sw_enigma_ver = self.get_info_value('enigmaver')
		self.sw_oe_ver = self.get_info_value('oever')

		self.node = self._get_node()
		self.installation_id = self._get_installation_id()
		self.python_version = self._get_python_version()
		self.python_version_touple = self._get_python_version_touple()

		self.is_vti_image = self._is_vti_image()
		self.is_dmm_image = self._is_dmm_image()

	def get_info_value(self, entry):
		value = self.boxinfo.get(entry)

		if value:
			return value

		# if no boxinfo from OpenWebif is available
		try:
			with open('/proc/stb/info/' + entry, 'r') as f:
				value = f.read().strip()
		except:
			value = 'unknown'

		return value

	def _get_node(self):
		ifaces = sorted(self.boxinfo.get('ifaces', []), key=lambda x: x['name'])
		if len(ifaces) > 0:
			mac_str = ifaces[0].get('mac')
			if mac_str:
				return mac_str.upper().replace(':', '')

		for method in ("_ip_getnode", "_ifconfig_getnode"):
			if hasattr(uuid, method):
				node = getattr(uuid, method)()
				if node:
					mac_str = ''.join(("%012X" % node)[i:i + 2] for i in range(0, 12, 2))
					break
		else:
			mac_str = ''

		return mac_str

	def _get_installation_id(self):
		from hashlib import md5
		return md5(str(self._get_node()).encode('utf-8')).hexdigest()

	@staticmethod
	def _get_arch():
		return platform.machine()

	@staticmethod
	def _get_python_version():
		return platform.python_version()

	@staticmethod
	def _get_python_version_touple():
		ver_major, ver_minor, patchlevel = platform.python_version_tuple()
		return (int(ver_major), int(ver_minor), int(patchlevel))

	@staticmethod
	def get_ip():
		try:
			s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
			s.connect(("8.8.8.8", 53))
			ip = s.getsockname()[0]
			s.close()
		except:
			ip = '127.0.0.1'
		return ip

	@staticmethod
	def _is_dmm_image():
		# this only works for OE >= 2.0
		try:
			from enigma import eTimer
			eTimer().timeout.connect
		except Exception as e:
			return False
		return True

	@staticmethod
	def _is_vti_image():
		# this returns True also for some DMM images based on OE < 2.0
		try:
			import inspect
			from skin import parseSize as __parseSize

			try:
				argspec = inspect.getargspec(__parseSize)
			except:
				argspec = inspect.getfullargspec(__parseSize)
			return len(argspec.args) == 2
		except:
			return False

stbinfo = StbInfo()
