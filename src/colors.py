import re
from .compat import DMM_IMAGE

if DMM_IMAGE:
	# DMM doesn't need color fix
	colorFixNeeded = False

	# 0xff is for DMM not transparent - oposite of other images (a then make software portable ...)
	alphaPrefix = "FF"
else:
	alphaPrefix = "00"
	try:
		# if there is Hex2strColor, then chceck the output ...
		from Tools.Hex2strColor import Hex2strColor
		if Hex2strColor(0xffffffff) == "\c????????":
			colorFixNeeded = True # old behaviour
		else:
			colorFixNeeded = False
	except:
		# hmm, what now - how to know, if there we need to fix colors ...
		# None will be handled the same way as True
		colorFixNeeded = None


def getEscapeColorFromHexString(color):
	if color.startswith('#'):
		color = color[1:]
	if len(color) == 6:
		color = alphaPrefix + color
	if len(color) != 8:
		print('invalid color %s' % color)
		return getEscapeColorFromHexString("ffffff")
	if colorFixNeeded == False:
		return color
	colorsarray = []
	for x in color:
		if x == "0":
			# cannot pass non-printable null to string :(
			c = "1"
		else:
			c = x
		colorsarray.append(chr(int(c, 16)))
	return ''.join(colorsarray)


COLORS = {
	"red":"FF0000",
	"white":"FFFFFF",
	"cyan":"00FFFF",
	"silver":"C0C0C0",
	"blue": "0000ff",
	"gray":"808080",
	"grey": "808080",
	"darkblue": "0000A0",
	"black": "000000",
	"lightblue":"ADD8E6",
	"orange":"FFA500",
	"purple":"800080",
	"brown":"A52A2A",
	"yellow":"FFFF00",
	"maroon":"800000",
	"lime":"00FF00",
	"green":"008000",
	"magenta":"FF00FF",
	"olive":"808000"
}

COLOR_italicColor = getEscapeColorFromHexString("FCE083")
COLOR_boldColor = getEscapeColorFromHexString("FCE083")
COLOR_defaultColor = getEscapeColorFromHexString("FFFFFF")


def ConvertColorsUni(text, delete_only=False):
	def delcolor(match):
		return match.group('text')

	def uppercase(match):
		return match.group('text').upper()

	def lowercase(match):
		return match.group('text').lower()

	def customColor(match):
		color = match.group('color').lower()
		if color in COLORS:
			ftext = '\\c%s%s\\c%s' % (getEscapeColorFromHexString(COLORS[color]), match.group('text'), COLOR_defaultColor)
		else:
			ftext = '\\c%s%s' % (COLOR_defaultColor, match.group('text'))
		return ftext

	def boldColor(match):
		return '\\c%s%s\\c%s' % (COLOR_boldColor, match.group('text'), COLOR_defaultColor)

	def italicColor(match):
		return '\\c%s%s\\c%s' % (COLOR_italicColor, match.group('text'), COLOR_defaultColor)
	
	text = re.sub(r'\[UPPERCASE\](?P<text>.+?)\[/UPPERCASE\]', uppercase, text)
	text = re.sub(r'\[LOWERCASE\](?P<text>.+?)\[/LOWERCASE\]', lowercase, text)
	text = re.sub(r'\[COLOR\ (?P<color>[^\]]+)\](?P<text>.+?)\[/COLOR\]', customColor if not delete_only else delcolor, text)
	text = re.sub(r'\[B\](?P<text>.+?)\[\/B\]', boldColor if not delete_only else delcolor, text)
	text = re.sub(r'\[I\](?P<text>.+?)\[\/I\]', italicColor if not delete_only else delcolor, text)
	text = text.replace('[CR]','\n')
	return text

def ConvertColors(text):
	return ConvertColorsUni( text, False )

def DeleteColors(text):
	return ConvertColorsUni( text, True )
