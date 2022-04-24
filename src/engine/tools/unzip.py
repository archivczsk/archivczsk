from zipfile import ZipFile
import os, errno

try:
	FileExistsError
	
	def check_EEXIST(e):
		return True
except:
	# py2 workaround
	FileExistsError = OSError
	
	def check_EEXIST(e):
		return e.errno == errno.EEXIST

		def __init__(self, msg):
			super(FileExistsError, self).__init__(errno.EEXIST, msg)

def unzip_to_dir( zip_file, dest_dir ):
	with ZipFile( zip_file, 'r' ) as z:
		for l in z.infolist():
			dst_file = os.path.join( dest_dir, l.filename )
	
			# check if it is a directory
			if l.external_attr == 16 or l.filename.endswith('/'):
				try:
					os.makedirs( dst_file )
				except FileExistsError as e:
					if check_EEXIST(e):
						pass
			else:
				with open( dst_file, 'wb' ) as f:
					f.write( z.read(l.filename) )
				
				# if we have saved permissions, then set it
				if (l.external_attr >> 16) != 0:
					os.chmod( dst_file, (l.external_attr >> 16) )
