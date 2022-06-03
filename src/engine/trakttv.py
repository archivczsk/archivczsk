# -*- coding: UTF-8 -*-
import sys
import os
import json
import traceback
import datetime
import requests
import time

from collections import OrderedDict
from Components.config import config
from Plugins.Extensions.archivCZSK import _, log
from Plugins.Extensions.archivCZSK.engine.tools.util import toString
from Plugins.Extensions.archivCZSK.gui.common import showInfoMessage
from Screens.ChoiceBox import ChoiceBox
from enigma import eTimer
from Plugins.Extensions.archivCZSK.compat import eConnectCallback

BASE = 'https://api.trakt.tv'

class TraktRefreshException(Exception):
	pass

def _log_dummy(message):
	print('[TRAKTTV]: ' + message )
	pass

# #################################################################################################

class trakt_tv(object):
	def __init__(self, cfg ):
		
		self.client_id = 'a6b6287e06b63ab217b51fb75a6215538f5d6f53bc9903f182395ced29f93f08'
		self.client_secret = '4412cc6e9c7897c6656419e22a4c20f7650ddd7d1ecc6d33e6ccbed05b8185c2'
		
		self.cfg = cfg
		self.pairing_data = None
		self.login_data = {}
		self.load_login_data()
		
	# #################################################################################################
	
	def load_login_data(self):
		value = self.cfg.access_token.getValue()
		if value:
			self.login_data['access_token'] = value

		value = self.cfg.refresh_token.getValue()
		if value:
			self.login_data['refresh_token'] = value

		value = self.cfg.expiration.getValue()
		if value:
			self.login_data['expiration'] = value
			
	# #################################################################################################
	
	def save_login_data(self):
		self.cfg.access_token.setValue( self.login_data.get('access_token', ''))
		self.cfg.access_token.save()
		self.cfg.refresh_token.setValue(self.login_data.get('refresh_token',''))
		self.cfg.refresh_token.save()
		self.cfg.expiration.setValue(self.login_data.get('expiration',0))
		self.cfg.expiration.save()
		
		try:
			from Components.config import configfile
			configfile.save()
		except:
			pass

	# #################################################################################################

	def call_trakt_api(self, endpoint, data=None):
		headers = {
			'Content-Type' : 'application/json',
			'trakt-api-version' : "2",
			'trakt-api-key' : self.client_id
		}
		
		if 'access_token' in self.login_data:
			headers['Authorization'] = 'Bearer %s' % self.login_data['access_token']

		if data:
			response = requests.post(BASE + endpoint, headers=headers, json=data)
		else:
			response = requests.get(BASE + endpoint, headers=headers)
		
		return response.status_code, response.json() if response.status_code < 300 else None 

	# #################################################################################################

	def getItemType(self, item):
		# 4- season+espisode
		# 3- season 1,2,3
		# 2- tvshow
		# 1- movie
		if item['type'] == 'movie':
			return 1
		elif item['type'] == 'show':
			if 'season' in item and 'episode' in item:
				return 4
			elif 'season' in item:
				return 3
			else:
				return 2

		raise Exception("Invalid trakt item (TYPE).")

	# #################################################################################################
	
	def getTraktIds(self, item):
		result = {}
		
		item = item['ids']
		if 'trakt' in item:
			result.update( { "trakt": item['trakt'] } )
		if 'tvdb' in item:
			result.update( { "tvdb": item['tvdb'] } )
		if 'tmdb' in item:
			result.update( { "tmdb": item['tmdb'] } )
		if 'imdb' in item:
			result.update( { "imdb": 'tt%s' % item['imdb'].replace('tt','') } )
			
		if len( result ) == 0:
			raise Exception("Invalid trakt item (IDs).")
		
		return result

	# #################################################################################################
	
	# API
	def get_lists(self):
		if self.valid():
			ret = []
			# always return watchlist category
			ret.append( { 'name': 'Watchlist', 'id': 'watchlist' } )
			
			code, data = self.call_trakt_api('/users/me/lists' )
			
			if code > 210:
				raise Exception('Wrong response from Trakt server: %d' % code )

			for m in data:
				ret.append( { 'name': m['name'], 'description': m['description'], 'id': m['ids']['slug'] } )
				
			return ret
		raise Exception('Invalid trakt token')

	# #################################################################################################
		
	def get_list_items(self, list_name):
		if self.valid():
			ret = []
			if list_name == 'watchlist':
				# watchlist category has different url
				code, data = self.call_trakt_api('/users/me/watchlist/items' )
			else:
				code, data = self.call_trakt_api('/users/me/lists/%s/items' % list_name )
			
			if code > 210:
				raise Exception('Wrong response from Trakt server: %d' % code )

			for m in data:
				tp = '%s'%m['type']
				obj = {'imdb':'%s'%m[tp]['ids']['imdb'], 'title':'%s (%s)'%(m[tp]['title'],m[tp]['year'])}
				ret.append(obj)
			return data
