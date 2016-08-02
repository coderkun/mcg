#!/usr/bin/env python3


import gi
gi.require_version('Gtk', '3.0')
import urllib

from gi.repository import Gio, Gtk, Gdk

from mcg import Environment
from mcg import widgets




class Application(Gtk.Application):
    TITLE = "MPDCoverGrid (Gtk)"
    ID = 'de.coderkun.mcg'


    def __init__(self):
        Gtk.Application.__init__(self, application_id=Application.ID, flags=Gio.ApplicationFlags.FLAGS_NONE)
        self._window = None


    def do_startup(self):
        Gtk.Application.do_startup(self)
        self._load_resource()
        self._load_settings()
        self._load_css()
        self._load_ui()


    def do_activate(self):
        Gtk.Application.do_activate(self)
        if not self._window:
            self._window = widgets.Window(self, self._builder, Application.TITLE, self._settings)
        self._window.present()


    def _load_resource(self):
        self._resource = Gio.resource_load(
            Environment.get_data(Application.ID + '.gresource')
        )
        Gio.Resource._register(self._resource)


    def _load_settings(self):
        self._settings = Gio.Settings.new(Application.ID)


    def _load_css(self):
        styleProvider = Gtk.CssProvider()
        styleProvider.load_from_resource(self._get_resource_path('mcg.css'))
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(),
            styleProvider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )


    def _load_ui(self):
        # Create builder to load UI
        self._builder = Gtk.Builder()
        self._builder.add_from_resource(self._get_resource_path('gtk.glade'))


    def _get_resource_path(self, path):
        return "/{}/{}".format(Application.ID.replace('.', '/'), path)
