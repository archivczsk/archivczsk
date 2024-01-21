# -*- coding: utf-8 -*-

import uuid
import socket

class BoxInfo:
	def __init__(self):
		try:
			from Plugins.Extensions.OpenWebif.controllers.models.info import getInfo
			self.boxinfo = getInfo()
		except:
			self.boxinfo = {}
			pass

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

	def get_node(self):
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

	def get_installation_id(self):
		from hashlib import md5
		return md5(str(self.get_node()).encode('utf-8')).hexdigest()

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
	def is_dmm_image():
		try:
			from enigma import eTimer
			eTimer().timeout.connect
		except Exception as e:
			return False
		return True

	@staticmethod
	def is_vti_image():
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
