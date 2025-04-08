# -*- coding: utf-8 -*-
import os, re, io
import traceback
from string import Template

try:
	from urlparse import urlparse
except:
	from urllib.parse import urlparse

from .logger import log
from .util import download_web_file
from Components.config import config

class VttToStr:
	"""Convert vtt to srt"""

	def __init__(self):
		pass

	def convert_header(self, contents):
		"""Convert of vtt header to srt format

		:contents -- contents of vtt file
		"""
		replacement = re.sub(r"WEBVTT\n", "", contents)
		replacement = re.sub(r"Kind:[ \-\w]+\n", "", replacement)
		replacement = re.sub(r"Language:[ \-\w]+\n", "", replacement)
		return replacement

	def add_padding_to_timestamp(self, contents):
		"""Add 00 to padding timestamp of to srt format

		:contents -- contents of vtt file
		"""
		find_srt = Template(r'$a,$b --> $a,$b(?:[ \-\w]+:[\w\%\d:,.]+)*\n')
		minute = r"((?:\d\d:){1}\d\d)"
		second = r"((?:\d\d:){0}\d\d)"
		padding_minute = find_srt.substitute(a=minute, b=r"(\d{0,3})")
		padding_second = find_srt.substitute(a=second, b=r"(\d{0,3})")
		replacement = re.sub(
			padding_minute, r"00:\1,\2 --> 00:\3,\4\n", contents)
		return re.sub(padding_second, r"00:00:\1,\2 --> 00:00:\3,\4\n", replacement)

	def convert_timestamp(self, contents):
		"""Convert timestamp of vtt file to srt format

		:contents -- contents of vtt file
		"""
		find_vtt = Template(r'$a.$b --> $a.$b(?:[ \-\w]+:[\w\%\d:,.]+)*\n')
		all_timestamp = find_vtt.substitute(
			a=r"((?:\d\d:){0,2}\d\d)", b=r"(\d{0,3})")
		return self.add_padding_to_timestamp(re.sub(all_timestamp, r"\1,\2 --> \3,\4\n", contents))

	def convert_content(self, contents):
		"""Convert content of vtt file to srt format

		:contents -- contents of vtt file
		"""
		replacement = self.convert_timestamp(contents)
		replacement = self.convert_header(replacement)
		replacement = re.sub(r"<c[.\w\d]*>", "", replacement)
		replacement = re.sub(r"</c>", "", replacement)
		replacement = re.sub(r"<\d\d:\d\d:\d\d.\d\d\d>", "", replacement)
		replacement = re.sub(
			r"::[\-\w]+\([\-.\w\d]+\)[ ]*{[.,:;\(\) \-\w\d]+\n }\n", "", replacement)
		replacement = re.sub(r"Style:\n##\n", "", replacement)
		replacement = self.remove_simple_identifiers(replacement)
		replacement = self.add_sequence_numbers(replacement)

		return replacement

	def has_timestamp(self, content):
		"""Check if line is a timestamp srt format

		:contents -- contents of vtt file
		"""
		return re.match(r"((\d\d:){2}\d\d),(\d{3}) --> ((\d\d:){2}\d\d),(\d{3})", content) is not None

	def add_sequence_numbers(self, contents):
		"""Adds sequence numbers to subtitle contents and returns new subtitle contents

		:contents -- contents of vtt file
		"""
		lines = contents.split('\n')
		out = ''
		counter = 1
		for line in lines:
			if self.has_timestamp(line):
				out += str(counter) + '\n'
				counter += 1
			out += line + '\n'
		return out

	def remove_simple_identifiers(self, contents):
		"""Remove simple identifiers of vtt file

		:contents -- contents of vtt file
		"""
		lines = contents.split('\n')
		out = []
		for i, line in enumerate(lines):
			if self.has_timestamp(line):
				if re.match(r"^\d+$", lines[i - 1]):
					out.pop()
			out.append(line)
		return '\n'.join(out)

	def write_file(self, filename, data, encoding_format="utf-8"):
		"""Create a file with some data

		:filename -- filename pat
		:data -- data to write
		:encoding_format -- encoding format
		"""
		try:
			file = open(filename, "w", encoding=encoding_format)
		except:
			file = io.open(filename, "w", encoding=encoding_format)

#		file.writelines(data)
		file.write(data)
		file.close()

	def read_file(self, filename, encoding_format = "utf-8"):
		"""Read a file text

		:filename -- filename path
		:encoding_format -- encoding format
		"""
		try:
			file = open(filename, mode="r", encoding=encoding_format)
		except:
			file = io.open(filename, mode="r", encoding=encoding_format)

		content = file.read()
		file.close()

		return content

	def process(self, filename, encoding_format = "utf-8"):
		"""Convert vtt file to a srt file

		:str_name_file -- filename path
		:encoding_format -- encoding format
		"""
		file_contents = self.read_file(filename, encoding_format)
		str_data = self.convert_content(file_contents)
		if filename.endswith('.vtt'):
			filename = filename.replace(".vtt", ".srt")
		else:
			filename = filename + ".srt"
		self.write_file(filename, str_data, encoding_format)
		return filename

def is_vtt(file):
	ret = False
	try:
		with open(file, 'r') as f:
			if 'WEBVTT' in f.readline():
				ret = True
	except:
		pass

	return ret

def download_subtitles(url):
	if not url or not url.startswith('http'):
		return url

	file_name = os.path.basename(urlparse(url).path)
	file_name = os.path.join(config.plugins.archivCZSK.tmpPath.getValue(), file_name)

	try:
		download_web_file(url, file_name)
		log.debug("Subtitles %s downloaded to %s" % (url, file_name))
	except:
		log.logError("Handle substitle file failed.\n%s" % traceback.format_exc())
		return None

	if file_name.endswith('.vtt') or is_vtt(file_name):
		log.debug("Subtitles are in WEBVTT format - converting to SRT")
		# VTT subtitles are not supported by SubSupport, so convert it to SRT
		try:
			file_name_srt = VttToStr().process(file_name)
			if file_name != file_name_srt:
				os.remove(file_name)
			file_name = file_name_srt
		except:
			log.logError("Failed to convert VTT subtitles to SRT.\n%s" % traceback.format_exc())

	return file_name
