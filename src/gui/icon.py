# -*- coding: UTF-8 -*-
import os

from Components.ActionMap import ActionMap
from Components.Pixmap import Pixmap
from Components.Label import Label
from Tools.LoadPixmap import LoadPixmap
from Components.config import config
from Components.AVSwitch import AVSwitch
from .base import BaseArchivCZSKListSourceScreen, BaseArchivCZSKScreen
from .common import toString
from ..settings import IMAGE_PATH
from ..compat import eCompatPicLoad, eCompatTimer
from ..engine.tools.lang import _
from ..engine.tools.logger import log
from ..engine.tools import util
from ..engine.tools.stbinfo import stbinfo
from ..engine.license import ArchivCZSKLicense
try:
	from ..engine.tools.monotonic import monotonic
except:
	from time import time as monotonic

class ArchivCZSKDonateScreen(BaseArchivCZSKListSourceScreen):
	def __init__(self, session, countdown=0):
		BaseArchivCZSKListSourceScreen.__init__(self, session)
		self.session = session
		self.license = ArchivCZSKLicense.get_instance()
		self.countdown = countdown

		self.countdown_tick_timer = eCompatTimer(self.countdown_tick)

		self.price = {
			'czk': (25, ' CZK'),
			'eur': (1, '€'),
		}

		if config.plugins.archivCZSK.colored_items.value:
			price_fmt = '[B]{}{}[/B]'
		else:
			price_fmt = '{}{}'

		self.pay_choices_list = [
			('cz', _('Send donation {price} from Czech republic').format(price=price_fmt.format(*self.price['czk']))),
			('sk', _('Send donation {price} from Slovakia').format(price=price_fmt.format(*self.price['eur']))),
			('eu', _('Send donation {price} from EU').format(price=price_fmt.format(*self.price['eur']))),
		]

		self["info_title"] = Label(_('Donation for ArchivCZSK project'))

		self["info_label_h1"] = Label(_('Why donate?'))
		self["info_label1"] = Label(_('Development, maintenance and addons functionality improvement is very time consuming process. Your donation allows project continuation.'))

		self["info_label_h2"] = Label(_('How much to donate?'))
		self["info_label2"] = Label(_('For the symbolic sum {sum_czk}/{sum_eur} a month you will get "Supporter" status for your receiver.').format(sum_czk='{}{}'.format(*self.price['czk']), sum_eur='{}{}'.format(*self.price['eur'])))

		self["info_label_h3"] = Label(_('Will I get any bonus?'))
		self["info_label3"] = Label(_('Basic functionality is available for free. Supporters will get bonus functionality and addons, which will gradually expand.'))

		self["info_label_h4"] = Label(_('I am interested. How to donate?'))
		self["info_label4"] = Label(_('Using the menu bellow, display unique payment QR code for your receiver. "Supporter" status will be automatically activated after crediting the payment to the bank account.'))

		self["donate_menu_title"] = Label(_("Select how do you want to send donation"))

		self["donate_status_label"] = Label(_('"Supporter" status:'))
		self["donate_result_yes"] = Label(_("Active"))
		self["donate_result_no"] = Label()
		self["donate_validity"] = Label()
		self.update_license_status()

		self["actions"] = ActionMap(["archivCZSKActions"],
				{
				"ok": self.ok,
				"cancel": self.cancel,
				"up": self.up,
				"down": self.down,
				"left": self.home,
				"right": self.end,
				}, -2)

		self.onShown.append(self.updateTitle)
		self.onShown.append(self.setup_countdown)
		self.onClose.append(self.__onClose)

		if self.license.get_aes_module():
			self.check_license()

	def update_license_status(self):
		if self.license.get_aes_module() == None:
			self["donate_result_yes"].hide()
			self["donate_result_no"].setText(_("Error"))
			self["donate_validity"].setText(_("Reinstall ArchivCZSK to resolve problem"))
			self["donate_result_no"].show()
			self["donate_validity"].show()
		else:
			if self.license.is_valid():
				self["donate_result_no"].hide()
				self["donate_validity"].setText(_("(Bonuses activated until {date})").format(date=self.license.valid_to()))
				self["donate_validity"].show()
				self["donate_result_yes"].show()
			else:
				self["donate_validity"].hide()
				self["donate_result_yes"].hide()
				self["donate_result_no"].setText(_("Inactive"))
				self["donate_result_no"].show()


	def updateTitle(self):
		if self.countdown > 0:
			self.title = _("ArchivCZSK Donate") + ' ({})'.format(self.countdown)
		else:
			self.title = _("ArchivCZSK Donate")

	def updateMenuList(self, index=0):
		self["menu"].list = [
			(
				LoadPixmap(os.path.join(IMAGE_PATH, item[0] + 'qr_small.png')),
				toString(item[1])
			) for item in self.pay_choices_list
		]

		self["menu"].index = index

	def setup_countdown(self):
		if self.countdown > 0:
			self.countdown_tick_timer.start(1000, True)

	def countdown_tick(self):
		self.countdown = self.countdown - 1
		self.updateTitle()
		self.setup_countdown()

	def ok(self):
		pay_type = self.pay_choices_list[self["menu"].index][0]
		log.debug("Pay type selected: %s" % pay_type)
		self.session.open(ArchivCZSKPaymentScreen, pay_type=pay_type)

	def cancel(self):
		if self.countdown <= 0:
			self.close(None)

	def __onClose(self):
		self.countdown_tick_timer.stop()
		del self.countdown_tick_timer

	def check_license(self):
		def __update_license_status(success, result):
			log.debug("License refreshed with response: %s" % success)
			if success:
				self.update_license_status()

		log.debug("Starting task that will refresh the license in background")
		self.license.bgservice.run_task('task(LicRefresh)', __update_license_status, self.license.refresh_license)


