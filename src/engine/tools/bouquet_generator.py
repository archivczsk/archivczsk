import sys, os, re, io, base64
import threading, requests
from hashlib import md5

try:
	from urllib import quote
except:
	from urllib.parse import quote
	
try:
	basestring
	def py2_decode_utf8( str ):
		return str.decode('utf-8')
	
except:
	def py2_decode_utf8( str ):
		return str
	
try:
	import unidecode
	
	def strip_accents(s):
		return unidecode.unidecode(s)
except:
	import unicodedata
	
	def strip_accents(s):
		return ''.join(c for c in unicodedata.normalize('NFD', py2_decode_utf8(s)) if unicodedata.category(c) != 'Mn')

class TransponderS():
	def __init__(self):
		self.Frequency = 0x0  # In Hertz
		self.SymbolRateBPS = 0x0  # Symbol rate in bits per second.
		# 0=Horizontal, 1=Vertical, 2=Circular Left, 3=Circular right.
		self.Polarization = 0x0
		self.FEC = 0x0	# FEC_Auto=0, FEC_1_2=1, FEC_2_3=2, FEC_3_4=3, FEC_5_6=4, FEC_7_8=5, FEC_8_9=6, FEC_3_5=7, FEC_4_5=8, FEC_9_10=9, FEC_6_7=10, FEC_None=15
		# in degrees East: 130 is 13.0E, 192 is 19.2E. Negative values are West -123 is 12.3West.
		self.OrbitalPosition = 0x0
		self.Inversion = 0x0  # Inversion_Off, Inversion_On, Inversion_Unknown
		# Flags (Only in version 4): Field is absent in version 3.
		self.Flags = 0x0
		self.System = 0x0  # System_DVB_S, System_DVB_S2
		self.Modulation = 0x0  # 0 - Modulation_Auto, 1 - Modulation_QPSK, 2 - Modulation_8PSK, 3 - Modulation_QAM16, 4 - Modulation_16APSK, 5 - Modulation_32APSK
		# (Only used in DVB-S2): RollOff_alpha_0_35, RollOff_alpha_0_25, RollOff_alpha_0_20, RollOff_auto
		self.Rolloff = 0x0
		# (Only used in DVB-S2): Pilot_Off, Pilot_On, Pilot_Unknown
		self.Pilot = 0x0

	def ReadData(self, Line):
		DataLine = Line.split(":")
#		 print("Parsing line: " + Line)

		if DataLine:
			try:
				self.Frequency = int(DataLine[0])
				self.SymbolRateBPS = int(DataLine[1])
				self.Polarization = int(DataLine[2])
				self.FEC = DataLine[3]
				self.OrbitalPosition = int(DataLine[4])
				self.Inversion = int(DataLine[5])
				self.Flags = int(DataLine[6])
				self.System = int(DataLine[7])
				self.Modulation = int(DataLine[8])
				self.Rolloff = int(DataLine[9])
				self.Pilot = int(DataLine[10])
			except IndexError:
				return
		else:
			raise


class Transponder():
	def __init__(self):
		self.DVBNameSpace = 0x0
		self.TransportStreamID = 0x0
		self.OriginalNetworkID = 0x0
		# Satellite DVB ( s ), Terestrial DVB ( t ), Cable DVB ( c )
		self.Type = ''
		self.Data = None

	def ReadHeader(self, Line):
		HeaderLine = re.match(r"([\d\w]+):([\d\w]+):([\d\w]+)", Line)
		if HeaderLine:
			self.DVBNameSpace = int(HeaderLine.group(1), 16)
			self.TransportStreamID = int(HeaderLine.group(2), 16)
			self.OriginalNetworkID = int(HeaderLine.group(3), 16)
		else:
			raise

	def ReadData(self, Line):
		DataLine = re.match(r"([stc]) ([\d\w:-]+)", Line)
		if DataLine:
			self.Type = DataLine.group(1)
			if self.Type == 's':
				self.Data = TransponderS()
				self.Data.ReadData(DataLine.group(2))


class Service():
	def __init__(self):
		self.ServiceID = 0x0
		self.ServiceType = 0x0
		self.ServiceNumber = 0x0
		self.Transponder = None
		self.ChannelName = None
		self.Provider = None

	def ReadData(self, Line):
		DataLine = Line.split(":")

		if DataLine:
			try:
				self.ServiceID = int(DataLine[0], 16)
				self.ServiceType = int(DataLine[4], 16)
				self.ServiceNumber = int(DataLine[5], 16)
			except IndexError:
				return None, None, None
		return int(DataLine[1], 16), int(DataLine[2], 16), int(DataLine[3], 16)

	def ReadChannelName(self, Line):
		self.ChannelName = Line.strip()

	def ReadProvider(self, Line):
		self.Provider = Line


