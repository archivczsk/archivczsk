import os
import stat
from zipfile import ZipFile
from .util import make_path


def _is_within_dir(directory, path):
	try:
		relative_path = os.path.relpath(os.path.realpath(path), directory)
	except ValueError:
		return False
	return relative_path == os.curdir or (
		relative_path != os.pardir and
		not relative_path.startswith(os.pardir + os.sep)
	)


def _get_destination_path(dest_dir, filename):
	if os.path.isabs(filename):
		raise ValueError("ZIP entry path is not relative: %s" % filename)

	dst_file = os.path.abspath(os.path.join(dest_dir, filename))
	if not _is_within_dir(dest_dir, dst_file):
		raise ValueError("ZIP entry path escapes destination directory: %s" % filename)
	return dst_file


def unzip_to_dir( zip_file, dest_dir ):
	dest_dir = os.path.realpath(dest_dir)
	with ZipFile( zip_file, 'r' ) as z:
		for l in z.infolist():
			dst_file = _get_destination_path(dest_dir, l.filename)
			mode = l.external_attr >> 16

			# check if it is a directory
			if l.external_attr == 16 or l.filename.endswith('/') or stat.S_ISDIR(mode):
				if not _is_within_dir(dest_dir, dst_file):
					raise ValueError("ZIP directory escapes destination directory: %s" % l.filename)
				make_path( dst_file )
			elif stat.S_ISLNK(mode):
				dst_file_dir = os.path.dirname(dst_file)
				if not os.path.isdir(dst_file_dir):
					make_path(dst_file_dir)
				if not _is_within_dir(dest_dir, dst_file_dir):
					raise ValueError("ZIP symlink path escapes destination directory: %s" % l.filename)

				link_target = z.read(l)
				if hasattr(os, 'fsdecode'):
					link_target = os.fsdecode(link_target)
				target_path = link_target if os.path.isabs(link_target) else os.path.join(dst_file_dir, link_target)
				if not _is_within_dir(dest_dir, target_path):
					raise ValueError("ZIP symlink target escapes destination directory: %s" % l.filename)

				os.symlink(link_target, dst_file)
			else:
				dst_file_dir = os.path.dirname(dst_file)
				if not os.path.isdir(dst_file_dir):
					# zip file doesn't need to contain parent directories
					make_path(dst_file_dir)

				if not _is_within_dir(dest_dir, dst_file_dir) or not _is_within_dir(dest_dir, dst_file):
					raise ValueError("ZIP file path escapes destination directory: %s" % l.filename)

				with open( dst_file, 'wb' ) as f:
					f.write( z.read(l) )

				# if we have saved permissions, then set it
				if mode != 0:
					os.chmod( dst_file, mode )
