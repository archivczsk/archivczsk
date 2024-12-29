# -*- coding: UTF-8 -*-
from .. import _, log
import traceback

from .tools.util import toString
from Screens.MessageBox import MessageBox
from Components.config import config, ConfigSelectionNumber
from Components.ActionMap import HelpableActionMap
from time import time
from .tools.stbinfo import stbinfo

try:
	from Screens.EpgSelectionGrid import EPGSelectionGrid
except ImportError:
	EPGSelectionGrid = None

try:
	from Screens.EpgSelectionSingle import EPGSelectionSingle
except ImportError:
	EPGSelectionSingle = None

try:
	from Plugins.Extensions.GraphMultiEPG.GraphMultiEpg import GraphMultiEPG
except ImportError:
	GraphMultiEPG = None

try:
	from Screens.EpgSelection import EPGSelection
except ImportError:
	EPGSelection = None

# #################################################################################################

def patch_histminutes():
	epg_viewer_history = int(config.plugins.archivCZSK.epg_viewer_history.value)
	new_history = epg_viewer_history * 24 * 60 # convert to minutes

	if isinstance(config.epg.histminutes, ConfigSelectionNumber) and (epg_viewer_history > 0):
		log.info("Patching histminutes to allow %d minutes history" % new_history)
		c = config.epg.histminutes.choices.choices

		if isinstance(c[0], type(())):
			log.debug("Patching using setSelection")
			c.append( (new_history, str(new_history),) )
			config.epg.histminutes.setSelectionList(c)
		else:
			log.debug("Patching using setChoices")
			if isinstance(c[0], str):
				c.append(str(new_history))
			else:
				c.append(new_history)

			config.epg.histminutes.setChoices(c)

	if epg_viewer_history > 0:
		config.epg.histminutes.value = new_history

		log.info("New histminutes value: %d" % int(config.epg.histminutes.value))

		try:
			if int(config.epg.maxdays.value) <= epg_viewer_history:
				config.epg.maxdays.value = int(config.epg.maxdays.value) + epg_viewer_history

			log.info("EPG maxdays is set to %d days" % int(config.epg.maxdays.value))
		except:
			pass

# #################################################################################################

def patch_show_old_epg():
	epg_viewer_history = int(config.plugins.archivCZSK.epg_viewer_history.value)
	new_history = epg_viewer_history * 24 * 3600 # convert to seconds

	if epg_viewer_history > 1:
		log.info("Patching show_old_epg to allow %d days history" % epg_viewer_history)
		c = config.usage.show_old_epg.choices.choices

		c.append( (str(new_history), '{} d'.format(epg_viewer_history), ) )
		config.usage.show_old_epg.setChoices(c)

	if epg_viewer_history > 0:
		config.usage.show_old_epg.value = str(new_history)
		log.info("New show_old_epg value: %d" % int(config.usage.show_old_epg.value))


# #################################################################################################

def inject_archive_into_epg():
	try:
		config.epg.histminutes.value
	except:
		log.debug("This image has not config.epg.histminutes option")
	else:
		patch_histminutes()

	try:
		config.usage.show_old_epg.value
	except:
		log.debug("This image has not config.usage.show_old_epg option")
	else:
		patch_show_old_epg()

	inject_play_button(EPGSelectionGrid)
	inject_play_button(EPGSelectionSingle)
	inject_play_button(EPGSelection)
	inject_play_button(GraphMultiEPG)

	try:
		if stbinfo.sw_distro == 'OpenPLi' and stbinfo.sw_distro_ver in ('9.0-release', '8.3-release'):
			log.info("Patching Open PLi's GraphMultiEPG")
			patch_pli_gmepg()
	except:
		log.error(traceback.format_exc())

	try:
		# CoolTV Guide is obfuscated, so this code is tested and will probably work only on version 8.0
		import Plugins.Extensions.CoolTVGuide.plugin as CoolTVGuide
		inject_play_button(CoolTVGuide.XMMMQX, True)
	except ImportError:
		pass
	except:
		log.error(traceback.format_exc())

# #################################################################################################

def inject_play_button(epg_component, cooltv=False):
	if epg_component is None:
		return

	original__init__ = epg_component.__init__

	def __new__init__(self, *args, **kwargs):
		original__init__(self, *args, **kwargs)
		self["ArchivCZSKArchiveActions"] = HelpableActionMap(self, "ArchivCZSKArchivePlayActions",
		{
			"play": (lambda: play_archive_entry(self, cooltv), _("Play Archive")),
		}, -2)

	epg_component.__init__ = __new__init__

