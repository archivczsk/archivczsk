import os

from Screens.Screen import Screen
from Components.ActionMap import ActionMap
from Components.Pixmap import Pixmap
from ..settings import IMAGE_PATH
from ..compat import eConnectCallback
from enigma import ePicLoad, getDesktop

class IconD(Screen):
	def __init__(self, session):
		whatWidth = getDesktop(0).size().width()

		if whatWidth >= 3000:
			self.skin = """
				<screen position="center,center" size="3840,2160" backgroundColor="#002C2C39">
					<widget name="myPic" position="center,center" size="3000,1860" zPosition="11" alphatest="on" />
				</screen>"""
			self.picPath = os.path.join(IMAGE_PATH, 'icon4k.png')
		elif whatWidth >= 2500:
			self.skin = """
				<screen position="center,center" size="2560,1440" backgroundColor="#002C2C39">
					<widget name="myPic" position="center,center" size="2000,1240" zPosition="11" alphatest="on" />
				</screen>"""
			self.picPath = os.path.join(IMAGE_PATH, 'icon3k.png')
		elif whatWidth >= 1900:
			self.skin = """
				<screen position="center,center" size="1920,1080" backgroundColor="#002C2C39">
					<widget name="myPic" position="center,center" size="1500,930" zPosition="11" alphatest="on" />
				</screen>"""
			self.picPath = os.path.join(IMAGE_PATH, 'icon2k.png')
		else:
			self.skin = """
				<screen position="center,center" size="1280,720" backgroundColor="#002C2C39">
					<widget name="myPic" position="center,center" size="1000,620" zPosition="11" alphatest="on" />
				</screen>"""
			self.picPath = os.path.join(IMAGE_PATH, 'icon.png')

		Screen.__init__(self, session)
		self.PicLoad = ePicLoad()
		self["myPic"] = Pixmap()
		self["actions"] = ActionMap(["OkCancelActions"], {
			"ok": self.close,
			"cancel": self.close
		}, -1)
		self.picLoad_conn = eConnectCallback(self.PicLoad.PictureData, self.DecodePicture)
		self.onLayoutFinish.append(self.ShowPicture)
		self.onClose.append(self.__onClose)

	def ShowPicture(self):
		if self.picPath is not None:
			self.PicLoad.setPara([
						self["myPic"].instance.size().width(),
						self["myPic"].instance.size().height(),
						100,
						100,
						0,
						1,
						"#002C2C39"])
			self.PicLoad.startDecode(self.picPath)

	def DecodePicture(self, PicInfo = ""):
		if self.picPath is not None:
			ptr = self.PicLoad.getData()
			self["myPic"].instance.setPixmap(ptr)

	def __onClose(self):
		del self.picLoad_conn
		del self.PicLoad
