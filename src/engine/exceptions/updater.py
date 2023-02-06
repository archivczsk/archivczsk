'''
Created on 10.3.2013

@author: marko
'''
class UpdaterException(Exception):
	pass

class UpdateXMLVersionError(UpdaterException):
	pass

class UpdateXMLDownloadError(UpdaterException):
	pass

class UpdateXMLNoUpdateUrl(UpdaterException):
	pass
