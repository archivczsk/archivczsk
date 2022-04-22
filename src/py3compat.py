try:
	basestring
	is_py3 = False
	
	def py2_encode_utf8( text ):
		return text.encode('utf-8', 'ignore')
	
	def py2_decode_utf8( text ):
		return text.decode('utf-8', 'ignore')
	
except NameError:
	is_py3 = True
	unicode = str
	basestring = str
	unichr = chr
	long = int
	
	def py2_encode_utf8( text ):
		return text

	def py2_decode_utf8( text ):
		return text