# #################################################################################################

def patch_pli_gmepg():
	# Graphical Multi EPG in OpenPLi 9.0 and 8.3 is broken and can't handle history by default
	# this will patch it based on modifications from OpenPLi 9.1 to make it work

	from Plugins.Extensions.GraphMultiEPG import GraphMultiEpg
	original_selEntry = GraphMultiEpg.EPGList.selEntry

	def new_selEntry(self, dir, visible=True):
		cur_service = self.cur_service    #(service, service_name, events, picon)
		self.recalcEntrySize()
		valid_event = self.cur_event is not None
		if cur_service:
			if dir == -1: #prev
				if valid_event and self.cur_event - 1 >= 0:
					pass
				elif self.offs > 0:
					pass
				else:
					new_time = self.time_base - self.time_epoch * 60
					now = time() - int(config.epg.histminutes.value) * 60
					if new_time - now + self.time_epoch < 0:
						new_time = now - now % int(config.misc.graph_mepg.roundTo.value)
					self.fillMultiEPG(None, stime=new_time)
					return True

		return original_selEntry(self, dir, visible)

	GraphMultiEpg.EPGList.selEntry = new_selEntry

	# this part is realy ugly, but it's not possible to patch it simpler way
	def fake_time():
		return time() + (int(config.epg.histminutes.value) * 60)

	def insert_fake_time(method_name):
		orig_method = getattr(GraphMultiEPG, method_name)

		def fake_method(self, *args, **kwargs):
			GraphMultiEpg.time = fake_time
			ret = orig_method(self, *args, **kwargs)
			GraphMultiEpg.time = time
			return ret

		setattr(GraphMultiEPG, method_name, fake_method)

	insert_fake_time('__init__')
	insert_fake_time('onDateTimeInputClosed')
	insert_fake_time('setNewTime')
	insert_fake_time('onSetupClose')


# #################################################################################################

def ensure_supporter(session):
	from .license import license

	if license.check_level(license.LEVEL_SUPPORTER):
		return True

	def mbox_cbk(result):
		if result:
			from ..gui.icon import ArchivCZSKDonateScreen
			session.open(ArchivCZSKDonateScreen)

	session.openWithCallback(mbox_cbk, MessageBox, text=toString(_('This is bonus functionality available only for product supporters. Do you want to know, how to get "Supporter" status?')), type=MessageBox.TYPE_YESNO)
	return False

# #################################################################################################

def play_archive_entry(self, cooltv=False):
	from ..client.shortcut import run_shortcut
	from .httpserver import archivCZSKHttpServer
	from ..gsession import GlobalSession

	event = None
	service = None

	try:
		if cooltv:
			# obfuscated name for CoolTV Guide 8.0
			event, service = self["list"].eCJvrXlkJ()[:2]
		else:
			event, service = self["list"].getCurrent()[:2]
	except:
		log.error(traceback.format_exc())

	if not event or not service:
		return

	try:
		begin_time = int(event.getBeginTime())
		end_time = begin_time + int(event.getDuration())
	except:
		log.error("Failed to extract event start time and duration")
		return

#	log.debug("Request to play archive for service/url: (%s), (URL=%s)" % (str(event), url))
#	log.debug("Event info: start: %d, end: %d, name: %s" % (begin_time, end_time, event.getEventName()))

	if begin_time > int(time()):
		log.info("Don't try to run archive - event start time is in the future")
		return

	ref_str = str(service)

	if ensure_supporter(GlobalSession.getSession()) == False:
		return

	url = None
	if 'http%3a//' in ref_str:
		# extract url from service reference (if there's any)
		url = ref_str.split(':')[10].replace('%3a', ':')

		log.debug("Extracted url: %s" % url)

		# extract addon's http endpoint from url
		endpoint = archivCZSKHttpServer.urlToEndpoint(url)
		if not endpoint:
			return None

		log.debug("Addon's endpoint extracted from url: %s" % endpoint)
		addon = archivCZSKHttpServer.getAddonByEndpoint(endpoint)
		if not addon:
			return

		log.debug("Found addon for endpoint: %s" % addon.id)
		path = url[url.find(endpoint) + len(endpoint) + 1:].split('#')[0]
		run_shortcut(GlobalSession.getSession(), addon, 'archive', {'path': path, 'event_begin': begin_time, 'event_end': end_time}, True)
	else:
		run_shortcut(GlobalSession.getSession(), None, 'archive', {'sref': service, 'event_begin': begin_time, 'event_end': end_time}, True)
