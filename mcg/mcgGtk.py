#!/usr/bin/env python3

"""MPDCoverGrid is a client for the Music Player Daemon, focused on albums instead of single tracks."""

__version__ = "0.5"


import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Avahi', '0.6')
try:
    import keyring
    use_keyring = True
except:
    use_keyring = False
import logging
import math
import os
import sys
import threading
import urllib

from gi.repository import Gio, Gtk, Gdk, GObject, GdkPixbuf, GLib
from gi.repository import Avahi

import mcg




class Application(Gtk.Application):
    TITLE = "MPDCoverGrid (Gtk)"
    SETTINGS_BASE_KEY = 'de.coderkun.mcg'
    SETTING_HOST = 'host'
    SETTING_PORT = 'port'
    SETTING_CONNECTED = 'connected'
    SETTING_IMAGE_DIR = 'image-dir'
    SETTING_WINDOW_SIZE = 'window-size'
    SETTING_WINDOW_MAXIMIZED = 'window-maximized'
    SETTING_PANEL = 'panel'
    SETTING_ITEM_SIZE = 'item-size'
    SETTING_SORT_ORDER = 'sort-order'
    SETTING_SORT_TYPE = 'sort-type'
    KEYRING_SYSTEM = 'MPDCoverGrid (Gtk)'
    KEYRING_USERNAME = 'mpd'


    def __init__(self):
        Gtk.Application.__init__(self, application_id="de.coderkun.mcg", flags=Gio.ApplicationFlags.FLAGS_NONE)
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
            self._window = Window(self, self._builder, Application.TITLE, self._settings)
        self._window.present()


    def load_css(self):
        styleProvider = Gtk.CssProvider()
        styleProvider.load_from_file(Gio.File.new_for_path('data/mcg.css'))
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(),
            styleProvider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )


    def load_thumbnail(cache, album, size):
        cache_url = cache.create_filename(album)
        pixbuf = None

        if os.path.isfile(cache_url):
            try:
                pixbuf = GdkPixbuf.Pixbuf.new_from_file(cache_url)
            except Exception as e:
                print(e)
        else:
            url = album.get_cover()
            if url is not None:
                if url.startswith('/'):
                    try:
                        pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(url, size, size)
                    except Exception as e:
                        print(e)
                else:
                    try:
                        response = urllib.request.urlopen(url)
                        loader = GdkPixbuf.PixbufLoader()
                        loader.write(response.read())
                        loader.close()
                        pixbuf = loader.get_pixbuf().scale_simple(size, size, GdkPixbuf.InterpType.HYPER)
                    except Exception as e:
                        print(e)
                if pixbuf is not None:
                    filetype = os.path.splitext(url)[1][1:]
                    if filetype == 'jpg':
                        filetype = 'jpeg'
                    pixbuf.savev(cache.create_filename(album), filetype, [], [])
        return pixbuf