#			return ret
		raise Exception('Invalid trakt token')

	# #################################################################################################

	def add_to_watchlist(self, item):
		mediatype= self.getItemType(item)
		postdata = {}
		if mediatype==1:
			postdata = {"movies": [{"ids": self.getTraktIds(item)}]}
		# to watchlist can be added only whole tvseason
		if mediatype==2 or mediatype==3 or mediatype==4:
			postdata = {'shows':[{'ids':self.getTraktIds(item)}]}
			
		code, data = self.call_trakt_api('/sync/watchlist', postdata )
		
		if code > 210:
			raise Exception('Wrong response from Trakt server: %d' % code )
		
		log.logDebug("add_to_watchlist response:\n%s"%data)
		
		if mediatype==1:
			if not (int(data['added']['movies'])==1 or int(data['existing']['movies'])==1):
				raise Exception('Movie item not added to watchlist.')
			
		if mediatype==2 or mediatype==3 or mediatype==4:
			if not (int(data['added']['shows'])==1 or int(data['existing']['shows'])==1):
				raise Exception('TvShow item not added to watchlist.')

	# #################################################################################################

	def remove_from_watchlist(self, item):
		mediatype= self.getItemType(item)
		postdata = {}
		
		if mediatype==1:
			postdata = {"movies": [{"ids": self.getTraktIds(item)}]}
			
		# to watchlist can be added only whole tvseason
		if mediatype==2 or mediatype==3 or mediatype==4:
			postdata = {'shows':[{'ids': self.getTraktIds(item)}]}
			
		code, data = self.call_trakt_api('/sync/watchlist/remove', postdata )
		
		if code > 210:
			raise Exception('Wrong response from Trakt server: %d' % code )

		log.logDebug("remove_from_watchlist response:\n%s"%data)
		if mediatype==1:
			if int(data['deleted']['movies'])!=1:
				raise Exception('Movie item not removed from watchlist.')
			
		if mediatype==2 or mediatype==3 or mediatype==4:
			if int(data['deleted']['shows'])!=1:
				raise Exception('TvShow item not removed from watchlist.')

	# #################################################################################################
	
	def mark_as_watched(self, item):
		mediatype= self.getItemType(item)
		postdata = {}
		if mediatype==1:
			postdata = {"movies": [{"ids": self.getTraktIds(item)}]}
		if mediatype==2:
			postdata = {'shows':[{'ids':self.getTraktIds(item)}]}
		if mediatype==3:
			postdata = {'shows':[{'seasons':[{'number':int('%s'%item['info']['season'])}], 'ids':self.getTraktIds(item)}]}
		if mediatype==4:
			postdata = {
				'shows':[
					{
						'ids':self.getTraktIds(item),
						'seasons':[
							{
								'episodes':[
									{
										'number':int('%s'%item['info']['episode'])
									}
								],
								'number':int('%s'%item['info']['season'])
							}
						]
					}
				]
			}

		log.logDebug("mark_as_watched postdata=%s"%postdata)
			
		code, data = self.call_trakt_api( '/sync/history', postdata )
		if code > 210:
			raise Exception('Wrong response from Trakt server: %d' % code )

		log.logDebug("mark_as_watched response:\n%s"%data)
		if mediatype==1:
			if int(data['added']['movies'])!=1:
				raise Exception('Movie item not mark as watched.')
		if mediatype==2 or mediatype==3:
			if int(data['added']['episodes'])<1:
				raise Exception('TvShow (season) not mark as watched.')
		if mediatype==4:
			if int(data['added']['episodes'])!=1:
				raise Exception('TvShow episode not mark as watched.')

	# #################################################################################################
	
	def mark_as_not_watched(self, item):
		mediatype= self.getItemType(item)
		postdata = {}
		if mediatype==1:
			postdata = {"movies": [{"ids": self.getTraktIds(item)}]}
		if mediatype==2:
			postdata = {'shows':[{'ids':self.getTraktIds(item)}]}
		if mediatype==3:
			postdata = {'shows':[{'seasons':[{'number':int('%s'%item['info']['season'])}], 'ids':self.getTraktIds(item)}]}
		if mediatype==4:
			postdata = {'shows':[{'seasons':[{'episodes':[{'number':int('%s'%item['info']['episode'])}], 'number':int('%s'%item['info']['season'])}], 'ids':self.getTraktIds(item)}]}
			
		code, data = self.call_trakt_api('/sync/history/remove', postdata)
		
		if code > 210:
			raise Exception('Wrong response from Trakt server: %d' % code )

		log.logDebug("mark_as_not_watched response:\n%s"%data)
		if mediatype==1:
			if int(data['deleted']['movies'])!=1:
				raise Exception('Movie item not mark as not watched.')
		if mediatype==2 or mediatype==3:
			if int(data['deleted']['episodes'])<1:
				raise Exception('TvShow (season) not mark as not watched.')
		if mediatype==4:
			if int(data['deleted']['episodes'])!=1:
				raise Exception('TvShow episode not mark as not watched.')
		pass

	# #################################################################################################
	
	def get_watched_modifications(self):
		def iso_to_timestamp( s ):
			if s:
				return int(datetime.datetime.strptime( s, '%Y-%m-%dT%H:%M:%S.000Z').strftime("%s"))-time.altzone
			else:
				return None
		
		mm = None
		ms = None
		if self.valid():
			code, data = self.call_trakt_api('/sync/last_activities')
			if code == 200:
				mm = iso_to_timestamp(data.get('movies',{}).get('watched_at'))
				ms = iso_to_timestamp(data.get('episodes',{}).get('watched_at'))
				
		return mm, ms
		
	# #################################################################################################
	
	def get_watched_movies(self):
		wm = []

		if self.valid():
			code, data = self.call_trakt_api('/sync/watched/movies')
			if code == 200:
				for item in data:
					ids = item.get('movie', {}).get('ids')
					if ids:
						witem = {}
						for id_name in [ 'trakt', 'tvdb', 'tmdb', 'imdb' ]:
							if id_name in ids:
								witem[id_name] = ids[id_name]
								
						wm.append( witem )
			
		return wm
	
	# #################################################################################################
	
	def get_watched_shows(self):
		ws = []
		
		if self.valid():
			code, data = self.call_trakt_api('/sync/watched/shows')
			
			if code == 200:
				for item in data:
					ids = item.get('show', {}).get('ids')
					if ids:
						witem = {}
						for id_name in [ 'trakt', 'tvdb', 'tmdb', 'imdb' ]:
							if id_name in ids:
								witem[id_name] = ids[id_name]

						witem['s'] = {}
						
						for sitem in item.get('seasons', []):
							witem['s'][ sitem['number'] ]  = [ e['number'] for e in sitem.get('episodes', []) ]
							
						ws.append( witem )
				
		return ws

	# #################################################################################################
	# PAIR
	def valid(self):
		if self.login_data.get('access_token') is None:
			return False
		
		# check refresh
		now = (datetime.datetime.now() - datetime.datetime(1970,1,1)).total_seconds()
		if self.login_data.get('expiration', 0)-432000 < now: #-5dni (5*24*60*60)
			if self.refresh_token() != 200:
				return False
			
		return True

	# #################################################################################################
	
	def get_pairing_data(self):
		if self.pairing_data != None:
			if int(time.time()) > self.pairing_data['expire_time']:
				self.pairing_data = None
				return None
			else:
				return self.pairing_data
		
		code, data = self.call_trakt_api('/oauth/device/code', {'client_id':self.client_id})

		if code == 200:
			self.pairing_data = data
			cur_time = int(time.time())
			self.pairing_data['next_pool_time'] = cur_time + self.pairing_data['interval']
			self.pairing_data['expire_time'] = cur_time + self.pairing_data['expires_in']
			return self.pairing_data
		else:
			return None

	# #################################################################################################
	
	def get_token(self):
		if self.pairing_data == None:
			return None
		
		self.login_data = {}
		code, data = self.call_trakt_api('/oauth/device/token', {'code':self.pairing_data['device_code'],'client_id':self.client_id, 'client_secret':self.client_secret})

		self.pairing_data['next_pool_time'] = int(time.time()) + self.pairing_data['interval']
		
		if code == 200:
			self.login_data['access_token'] = data['access_token']
			self.login_data['refresh_token'] = data['refresh_token']
			self.login_data['expiration'] = data['expires_in'] + data['created_at']
			self.save_login_data()
			self.pairing_data = None
		return code

	# #################################################################################################
	
	def refresh_token(self):
		if 'access_token' in self.login_data:
			del self.login_data['access_token']
			code, data = self.call_trakt_api('/oauth/device/token', data={'refresh_token':self.login_data['refresh_token'], 'client_id':self.client_id, 'client_secret':self.client_secret, 'redirect_uri':'urn:ietf:wg:oauth:2.0:oob', 'grant_type':'refresh_token'} )

		if code == 200:
			self.login_data['access_token'] = data['access_token']
			self.login_data['refresh_token'] = data['refresh_token']
			self.login_data['expiration'] = data['expires_in'] + data['created_at']
			self.save_login_data()
		return code
		
	# #################################################################################################

	def handle_trakt_action( self, action, item ):
		try:
			# action:
			#	- add		add item to watchlist
			#	- remove	remove item from watchlist
			#	- watched	add to watched collection
			#	- unwatched remove from watched collection
	
			if self.valid():
				log.logDebug("Trakt hit action=%s ..." % action)

				if action=='add':
					self.add_to_watchlist(item)
				elif action=='remove':
					self.remove_from_watchlist(item)
				elif action=='watched':
					self.mark_as_watched(item)
				elif action=='unwatched':
					self.mark_as_not_watched(item)

				# add result message to show only for trakt
				result = "success"
				msg = _("Trakt.tv operation {action} ended successfuly".format(action=action))
			else:
				result = "fail"
				msg = _("Trakt.tv is not paired with this device.")
		except:
			log.logError("Trakt action (%s) failed.\n%s" % (action, traceback.format_exc()) )
			result = "fail"
			msg = _('Trakt.tv operation "{action}" failed'.format(action=action))
			
		return result, msg
	
	# #################################################################################################
	
	def open_trakt_action_choicebox( self, session, item, cmdTrakt):
		def getListInputCB(selected=None):
			if selected is not None:
				cmdTrakt(item, choice_list[selected[0]])
	
		choice_list = OrderedDict()
		choice_list[ _('Add to watchlist') ] = 'add'
		choice_list[ _('Delete from watchlist') ] = 'remove'
		choice_list[ _('Mark as watched') ] = 'watched'
		choice_list[ _("Mark as not watched") ] = 'unwatched'
	
		newlist = [ (name,) for name in choice_list.keys()]
		session.openWithCallback(getListInputCB, ChoiceBox, toString( _("Choose Trakt.tv action")), newlist, skin_name="ArchivCZSKChoiceBox")
	
	# #################################################################################################
	
	def handle_trakt_pairing( self, session, cbk=None ):
		def return_error( result ):
			if cbk:
				cbk(None)
	
		def return_success( result ):
			if cbk:
				cbk(None)
				
		def check_activation(result):
			if result == None:
				return showInfoMessage( session, _('Pairing timed out!'), 10, return_error, enableInput=True)
			elif result == False:
				# aborted by user
				return showInfoMessage( session, _('Pairing aborted by user'), 10, return_error, enableInput=True)
			
			cur_time = int(time.time())
			if pairing_data['next_pool_time'] > cur_time:
				time.sleep( pairing_data['next_pool_time'] - cur_time )
			
			code = self.get_token()
			
			if code == 200:
				return showInfoMessage( session, _('Pairing succesed. You can use Trakt.tv functions now'), 10, return_success, enableInput=True)
			elif code == 400 or code == 429:
				ask_to_activate()
			else:
				return showInfoMessage( session, _('Pairing aborted by user'), 10, return_error, enableInput=True)
			
	
		def ask_to_activate():
			# request device code
			if not self.get_pairing_data():
				# timeout
				check_activation(None)
	
			msg = _("To pair Trakt.tv with this device go to the activation address and enter pairing code.\nActivation URL: {url}\nActivation code: {code}").format(url=pairing_data['verification_url'], code=pairing_data['user_code'])
			return showInfoMessage( session, msg, pairing_data['interval']+1, check_activation, enableInput=True)
			
				
		pairing_data = self.get_pairing_data()
		
		ask_to_activate()

# #################################################################################################

trakttv = trakt_tv( config.plugins.archivCZSK.trakt )
