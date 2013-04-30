#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""MPDCoverGrid (GTK version) is a client for the Music Player Daemon, focused on albums instead of single tracks."""

__author__ = "coderkun"
__email__ = "<olli@coderkun.de>"
__license__ = "GPL"
__version__ = "0.3"
__status__ = "Development"




from gi.repository import Gtk, Gdk, GObject

import gui.gtk


if __name__ == "__main__":
	GObject.threads_init()
	Gdk.threads_init()
	mcgg = gui.gtk.MCGGtk()
	mcgg.show_all()
	try:
		Gtk.main()
	except (KeyboardInterrupt, SystemExit):
		pass