class Window():
    _PANEL_INDEX_CONNECTION = 0
    _PANEL_INDEX_COVER = 1
    _PANEL_INDEX_PLAYLIST = 2
    _PANEL_INDEX_LIBRARY = 3


    def __init__(self, app, builder, title, settings):
        self._appwindow = builder.get_object('appwindow')
        self._appwindow.set_application(app)
        self._appwindow.set_title(title)
        self._settings = settings
        self._panels = []
        self._mcg = mcg.Client()    
        self._logger = logging.getLogger(__name__)
        self._logger.addHandler(logging.StreamHandler(stream=sys.stdout))
        self._logger.setLevel(logging.ERROR)
        logging.getLogger(mcg.__name__).addHandler(logging.StreamHandler(stream=sys.stdout))
        logging.getLogger(mcg.__name__).setLevel(logging.ERROR)
        #self._mcg.get_logger().addHandler(logging.StreamHandler(stream=sys.stdout))
        #self._mcg.get_logger().setLevel(logging.ERROR)
        self._size = self._settings.get_value(Application.SETTING_WINDOW_SIZE)
        self._maximized = self._settings.get_boolean(Application.SETTING_WINDOW_MAXIMIZED)
        self._fullscreened = False

        # Panels
        self._panels.append(ConnectionPanel(builder))
        self._panels.append(CoverPanel(builder))
        self._panels.append(PlaylistPanel(builder))
        self._panels.append(LibraryPanel(builder))

        # Widgets
        # InfoBar
        self._infobar = InfoBar(builder)
        # Stack
        self._stack = builder.get_object('panelstack')
        # Header
        self._header_bar = HeaderBar(builder)
        # Toolbar stack
        self._toolbar_stack = builder.get_object('toolbarstack')

        # Properties
        self._header_bar.set_sensitive(False, False)
        self._panels[Window._PANEL_INDEX_CONNECTION].set_host(self._settings.get_string(Application.SETTING_HOST))
        self._panels[Window._PANEL_INDEX_CONNECTION].set_port(self._settings.get_int(Application.SETTING_PORT))
        if use_keyring:
            self._panels[Window._PANEL_INDEX_CONNECTION].set_password(keyring.get_password(Application.KEYRING_SYSTEM, Application.KEYRING_USERNAME))
        self._panels[Window._PANEL_INDEX_CONNECTION].set_image_dir(self._settings.get_string(Application.SETTING_IMAGE_DIR))
        self._panels[Window._PANEL_INDEX_PLAYLIST].set_item_size(self._settings.get_int(Application.SETTING_ITEM_SIZE))
        self._panels[Window._PANEL_INDEX_LIBRARY].set_item_size(self._settings.get_int(Application.SETTING_ITEM_SIZE))
        self._panels[Window._PANEL_INDEX_LIBRARY].set_sort_order(self._settings.get_string(Application.SETTING_SORT_ORDER))
        self._panels[Window._PANEL_INDEX_LIBRARY].set_sort_type(self._settings.get_boolean(Application.SETTING_SORT_TYPE))

        # Signals
        self._header_bar.connect_signal(HeaderBar.SIGNAL_STACK_SWITCHED, self.on_header_bar_stack_switched)
        self._header_bar.connect_signal(HeaderBar.SIGNAL_CONNECT, self.on_header_bar_connect)
        self._header_bar.connect_signal(HeaderBar.SIGNAL_PLAYPAUSE, self.on_header_bar_playpause)
        self._header_bar.connect_signal(HeaderBar.SIGNAL_SET_VOLUME, self.on_header_bar_set_volume)
        self._panels[Window._PANEL_INDEX_CONNECTION].connect_signal(ConnectionPanel.SIGNAL_CONNECTION_CHANGED, self.on_connection_panel_connection_changed)
        self._panels[Window._PANEL_INDEX_COVER].connect_signal(CoverPanel.SIGNAL_TOGGLE_FULLSCREEN, self.on_cover_panel_toggle_fullscreen)
        self._panels[Window._PANEL_INDEX_COVER].connect_signal(CoverPanel.SIGNAL_SET_SONG, self.on_cover_panel_set_song)
        self._panels[Window._PANEL_INDEX_PLAYLIST].connect_signal(PlaylistPanel.SIGNAL_CLEAR_PLAYLIST, self.on_playlist_panel_clear_playlist)
        self._panels[Window._PANEL_INDEX_LIBRARY].connect_signal(LibraryPanel.SIGNAL_UPDATE, self.on_library_panel_update)
        self._panels[Window._PANEL_INDEX_LIBRARY].connect_signal(LibraryPanel.SIGNAL_PLAY, self.on_library_panel_play)
        self._panels[Window._PANEL_INDEX_LIBRARY].connect_signal(LibraryPanel.SIGNAL_ITEM_SIZE_CHANGED, self.on_library_panel_item_size_changed)
        self._panels[Window._PANEL_INDEX_LIBRARY].connect_signal(LibraryPanel.SIGNAL_SORT_ORDER_CHANGED, self.on_library_panel_sort_order_changed)
        self._panels[Window._PANEL_INDEX_LIBRARY].connect_signal(LibraryPanel.SIGNAL_SORT_TYPE_CHANGED, self.on_library_panel_sort_type_changed)
        self._mcg.connect_signal(mcg.Client.SIGNAL_CONNECTION, self.on_mcg_connect)
        self._mcg.connect_signal(mcg.Client.SIGNAL_STATUS, self.on_mcg_status)
        self._mcg.connect_signal(mcg.Client.SIGNAL_LOAD_PLAYLIST, self.on_mcg_load_playlist)
        self._mcg.connect_signal(mcg.Client.SIGNAL_LOAD_ALBUMS, self.on_mcg_load_albums)
        self._mcg.connect_signal(mcg.Client.SIGNAL_ERROR, self.on_mcg_error)
        self._settings.connect('changed::'+Application.SETTING_PANEL, self.on_settings_panel_changed)
        self._settings.connect('changed::'+Application.SETTING_ITEM_SIZE, self.on_settings_item_size_changed)
        self._settings.connect('changed::'+Application.SETTING_SORT_ORDER, self.on_settings_sort_order_changed)
        self._settings.connect('changed::'+Application.SETTING_SORT_TYPE, self.on_settings_sort_type_changed)
        handlers = {
            'on_appwindow_size_allocate': self.on_resize,
            'on_appwindow_window_state_event': self.on_state,
            'on_appwindow_destroy': self.on_destroy
        }
        handlers.update(self._header_bar.get_signal_handlers())
        handlers.update(self._infobar.get_signal_handlers())
        handlers.update(self._panels[Window._PANEL_INDEX_CONNECTION].get_signal_handlers())
        handlers.update(self._panels[Window._PANEL_INDEX_COVER].get_signal_handlers())
        handlers.update(self._panels[Window._PANEL_INDEX_PLAYLIST].get_signal_handlers())
        handlers.update(self._panels[Window._PANEL_INDEX_LIBRARY].get_signal_handlers())
        builder.connect_signals(handlers)

        # Actions
        self._appwindow.resize(int(self._size[0]), int(self._size[1]))
        if self._maximized:
            self._appwindow.maximize()
        self._appwindow.show_all()
        self._stack.set_visible_child(self._panels[Window._PANEL_INDEX_CONNECTION].get())
        if self._settings.get_boolean(Application.SETTING_CONNECTED):
            self._connect()


    def present(self):
        self._appwindow.present()
        self._appwindow.resize(800, 600)


    def on_resize(self, widget, event):
        if not self._maximized:
            self._size = (self._appwindow.get_allocation().width, self._appwindow.get_allocation().height)


    def on_state(self, widget, state):
        self._maximized = (state.new_window_state & Gdk.WindowState.MAXIMIZED > 0)
        self._fullscreen((state.new_window_state & Gdk.WindowState.FULLSCREEN > 0))
        self._settings.set_boolean(Application.SETTING_WINDOW_MAXIMIZED, self._maximized)


    def on_destroy(self, window):
        self._settings.set_value(Application.SETTING_WINDOW_SIZE, GLib.Variant('ai', list(self._size)))


    # HeaderBar callbacks

    def on_header_bar_stack_switched(self, widget):
        self._set_visible_toolbar()
        self._save_visible_panel()


    def on_header_bar_connect(self):
        self._connect()


    def on_header_bar_playpause(self):
        self._mcg.playpause()
        self._mcg.get_status()


    def on_header_bar_set_volume(self, volume):
        self._mcg.set_volume(volume)


    # Panel callbacks

    def on_connection_panel_connection_changed(self, host, port, password, image_dir):
        self._settings.set_string(Application.SETTING_HOST, host)
        self._settings.set_int(Application.SETTING_PORT, port)
        if use_keyring:
            if password:
                keyring.set_password(Application.KEYRING_SYSTEM, Application.KEYRING_USERNAME, password)
            else:
                if keyring.get_password(Application.KEYRING_SYSTEM, Application.KEYRING_USERNAME):
                   keyring.delete_password(Application.KEYRING_SYSTEM, Application.KEYRING_USERNAME)
        self._settings.set_string(Application.SETTING_IMAGE_DIR, image_dir)


    def on_playlist_panel_clear_playlist(self):
        self._mcg.clear_playlist()


    def on_cover_panel_toggle_fullscreen(self):
        if not self._fullscreened:
            self.fullscreen()
        else:
            self.unfullscreen()


    def on_cover_panel_set_song(self, pos, time):
        self._mcg.seek(pos, time)


    def on_library_panel_update(self):
        self._mcg.update()


    def on_library_panel_play(self, album):
        self._mcg.play_album(album)


    def on_library_panel_item_size_changed(self, size):
        self._panels[Window._PANEL_INDEX_PLAYLIST].set_item_size(size)
        self._settings.set_int(Application.SETTING_ITEM_SIZE, self._panels[Window._PANEL_INDEX_LIBRARY].get_item_size())


    def on_library_panel_sort_order_changed(self, sort_order):
        self._settings.set_string(Application.SETTING_SORT_ORDER, self._panels[Window._PANEL_INDEX_LIBRARY].get_sort_order())


    def on_library_panel_sort_type_changed(self, sort_type):
        self._settings.set_boolean(Application.SETTING_SORT_TYPE, self._panels[Window._PANEL_INDEX_LIBRARY].get_sort_type())


    # MCG callbacks

    def on_mcg_connect(self, connected):
        if connected:
            GObject.idle_add(self._connect_connected)
            self._mcg.load_playlist()
            self._mcg.load_albums()
            self._mcg.get_status()
        else:
            GObject.idle_add(self._connect_disconnected)


    def on_mcg_status(self, state, album, pos, time, volume, error):
        # Album
        if album:
            GObject.idle_add(self._panels[Window._PANEL_INDEX_COVER].set_album, album)
        # State
        if state == 'play':
            GObject.idle_add(self._header_bar.set_play)
            GObject.idle_add(self._panels[Window._PANEL_INDEX_COVER].set_play, pos, time)
        elif state == 'pause' or state == 'stop':
            GObject.idle_add(self._header_bar.set_pause)
            GObject.idle_add(self._panels[Window._PANEL_INDEX_COVER].set_pause)
        # Volume
        GObject.idle_add(self._header_bar.set_volume, volume)
        # Error
        if error is None:
            self._infobar.hide()
        else:
            self._show_error(error)


    def on_mcg_load_playlist(self, playlist):
        self._panels[self._PANEL_INDEX_PLAYLIST].set_playlist(self._panels[self._PANEL_INDEX_CONNECTION].get_host(), playlist)


    def on_mcg_load_albums(self, albums):
        self._panels[self._PANEL_INDEX_LIBRARY].set_albums(self._panels[self._PANEL_INDEX_CONNECTION].get_host(), albums)


    def on_mcg_error(self, error):
        GObject.idle_add(self._show_error, str(error))


    # Settings callbacks

    def on_settings_panel_changed(self, settings, key):
        panel_index = settings.get_int(key)
        self._stack.set_visible_child(self._panels[panel_index].get())


    def on_settings_item_size_changed(self, settings, key):
        size = settings.get_int(key)
        self._panels[Window._PANEL_INDEX_PLAYLIST].set_item_size(size)
        self._panels[Window._PANEL_INDEX_LIBRARY].set_item_size(size)


    def on_settings_sort_order_changed(self, settings, key):
        sort_order = settings.get_string(key)
        self._panels[Window._PANEL_INDEX_LIBRARY].set_sort_order(sort_order)


    def on_settings_sort_type_changed(self, settings, key):
        sort_type = settings.get_boolean(key)
        self._panels[Window._PANEL_INDEX_LIBRARY].set_sort_type(sort_type)


    # Private methods

    def _connect(self):
        connection_panel = self._panels[Window._PANEL_INDEX_CONNECTION]
        connection_panel.get().set_sensitive(False)
        self._header_bar.set_sensitive(False, True)
        if self._mcg.is_connected():
            self._mcg.disconnect()
            self._settings.set_boolean(Application.SETTING_CONNECTED, False)
        else:
            host = connection_panel.get_host()
            port = connection_panel.get_port()
            password = connection_panel.get_password()
            image_dir = connection_panel.get_image_dir()
            self._mcg.connect(host, port, password, image_dir)
            self._settings.set_boolean(Application.SETTING_CONNECTED, True)


    def _connect_connected(self):
        self._header_bar.connected()
        self._header_bar.set_sensitive(True, False)
        self._stack.set_visible_child(self._panels[self._settings.get_int(Application.SETTING_PANEL)].get())


    def _connect_disconnected(self):
        self._panels[Window._PANEL_INDEX_PLAYLIST].stop_threads();
        self._panels[Window._PANEL_INDEX_LIBRARY].stop_threads();
        self._header_bar.disconnected()
        self._header_bar.set_sensitive(False, False)
        self._save_visible_panel()
        self._stack.set_visible_child(self._panels[Window._PANEL_INDEX_CONNECTION].get())
        self._panels[Window._PANEL_INDEX_CONNECTION].get().set_sensitive(True)


    def _fullscreen(self, fullscreened_new):
        if fullscreened_new != self._fullscreened:
            self._fullscreened = fullscreened_new
            if self._fullscreened:
                self._header_bar.hide()
                self._panels[Window._PANEL_INDEX_COVER].set_fullscreen(True)
            else:
                self._header_bar.show()
                self._panels[Window._PANEL_INDEX_COVER].set_fullscreen(False)


    def _save_visible_panel(self):
        panels = [panel.get() for panel in self._panels]
        panel_index_selected = panels.index(self._stack.get_visible_child())
        if panel_index_selected > 0:
            self._settings.set_int(Application.SETTING_PANEL, panel_index_selected)


    def _set_visible_toolbar(self):
        panels = [panel.get() for panel in self._panels]
        panel_index_selected = panels.index(self._stack.get_visible_child())
        toolbar = self._panels[panel_index_selected].get_toolbar()
        self._toolbar_stack.set_visible_child(toolbar)


    def _show_error(self, message):
        self._infobar.show_error(message)




