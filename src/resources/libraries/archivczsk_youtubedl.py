import json
import sys
import os

from sys import stdin, stdout
import struct

def getRequest():
	data_size = struct.unpack('!I', stdin.read(4) )[0]
	data = stdin.read(data_size)
	return json.loads(data)

def sendResponse(response):
	dump = json.dumps(response).encode('ascii')
	os.write( stdout.fileno(), struct.pack('!I', len(dump)) + dump )
	stdout.flush()

def mainLoop():
	info = {'type': 'info', 'status':True, 'version': '', 'exception': None}
	try:
		import youtube_dl
		options = {'quiet': True}
		ydl = youtube_dl.YoutubeDL(options)
		sendResponse(info)
	except Exception as e:
		info['status'] = False
		info['exception'] = str(e)
		sendResponse(info)
		exit(1)

	while True:
		request = getRequest()
		if request:
			response = {'type':'request', 'status':False, 'result':None, 'exception':None}
			try:
				result = ydl.extract_info(request['url'], False)
				response['status'] = True
				response['result'] = result
			except Exception as e:
				response['exception'] = str(e)
			sendResponse(response)

if __name__ == "__main__":
	ydl_lib = os.path.dirname(os.path.realpath(__file__))
	sys.path.append(ydl_lib)
	mainLoop()
