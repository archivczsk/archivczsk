# -*- coding: utf-8 -*-
"""
  monotonic
  ~~~~~~~~~

  This module provides a ``monotonic()`` function which returns the
  value (in fractional seconds) of a clock which never goes backwards.

  On Python 3.3 or newer, ``monotonic`` will be an alias of
  ``time.monotonic`` from the standard library. On older versions,
  it will fall back to an equivalent implementation:

  +-------------+----------------------------------------+
  | Linux, BSD  | ``clock_gettime(3)``                   |
  +-------------+----------------------------------------+

  If no suitable implementation exists for the current platform,
  attempting to import this module (or to import from it) will
  cause a ``RuntimeError`` exception to be raised.


  Copyright 2014, 2015, 2016 Ori Livneh <ori@wikimedia.org>

  Licensed under the Apache License, Version 2.0 (the "License");
  you may not use this file except in compliance with the License.
  You may obtain a copy of the License at

	http://www.apache.org/licenses/LICENSE-2.0

  Unless required by applicable law or agreed to in writing, software
  distributed under the License is distributed on an "AS IS" BASIS,
  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
  See the License for the specific language governing permissions and
  limitations under the License.

"""
import time


__all__ = ('monotonic',)


try:
	monotonic = time.monotonic
except AttributeError:
	import ctypes
	import ctypes.util
	import os
	try:
		try:
			clock_gettime = ctypes.CDLL(ctypes.util.find_library('c'),
										use_errno=True).clock_gettime
		except Exception:
			clock_gettime = ctypes.CDLL(ctypes.util.find_library('rt'),
										use_errno=True).clock_gettime

		class timespec(ctypes.Structure):
			"""Time specification, as described in clock_gettime(3)."""
			_fields_ = (('tv_sec', ctypes.c_long),
						('tv_nsec', ctypes.c_long))

		def monotonic():
			"""Monotonic clock, cannot go backward."""
			ts = timespec()
			if clock_gettime(1, ctypes.pointer(ts)):
				errno = ctypes.get_errno()
				raise OSError(errno, os.strerror(errno))
			return ts.tv_sec + ts.tv_nsec / 1.0e9

		# Perform a sanity-check.
		if monotonic() - monotonic() > 0:
			raise ValueError('monotonic() is not monotonic!')

	except Exception as e:
		raise RuntimeError('no suitable implementation for this system: ' + repr(e))