class HeaderBar(mcg.Base):
    SIGNAL_STACK_SWITCHED = 'stack-switched'
    SIGNAL_CONNECT = 'on_headerbar-connection_active_notify'
    SIGNAL_PLAYPAUSE = 'on_headerbar-playpause_toggled'
    SIGNAL_SET_VOLUME = 'set-volume'


    def __init__(self, builder):
        mcg.Base.__init__(self)

        self._buttons = {}
        self._changing_volume = False
        self._setting_volume = False

        # Widgets
        self._header_bar = builder.get_object('headerbar')
        self._stack_switcher = StackSwitcher(builder)
        self._buttons[HeaderBar.SIGNAL_CONNECT] = builder.get_object('headerbar-connection')
        self._buttons[HeaderBar.SIGNAL_PLAYPAUSE] = builder.get_object('headerbar-playpause')
        self._buttons[HeaderBar.SIGNAL_SET_VOLUME] = builder.get_object('headerbar-volume')

        # Signals
        self._stack_switcher.connect_signal(StackSwitcher.SIGNAL_STACK_SWITCHED, self.on_stack_switched)
        self._button_handlers = {
            'on_headerbar-connection_active_notify': self._callback_from_widget,
            'on_headerbar-connection_state_set': self.on_connection_state_set,
            'on_headerbar-playpause_toggled': self._callback_from_widget,
            'on_headerbar-volume_value_changed': self.on_volume_changed,
            'on_headerbar-volume_button_press_event': self.on_volume_press,
            'on_headerbar-volume_button_release_event': self.on_volume_release
        }


    def get(self):
        return self._header_bar


    def get_signal_handlers(self):
        return self._button_handlers


    def set_sensitive(self, sensitive, connecting):
        for button_signal in self._buttons:
            self._buttons[button_signal].set_sensitive(sensitive)
        self._stack_switcher.get().set_sensitive(sensitive)
        self._buttons[HeaderBar.SIGNAL_CONNECT].set_sensitive(not connecting)


    def on_connection_state_set(self, widget, state):
        return True


    def on_stack_switched(self, widget):
        self._callback(HeaderBar.SIGNAL_STACK_SWITCHED, widget)


    def on_volume_changed(self, widget, value):
        if not self._setting_volume:
            self._callback(self.SIGNAL_SET_VOLUME, int(value*100))


    def on_volume_press(self, *args):
        self.volume_set_active(None, None, True)


    def on_volume_release(self, *args):
        self.volume_set_active(None, None, False)


    def volume_set_active(self, widget, event, active):
        self._changing_volume = active


    def connected(self):
        self._buttons[HeaderBar.SIGNAL_CONNECT].handler_block_by_func(
            self._button_handlers[HeaderBar.SIGNAL_CONNECT]
        )
        self._buttons[HeaderBar.SIGNAL_CONNECT].set_active(True)
        self._buttons[HeaderBar.SIGNAL_CONNECT].set_state(True)
        self._buttons[HeaderBar.SIGNAL_CONNECT].handler_unblock_by_func(
            self._button_handlers[HeaderBar.SIGNAL_CONNECT]
        )


    def disconnected(self):
        self._buttons[HeaderBar.SIGNAL_CONNECT].handler_block_by_func(
            self._button_handlers[HeaderBar.SIGNAL_CONNECT]
        )
        self._buttons[HeaderBar.SIGNAL_CONNECT].set_active(False)
        self._buttons[HeaderBar.SIGNAL_CONNECT].set_state(False)
        self._buttons[HeaderBar.SIGNAL_CONNECT].handler_unblock_by_func(
            self._button_handlers[HeaderBar.SIGNAL_CONNECT]
        )


    def set_play(self):
        self._buttons[HeaderBar.SIGNAL_PLAYPAUSE].handler_block_by_func(
            self._button_handlers[HeaderBar.SIGNAL_PLAYPAUSE]
        )
        self._buttons[HeaderBar.SIGNAL_PLAYPAUSE].set_active(True)
        self._buttons[HeaderBar.SIGNAL_PLAYPAUSE].handler_unblock_by_func(
            self._button_handlers[HeaderBar.SIGNAL_PLAYPAUSE]
        )


    def set_pause(self):
        self._buttons[HeaderBar.SIGNAL_PLAYPAUSE].handler_block_by_func(
            self._button_handlers[HeaderBar.SIGNAL_PLAYPAUSE]
        )
        self._buttons[HeaderBar.SIGNAL_PLAYPAUSE].set_active(False)
        self._buttons[HeaderBar.SIGNAL_PLAYPAUSE].handler_unblock_by_func(
            self._button_handlers[HeaderBar.SIGNAL_PLAYPAUSE]
        )


    def set_volume(self, volume):
        if volume >= 0:
            self._buttons[HeaderBar.SIGNAL_SET_VOLUME].set_visible(True)
            if not self._changing_volume:
                self._setting_volume = True
                self._buttons[HeaderBar.SIGNAL_SET_VOLUME].set_value(volume / 100)
                self._setting_volume = False
        else:
            self._buttons[HeaderBar.SIGNAL_SET_VOLUME].set_visible(False)


    def _callback_from_widget(self, widget, *args):
        if widget is self._buttons[HeaderBar.SIGNAL_CONNECT]:
            self._callback(self.SIGNAL_CONNECT)
        elif widget is self._buttons[HeaderBar.SIGNAL_PLAYPAUSE]:
            self._callback(self.SIGNAL_PLAYPAUSE)




