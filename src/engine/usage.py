# -*- coding: utf-8 -*-
import os, time, traceback
import json
from ..settings import config
from .. import log
from .bgservice import AddonBackgroundService
from datetime import datetime
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
		self.year, self.week_number, _ = datetime.now().isocalendar()
		self.addon_stats = {}
		self.running = {}
		self.need_save = False
		self.load()
		self.bgservice.run_in_loop('CheckStats', 7200, self.check_stats)
	
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
		self.year, self.week_number, _ = datetime.now().isocalendar()
		self.save()

	def check_stats(self):
		year, week_number, _ = datetime.now().isocalendar()

		if year > self.year or week_number > self.week_number:
			self.send()
	
	def get_addon_stats(self, addon):
		return self.addon_stats.get(addon.id,{}).get(addon.version,{})

	def set_addon_stats(self, addon, stats):
		# if this will be uncommented, then stats will be checked by every insert, but we don't need to be so accurate
		# check_stats is called on start and then every 2 hours, so there will be max. 2 hours of inaccuracy per week
#		self.check_stats()
		if addon.id not in self.addon_stats:
			self.addon_stats[addon.id] = {}
			
		self.addon_stats[addon.id][addon.version] = stats
		self.need_save = True
		
	def addon_start(self, addon):
		self.running[addon.id] = int(time.time())
		
	def addon_stop(self, addon):
		stats = self.get_addon_stats(addon)
		
		stats['used'] = stats.get('used', 0) + 1
		stats['time'] = stats.get('time', 0) + (int(time.time()) - self.running[addon.id])
		del self.running[addon.id]
		self.set_addon_stats(addon, stats)

	def addon_http_call(self, addon):
		stats = self.get_addon_stats(addon)
		stats['http_calls'] = stats.get('http_calls', 0) + 1
		self.set_addon_stats(addon, stats)

	def get_installation_id(self):
		from uuid import getnode
		from hashlib import md5
		return md5(str(getnode()).encode('utf-8')).hexdigest()

	def send(self):
		if config.plugins.archivCZSK.send_usage_stats.value:
			from ..version import version

			data = {
				'version': 1,
				'year': self.year,
				'week': self.week_number,
				'checksum': None,
				'archivczsk': {
					'version': version,
					'id': self.get_installation_id(),
					'update_enabled': config.plugins.archivCZSK.archivAutoUpdate.value,
					'addons_update_enabled': config.plugins.archivCZSK.autoUpdate.value,
					'update_channel': config.plugins.archivCZSK.update_branch.value
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

			self.bgservice.run_task("SendStats", None, self.__send_data, data)
		self.reset()

	def __send_data(self, data):
		#requests.post('http://archivczsk.eu/usagestats.php', json=data)

		# just dummy debug dump for now
#		with open('/tmp/%d_stats_to_send.json' % data['week'], 'w') as f:
#			json.dump(data, f)
		return


usage_stats = UsageStats()
