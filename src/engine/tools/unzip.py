from zipfile import ZipFile
import os
from .util import make_path

def unzip_to_dir( zip_file, dest_dir ):
	with ZipFile( zip_file, 'r' ) as z:
		for l in z.infolist():
			dst_file = os.path.join( dest_dir, l.filename )

			# check if it is a directory
			if l.external_attr == 16 or l.filename.endswith('/'):
				make_path( dst_file )
			else:
				dst_file_dir = os.path.dirname(dst_file)
				if not os.path.isdir(dst_file_dir):
					# zip file doesn't need to contain parent directories
					make_path(dst_file_dir)

				with open( dst_file, 'wb' ) as f:
					f.write( z.read(l.filename) )

				# if we have saved permissions, then set it
				if (l.external_attr >> 16) != 0:
					os.chmod( dst_file, (l.external_attr >> 16) )