class InfoBar():
    def __init__(self, builder):
        # Widgets
        self._revealer = builder.get_object('server-info-revealer')
        self._bar = builder.get_object('server-info-bar')
        self._message_label = builder.get_object('server-info-label')


    def get_signal_handlers(self):
        return {
            'on_server-info-bar_close': self.on_close,
            'on_server-info-bar_response': self.on_response
        }


    def on_close(self, *args):
        self.hide()


    def on_response(self, widget, response):
        self.hide()


    def hide(self):
        self._revealer.set_reveal_child(False)


    def show_error(self, message):
        self._bar.set_message_type(Gtk.MessageType.ERROR)
        self._message_label.set_text(message)
        self._revealer.set_reveal_child(True)




class ConnectionPanel(mcg.Base):
    SIGNAL_CONNECTION_CHANGED = 'connection-changed'


    def __init__(self, builder):
        mcg.Base.__init__(self)
        self._services = Gtk.ListStore(str, str, int)
        self._profile = None

        # Widgets
        self._panel = builder.get_object('server-panel')
        self._toolbar = builder.get_object('server-toolbar')
        # Zeroconf
        self._zeroconf_list = builder.get_object('server-zeroconf-list')
        self._zeroconf_list.set_model(self._services)
        renderer = Gtk.CellRendererText()
        column = Gtk.TreeViewColumn("Zeroconf", renderer, text=0)
        self._zeroconf_list.append_column(column)
        # Host
        self._host_entry = builder.get_object('server-host')
        # Port
        self._port_spinner = builder.get_object('server-port')
        # Passwort
        self._password_entry = builder.get_object('server-password')
        # Image dir
        self._image_dir_entry = builder.get_object('server-image-dir')

        # Zeroconf provider
        self._zeroconf_provider = ZeroconfProvider()
        self._zeroconf_provider.connect_signal(ZeroconfProvider.SIGNAL_SERVICE_NEW, self.on_new_service)


    def get(self):
        return self._panel


    def get_toolbar(self):
        return self._toolbar


    def get_signal_handlers(self):
        return {
            'on_server-zeroconf-list-selection_changed': self.on_service_selected,
            'on_server-zeroconf-list_focus_out_event': self.on_zeroconf_list_outfocused,
            'on_server-host_focus_out_event': self.on_host_entry_outfocused,
            'on_server-port_value_changed': self.on_port_spinner_value_changed,
            'on_server-password_focus_out_event': self.on_password_entry_outfocused,
            'on_server-image-dir_focus_out_event': self.on_image_dir_entry_outfocused
        }


    def on_new_service(self, service):
        name, host, port = service
        self._services.append([name, host, port])


    def on_service_selected(self, selection):
        model, treeiter = selection.get_selected()
        if treeiter != None:
            service = model[treeiter]
            self.set_host(service[1])
            self.set_port(service[2])


    def on_zeroconf_list_outfocused(self, widget, event):
        self._zeroconf_list.get_selection().unselect_all()


    def on_host_entry_outfocused(self, widget, event):
        self._call_back()


    def on_port_spinner_value_changed(self, widget):
        self._call_back()


    def on_password_entry_outfocused(self, widget, event):
        self._call_back()


    def on_image_dir_entry_outfocused(self, widget, event):
        self._call_back()


    def set_host(self, host):
        self._host_entry.set_text(host)


    def get_host(self):
        return self._host_entry.get_text()


    def set_port(self, port):
        self._port_spinner.set_value(port)


    def get_port(self):
        return self._port_spinner.get_value_as_int()


    def set_password(self, password):
        if password is None:
            password = ""
        self._password_entry.set_text(password)


    def get_password(self):
        if self._password_entry.get_text() == "":
            return None
        else:
            return self._password_entry.get_text()


    def set_image_dir(self, image_dir):
        self._image_dir_entry.set_text(image_dir)


    def get_image_dir(self):
        return self._image_dir_entry.get_text()


    def _call_back(self):
        self._callback(ConnectionPanel.SIGNAL_CONNECTION_CHANGED, self.get_host(), self.get_port(), self.get_password(), self.get_image_dir())




