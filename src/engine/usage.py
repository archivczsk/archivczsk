# -*- coding: utf-8 -*-
import os, time, traceback
import json
from ..settings import config
from .. import log
from .bgservice import AddonBackgroundService
from datetime import datetime
from .tools.stbinfo import stbinfo
from .tools.util import get_ntp_timestamp
import requests

try:
	import cPickle as pickle
except:
	import pickle


class UsageStats(object):

	def __init__(self, store_as_json=False):
		if store_as_json:
			self.stats_file = os.path.join(config.plugins.archivCZSK.dataPath.value, 'usage_stats.json')
			self.stats_open_mode = ''
		else:
			self.stats_file = os.path.join(config.plugins.archivCZSK.dataPath.value, 'usage_stats.dat')
			self.stats_open_mode = 'b'
		self.store_as_json = store_as_json
		self.bgservice = AddonBackgroundService('UsageStats')
		self.year = None
		self.week_number = None
		self.addon_stats = {}
		self.running = {}
		self.need_save = False
		self.load()
		if self.year == None or self.week_number == None:
			# year and week number not loaded from cache, so set to actuall
			self.year, self.week_number = self.get_year_and_week_number()

		self.bgservice.run_in_loop('CheckStats', 7200, self.check_stats)

	def get_year_and_week_number(self):
		# actual date is in many times inaccurate, so try to get one from internet
		t = get_ntp_timestamp()

		if t != None:
			year, week_number, _ = datetime.fromtimestamp(t).isocalendar()
			log.debug("Received date info from ntp.org: year = %d, week_number = %d" % (year, week_number))
		else:
			# NTP not worked - try HTTP instead
			try:
				inet_date = requests.get('http://worldtimeapi.org/api/timezone/Europe/London', timeout=3).json()

				week_number = int(inet_date['week_number'])
				year = int(inet_date['utc_datetime'].split('-')[0])
				log.debug("Received date info from worldtimeapi: year = %d, week_number = %d" % (year, week_number))
			except:
				# failed to get data from net, so use one (untrusted) from local clock
				year, week_number, _ = datetime.now().isocalendar()
				log.error("Failed to get date info from internet - using local provided by system: year = %d, week_number = %d" % (year, week_number))

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
		except:
			pass

	def save(self):
		if self.need_save:
			try:
				with open(self.stats_file, 'w' + self.stats_open_mode) as f:
					data = {
						'year': self.year,
						'week': self.week_number,
						'addons': self.addon_stats,
					}
					if self.store_as_json:
						json.dump(data, f)
					else:
						pickle.dump(data, f, pickle.HIGHEST_PROTOCOL)
					self.need_save = False
			except:
				log.error(traceback.format_exc())

	def reset(self):
		if self.addon_stats != {}:
			self.addon_stats = {}
			self.need_save = True
		self.year, self.week_number = self.get_year_and_week_number()
		self.save()

	def check_stats(self, in_background=False):
		year, week_number = self.get_year_and_week_number()

		if year > self.year or week_number > self.week_number:
			self.send(in_background)

	def get_addon_stats(self, addon):
		return self.addon_stats.get(addon.id,{}).get(addon.version,{})

	def set_addon_stats(self, addon, stats):
		# if this will be uncommented, then stats will be checked by every insert, but we don't need to be so accurate
		# check_stats is called on start and then every 2 hours, so there will be max. 2 hours of inaccuracy per week
#		self.check_stats(True)
		if addon.id not in self.addon_stats:
			self.addon_stats[addon.id] = {}

		self.addon_stats[addon.id][addon.version] = stats
		self.need_save = True

	def addon_start(self, addon):
		self.running[addon.id] = int(time.time())

	def addon_stop(self, addon):
		if addon.id in self.running:
			stats = self.get_addon_stats(addon)

			stats['used'] = stats.get('used', 0) + 1
			stats['time'] = stats.get('time', 0) + (int(time.time()) - self.running[addon.id])
			del self.running[addon.id]
			self.set_addon_stats(addon, stats)

	def addon_http_call(self, addon):
		stats = self.get_addon_stats(addon)
		stats['http_calls'] = stats.get('http_calls', 0) + 1
		self.set_addon_stats(addon, stats)

	def calc_data_checksum(self, data):
		from hashlib import md5
		data = json.dumps(data, sort_keys=True, ensure_ascii=True, separators=('','')).encode('ascii')
		return md5(data).hexdigest()

	def send(self, in_background=False):
		if config.plugins.archivCZSK.send_usage_stats.value:
			from ..version import version

			if stbinfo.is_dmm_image:
				distro_type = 'dmm'
			elif stbinfo.is_vti_image:
				distro_type = 'vti'
			else:
				distro_type = 'other'

			data = {
				'version': 1,
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
				},
				'archivczsk': {
					'version': version,
					'id': stbinfo.installation_id,
					'update_enabled': config.plugins.archivCZSK.archivAutoUpdate.value,
					'addons_update_enabled': config.plugins.archivCZSK.autoUpdate.value,
					'update_channel': config.plugins.archivCZSK.update_branch.value,
					'settings' : {
						'csfd_mode': config.plugins.archivCZSK.csfdMode.value,
						'parental_enabled': config.plugins.archivCZSK.parental.enable.value
					}
				},
				'addons': []
			}

			for addon_id, versions_data in self.addon_stats.items():
				for addon_ver, stats_data in versions_data.items():
					data['addons'].append({
						'id': addon_id,
						'version': addon_ver,
						'used': stats_data.get('used', 0),
						'time': stats_data.get('time', 0),
						'http_calls': stats_data.get('http_calls', 0),
					})

			data['checksum'] = self.calc_data_checksum(data)

			if in_background:
				self.bgservice.run_task("SendStats", None, self.__send_data, data, in_background)
			else:
				self.__send_data(data)
		self.reset()

	def __send_data(self, data, in_background=False):
		try:
			requests.post('http://archivczsk.webredirect.org:15101/stats/send', json=data, timeout=10 if in_background else 3)
		except Exception as e:
			log.error("Failed to send stats data: %s" % str(e))

		# just dummy debug dump for now
#		with open('/tmp/%d_stats_to_send.json' % data['week'], 'w') as f:
#			json.dump(data, f)
		return

usage_stats = UsageStats()
