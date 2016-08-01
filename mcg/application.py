#!/usr/bin/env python3


import gi
gi.require_version('Gtk', '3.0')
import urllib

from gi.repository import Gio, Gtk, Gdk

from mcg import widgets




class Application(Gtk.Application):
    TITLE = "MPDCoverGrid (Gtk)"
    SETTINGS_BASE_KEY = 'de.coderkun.mcg'


    def __init__(self):
        Gtk.Application.__init__(self, application_id="de.coderkun.mcg-dev", flags=Gio.ApplicationFlags.FLAGS_NONE)
        self._window = None


    def do_startup(self):
        Gtk.Application.do_startup(self)
        self._settings = Gio.Settings.new(Application.SETTINGS_BASE_KEY)
        self.load_css()

        # Create builder to load UI
        self._builder = Gtk.Builder()
        self._builder.add_from_file('data/gtk.glade')


    def do_activate(self):
        Gtk.Application.do_activate(self)
        if not self._window:
            self._window = widgets.Window(self, self._builder, Application.TITLE, self._settings)
        self._window.present()


    def load_css(self):
        styleProvider = Gtk.CssProvider()
        styleProvider.load_from_file(Gio.File.new_for_path('data/mcg.css'))
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(),
            styleProvider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