class CoverPanel(mcg.Base):
    SIGNAL_TOGGLE_FULLSCREEN = 'toggle-fullscreen'
    SIGNAL_SET_SONG = 'set-song'


    def __init__(self, builder):
        mcg.Base.__init__(self)

        self._current_album = None
        self._cover_pixbuf = None
        self._timer = None
        self._properties = {}

        # Widgets
        self._panel = builder.get_object('cover-panel')
        self._toolbar = builder.get_object('cover-toolbar')
        # Cover
        self._cover_scroll = builder.get_object('cover-scroll')
        self._cover_image = builder.get_object('cover-image')
        # Songs
        self._songs_scale = builder.get_object('cover-songs')
        self._songs_scale.override_color(Gtk.StateFlags.NORMAL, Gdk.RGBA(0, 0, 0, 1))
        # Album Infos
        self._album_title_label = builder.get_object('cover-album')
        self._album_date_label = builder.get_object('cover-date')
        self._album_artist_label = builder.get_object('cover-artist')


    def get(self):
        return self._panel


    def get_toolbar(self):
        return self._toolbar


    def get_signal_handlers(self):
        return {
            'on_cover-box_button_press_event': self.on_cover_box_pressed,
            'on_cover-scroll_size_allocate': self.on_cover_size_allocate,
            'on_cover-songs_button_press_event': self.on_songs_start_change,
            'on_cover-songs_button_release_event': self.on_songs_change
        }


    def on_cover_box_pressed(self, widget, event):
        if event.type == Gdk.EventType._2BUTTON_PRESS:
            self._callback(self.SIGNAL_TOGGLE_FULLSCREEN)


    def on_cover_size_allocate(self, widget, allocation):
        self._resize_image()


    def on_songs_start_change(self, widget, event):
        if self._timer:
            GObject.source_remove(self._timer)
            self._timer = None


    def on_songs_change(self, widget, event):
        value = int(self._songs_scale.get_value())
        time = self._current_album.get_length()
        tracks = self._current_album.get_tracks()
        pos = 0
        for index in range(len(tracks)-1, -1, -1):
            time = time - tracks[index].get_length()
            pos = tracks[index].get_pos()
            if time < value:
                break
        time = max(value - time - 1, 0)
        self._callback(self.SIGNAL_SET_SONG, pos, time)


    def set_album(self, album):
        self._album_title_label.set_markup(
            "<b><big>{}</big></b>".format(
                GObject.markup_escape_text(
                    album.get_title()
                )
            )
        )
        self._album_date_label.set_markup(
            "<big>{}</big>".format(
                GObject.markup_escape_text(
                    ', '.join(album.get_dates())
                )
            )
        )
        self._album_artist_label.set_markup(
            "<big>{}</big>".format(
                GObject.markup_escape_text(
                    ', '.join(album.get_artists())
                )
            )
        )
        self._set_cover(album)
        self._set_tracks(album)


    def set_play(self, pos, time):
        if self._timer is not None:
            GObject.source_remove(self._timer)
            self._timer = None
        tracks = self._current_album.get_tracks()
        for index in range(0, pos):
            time = time + tracks[index].get_length()

        self._songs_scale.set_value(time+1)
        self._timer = GObject.timeout_add(1000, self._playing)


    def set_pause(self):
        if self._timer is not None:
            GObject.source_remove(self._timer)
            self._timer = None


    def set_fullscreen(self, active):
        if active:
            self._songs_scale.hide()
            self._info_grid.hide()
            self.child_set_property(self._current_box, 'padding', 0)
            self._current_box.child_set_property(self._cover_scroll, 'padding', 0)
            self._cover_box.override_background_color(Gtk.StateFlags.NORMAL, Gdk.RGBA(0, 0, 0, 1))
        else:
            self._songs_scale.show()
            self._info_grid.show()
            self.child_set_property(self._current_box, 'padding', 10)
            self._current_box.child_set_property(self._cover_scroll, 'padding', 10)
            self._cover_box.override_background_color(Gtk.StateFlags.NORMAL, Gdk.RGBA(0, 0, 0, 0))
            GObject.idle_add(self._resize_image)


    def _set_cover(self, album):
        if self._current_album is not None and album.get_hash() == self._current_album.get_hash():
            return
        self._current_album = album
        url = album.get_cover()
        if url is not None and url is not "":
            # Load image and draw it
            self._cover_pixbuf = self._load_cover(url)
            self._resize_image()
        else:
            # Reset image
            self._cover_pixbuf = None
            self._cover_image.clear()


    def _set_tracks(self, album):
        self._songs_scale.clear_marks()
        self._songs_scale.set_range(0, album.get_length())
        length = 0
        for track in album.get_tracks():
            cur_length = length
            if length > 0 and length < album.get_length():
                cur_length = cur_length + 1
            self._songs_scale.add_mark(
                cur_length,
                Gtk.PositionType.RIGHT, 
                GObject.markup_escape_text(
                    track.get_title()
                )
            )
            length = length + track.get_length()
        self._songs_scale.add_mark(length, Gtk.PositionType.RIGHT, "{0[0]:02d}:{0[1]:02d} minutes".format(divmod(length, 60)))


    def _playing(self):
        value = self._songs_scale.get_value() + 1
        self._songs_scale.set_value(value)

        return True


    def _load_cover(self, url):
        if url.startswith('/'):
            try:
                return GdkPixbuf.Pixbuf.new_from_file(url)
            except Exception as e:
                print(e)
                return None
        else:
            try:
                response = urllib.request.urlopen(url)
                loader = GdkPixbuf.PixbufLoader()
                loader.write(response.read())
                loader.close()
                return loader.get_pixbuf()
            except Exception as e:
                print(e)
                return None


    def _resize_image(self):
        """Diese Methode skaliert das geladene Bild aus dem Pixelpuffer
        auf die Größe des Fensters unter Beibehalt der Seitenverhältnisse
        """
        pixbuf = self._cover_pixbuf
        size = self._cover_scroll.get_allocation()
        # Check pixelbuffer
        if pixbuf is None:
            return

        # Skalierungswert für Breite und Höhe ermitteln
        ratioW = float(size.width) / float(pixbuf.get_width())
        ratioH = float(size.height) / float(pixbuf.get_height())
        # Kleineren beider Skalierungswerte nehmen, nicht Hochskalieren
        ratio = min(ratioW, ratioH)
        ratio = min(ratio, 1)
        # Neue Breite und Höhe berechnen
        width = int(math.floor(pixbuf.get_width()*ratio))
        height = int(math.floor(pixbuf.get_height()*ratio))
        if width <= 0 or height <= 0:
            return
        # Pixelpuffer auf Oberfläche zeichnen
        self._cover_image.set_allocation(self._cover_scroll.get_allocation())
        self._cover_image.set_from_pixbuf(pixbuf.scale_simple(width, height, GdkPixbuf.InterpType.HYPER))
        self._cover_image.show()




