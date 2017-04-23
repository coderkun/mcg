#!/usr/bin/env python3


import gi
gi.require_version('Gtk', '3.0')
import locale
import logging
import urllib

from gi.repository import Gio, Gtk, Gdk, GLib

from mcg import Environment
from mcg import widgets




class Application(Gtk.Application):
    TITLE = "MPDCoverGrid"
    ID = 'de.coderkun.mcg'
    DOMAIN = 'mcg'


    def _get_option(shortname, longname, description):
        option = GLib.OptionEntry()
        option.short_name = ord(shortname)
        option.long_name = longname
        option.description = description
        return option


    def __init__(self):
        Gtk.Application.__init__(self, application_id=Application.ID, flags=Gio.ApplicationFlags.FLAGS_NONE)
        self._window = None
        self._verbosity = self._verbosity = logging.WARNING
        self.add_main_option_entries([
            Application._get_option("v", "verbose", "Be verbose: show info messages"),
            Application._get_option("d", "debug", "Enable debugging: show debug messages")
        ])
        self.connect('handle-local-options', self.handle_local_options)


    def handle_local_options(self, widget, options):
        if options.contains("debug") and options.lookup_value('debug'):
            self._verbosity = logging.DEBUG
        elif options.contains("verbose") and options.lookup_value('verbose'):
            self._verbosity = logging.INFO
        return -1


    def do_startup(self):
        Gtk.Application.do_startup(self)
        self._setup_logging()
        self._load_resource()
        self._load_settings()
        self._load_css()
        self._setup_locale()
        self._load_ui()
        self._setup_actions()
        self._load_appmenu()


    def do_activate(self):
        Gtk.Application.do_activate(self)
        if not self._window:
            self._window = widgets.Window(self, self._builder, Application.TITLE, self._settings)
        self._window.present()


    def on_quit(self, action, param):
        self.quit()


    def _setup_logging(self):
        logging.basicConfig(
            level=self._verbosity,
            format="%(asctime)s %(levelname)s: %(message)s"
        )


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


    def _setup_locale(self):
        relpath = Environment.get_locale()
        locale.bindtextdomain(Application.DOMAIN, relpath)


    def _load_ui(self):
        # Create builder to load UI
        self._builder = Gtk.Builder()
        self._builder.set_translation_domain(Application.DOMAIN)
        self._builder.add_from_resource(self._get_resource_path('gtk.glade'))


    def _setup_actions(self):
        action = Gio.SimpleAction.new("quit", None)
        action.connect('activate', self.on_quit)
        self.add_action(action)


    def _load_appmenu(self):
        builder = Gtk.Builder()
        builder.set_translation_domain(Application.DOMAIN)
        builder.add_from_resource(self._get_resource_path('menu.ui'))
        self.set_app_menu(builder.get_object('app-menu'))


    def _get_resource_path(self, path):
        return "/{}/{}".format(Application.ID.replace('.', '/'), path)
