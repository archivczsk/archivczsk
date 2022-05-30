from Plugins.Extensions.archivCZSK import _, log
from Plugins.Extensions.archivCZSK.engine.tools.util import toString
from Screens.ChoiceBox import ChoiceBox

def open_trakt_action_choicebox(session, item, cmdTrakt):
	def getListInputCB(selected=None):
		if selected is not None:
			cmdTrakt(item, choice_list[selected[0]])

	choice_list = {
		_('Add to watchlist'): 'add',
		_('Delete from watchlist'): 'remove',
		_('Mark as watched'): 'watched',
		_("Mark as not watched"): 'unwatched'
	}
	newlist = [ (name,) for name in choice_list.keys()]
	session.openWithCallback(getListInputCB, ChoiceBox, toString( _("Choose Trakt.tv action")), newlist, skin_name="ArchivCZSKChoiceBox")