class PlaylistPanel(mcg.Base):
    SIGNAL_CLEAR_PLAYLIST = 'clear-playlist'


    def __init__(self, builder):
        mcg.Base.__init__(self)
        self._host = None
        self._item_size = 150
        self._playlist = None
        self._playlist_lock = threading.Lock()
        self._playlist_stop = threading.Event()
        self._icon_theme = Gtk.IconTheme.get_default()

        # Widgets
        self._panel = builder.get_object('playlist-panel')
        self._toolbar = builder.get_object('playlist-toolbar')
        # Clear button
        self._playlist_clear_button = builder.get_object('playlist-toolbar-clear')
        # Playlist Grid: Model
        self._playlist_grid_model = Gtk.ListStore(GdkPixbuf.Pixbuf, str, str)
        # Playlist Grid
        self._playlist_grid = builder.get_object('playlist-iconview')
        self._playlist_grid.set_model(self._playlist_grid_model)
        self._playlist_grid.set_pixbuf_column(0)
        self._playlist_grid.set_text_column(-1)
        self._playlist_grid.set_tooltip_column(1)


    def get(self):
        return self._panel


    def get_toolbar(self):
        return self._toolbar


    def get_signal_handlers(self):
        return {
            'on_playlist-toolbar-clear_clicked': self._callback_from_widget
        }


    def set_item_size(self, item_size):
        if self._item_size != item_size:
            self._item_size = item_size
            self._redraw()


    def get_item_size(self):
        return self._item_size


    def set_playlist(self, host, playlist):
        self._host = host
        self._playlist_stop.set()
        threading.Thread(target=self._set_playlist, args=(host, playlist, self._item_size,)).start()


    def stop_threads(self):
        self._playlist_stop.set()


    def _set_playlist(self, host, playlist, size):
        self._playlist_lock.acquire()
        self._playlist_stop.clear()
        self._playlist = playlist
        self._playlist_grid.set_model(None)
        self._playlist_grid.freeze_child_notify()
        self._playlist_grid_model.clear()

        cache = mcg.MCGCache(host, size)
        for album in playlist:
            pixbuf = None
            if album.get_cover() is not None:
                try:
                    pixbuf = Application.load_thumbnail(cache, album, size)
                except Exception as e:
                    print(e)
            if pixbuf is None:
                pixbuf = self._icon_theme.load_icon('image-x-generic-symbolic', self._item_size, Gtk.IconLookupFlags.FORCE_SVG & Gtk.IconLookupFlags.FORCE_SIZE)
            if pixbuf is not None:
                self._playlist_grid_model.append([
                    pixbuf,
                    GObject.markup_escape_text("\n".join([
                        album.get_title(),
                        ', '.join(album.get_dates()),
                        ', '.join(album.get_artists())
                    ])),
                    album.get_hash()
                ])

            if self._playlist_stop.is_set():
                self._playlist_lock.release()
                return

        self._playlist_grid.set_model(self._playlist_grid_model)
        self._playlist_grid.thaw_child_notify()
        # TODO why set_columns()?
        #self._playlist_grid.set_columns(len(playlist))
        self._playlist_lock.release()


    def _redraw(self):
        if self._playlist is not None:
            self.set_playlist(self._host, self._playlist)


    def _callback_from_widget(self, widget):
        if widget is self._playlist_clear_button:
            self._callback(PlaylistPanel.SIGNAL_CLEAR_PLAYLIST)