class ArchivCZSKPaymentScreen(BaseArchivCZSKScreen):
	def __init__(self, session, pay_type):
		BaseArchivCZSKScreen.__init__(self, session)
		self.session = session
		self.pay_type = pay_type
		self.screen_time = None

		if pay_type == 'sk':
			title2 = _("It is compatible with slovak bank applications.")
		elif pay_type == 'cz':
			title2 = _("It is compatible with czech bank applications.")
		elif pay_type == 'eu':
			title2 = _("It is compatible bank applications supporting EPC/GiroCode format.")

		self["info_title1"] = Label(_('Scan this QR code using your bank application on your mobile phone.'))
		self["info_title2"] = Label(title2)
		self["footer"] = Label(_('Supporter status will be automatically activated after receiving payment. If you send instant payment, it will be activated within an hour. If you send standard transfer, it will be activated on next business day.'))

		self["qrimage"] = Pixmap()
		self.PicLoad = eCompatPicLoad(self.DecodePicture)

		self["actions"] = ActionMap(["OkCancelActions"], {
			"ok": self.close,
			"cancel": self.close
		}, -1)

		self.onLayoutFinish.append(self.download_qr)
		self.onShown.append(self.updateTitle)
		self.onShown.append(self.windowShown)
		self.onClose.append(self.windowClosed)

	def windowShown(self):
		self.screen_time = int(monotonic())

	def windowClosed(self):
		if self.screen_time != None:
			payment_screen_time = int(monotonic()) - self.screen_time
			if payment_screen_time > 10:
				log.info("Payment screen time was {}s - enabling extra license checks for next 24 hours".format(payment_screen_time))
				ArchivCZSKLicense.get_instance().enable_extra_checks()

		del self.PicLoad


	def updateTitle(self):
		self.title = _("Payment information")

	def cancel(self):
		self.close(None)

	def DecodePicture(self, PicInfo = ""):
		ptr = self.PicLoad.getData()
		self["qrimage"].instance.setPixmap(ptr)

	def ShowPicture(self, picPath):
		self["qrimage"].instance.setPixmap(LoadPixmap(picPath))

	def _image_downloaded(self, url, path):
		if path is None:
			return

		# OpenPLi, OpenATV, ... can directly show downloaded PNG using LoadPixmap(). They also support 1-bit PNG. But we have also VTi where it doesn't show anything and 1-bit PNGs are not supported.
		# So ePicload() is a must here ...
#		self.ShowPicture(path)
		sc = AVSwitch().getFramebufferScale()
		self.PicLoad.setPara([
					self["qrimage"].instance.size().width(),
					self["qrimage"].instance.size().height(),
					sc[0],
					sc[1],
					False,
					1,
					"#FF000000"])
		self.PicLoad.startDecode(path)

	def download_qr(self):
		png_file = os.path.join(config.plugins.archivCZSK.tmpPath.value, 'archivczsk_pay_{}.png'.format(self.pay_type))

		if os.path.isfile(png_file):
			return self._image_downloaded(None, png_file)

		png_url = 'http://archivczsk.webredirect.org/qr/{}/{}.png'.format(self.pay_type, stbinfo.installation_id)

		from ..version import version
		headers = {"User-Agent": 'ArchivCZSK/' + version }
		util.download_to_file_async(toString(png_url), png_file, self._image_downloaded, headers=headers, timeout=5)
		return None
