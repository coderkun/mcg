#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""MPDCoverGrid (GTK version) is a client for the Music Player Daemon, focused on albums instead of single tracks."""

__author__ = "coderkun"
__email__ = "<olli@coderkun.de>"
__license__ = "GPL"
__version__ = "0.4"
__status__ = "Development"




import os
import sys

from gi.repository import Gtk, Gdk, GObject

from gui import gtk




# Set environment
srcdir = os.path.abspath(os.path.join(os.path.dirname(gtk.__file__), '..'))
if not os.environ.get('GSETTINGS_SCHEMA_DIR'):
	os.environ['GSETTINGS_SCHEMA_DIR'] = os.path.join(srcdir, 'data')




if __name__ == "__main__":
	# Start application
	app = gtk.Application()
	exit_status = app.run(sys.argv)
	sys.exit(exit_status)

