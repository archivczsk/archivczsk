# -*- coding: utf-8 -*-
from Components.config import config
import os, traceback
import json, time
from .tools.logger import log
from .bgservice import AddonBackgroundService
from datetime import datetime, date
from .tools.stbinfo import stbinfo
import requests
import time

import binascii
import sys

# #################################################################################################

class ArchivCZSKLicense(object):
	LEVEL_FREE = 0
	LEVEL_SUPPORTER = 1
	LEVEL_DEVELOPER = 2

	def __init__(self):
		self.lic_file = os.path.join(config.plugins.archivCZSK.dataPath.value, 'license.dat')
		self.lic_data = {}
		self.online_check = 0
		self.extra_online_check = 0

		self.bgservice = AddonBackgroundService('LicChecker')
		self.load()
		self.bgservice.run_in_loop('Check', 3600, self.check_license)

	def get_aes_module(self):
		try:
			from Cryptodome.Cipher import AES
			return AES
		except:
			try:
				from Crypto.Cipher import AES
				return AES
			except:
				log.error("Cryptodome library is not available")
				return None

	def load(self):
		self.lic_data = {}

		AES = self.get_aes_module()

		try:
			if os.path.isfile(self.lic_file):
				with open(self.lic_file, 'rb') as f:
					pp = (lambda s: s[0:-ord(s[-1])]) if sys.version_info[0] == 2 else (lambda s: s[0:-s[-1]])
					self.lic_data = json.loads(pp(AES.new(binascii.a2b_hex(stbinfo.installation_id), AES.MODE_CBC, f.read(16)).decrypt(f.read())))

		except:
			log.error("License load failed")
			if AES != None:
				log.debug(traceback.format_exc())

		if self.lic_data.get('level', self.LEVEL_FREE) != self.LEVEL_FREE:
			log.info('Loaded license level %d valid from %s to %s' % (self.lic_data['level'], self.valid_from(), self.valid_to() ))

	def reset(self):
		self.lic_data = {}
		try:
			os.remove(self.lic_file)
		except:
			pass

	def is_valid(self, act_time=None):
		if act_time == None:
			act_time = int(time.time())

		if act_time >= self.lic_data.get('valid_from', act_time+1) and act_time <= self.lic_data.get('valid_to', act_time-1) and self.lic_data.get('level', 0) != self.LEVEL_FREE:
			return True

		return False

	def request_license(self):
		from ..version import version
		act_time = int(time.time())
		ret = False

		data = {
			'version': 1,
			'id': stbinfo.installation_id,
			'archivczsk_version': version,
			'system_time': act_time,
			'periodic_check': self.online_check != 0,
			'extra_check': self.extra_online_check != 0 and self.extra_online_check > act_time
		}
		data['checksum'] = self.calc_data_checksum(data)

		try:
			log.debug("Requesting license from server")
			response = requests.post('http://archivczsk.webredirect.org/license/get', json=data, timeout=10, verify=False)

			if response.status_code == 200:
				log.debug("License received")
				with open(self.lic_file, 'wb') as f:
					f.write(response.content)

				self.extra_online_check = 0
				ret = True
			elif response.status_code == 404:
				log.info("This installation has no valid license")
			else:
				log.error("Failed to get license: server returned error %s" % response.status_code)
		except:
			log.error("Failed to donwload license:\n%s" % traceback.format_exc())

		return ret

	def refresh_license(self):
		if self.request_license():
			self.load()
			self.online_check = int(time.time()) + (24 * 3600)

	def check_license(self):
		act_time = int(time.time())

		if self.is_valid(act_time):
			return

		if self.lic_data.get('level', 0) != self.LEVEL_FREE:
			log.info("License expired")

		self.reset()
		if (self.online_check == 0 or act_time > self.online_check) or (act_time != 0 and act_time < self.extra_online_check):
			self.refresh_license()

	def check_level(self, level):
		return self.is_valid() and (self.lic_data.get('level', 0) & level) == level

	def calc_data_checksum(self, data):
		from hashlib import md5
		data = json.dumps(data, sort_keys=True, ensure_ascii=True, separators=('','')).encode('ascii')
		return md5(data).hexdigest()

	def enable_extra_checks(self):
		self.extra_online_check = int(time.time()) + (24 * 3600)

	def valid_from(self):
		return date.fromtimestamp(self.lic_data.get('valid_from', 0)).strftime('%d.%m.%Y')

	def valid_to(self):
		return date.fromtimestamp(self.lic_data.get('valid_to', 0)).strftime('%d.%m.%Y')


license = ArchivCZSKLicense()
