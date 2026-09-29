# -*- coding: utf-8 -*-
from __future__ import absolute_import

import ctypes
import os
import sys
import types
from ..tools.stbinfo import stbinfo

_PAYLOAD_MAGIC = b"&PYME1"

class EncryptedModuleError(ImportError):
	pass


try:
	_NATIVE = ctypes.PyDLL(os.path.join(os.path.dirname(__file__), "_loader_%s.so" % stbinfo.hw_arch))
except OSError as error:
	raise EncryptedModuleError("cannot load encrypted-module loader: %s" % error)

_NATIVE.execute_file.argtypes = [ctypes.c_char_p, ctypes.py_object]
_NATIVE.execute_file.restype = ctypes.c_int


def _execute_source(module, payload_path):
	if not isinstance(payload_path, bytes):
		payload_path = payload_path.encode(sys.getfilesystemencoding() or "utf-8")
	result = _NATIVE.execute_file(payload_path, module.__dict__)
	if result != 0:
		messages = {
			1: "cannot read encrypted module",
			2: "invalid encrypted module format",
			3: "encrypted module authentication failed",
			4: "not enough memory to decrypt module",
			5: "encrypted module compilation or execution failed",
			6: "required runtime components are unavailable",
		}
		raise EncryptedModuleError(messages.get(result, "encrypted loader failure"))


class _EncryptedModuleFinder(object):
	def __init__(self):
		self._pending = {}

	@staticmethod
	def _has_payload_magic(payload_path):
		if not os.path.isfile(payload_path):
			return False
		try:
			with open(payload_path, "rb") as payload_file:
				return payload_file.read(len(_PAYLOAD_MAGIC)) == _PAYLOAD_MAGIC
		except (IOError, OSError):
			return False

	def _find_payload(self, fullname, path=None):
		module_name = fullname.rsplit(".", 1)[-1]
		search_path = sys.path if path is None else path
		for directory in search_path:
			root = os.path.abspath(directory or os.getcwd())
			package_payload = os.path.join(root, module_name, "__init__.pye")
			if self._has_payload_magic(package_payload):
				return package_payload, True
			module_payload = os.path.join(root, module_name + ".pye")
			if self._has_payload_magic(module_payload):
				return module_payload, False
		return None

	def _remember_payload(self, fullname, path=None):
		payload = self._find_payload(fullname, path)
		if payload is not None:
			self._pending[fullname] = payload
		return payload

	def _payload(self, fullname):
		payload = self._pending.get(fullname)
		if payload is None:
			payload = self._find_payload(fullname)
		if payload is None:
			raise EncryptedModuleError("encrypted module not found: %s" % fullname)
		return payload

	def find_module(self, fullname, path=None):
		if self._remember_payload(fullname, path) is not None:
			return self
		return None

	def load_module(self, fullname):
		payload_path, is_package = self._payload(fullname)
		if fullname in sys.modules:
			return sys.modules[fullname]
		module = types.ModuleType(fullname)
		module.__file__ = payload_path
		module.__loader__ = self
		module.__package__ = fullname if is_package else fullname.rpartition(".")[0]
		if is_package:
			module.__path__ = [os.path.dirname(payload_path)]
		sys.modules[fullname] = module
		try:
			_execute_source(module, payload_path)
		except Exception:
			sys.modules.pop(fullname, None)
			raise
		finally:
			self._pending.pop(fullname, None)
		return module

	def find_spec(self, fullname, path=None, target=None):
		payload = self._remember_payload(fullname, path)
		if payload is None:
			return None
		payload_path, is_package = payload
		from importlib.util import spec_from_loader
		return spec_from_loader(fullname, self, origin=payload_path, is_package=is_package)

	def create_module(self, spec):
		return None

	def exec_module(self, module):
		payload_path, is_package = self._payload(module.__name__)
		module.__file__ = payload_path
		if is_package:
			module.__path__ = [os.path.dirname(payload_path)]
		try:
			_execute_source(module, payload_path)
		finally:
			self._pending.pop(module.__name__, None)


def install_encrypted_loader():
	for finder in sys.meta_path:
		if isinstance(finder, _EncryptedModuleFinder):
			return

	sys.meta_path.append(_EncryptedModuleFinder())

def uninstall_encrypted_loader():
	for finder in sys.meta_path:
		if isinstance(finder, _EncryptedModuleFinder):
			sys.meta_path.remove(finder)
			return