class lameDB():
	def __init__(self, Path):
		if Path == None:
			return
		self.Transponders = []
		self.Services = {}
		self.Open(Path)

	def getOrbitals(self):
		data = set()
		for transponder in self.Transponders:
			data.add(transponder.Data.OrbitalPosition)

		return list(data)

	def Open(self, Path):
		try:
			self._file = open(Path, encoding='utf-8', mode="r", errors='ignore')
		except:
			self._file = io.open(Path, encoding='utf-8', mode="r", errors='ignore')

		self._read()

	def _read(self):
		self._checkheader()
		self._readTranspondersSection()
		self._readServiceSection()

	def _checkheader(self):
		HeaderLine = re.match(r"eDVB services /(4)/", self._file.readline())

		if HeaderLine:
			self._version = HeaderLine.group(1)
		else:
			raise

	def _readTranspondersSection(self):
		transpondersLine = self._file.readline().strip()
		if transpondersLine != 'transponders':
			raise

		while True:
			Line = self._file.readline().strip()
			if Line == 'end':
				break

			transponder = Transponder()
			transponder.ReadHeader(Line)
			transponder.ReadData(self._file.readline().strip())

			self.Transponders.append(transponder)

			if self._file.readline().strip() != '/':
				raise

	def name_normalise( self, name ):
		name = strip_accents( name ).lower()

		name = name.replace("television", "tv")
		name = name.replace("(bonus)", "").strip()
		name = name.replace("eins", "1")
		
		if name.endswith(" hd"):
			name = name[:name.rfind(" hd")]

		if name.endswith(" tv"):
			name = name[:name.rfind(" tv")]
		
		if name.startswith("tv "):
			name = name[3:]

		if name.endswith(" channel"):
			name = name[:name.rfind(" channel")]

		name = name.replace("&", " and ").replace("'", "").replace(".", "").replace(" ", "")
		return name

	def _readServiceSection(self):
		transpondersLine = self._file.readline().strip()
		if transpondersLine != 'services':
			raise

		while True:
			Line = self._file.readline().strip()
			if Line == 'end':
				break

			service = Service()
			DVBNameSpace, TransportStreamID, OriginalNetworkID = service.ReadData(
				Line)

			service.ReadChannelName(self._file.readline().strip())
			service.ReadProvider(self._file.readline().strip())

			for transponder in self.Transponders:
				if transponder.DVBNameSpace == DVBNameSpace and transponder.TransportStreamID == TransportStreamID and transponder.OriginalNetworkID == OriginalNetworkID:
					service.Transponder = transponder
					break

			if service.Transponder == None:
				continue

			name = self.name_normalise( service.ChannelName )
			
			if name not in self.Services:
				self.Services[name] = []
				
			self.Services[name].append(service)
		return


class BouquetGeneratorTemplate:
	def __init__(self, endpoint):
		# configuration to make this class little bit reusable also in other addons
		self.proxy_url = endpoint
		self.userbouquet_file_name = "userbouquet.%s.tv" % self.prefix
		# Child class must define these values 
