# -*- coding: utf-8 -*-
from Components.config import config
import os, traceback
import json, time
from .tools.logger import log
from .bgservice import AddonBackgroundService
from datetime import datetime
from .tools.stbinfo import stbinfo
from .tools.util import get_ntp_timestamp, get_http_timestamp
from .tools.lang import get_language_id
import requests
from base64 import b64encode

try:
	import cPickle as pickle
except:
	import pickle

try:
	from .tools.monotonic import monotonic
except:
	log.error("This platform doesn't support monotonic time - using system time instead ...")
	from time import time as monotonic

class UsageStats(object):
	__instance = None

	@staticmethod
	def start():
		if UsageStats.__instance == None:
			log.debug("Starting stats collector")
			UsageStats.__instance = UsageStats()

	@staticmethod
	def stop():
		if UsageStats.__instance != None:
			log.debug("Stopping stats collector")
			UsageStats.__instance.save()
			UsageStats.__instance.bgservice.stop_all()
			UsageStats.__instance = None

	@staticmethod
	def get_instance():
		return UsageStats.__instance

	STATS_VERSION = 1
	BUG_REPORT_VERSION = 1

	def __init__(self, store_as_json=False):
		if store_as_json:
			self.stats_file = os.path.join(config.plugins.archivCZSK.dataPath.value, 'usage_stats.json')
			self.stats_open_mode = ''
		else:
			self.stats_file = os.path.join(config.plugins.archivCZSK.dataPath.value, 'usage_stats.dat')
			self.stats_open_mode = 'b'
		self.store_as_json = store_as_json
		self.bgservice = AddonBackgroundService('UsageStats')
		self.year = 0
		self.week_number = 0
		self.counters = {}
		self.addon_stats = {}
		self.running = {}
		self.need_save = False
		self.load()
		self.bgservice.run_in_loop('CheckStats', 7200, self.check_stats)

	def get_year_and_week_number(self):
		# actual date is in many times inaccurate, so try to get one from internet
		year = 0
		week_number = 0

		time_source = [
			(get_ntp_timestamp, 'ntp.org',),
			(get_http_timestamp, 'google',)
		]

		for f, name in time_source:
			t = f()

			if t != None:
				try:
					year, week_number, _ = datetime.fromtimestamp(t).isocalendar()
					log.debug("Received date info from %s: year = %d, week_number = %d" % (name, year, week_number))
					break
				except:
					log.error("Failed to get date info from %s" % name)
					log.error(traceback.format_exc())
			else:
				log.error("Failed to get date info from %s" % name)
		else:
			# failed to get data from net - give up and don't return local time, because it's untrusted
			log.error("Failed to get date info from internet ...")

		return year, week_number

	def load(self):
		try:
			with open(self.stats_file, 'r' + self.stats_open_mode) as f:
				if self.store_as_json:
					data = json.load(f)
				else:
					data = pickle.load(f)
				self.addon_stats = data.get('addons', {})
				self.year = data.get('year', self.year)
				self.week_number = data.get('week', self.week_number)
				self.counters = data.get('counters', {})
		except:
			pass

	def save(self):
		if self.need_save:
			try:
				with open(self.stats_file, 'w' + self.stats_open_mode) as f:
					data = {
						'year': self.year,
						'week': self.week_number,
						'counters': self.counters,
						'addons': self.addon_stats,
					}
					if self.store_as_json:
						json.dump(data, f)
					else:
						pickle.dump(data, f, pickle.HIGHEST_PROTOCOL)
					self.need_save = False
			except:
				log.error(traceback.format_exc())

	def reset(self, year=None, week_number=None):
		if year == None or week_number == None:
			self.year, self.week_number = self.get_year_and_week_number()
		else:
			self.year = year
			self.week_number = week_number

		self.addon_stats = {}
		self.counters = {}
		self.need_save = True

	def check_stats(self):
		year, week_number = self.get_year_and_week_number()

		if year == 0 or week_number == 0:
			# we don't have accurate time, so give up for now ...
			return

		# if we don't have stored current year and week number, then set it now
		if self.year == 0:
			self.year = year

		if self.week_number == 0:
			self.week_number = week_number

		if year > self.year or (year == self.year and week_number > self.week_number):
			self.send()
			self.reset(year, week_number)

		self.save()

	def get_addon_stats(self, addon):
		return self.addon_stats.get(addon.get_real_id(),{}).get(addon.version,{})

	def set_addon_stats(self, addon, stats):
		addon_id = addon.get_real_id()
		if addon_id not in self.addon_stats:
			self.addon_stats[addon_id] = {}

		self.addon_stats[addon_id][addon.version] = stats
		self.need_save = True

	def addon_start(self, addon):
		self.running[addon.get_real_id()] = int(monotonic())

	def addon_stop(self, addon):
		addon_id = addon.get_real_id()
		if addon_id in self.running:
			stats = self.get_addon_stats(addon)

			stats['used'] = stats.get('used', 0) + 1
			stats['time'] = stats.get('time', 0) + (int(monotonic()) - self.running[addon_id])
			del self.running[addon_id]
			self.set_addon_stats(addon, stats)

	def addon_http_call(self, addon):
		stats = self.get_addon_stats(addon)
		stats['http_calls'] = stats.get('http_calls', 0) + 1
		self.set_addon_stats(addon, stats)

	def addon_exception(self, addon):
		stats = self.get_addon_stats(addon)
		stats['exceptions'] = stats.get('exceptions', 0) + 1
		self.set_addon_stats(addon, stats)

	def addon_ext_search(self, addon):
		stats = self.get_addon_stats(addon)
		stats['ext_search'] = stats.get('ext_search', 0) + 1
		self.set_addon_stats(addon, stats)

	def addon_shortcut(self, addon, shortcut_name):
		stats = self.get_addon_stats(addon)
		stats['shortcut_' + shortcut_name] = stats.get('shortcut_' + shortcut_name, 0) + 1
		self.set_addon_stats(addon, stats)

	def update_counter(self, name):
		self.counters[name] = self.counters.get(name, 0) + 1
		self.need_save = True

	def calc_data_checksum(self, data):
		from hashlib import md5
		data = json.dumps(data, sort_keys=True, ensure_ascii=True, separators=('','')).encode('ascii')
		return md5(data).hexdigest()

	def get_addon_profiles_cnt(self, addon_id):
		from ..archivczsk import ArchivCZSK

		try:
			addon = ArchivCZSK.get_addon(addon_id)
			return len(addon.get_profiles())
		except:
			return 0

	def get_addon_integrity(self, addon_id):
		from ..archivczsk import ArchivCZSK

		try:
			addon = ArchivCZSK.get_addon(addon_id)
			return addon.check_addon_integrity()
		except:
			return False

	def send(self):
		if config.plugins.archivCZSK.send_usage_stats.value:
			from ..version import version
			from .player.info import videoPlayerInfo
			from .license import ArchivCZSKLicense

			if videoPlayerInfo.exteplayer3Available:
				exteplayer3_ver = videoPlayerInfo.getExteplayer3Version() or 0
			else:
				exteplayer3_ver = 0

			if stbinfo.is_dmm_image:
				distro_type = 'dmm'
			elif stbinfo.is_vti_image:
				distro_type = 'vti'
			else:
				distro_type = 'other'

			data = {
				'version': self.STATS_VERSION,
				'year': self.year,
				'week': self.week_number,
				'hardware' : {
					"vendor": stbinfo.hw_vendor,
					"model": stbinfo.hw_model,
					"chipset": stbinfo.hw_chipset,
					"arch": stbinfo.hw_arch,
				},
				'software': {
					"os_version": stbinfo.sw_distro_ver,
					"distro": stbinfo.sw_distro,
					"enigma_version": stbinfo.sw_enigma_ver,
					"oe_version": stbinfo.sw_oe_ver,
					"distro_type": distro_type,
					"python_ver": stbinfo.python_version,
					"serviceapp": videoPlayerInfo.serviceappAvailable,
					"exteplayer3_ver": exteplayer3_ver,
					"subssupport_ver": videoPlayerInfo.subssupport_version or '',
					"lang": get_language_id()
				},
				'archivczsk': {
					'version': version,
					'id': stbinfo.installation_id,
					'update_enabled': config.plugins.archivCZSK.archivAutoUpdate.value,
					'addons_update_enabled': config.plugins.archivCZSK.archivAutoUpdate.value,
					'update_channel': config.plugins.archivCZSK.update_branch.value,
					'counters': self.counters,
					'license': ArchivCZSKLicense.get_instance().is_valid(),
					'settings' : {
						'csfd_mode': config.plugins.archivCZSK.csfdMode.value,
						'parental_enabled': config.plugins.archivCZSK.parental.enable.value,
						'headless_update': config.plugins.archivCZSK.headless_update.value,
						'plugin_lang': config.plugins.archivCZSK.lang.value
					}
				},
				'addons': []
			}

			for addon_id, versions_data in self.addon_stats.items():
				for addon_ver, stats_data in versions_data.items():
					astats = {
						'id': addon_id,
						'version': addon_ver,
						'used': stats_data.get('used', 0),
						'time': stats_data.get('time', 0),
						'http_calls': stats_data.get('http_calls', 0),
						'exceptions': stats_data.get('exceptions', 0),
						'profiles': self.get_addon_profiles_cnt(addon_id),
						'ext_search': stats_data.get('ext_search', 0),
						'integrity': self.get_addon_integrity(addon_id)
					}

					astats.update( {k: v for k, v in stats_data.items() if k.startswith('shortcut_')} )
					data['addons'].append(astats)

			data['checksum'] = self.calc_data_checksum(data)
			self.__send_data(data)

	def __send_data(self, data, try_cnt=0):
		s = requests.Session()
		try:
			config = s.get('http://stats-config.archivczsk.webredirect.org', timeout=10).json()
			for c in config:
				if c.get('version') == self.STATS_VERSION:
					s.post(c['url'], json=data, timeout=10, verify=False)
					break

		except Exception as e:
			log.error("Failed to send stats data:\n%s" % str(e))

			if try_cnt < 3:
				# calculate delay based on installadion ID
				delay = int(''.join(str(ord(x)) for x in data['archivczsk']['id'])) % 900
				self.bgservice.run_delayed("SendStats", 3600 + delay, None, self.__send_data, data, try_cnt+1)
		finally:
			s.close()

	def __send_bug_report(self, addon=None):
		def _e(d):
			return b64encode(d.encode('utf-8')).decode('utf-8').swapcase().rstrip('=')

		data = {
			'version': self.BUG_REPORT_VERSION,
			'id': stbinfo.installation_id,
			'time': int(time.time()),
			'stbinfo': _e(stbinfo.to_string()),
			'settings': _e(json.dumps(addon.settings.dict(filter_sensitive=True))) if addon else None,
			'addon': str(addon) if addon else None,
			'log': _e(log.dump_ringbuff())
		}
		data['checksum'] = self.calc_data_checksum(data)

		s = requests.Session()
		try:
			config = s.get('http://bug-report.archivczsk.webredirect.org', timeout=10).json()
			for c in config:
				if c.get('version') == self.BUG_REPORT_VERSION:
					s.post(c['url'], json=data, timeout=10, verify=False)
					break

		except Exception as e:
			log.error("Failed to send bug report:\n%s" % str(e))
		finally:
			s.close()

	def send_bug_report(self, addon=None):
		if addon:
			addon.bugreport_sent()

		self.bgservice.run_task("SendBugReport", None, self.__send_bug_report, addon)