class LibraryPanel(mcg.Base):
    SIGNAL_UPDATE = 'update'
    SIGNAL_PLAY = 'play'
    SIGNAL_ITEM_SIZE_CHANGED = 'item-size-changed'
    SIGNAL_SORT_ORDER_CHANGED = 'sort-order-changed'
    SIGNAL_SORT_TYPE_CHANGED = 'sort-type-changed'


    def __init__(self, builder):
        mcg.Base.__init__(self)
        self._buttons = {}
        self._albums = None
        self._host = "localhost"
        self._filter_string = ""
        self._item_size = 150
        self._sort_order = mcg.MCGAlbum.SORT_BY_YEAR
        self._sort_type = Gtk.SortType.DESCENDING
        self._grid_pixbufs = {}
        self._old_ranges = {}
        self._library_lock = threading.Lock()
        self._library_stop = threading.Event()
        self._icon_theme = Gtk.IconTheme.get_default()

        # Widgets
        self._panel = builder.get_object('library-panel')
        self._toolbar = builder.get_object('library-toolbar')
        # Progress Bar
        self._progress_revealer = builder.get_object('library-progress-revealer')
        self._progress_bar = builder.get_object('library-progress')
        # Toolbar
        # Filter entry
        self._filter_entry = builder.get_object('library-filter')
        # Grid scale
        self._grid_scale = builder.get_object('library-grid-scale')
        self._grid_scale.set_value(self._item_size)
        # Sort menu
        library_sort_store = Gtk.ListStore(str, str)
        library_sort_store.append([mcg.MCGAlbum.SORT_BY_ARTIST, "sort by artist"])
        library_sort_store.append([mcg.MCGAlbum.SORT_BY_TITLE, "sort by title"])
        library_sort_store.append([mcg.MCGAlbum.SORT_BY_YEAR, "sort by year"])        
        self._library_sort_combo = builder.get_object('library-sort')
        self._library_sort_combo.set_model(library_sort_store)
        renderer_text = Gtk.CellRendererText()
        self._library_sort_combo.pack_start(renderer_text, True)
        self._library_sort_combo.add_attribute(renderer_text, "text", 1)
        self._library_sort_combo.set_id_column(0)
        self._library_sort_combo.set_active_id(self._sort_order)
        # Sort type
        self._library_sort_type_button = builder.get_object('library-sort-order')
        # Library Grid: Model
        self._library_grid_model = Gtk.ListStore(GdkPixbuf.Pixbuf, str, str)
        self._library_grid_model.set_sort_func(2, self.compare_albums, self._sort_order)
        self._library_grid_model.set_sort_column_id(2, self._sort_type)
        self._library_grid_filter = self._library_grid_model.filter_new()
        self._library_grid_filter.set_visible_func(self.on_filter_visible)
        # Library Grid
        self._library_grid = builder.get_object('library-iconview')
        self._library_grid.set_model(self._library_grid_filter)
        self._library_grid.set_pixbuf_column(0)
        self._library_grid.set_text_column(-1)
        self._library_grid.set_tooltip_column(1)


    def get(self):
        return self._panel


    def get_toolbar(self):
        return self._toolbar


    def get_signal_handlers(self):
        return {
            'on_library-update_clicked': self.on_update_clicked,
            'on_library-grid-scale_change_value': self.on_grid_scale_change,
            'on_library-grid-scale_button_release_event': self.on_grid_scale_changed,
            'on_library-sort_changed': self.on_library_sort_combo_changed,
            'on_library-sort-order_clicked': self.on_library_sort_type_button_activated,
            'on_library-filter_search_changed': self.on_filter_entry_changed,
            'on_library-iconview_item_activated': self.on_library_grid_clicked
        }


    def on_update_clicked(self, widget):
        self._callback(self.SIGNAL_UPDATE)


    def on_filter_visible(self, model, iter, data):
        hash = model.get_value(iter, 2)
        if not hash in self._albums.keys():
            return
        album = self._albums[hash]
        return album.filter(self._filter_string)


    def on_filter_entry_changed(self, widget):
        self._filter_string = self._filter_entry.get_text()
        GObject.idle_add(self._library_grid_filter.refilter)


    def on_grid_scale_change(self, widget, scroll, value):
        size = round(value)
        range =  self._grid_scale.get_adjustment()
        if size < range.get_lower() or size > range.get_upper():
            return
        self._item_size = size
        GObject.idle_add(self._set_widget_grid_size, self._library_grid, size, True)


    def on_grid_scale_changed(self, widget, event):
        size = round(self._grid_scale.get_value())
        range =  self._grid_scale.get_adjustment()
        if size < range.get_lower() or size > range.get_upper():
            return
        self._callback(LibraryPanel.SIGNAL_ITEM_SIZE_CHANGED, size)
        self._redraw()


    def on_library_sort_combo_changed(self, combo):
        sort_order = combo.get_active_id()
        self._sort_order = sort_order
        self._library_grid_model.set_sort_func(2, self.compare_albums, sort_order)
        self._callback(LibraryPanel.SIGNAL_SORT_ORDER_CHANGED, sort_order)


    def on_library_sort_type_button_activated(self, button):
        if button.get_active():
            sort_type = Gtk.SortType.DESCENDING
            button.set_stock_id(Gtk.STOCK_SORT_DESCENDING)
        else:
            sort_type = Gtk.SortType.ASCENDING
            button.set_stock_id(Gtk.STOCK_SORT_ASCENDING)
        self._sort_type = sort_type
        self._library_grid_model.set_sort_column_id(2, sort_type)
        self._callback(LibraryPanel.SIGNAL_SORT_TYPE_CHANGED, sort_type)


    def on_library_grid_clicked(self, widget, path):
        path = self._library_grid_filter.convert_path_to_child_path(path)
        iter = self._library_grid_model.get_iter(path)
        self._callback(LibraryPanel.SIGNAL_PLAY, self._library_grid_model.get_value(iter, 2))


    def set_item_size(self, item_size):
        if self._item_size != item_size:
            self._item_size = item_size
            self._grid_scale.set_value(item_size)
            self._redraw()


    def get_item_size(self):
        return self._item_size


    def set_sort_order(self, sort_order):
        if self._sort_order != sort_order:
            result = self._library_sort_combo.set_active_id(sort_order)
            if self._sort_order != sort_order:
                self._sort_order = sort_order
                self._library_grid_model.set_sort_func(2, self.compare_albums, self._sort_order)


    def get_sort_order(self):
        return self._sort_order


    def set_sort_type(self, sort_type):
        if self._sort_type != sort_type:
            if sort_type:
                sort_type_gtk = Gtk.SortType.DESCENDING
                stock_id = Gtk.STOCK_SORT_DESCENDING
                self._library_sort_type_button.set_active(True)
            else:
                sort_type_gtk = Gtk.SortType.ASCENDING
                self._library_sort_type_button.set_active(False)
                stock_id = Gtk.STOCK_SORT_ASCENDING
            if self._sort_type != sort_type_gtk:
                self._sort_type = sort_type_gtk
                self._library_sort_type_button.set_stock_id(stock_id)
                self._library_grid_model.set_sort_column_id(2, sort_type)


    def get_sort_type(self):
        return (self._sort_type != Gtk.SortType.ASCENDING)


    def set_albums(self, host, albums):
        self._host = host
        self._library_stop.set()
        threading.Thread(target=self._set_albums, args=(host, albums, self._item_size,)).start()


    def compare_albums(self, model, row1, row2, criterion):
        hash1 = model.get_value(row1, 2)
        hash2 = model.get_value(row2, 2)

        if hash1 == "" or hash2 == "":
            return
        return mcg.MCGAlbum.compare(self._albums[hash1], self._albums[hash2], criterion)


    def stop_threads(self):
        self._library_stop.set()


    def _set_albums(self, host, albums, size):
        self._library_lock.acquire()
        self._library_stop.clear()
        self._albums = albums
        self._progress_revealer.set_reveal_child(True)
        GObject.idle_add(self._progress_bar.set_fraction, 0.0)
        self._library_grid.set_model(None)
        self._library_grid.freeze_child_notify()
        self._library_grid_model.clear()

        i = 0
        n = len(albums)
        cache = mcg.MCGCache(host, size)
        self._grid_pixbufs.clear()
        for hash in albums.keys():
            album = albums[hash]
            pixbuf = None
            try:
                pixbuf = Application.load_thumbnail(cache, album, size)
            except Exception as e:
                print(e)
            if pixbuf is None:
                pixbuf = self._icon_theme.load_icon('image-x-generic-symbolic', self._item_size, Gtk.IconLookupFlags.FORCE_SVG & Gtk.IconLookupFlags.FORCE_SIZE)
            if pixbuf is not None:
                self._grid_pixbufs[album.get_hash()] = pixbuf
                self._library_grid_model.append([
                    pixbuf,
                    GObject.markup_escape_text("\n".join([
                        album.get_title(),
                        ', '.join(album.get_dates()),
                        ', '.join(album.get_artists())
                    ])),
                    hash
                ])

            i += 1
            GObject.idle_add(self._progress_bar.set_fraction, i/n)
            if self._library_stop.is_set():
                self._library_lock.release()
                return

        self._library_grid.set_model(self._library_grid_filter)
        self._library_grid.thaw_child_notify()
        self._library_grid.set_item_width(-1)
        self._library_lock.release()
        self._progress_revealer.set_reveal_child(False)


    def _set_widget_grid_size(self, grid_widget, size, vertical):
        self._library_stop.set()
        threading.Thread(target=self._set_widget_grid_size_thread, args=(grid_widget, size, vertical,)).start()


    def _set_widget_grid_size_thread(self, grid_widget, size, vertical):
        self._library_lock.acquire()
        self._library_stop.clear()
        grid_filter = grid_widget.get_model()
        grid_model = grid_filter.get_model()

        # get old_range
        grid_widget_id = id(grid_widget)
        if grid_widget_id not in self._old_ranges or self._old_ranges[grid_widget_id] is None:
            self._old_ranges[grid_widget_id] = range(0, len(grid_filter))
        old_range = self._old_ranges[grid_widget_id]
        old_start = len(old_range) > 0 and old_range[0] or 0
        old_end = len(old_range) > 0 and old_range[len(old_range)-1] + 1 or 0

        # calculate visible range
        w = (grid_widget.get_allocation().width // size) + (vertical and 0 or 1)
        h = (grid_widget.get_allocation().height // size) + (vertical and 1 or 0)
        c = w * h
        vis_range = grid_widget.get_visible_range()
        if vis_range is None:
            self._library_lock.release()
            return
        (vis_start,), (vis_end,) = vis_range
        vis_end = min(vis_start + c, len(grid_filter))
        vis_range = range(vis_start, vis_end)
        
        # set pixbuf
        cur_start = min(old_start, vis_start)
        cur_end = max(old_end, vis_end)
        cur_range = range(cur_start, cur_end)
        for index in cur_range:
            iter = grid_filter.convert_iter_to_child_iter(grid_filter[index].iter)
            if index in vis_range:
                hash = grid_model.get_value(iter, 2)
                pixbuf = self._grid_pixbufs[hash]
                pixbuf = pixbuf.scale_simple(size, size, GdkPixbuf.InterpType.NEAREST)
            else:
                pixbuf = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, False, 8, 1, 1)
            grid_model.set_value(iter, 0, pixbuf)

            if self._library_stop.is_set():
                self._library_lock.release()
                return

        self._old_ranges[grid_widget_id] = vis_range
        grid_widget.set_item_width(size)

        self._library_lock.release()


    def _redraw(self):
        if self._albums is not None:
            self.set_albums(self._host, self._albums)




class StackSwitcher(mcg.Base):
    SIGNAL_STACK_SWITCHED = 'stack-switched'


    def __init__(self, builder):
        mcg.Base.__init__(self)

        self._temp_button = None
        self._stack_switcher = builder.get_object('header-panelswitcher')
        for child in self._stack_switcher.get_children():
            if type(child) is Gtk.RadioButton:
                child.connect('clicked', self.on_clicked)


    def on_clicked(self, widget):
        if not self._temp_button:
            self._temp_button = widget
        else:
            self._temp_button = None
            self._callback(StackSwitcher.SIGNAL_STACK_SWITCHED, self)


    def get(self):
        return self._stack_switcher




class ZeroconfProvider(mcg.Base):
    SIGNAL_SERVICE_NEW = 'service-new'
    TYPE = '_mpd._tcp'


    def __init__(self):
        mcg.Base.__init__(self)
        self._service_resolvers = []
        self._services = {}
        self._logger = logging.getLogger(__name__)
        # Client
        self._client = Avahi.Client(flags=0,)
        self._logger.info("avahi info")
        self._logger.warning("avahi warning")
        self._logger.error("avahi error")
        try:
            self._client.start()
            # Browser
            self._service_browser = Avahi.ServiceBrowser(domain='local', flags=0, interface=-1, protocol=Avahi.Protocol.GA_PROTOCOL_UNSPEC, type=ZeroconfProvider.TYPE)
            self._service_browser.connect('new_service', self.on_new_service)
            self._service_browser.attach(self._client)
        except Exception as e:
            self._logger.info(e)


    def on_new_service(self, browser, interface, protocol, name, type, domain, flags):
        #if not (flags & Avahi.LookupResultFlags.GA_LOOKUP_RESULT_LOCAL):
        service_resolver = Avahi.ServiceResolver(interface=interface, protocol=protocol, name=name, type=type, domain=domain, aprotocol=Avahi.Protocol.GA_PROTOCOL_UNSPEC, flags=0,)
        service_resolver.connect('found', self.on_found)
        service_resolver.connect('failure', self.on_failure)
        service_resolver.attach(self._client)
        self._service_resolvers.append(service_resolver)


    def on_found(self, resolver, interface, protocol, name, type, domain, host, date, port, *args):
        if (host, port) not in self._services.keys():
            service = (name,host,port)
            self._services[(host,port)] = service
            self._callback(ZeroconfProvider.SIGNAL_SERVICE_NEW, service)


    def on_failure(self, resolver, date):
        if resolver in self._service_resolvers:
            self._service_resolvers.remove(resolver)




if __name__ == "__main__":
    # Set environment
    srcdir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    if not os.environ.get('GSETTINGS_SCHEMA_DIR'):
        os.environ['GSETTINGS_SCHEMA_DIR'] = os.path.join(srcdir, 'data')

    # Start application
    app = Application()
    exit_status = app.run(sys.argv)
    sys.exit(exit_status)