#		self.prefix = "o2tv"
#		self.name = "O2TV"
#		self.sid_start = 0xE000
#		self.tid = 5
#		self.onid = 2
#		self.namespace = 0xE030000
	
	@staticmethod
	def download_picons(picons):
		if not os.path.exists( '/usr/share/enigma2/picon' ):
			os.mkdir('/usr/share/enigma2/picon')
			
		for ref in picons:
			if not picons[ref].endswith('.png'):
				continue
			
			fileout = '/usr/share/enigma2/picon/' + ref + '.png'
			
			if not os.path.exists(fileout):
				try:
					r = requests.get( picons[ref], timeout=5 )
					if r.status_code == 200:
						with open(fileout, 'wb') as f:
							f.write( r.content )
				except:
					pass
				
	def reload_bouquets(self):
		try:
			requests.get("http://127.0.0.1/web/servicelistreload?mode=2")
		except:
			pass

	def userbouquet_exists(self):
		return os.path.exists( "/etc/enigma2/" + self.userbouquet_file_name )
	
	def userbouquet_remove(self):
		if not self.userbouquet_exists():
			return False
		
		ub_service_ref = '#SERVICE 1:7:1:0:0:0:0:0:0:0:FROM BOUQUET "' + self.userbouquet_file_name + '" ORDER BY bouquet'
		
		with open( "/etc/enigma2/bouquets.tv.temporary", "w" ) as fw:
			with open( "/etc/enigma2/bouquets.tv", "r" ) as f:
				for line in f.readlines():
					if not line.startswith(ub_service_ref):
						fw.write(line)
				os.rename("/etc/enigma2/bouquets.tv.temporary", "/etc/enigma2/bouquets.tv")
		
		os.remove( "/etc/enigma2/" + self.userbouquet_file_name )
		self.reload_bouquets()
		return True
	def userbouquet_md5(self):
		hash_md5 = md5()
		
		try:
			with open("/etc/enigma2/" + self.userbouquet_file_name, "rb") as f:
				for chunk in iter(lambda: f.read(4096), b""):
					hash_md5.update(chunk)
	
			return hash_md5.hexdigest()
		except:
			pass
		
		return None

	def build_service_ref( self, service, player_id ):
		return player_id + ":0:{:X}:{:X}:{:X}:{:X}:{:X}:0:0:0:".format( service.ServiceType, service.ServiceID, service.Transponder.TransportStreamID, service.Transponder.OriginalNetworkID, service.Transponder.DVBNameSpace )


	def service_ref_get( self, lamedb, channel_name, player_id, channel_id ):
		
		skylink_freq = [ 11739, 11778, 11856, 11876, 11934, 11954, 11973, 12012, 12032, 12070, 12090, 12110, 12129, 12168, 12344, 12363 ]
		antik_freq = [ 11055, 11094, 11231, 11283, 11324, 11471, 11554, 11595, 11637, 12605 ]
		
		def cmp_freq( f, f_list ):
			f = int(f/1000)
			
			for f2 in f_list:
				if abs( f - f2) < 5:
					return True
		
			return False
	
		if lamedb != None:
			try:
				services = lamedb.Services[ lamedb.name_normalise( channel_name ) ]
				
				# try position 23.5E first
				for s in services:
					if s.Transponder.Data.OrbitalPosition == 235 and cmp_freq( s.Transponder.Data.Frequency, skylink_freq ):
						return self.build_service_ref(s, player_id)
		
				# then 16E
				for s in services:
					if s.Transponder.Data.OrbitalPosition == 160 and cmp_freq( s.Transponder.Data.Frequency, antik_freq ):
						return self.build_service_ref(s, player_id)
		
				for s in services:
					if s.Transponder.Data.OrbitalPosition == 235:
						return self.build_service_ref(s, player_id)
		
				# then 16E
				for s in services:
					if s.Transponder.Data.OrbitalPosition == 160:
						return self.build_service_ref(s, player_id)
		
				# then 0,8W
				for s in services:
					if s.Transponder.Data.OrbitalPosition == -8:
						return self.build_service_ref(s, player_id)
		
				# then 192
				for s in services:
					if s.Transponder.Data.OrbitalPosition == 192:
						return self.build_service_ref(s, player_id)
		
				# take the first one
				for s in services:
					return self.build_service_ref(s, player_id)
		
			except:
				pass
		
		return player_id + ":0:1:%X:%X:%X:%X:0:0:0:" % (self.sid_start + channel_id, self.tid, self.onid, self.namespace)
	
	
	def generate_bouquet(self, channels, enable_adult=True, enable_xmlepg=False, enable_picons=False, player_name="0"):
		current_chsum = self.userbouquet_md5()
		
		# if epg generator is disabled, then try to create service references based on lamedb
		if enable_xmlepg:
			lamedb = None
		else:
			lamedb = lameDB("/etc/enigma2/lamedb")
		
		if player_name == "1": # gstplayer
			player_id = "5001"
		elif player_name == "2": # exteplayer3
			player_id = "5002"
		elif player_name == "3": # DMM
			player_id = "8193"
		elif player_name == "4": # DVB service (OE >=2.5)
			player_id = "1"
		else:
			player_id = "4097" # system default
	
		file_name = "userbouquet.%s.tv" % self.prefix
		
		picons = {}
		
		service_ref_uniq = ':%X:%X:%X:0:0:0:' % (self.tid, self.onid, self.namespace)
		
		bdata = "#NAME %s\n" % self.name
		
		for channel in channels:
			if not enable_adult and channel['adult']:
				continue
			
			channel_name = channel['name']
			url = self.proxy_url + '/playlive/' + base64.b64encode( channel['key'].encode('utf-8') ).decode('utf-8')
			url = quote( url )
			
			service_ref = self.service_ref_get( lamedb, channel_name, player_id, channel['id'] )

			bdata += "#SERVICE " + service_ref + url + ":" + channel_name + "\n"
			bdata += "#DESCRIPTION " + channel_name + "\n"
			
			try:
				if enable_picons and service_ref.endswith( service_ref_uniq ):
					picons[ service_ref[:-1].replace(':', '_') ] = channel['picon']
			except:
				pass
		
		if md5( bdata.encode('utf-8') ).hexdigest() != current_chsum:
			with open( "/etc/enigma2/" + self.userbouquet_file_name, "w" ) as f:
				f.write(bdata)

			first_export = True
			with open( "/etc/enigma2/bouquets.tv", "r" ) as f:
				for line in f.readlines():
					if self.userbouquet_file_name in line:
						first_export = False
						break
			
			if first_export:
				with open( "/etc/enigma2/bouquets.tv", "a" ) as f:
					f.write( '#SERVICE 1:7:1:0:0:0:0:0:0:0:FROM BOUQUET "' + self.userbouquet_file_name + '" ORDER BY bouquet' + "\n" )
		
			self.reload_bouquets()
			ret = True
		else:
			ret = False
			
		if enable_picons:
			threading.Thread(target=BouquetGeneratorTemplate.download_picons,args=(picons,)).start()
		
		return ret
