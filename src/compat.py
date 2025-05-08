'''
Created on Feb 19, 2015

@author: marko

'''

from Components.MenuList import MenuList
from Screens.MessageBox import MessageBox as OrigMessageBox

from enigma import eTimer, ePicLoad, ePythonMessagePump

from skin import parseSize as __parseSize
from skin import parsePosition as __parsePosition

from .engine.tools.stbinfo import stbinfo
DMM_IMAGE = stbinfo.is_dmm_image
VTI_IMAGE = stbinfo.is_vti_image

def parseSize(s, scale, object = None, desktop = None):
	if VTI_IMAGE:
		return __parseSize(s, scale)
	if DMM_IMAGE:
		return __parseSize(s, scale, desktop, object)
	return __parseSize(s, scale, object, desktop)

def parsePosition(s, scale, object = None, desktop = None, size = None):
	if VTI_IMAGE:
		return __parsePosition(s, scale, desktop, size)
	if DMM_IMAGE:
		return __parsePosition(s, scale, desktop, object)
	return __parsePosition(s, scale, object, desktop, size)


# taken from IPTVPlayer
class eConnectCallbackObj:
	def __init__(self, obj=None, connectHandler=None):
		self.connectHandler = connectHandler
		self.obj = obj

	def __del__(self):
		if 'connect' not in dir(self.obj):
			if 'get' in dir(self.obj):
				self.obj.get().remove(self.connectHandler)
			else:
				self.obj.remove(self.connectHandler)
		else:
			del self.connectHandler
		self.connectHandler = None
		self.obj = None

# taken from IPTVPlayer
def eConnectCallback(obj, callbackFun):
	if 'connect' in dir(obj):
		return eConnectCallbackObj(obj, obj.connect(callbackFun))
	else:
		if 'get' in dir(obj):
			obj.get().append(callbackFun)
		else:
			obj.append(callbackFun)
		return eConnectCallbackObj(obj, callbackFun)

class eCompatWrapper(object):
	def __init__(self, callbackFun):
		self.t = self.__class__.COMPAT_OBJECT()
		self.callbackFun = callbackFun

		obj = getattr(self.t, self.__class__.CALLBACK_MEMBER)

		if 'connect' in dir(obj):
			self.conn_obj = obj.connect(callbackFun)
		elif 'get' in dir(obj):
			obj.get().append(callbackFun)
		else:
			obj.append(callbackFun)

	def __del__(self):
		obj = getattr(self.t, self.CALLBACK_MEMBER)
		if 'connect' in dir(obj):
			try:
				del self.conn_obj
			except:
				pass
		elif 'get' in dir(obj):
			obj.get().remove(self.callbackFun)
		else:
			obj.remove(self.callbackFun)

		self.callbackFun = None
		del self.t

	def __getattr__(self, name):
		return getattr(self.t, name)

class eCompatTimer(eCompatWrapper):
	COMPAT_OBJECT = eTimer
	CALLBACK_MEMBER = 'timeout'

class eCompatPicLoad(eCompatWrapper):
	COMPAT_OBJECT = ePicLoad
	CALLBACK_MEMBER = 'PictureData'

class eCompatPythonMessagePump(eCompatWrapper):
	COMPAT_OBJECT = ePythonMessagePump
	CALLBACK_MEMBER = 'recv_msg'


class MessageBox(OrigMessageBox):
	def __init__(self, *args, **kwargs):
		list = None
		self.dmm_fix = False
		import inspect
		try:
			argspec = inspect.getargspec(OrigMessageBox.__init__)
		except:
			argspec = inspect.getfullargspec(OrigMessageBox.__init__)

		if kwargs.get('list') is not None and ('list' not in argspec.args):
			list = kwargs.pop('list')
			self.dmm_fix = True

		# check arguments and remove one if it's not supported by enigma's MessageBox
		for a in kwargs.keys():
			if a not in argspec.args:
				del kwargs[a]

		OrigMessageBox.__init__(self, *args, **kwargs)
		# this is taylored solution for DMM based images, so it might crash elsewhere
		# or when dreambox changes something in MessageBox
		if list:
			self.list = list
			self["selectedChoice"].setText(self.list[0][0])
			self["list"] = MenuList(self.list)

	def ok(self):
		if self.dmm_fix:
			if self.list:
					self.close(self["list"].getCurrent()[1])
			else:
					self.close(True)
		else:
			OrigMessageBox.ok(self)
