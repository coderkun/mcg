#!/usr/bin/env python3


import gi
gi.require_version('Gtk', '3.0')
try:
    import keyring
    use_keyring = True
except:
    use_keyring = False
import logging
import math
import sys
import threading

from gi.repository import Gtk, Gdk, GObject, GdkPixbuf, GLib, Gio

from mcg import client
from mcg.utils import SortOrder
from mcg.utils import TracklistSize
from mcg.utils import Utils
from mcg.zeroconf import ZeroconfProvider




class ShortcutsDialog():


    def __init__(self, builder, window):
        # Widgets
        self._window = builder.get_object('shortcuts-dialog')
        self._window.set_transient_for(window.get())


    def get(self):
        return self._window


    def present(self):
        self._window.present()




class InfoDialog():


    def __init__(self, builder):
        self._logger = logging.getLogger(__name__)

        # Widgets
        self._info_dialog = builder.get_object('info-dialog')
        self._resize_logo()


    def get(self):
        return self._info_dialog


    def run(self):
        self._info_dialog.run()
        self._info_dialog.hide()


    def _resize_logo(self):
        try:
            logo_pixbuf = self._info_dialog.get_logo()
            self._info_dialog.set_logo(
                logo_pixbuf.scale_simple(256, 256, GdkPixbuf.InterpType.HYPER)
            )
        except:
            self._logger.warn("Failed to resize logo")




class Window():
    SETTING_HOST = 'host'
    SETTING_PORT = 'port'
    SETTING_CONNECTED = 'connected'
    SETTING_IMAGE_DIR = 'image-dir'
    SETTING_WINDOW_SIZE = 'window-size'
    SETTING_WINDOW_MAXIMIZED = 'window-maximized'
    SETTING_PANEL = 'panel'
    SETTING_TRACKLIST_SIZE = 'tracklist-size'
    SETTING_ITEM_SIZE = 'item-size'
    SETTING_SORT_ORDER = 'sort-order'
    SETTING_SORT_TYPE = 'sort-type'
    STOCK_ICON_DEFAULT = 'image-x-generic-symbolic'
    _PANEL_INDEX_SERVER = 0
    _PANEL_INDEX_COVER = 1
    _PANEL_INDEX_PLAYLIST = 2
    _PANEL_INDEX_LIBRARY = 3
    _CSS_SELECTION = 'selection'


    def __init__(self, app, builder, title, settings):
        self._appwindow = builder.get_object('appwindow')
        self._appwindow.set_application(app)
        self._appwindow.set_title(title)
        self._settings = settings
        self._panels = []
        self._mcg = client.Client()    
        self._logger = logging.getLogger(__name__)
        self._size = self._settings.get_value(Window.SETTING_WINDOW_SIZE)
        self._maximized = self._settings.get_boolean(Window.SETTING_WINDOW_MAXIMIZED)
        self._fullscreened = False

        # Login screen
        self._connection_panel = ConnectionPanel(builder)
        # Panels
        self._panels.append(ServerPanel(builder))
        self._panels.append(CoverPanel(builder))
        self._panels.append(PlaylistPanel(builder))
        self._panels.append(LibraryPanel(builder))

        # Widgets
        # InfoBar
        self._infobar = InfoBar(builder)
        # Stack
        self._content_stack = builder.get_object('contentstack')
        self._stack = builder.get_object('panelstack')
        # Header
        self._header_bar = HeaderBar(builder)
        # Toolbar stack
        self._toolbar_stack = builder.get_object('toolbarstack')

        # Properties
        self._header_bar.set_sensitive(False, False)
        self._connection_panel.set_host(self._settings.get_string(Window.SETTING_HOST))
        self._connection_panel.set_port(self._settings.get_int(Window.SETTING_PORT))
        if use_keyring:
            self._connection_panel.set_password(keyring.get_password(ZeroconfProvider.KEYRING_SYSTEM, ZeroconfProvider.KEYRING_USERNAME))
        self._connection_panel.set_image_dir(self._settings.get_string(Window.SETTING_IMAGE_DIR))
        self._panels[Window._PANEL_INDEX_COVER].set_tracklist_size(self._settings.get_enum(Window.SETTING_TRACKLIST_SIZE))
        self._panels[Window._PANEL_INDEX_PLAYLIST].set_item_size(self._settings.get_int(Window.SETTING_ITEM_SIZE))
        self._panels[Window._PANEL_INDEX_LIBRARY].set_item_size(self._settings.get_int(Window.SETTING_ITEM_SIZE))
        self._panels[Window._PANEL_INDEX_LIBRARY].set_sort_order(self._settings.get_enum(Window.SETTING_SORT_ORDER))
        self._panels[Window._PANEL_INDEX_LIBRARY].set_sort_type(self._settings.get_boolean(Window.SETTING_SORT_TYPE))

        # Signals
        self._header_bar.connect('stack-switched', self.on_header_bar_stack_switched)
        self._header_bar.connect('toolbar-connect', self.on_header_bar_connect)
        self._header_bar.connect('toolbar-playpause', self.on_header_bar_playpause)
        self._header_bar.connect('toolbar-set-volume', self.on_header_bar_set_volume)
        self._connection_panel.connect('connection-changed', self.on_connection_panel_connection_changed)
        self._panels[Window._PANEL_INDEX_SERVER].connect('change-output-device', self.on_server_panel_output_device_changed)
        self._panels[Window._PANEL_INDEX_COVER].connect('toggle-fullscreen', self.on_cover_panel_toggle_fullscreen)
        self._panels[Window._PANEL_INDEX_COVER].connect('tracklist-size-changed', self.on_cover_panel_tracklist_size_changed)
        self._panels[Window._PANEL_INDEX_COVER].connect('set-song', self.on_cover_panel_set_song)
        self._panels[Window._PANEL_INDEX_PLAYLIST].connect('clear-playlist', self.on_playlist_panel_clear_playlist)
        self._panels[Window._PANEL_INDEX_PLAYLIST].connect('remove', self.on_playlist_panel_remove)
        self._panels[Window._PANEL_INDEX_PLAYLIST].connect('remove-multiple', self.on_playlist_panel_remove_multiple)
        self._panels[Window._PANEL_INDEX_PLAYLIST].connect('play', self.on_playlist_panel_play)
        self._panels[Window._PANEL_INDEX_LIBRARY].connect('update', self.on_library_panel_update)
        self._panels[Window._PANEL_INDEX_LIBRARY].connect('play', self.on_library_panel_play)
        self._panels[Window._PANEL_INDEX_LIBRARY].connect('play-multiple', self.on_library_panel_play_multiple)
        self._panels[Window._PANEL_INDEX_LIBRARY].connect('item-size-changed', self.on_library_panel_item_size_changed)
        self._panels[Window._PANEL_INDEX_LIBRARY].connect('sort-order-changed', self.on_library_panel_sort_order_changed)
        self._panels[Window._PANEL_INDEX_LIBRARY].connect('sort-type-changed', self.on_library_panel_sort_type_changed)
        self._mcg.connect_signal(client.Client.SIGNAL_CONNECTION, self.on_mcg_connect)
        self._mcg.connect_signal(client.Client.SIGNAL_STATUS, self.on_mcg_status)
        self._mcg.connect_signal(client.Client.SIGNAL_STATS, self.on_mcg_stats)
        self._mcg.connect_signal(client.Client.SIGNAL_LOAD_OUTPUT_DEVICES, self.on_mcg_load_output_devices)
        self._mcg.connect_signal(client.Client.SIGNAL_LOAD_PLAYLIST, self.on_mcg_load_playlist)
        self._mcg.connect_signal(client.Client.SIGNAL_LOAD_ALBUMS, self.on_mcg_load_albums)
        self._mcg.connect_signal(client.Client.SIGNAL_ERROR, self.on_mcg_error)
        self._settings.connect('changed::'+Window.SETTING_PANEL, self.on_settings_panel_changed)
        self._settings.connect('changed::'+Window.SETTING_TRACKLIST_SIZE, self.on_settings_tracklist_size_changed)
        self._settings.connect('changed::'+Window.SETTING_ITEM_SIZE, self.on_settings_item_size_changed)
        self._settings.connect('changed::'+Window.SETTING_SORT_ORDER, self.on_settings_sort_order_changed)
        self._settings.connect('changed::'+Window.SETTING_SORT_TYPE, self.on_settings_sort_type_changed)
        handlers = {
            'on_appwindow_size_allocate': self.on_resize,
            'on_appwindow_window_state_event': self.on_state,
            'on_appwindow_destroy': self.on_destroy
        }
        handlers.update(self._header_bar.get_signal_handlers())
        handlers.update(self._infobar.get_signal_handlers())
        handlers.update(self._connection_panel.get_signal_handlers())
        handlers.update(self._panels[Window._PANEL_INDEX_COVER].get_signal_handlers())
        handlers.update(self._panels[Window._PANEL_INDEX_PLAYLIST].get_signal_handlers())
        handlers.update(self._panels[Window._PANEL_INDEX_LIBRARY].get_signal_handlers())
        builder.connect_signals(handlers)

        # Actions
        self._appwindow.resize(int(self._size[0]), int(self._size[1]))
        if self._maximized:
            self._appwindow.maximize()
        self._appwindow.show_all()
        self._content_stack.set_visible_child(self._connection_panel.get())
        if self._settings.get_boolean(Window.SETTING_CONNECTED):
            self._connect()

        # Menu actions
        self._connect_action = Gio.SimpleAction.new_stateful("connect", None, GLib.Variant.new_boolean(False))
        self._connect_action.connect('change-state', self.on_menu_connect)
        self._appwindow.add_action(self._connect_action)
        self._play_action = Gio.SimpleAction.new_stateful("play", None, GLib.Variant.new_boolean(False))
        self._play_action.set_enabled(False)
        self._play_action.connect('change-state', self.on_menu_play)
        self._appwindow.add_action(self._play_action)
        self._clear_playlist_action = Gio.SimpleAction.new("clear-playlist", None)
        self._clear_playlist_action.set_enabled(False)
        self._clear_playlist_action.connect('activate', self.on_menu_clear_playlist)
        self._appwindow.add_action(self._clear_playlist_action)
        panel_variant = GLib.Variant.new_string("0")
        self._panel_action = Gio.SimpleAction.new_stateful("panel", panel_variant.get_type(), panel_variant)
        self._panel_action.set_enabled(False)
        self._panel_action.connect('change-state', self.on_menu_panel)
        self._appwindow.add_action(self._panel_action)


    def get(self):
        return self._appwindow


    def present(self):
        self._appwindow.present()
        self._appwindow.resize(800, 600)


    def on_resize(self, widget, event):
        if not self._maximized:
            self._size = (self._appwindow.get_allocation().width, self._appwindow.get_allocation().height)


    def on_state(self, widget, state):
        self._maximized = (state.new_window_state & Gdk.WindowState.MAXIMIZED > 0)
        self._fullscreen((state.new_window_state & Gdk.WindowState.FULLSCREEN > 0))
        self._settings.set_boolean(Window.SETTING_WINDOW_MAXIMIZED, self._maximized)


    def on_destroy(self, window):
        self._settings.set_value(Window.SETTING_WINDOW_SIZE, GLib.Variant('ai', list(self._size)))


    def on_menu_connect(self, action, value):
        self._connect()


    def on_menu_play(self, action, value):
        self._mcg.playpause()


    def on_menu_clear_playlist(self, action, value):
        self._mcg.clear_playlist()


    def on_menu_panel(self, action, value):
        action.set_state(value)
        self._stack.set_visible_child(self._panels[int(value.get_string())].get())


    # HeaderBar callbacks

    def on_header_bar_stack_switched(self, widget):
        self._set_visible_toolbar()
        self._save_visible_panel()
        self._set_menu_visible_panel()


    def on_header_bar_connect(self, widget):
        self._connect()


    def on_header_bar_playpause(self, widget):
        self._mcg.playpause()
        self._mcg.get_status()


    def on_header_bar_set_volume(self, widget, volume):
        self._mcg.set_volume(volume)


    # Panel callbacks

    def on_connection_panel_connection_changed(self, widget, host, port, password, image_dir):
        self._settings.set_string(Window.SETTING_HOST, host)
        self._settings.set_int(Window.SETTING_PORT, port)
        if use_keyring:
            if password:
                keyring.set_password(ZeroconfProvider.KEYRING_SYSTEM, ZeroconfProvider.KEYRING_USERNAME, password)
            else:
                if keyring.get_password(ZeroconfProvider.KEYRING_SYSTEM, ZeroconfProvider.KEYRING_USERNAME):
                   keyring.delete_password(ZeroconfProvider.KEYRING_SYSTEM, ZeroconfProvider.KEYRING_USERNAME)
        self._settings.set_string(Window.SETTING_IMAGE_DIR, image_dir)


    def on_playlist_panel_clear_playlist(self, widget):
        self._mcg.clear_playlist()


    def on_playlist_panel_remove(self, widget, album):
        self._mcg.remove_album_from_playlist(album)


    def on_playlist_panel_remove_multiple(self, widget, albums):
        self._mcg.remove_albums_from_playlist(albums)


    def on_playlist_panel_play(self, widget, album):
        self._mcg.play_album_from_playlist(album)


    def on_server_panel_output_device_changed(self, widget, device, enabled):
        self._mcg.enable_output_device(device, enabled)


    def on_cover_panel_toggle_fullscreen(self, widget):
        if not self._fullscreened:
            self._appwindow.fullscreen()
        else:
            self._appwindow.unfullscreen()


    def on_cover_panel_tracklist_size_changed(self, widget, size):
        self._settings.set_enum(Window.SETTING_TRACKLIST_SIZE, size)


    def on_cover_panel_set_song(self, widget, pos, time):
        self._mcg.seek(pos, time)


    def on_library_panel_update(self, widget):
        self._mcg.update()


    def on_library_panel_play(self, widget, album):
        self._mcg.play_album(album)


    def on_library_panel_play_multiple(self, widget, albums):
        self._mcg.play_albums(albums)


    def on_library_panel_item_size_changed(self, widget, size):
        self._panels[Window._PANEL_INDEX_PLAYLIST].set_item_size(size)
        self._settings.set_int(Window.SETTING_ITEM_SIZE, self._panels[Window._PANEL_INDEX_LIBRARY].get_item_size())


    def on_library_panel_sort_order_changed(self, widget, sort_order):
        self._settings.set_enum(Window.SETTING_SORT_ORDER, self._panels[Window._PANEL_INDEX_LIBRARY].get_sort_order())


    def on_library_panel_sort_type_changed(self, widget, sort_type):
        self._settings.set_boolean(Window.SETTING_SORT_TYPE, self._panels[Window._PANEL_INDEX_LIBRARY].get_sort_type())


    # MCG callbacks

    def on_mcg_connect(self, connected):
        if connected:
            GObject.idle_add(self._connect_connected)
            self._mcg.load_playlist()
            self._mcg.load_albums()
            self._mcg.get_status()
            self._mcg.get_stats()
            self._mcg.get_output_devices()
            self._connect_action.set_state(GLib.Variant.new_boolean(True))
            self._play_action.set_enabled(True)
            self._clear_playlist_action.set_enabled(True)
            self._panel_action.set_enabled(True)
        else:
            GObject.idle_add(self._connect_disconnected)
            self._connect_action.set_state(GLib.Variant.new_boolean(False))
            self._play_action.set_enabled(False)
            self._clear_playlist_action.set_enabled(False)
            self._panel_action.set_enabled(False)


    def on_mcg_status(self, state, album, pos, time, volume, file, audio, bitrate, error):
        # Album
        GObject.idle_add(self._panels[Window._PANEL_INDEX_COVER].set_album, album)
        if not album and self._fullscreened:
            self._fullscreen(False)
        # State
        if state == 'play':
            GObject.idle_add(self._header_bar.set_play)
            GObject.idle_add(self._panels[Window._PANEL_INDEX_COVER].set_play, pos, time)
            self._play_action.set_state(GLib.Variant.new_boolean(True))
        elif state == 'pause' or state == 'stop':
            GObject.idle_add(self._header_bar.set_pause)
            GObject.idle_add(self._panels[Window._PANEL_INDEX_COVER].set_pause)
            self._play_action.set_state(GLib.Variant.new_boolean(False))
        # Volume
        GObject.idle_add(self._header_bar.set_volume, volume)
        # Status
        self._panels[Window._PANEL_INDEX_SERVER].set_status(file, audio, bitrate, error)
        # Error
        if error is None:
            self._infobar.hide()
        else:
            self._show_error(error)


    def on_mcg_stats(self, artists, albums, songs, dbplaytime, playtime, uptime):
        self._panels[Window._PANEL_INDEX_SERVER].set_stats(artists, albums, songs, dbplaytime, playtime, uptime)


    def on_mcg_load_output_devices(self, devices):
        self._panels[Window._PANEL_INDEX_SERVER].set_output_devices(devices)


    def on_mcg_load_playlist(self, playlist):
        self._panels[self._PANEL_INDEX_PLAYLIST].set_playlist(self._connection_panel.get_host(), playlist)


    def on_mcg_load_albums(self, albums):
        self._panels[self._PANEL_INDEX_LIBRARY].set_albums(self._connection_panel.get_host(), albums)


    def on_mcg_error(self, error):
        GObject.idle_add(self._show_error, str(error))


    # Settings callbacks

    def on_settings_panel_changed(self, settings, key):
        panel_index = settings.get_int(key)
        self._stack.set_visible_child(self._panels[panel_index].get())


    def on_settings_tracklist_size_changed(self, settings, key):
        size = settings.get_enum(key)
        self._panels[Window._PANEL_INDEX_COVER].set_tracklist_size(size)


    def on_settings_item_size_changed(self, settings, key):
        size = settings.get_int(key)
        self._panels[Window._PANEL_INDEX_PLAYLIST].set_item_size(size)
        self._panels[Window._PANEL_INDEX_LIBRARY].set_item_size(size)


    def on_settings_sort_order_changed(self, settings, key):
        sort_order = settings.get_enum(key)
        self._panels[Window._PANEL_INDEX_LIBRARY].set_sort_order(sort_order)


    def on_settings_sort_type_changed(self, settings, key):
        sort_type = settings.get_boolean(key)
        self._panels[Window._PANEL_INDEX_LIBRARY].set_sort_type(sort_type)


    # Private methods

    def _connect(self):
        self._connection_panel.get().set_sensitive(False)
        self._header_bar.set_sensitive(False, True)
        if self._mcg.is_connected():
            self._mcg.disconnect()
            self._settings.set_boolean(Window.SETTING_CONNECTED, False)
        else:
            host = self._connection_panel.get_host()
            port = self._connection_panel.get_port()
            password = self._connection_panel.get_password()
            image_dir = self._connection_panel.get_image_dir()
            self._mcg.connect(host, port, password, image_dir)
            self._settings.set_boolean(Window.SETTING_CONNECTED, True)


    def _connect_connected(self):
        self._header_bar.connected()
        self._header_bar.set_sensitive(True, False)
        self._content_stack.set_visible_child(self._stack)
        self._stack.set_visible_child(self._panels[self._settings.get_int(Window.SETTING_PANEL)].get())


    def _connect_disconnected(self):
        self._panels[Window._PANEL_INDEX_PLAYLIST].stop_threads();
        self._panels[Window._PANEL_INDEX_LIBRARY].stop_threads();
        self._header_bar.disconnected()
        self._header_bar.set_sensitive(False, False)
        self._save_visible_panel()
        self._content_stack.set_visible_child(self._connection_panel.get())
        self._connection_panel.get().set_sensitive(True)


    def _fullscreen(self, fullscreened_new):
        if fullscreened_new != self._fullscreened:
            self._fullscreened = fullscreened_new
            if self._fullscreened:
                self._header_bar.get().hide()
                self._panels[Window._PANEL_INDEX_COVER].set_fullscreen(True)
            else:
                self._header_bar.get().show()
                self._panels[Window._PANEL_INDEX_COVER].set_fullscreen(False)


    def _save_visible_panel(self):
        panels = [panel.get() for panel in self._panels]
        panel_index_selected = panels.index(self._stack.get_visible_child())
        self._settings.set_int(Window.SETTING_PANEL, panel_index_selected)


    def _set_menu_visible_panel(self):
        panels = [panel.get() for panel in self._panels]
        panel_index_selected = panels.index(self._stack.get_visible_child())
        self._panel_action.set_state(GLib.Variant.new_string(str(panel_index_selected)))


    def _set_visible_toolbar(self):
        panels = [panel.get() for panel in self._panels]
        panel_index_selected = panels.index(self._stack.get_visible_child())
        toolbar = self._panels[panel_index_selected].get_toolbar()
        self._toolbar_stack.set_visible_child(toolbar)


    def _show_error(self, message):
        self._infobar.show_error(message)




class HeaderBar(GObject.GObject):
    __gsignals__ = {
        'stack-switched': (GObject.SIGNAL_RUN_FIRST, None, ()),
        'toolbar-connect': (GObject.SIGNAL_RUN_FIRST, None, ()),
        'toolbar-playpause': (GObject.SIGNAL_RUN_FIRST, None, ()),
        'toolbar-set-volume': (GObject.SIGNAL_RUN_FIRST, None, (int,))
    }


    def __init__(self, builder):
        GObject.GObject.__init__(self)
        self._changing_volume = False
        self._setting_volume = False

        # Widgets
        self._header_bar = builder.get_object('headerbar')
        self._title_stack = builder.get_object('headerbar-title-stack')
        self._connection_label = builder.get_object('headerbar-connectionn-label')
        self._stack_switcher = StackSwitcher(builder)
        self._button_connect = builder.get_object('headerbar-connection')
        self._button_playpause = builder.get_object('headerbar-playpause')
        self._button_volume = builder.get_object('headerbar-volume')

        # Signals
        self._stack_switcher.connect('stack-switched', self.on_stack_switched)
        self._button_handlers = {
            'on_headerbar-connection_active_notify': self.on_connection_active_notify,
            'on_headerbar-connection_state_set': self.on_connection_state_set,
            'on_headerbar-playpause_toggled': self.on_playpause_toggled,
            'on_headerbar-volume_value_changed': self.on_volume_changed,
            'on_headerbar-volume_button_press_event': self.on_volume_press,
            'on_headerbar-volume_button_release_event': self.on_volume_release
        }


    def get(self):
        return self._header_bar


    def get_signal_handlers(self):
        return self._button_handlers


    def set_sensitive(self, sensitive, connecting):
        self._button_playpause.set_sensitive(sensitive)
        self._button_volume.set_sensitive(sensitive)
        self._stack_switcher.get().set_sensitive(sensitive)
        self._button_connect.set_sensitive(not connecting)


    def on_connection_active_notify(self, widget, status):
        self.emit('toolbar-connect')


    def on_connection_state_set(self, widget, state):
        return True


    def on_playpause_toggled(self, widget):
        self.emit('toolbar-playpause')


    def on_stack_switched(self, widget):
        self.emit('stack-switched')


    def on_volume_changed(self, widget, value):
        if not self._setting_volume:
            self.emit('toolbar-set-volume', int(value*100))


    def on_volume_press(self, *args):
        self.volume_set_active(None, None, True)


    def on_volume_release(self, *args):
        self.volume_set_active(None, None, False)


    def volume_set_active(self, widget, event, active):
        self._changing_volume = active


    def connected(self):
        self._button_connect.handler_block_by_func(
            self.on_connection_active_notify
        )
        self._button_connect.set_active(True)
        self._button_connect.set_state(True)
        self._button_connect.handler_unblock_by_func(
            self.on_connection_active_notify
        )
        self._title_stack.set_visible_child(self._stack_switcher.get())


    def disconnected(self):
        self._button_connect.handler_block_by_func(
            self.on_connection_active_notify
        )
        self._button_connect.set_active(False)
        self._button_connect.set_state(False)
        self._button_connect.handler_unblock_by_func(
            self.on_connection_active_notify
        )
        self._title_stack.set_visible_child(self._connection_label)


    def set_play(self):
        self._button_playpause.handler_block_by_func(
            self.on_playpause_toggled
        )
        self._button_playpause.set_active(True)
        self._button_playpause.handler_unblock_by_func(
            self.on_playpause_toggled
        )


    def set_pause(self):
        self._button_playpause.handler_block_by_func(
            self.on_playpause_toggled
        )
        self._button_playpause.set_active(False)
        self._button_playpause.handler_unblock_by_func(
            self.on_playpause_toggled
        )


    def set_volume(self, volume):
        if volume >= 0:
            self._button_volume.set_visible(True)
            if not self._changing_volume:
                self._setting_volume = True
                self._button_volume.set_value(volume / 100)
                self._setting_volume = False
        else:
            self._button_volume.set_visible(False)




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




class ConnectionPanel(GObject.GObject):
    __gsignals__ = {
        'connection-changed': (GObject.SIGNAL_RUN_FIRST, None, (str, int, str, str))
    }


    def __init__(self, builder):
        GObject.GObject.__init__(self)
        self._services = Gtk.ListStore(str, str, int)
        self._profile = None

        # Widgets
        self._panel = builder.get_object('connection-panel')
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
        # Image directory
        self._image_dir_entry = builder.get_object('server-image-dir')

        # Zeroconf provider
        self._zeroconf_provider = ZeroconfProvider()
        self._zeroconf_provider.connect_signal(ZeroconfProvider.SIGNAL_SERVICE_NEW, self.on_new_service)


    def get(self):
        return self._panel


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
        self.emit('connection-changed', self.get_host(), self.get_port(), self.get_password(), self.get_image_dir())




class ServerPanel(GObject.GObject):
    __gsignals__ = {
        'change-output-device': (GObject.SIGNAL_RUN_FIRST, None, (GObject.TYPE_PYOBJECT,bool,)),
    }


    def __init__(self, builder):
        GObject.GObject.__init__(self)
        self._none_label = ""
        self._output_buttons = {}

        # Widgets
        self._panel = builder.get_object('server-panel')
        self._toolbar = builder.get_object('server-toolbar')
        self._stack = builder.get_object('server-stack')

        # Status widgets
        self._status_file = builder.get_object('server-status-file')
        self._status_audio = builder.get_object('server-status-audio')
        self._status_bitrate = builder.get_object('server-status-bitrate')
        self._status_error = builder.get_object('server-status-error')
        self._none_label = self._status_file.get_label()

        # Stats widgets
        self._stats_artists = builder.get_object('server-stats-artists')
        self._stats_albums = builder.get_object('server-stats-albums')
        self._stats_songs = builder.get_object('server-stats-songs')
        self._stats_dbplaytime = builder.get_object('server-stats-dbplaytime')
        self._stats_playtime = builder.get_object('server-stats-playtime')
        self._stats_uptime = builder.get_object('server-stats-uptime')

        # Audio ouptut devices widgets
        self._output_devices = builder.get_object('server-output-devices')


    def get(self):
        return self._panel


    def get_toolbar(self):
        return self._toolbar


    def on_output_device_toggled(self, widget, device):
        self.emit('change-output-device', device, widget.get_active())


    def set_status(self, file, audio, bitrate, error):
        if file:
            file = GObject.markup_escape_text(file)
        else:
            file = self._none_label
        self._status_file.set_markup(file)
        # Audio information
        if  audio:
            parts = audio.split(":")
            if len(parts) == 3:
                audio = "{} Hz, {} bit, {} channels".format(parts[0], parts[1], parts[2])
        else:
            audio = self._none_label
        self._status_audio.set_markup(audio)
        # Bitrate
        if bitrate:
            bitrate = bitrate + " kb/s"
        else:
            bitrate = self._none_label
        self._status_bitrate.set_markup(bitrate)
        # Error
        if error:
            error = GObject.markup_escape_text(error)
        else:
            error = self._none_label
        self._status_error.set_markup(error)


    def set_stats(self, artists, albums, songs, dbplaytime, playtime, uptime):
        self._stats_artists.set_text(str(artists))
        self._stats_albums.set_text(str(albums))
        self._stats_songs.set_text(str(songs))
        self._stats_dbplaytime.set_text(str(dbplaytime))
        self._stats_playtime.set_text(str(playtime))
        self._stats_uptime.set_text(str(uptime))


    def set_output_devices(self, devices):
        device_ids = []

        # Add devices
        for device in devices:
            device_ids.append(device.get_id())
            if device.get_id() in self._output_buttons.keys():
                self._output_buttons[device.get_id()].freeze_notify()
                self._output_buttons[device.get_id()].set_active(device.is_enabled())
                self._output_buttons[device.get_id()].thaw_notify()
            else:
                button = Gtk.CheckButton(device.get_name())
                if device.is_enabled():
                    button.set_active(True)
                handler = button.connect('toggled', self.on_output_device_toggled, device)
                self._output_devices.insert(button, -1)
                self._output_buttons[device.get_id()] = button
        self._output_devices.show_all()

        # Remove devices
        for id in self._output_buttons.keys():
            if id not in device_ids:
                self._output_devices.remove(self._output_buttons[id].get_parent())





class CoverPanel(GObject.GObject):
    __gsignals__ = {
        'toggle-fullscreen': (GObject.SIGNAL_RUN_FIRST, None, ()),
        'tracklist-size-changed': (GObject.SIGNAL_RUN_FIRST, None, (int,)),
        'set-song': (GObject.SIGNAL_RUN_FIRST, None, (int, int,))
    }


    def __init__(self, builder):
        GObject.GObject.__init__(self)

        self._current_album = None
        self._cover_pixbuf = None
        self._timer = None
        self._properties = {}
        self._tracklist_size = TracklistSize.LARGE
        self._icon_theme = Gtk.IconTheme.get_default()
        self._fullscreened = False

        # Widgets
        self._appwindow = builder.get_object('appwindow')
        self._panel = builder.get_object('cover-panel')
        self._toolbar = builder.get_object('cover-toolbar')
        # Toolbar menu
        self._toolbar_fullscreen_button = builder.get_object('cover-toolbar-fullscreen')
        self._toolbar_tracklist = builder.get_object('cover-toolbar-tracklist')
        self._toolbar_tracklist_buttons = {
            TracklistSize.LARGE: builder.get_object('cover-toolbar-tracklist-large'),
            TracklistSize.SMALL: builder.get_object('cover-toolbar-tracklist-small'),
            TracklistSize.HIDDEN: builder.get_object('cover-toolbar-tracklist-hidden')
        }
        # Cover
        self._cover_stack = builder.get_object('cover-stack')
        self._cover_spinner = builder.get_object('cover-spinner')
        self._cover_scroll = builder.get_object('cover-scroll')
        self._cover_box = builder.get_object('cover-box')
        self._cover_image = builder.get_object('cover-image')
        self._cover_stack.set_visible_child(self._cover_scroll)
        self._cover_pixbuf = self._get_default_image()
        # Album Infos
        self._info_revealer = builder.get_object('cover-info-revealer')
        self._info_box = builder.get_object('cover-info-box')
        self._album_title_label = builder.get_object('cover-album')
        self._album_date_label = builder.get_object('cover-date')
        self._album_artist_label = builder.get_object('cover-artist')
        # Songs
        self._songs_scale = builder.get_object('cover-songs')
        self._songs_scale.override_color(Gtk.StateFlags.NORMAL, Gdk.RGBA(0, 0, 0, 1))

        # Initial actions
        GObject.idle_add(self._enable_tracklist)


    def get(self):
        return self._panel


    def get_toolbar(self):
        return self._toolbar


    def get_signal_handlers(self):
        return {
            'on_cover-toolbar-fullscreen_clicked': self.on_fullscreen_clicked,
            'on_cover-toolbar-tracklist_toggled': self.on_tracklist_togged,
            'on_cover-box_button_press_event': self.on_cover_box_pressed,
            'on_cover-scroll_size_allocate': self.on_cover_size_allocate,
            'on_cover-songs_button_press_event': self.on_songs_start_change,
            'on_cover-songs_button_release_event': self.on_songs_change
        }


    def on_fullscreen_clicked(self, widget):
        self.emit('toggle-fullscreen')


    def on_tracklist_togged(self, widget):
        if widget.get_active():
            size = [key for key, value in self._toolbar_tracklist_buttons.items() if value is widget][0]
            self._change_tracklist_size(size)


    def on_cover_box_pressed(self, widget, event):
        if self._current_album and event.type == Gdk.EventType._2BUTTON_PRESS:
            self.emit('toggle-fullscreen')


    def on_cover_size_allocate(self, widget, allocation):
        GObject.idle_add(self._resize_image)


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
        self.emit('set-song', pos, time)


    def set_tracklist_size(self, size):
        if self._tracklist_size != size:
            button = self._toolbar_tracklist_buttons[size]
            if button and not button.get_active():
                button.set_active(True)
                self._change_tracklist_size(size, False)


    def get_tracklist_size(self):
        return self._tracklist_size


    def set_album(self, album):
        if album:
            # Set labels
            self._album_title_label.set_label(
                GObject.markup_escape_text(
                    album.get_title()
                )
            )
            self._album_date_label.set_markup(
                GObject.markup_escape_text(
                    ', '.join(album.get_dates())
                )
            )
            self._album_artist_label.set_markup(
                GObject.markup_escape_text(
                    ', '.join(album.get_albumartists())
                )
            )
            # Set tracks
            self._set_tracks(album)

        # Set current album
        old_album = self._current_album
        self._current_album = album
        self._enable_tracklist()
        self._toolbar_fullscreen_button.set_sensitive(self._current_album is not None)

        # Load cover
        threading.Thread(target=self._set_cover, args=(old_album, album,)).start()


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
            self._change_tracklist_size(TracklistSize.HIDDEN, False, False)
            self._cover_box.override_background_color(Gtk.StateFlags.NORMAL, Gdk.RGBA(0, 0, 0, 1))
            GObject.idle_add(self._resize_image)
            # Hide curser
            self._appwindow.get_window().set_cursor(
                Gdk.Cursor.new_from_name(Gdk.Display.get_default(), "none")
            )
            self._fullscreened = True
        else:
            self._fullscreened = False
            self._change_tracklist_size(self._tracklist_size, False, False)
            self._cover_box.override_background_color(Gtk.StateFlags.NORMAL, Gdk.RGBA(0, 0, 0, 0))
            GObject.idle_add(self._resize_image)
            # Reset cursor
            self._appwindow.get_window().set_cursor(
                Gdk.Cursor.new_from_name(Gdk.Display.get_default(), "default")
            )


    def _set_cover(self, current_album, new_album):
        self._cover_stack.set_visible_child(self._cover_spinner)
        self._cover_spinner.start()
        current_hash = current_album.get_hash() if current_album else None
        new_hash = new_album.get_hash() if new_album else None
        if not current_hash or not new_hash or current_hash != new_hash:
            url = new_album.get_cover() if new_album else None
            if url and url is not "":
                # Load image and draw it
                self._cover_pixbuf = Utils.load_cover(url)
            else:
                # Reset image
                self._cover_pixbuf = self._get_default_image()
            self._resize_image()
        self._cover_stack.set_visible_child(self._cover_scroll)
        self._cover_spinner.stop()


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
                    Utils.create_track_title(track)
                )
            )
            length = length + track.get_length()
        self._songs_scale.add_mark(length, Gtk.PositionType.RIGHT, "{0[0]:02d}:{0[1]:02d} minutes".format(divmod(length, 60)))


    def _enable_tracklist(self):
        if self._current_album:
            # enable
            self._toolbar_tracklist.set_sensitive(True)
            self._change_tracklist_size(self._tracklist_size, False, False)
        else:
            # disable
            self._toolbar_tracklist.set_sensitive(False)
            self._change_tracklist_size(TracklistSize.HIDDEN, False, False)


    def _change_tracklist_size(self, size, notify=True, store=True):
        # Set tracklist size
        if not self._fullscreened:
            if size == TracklistSize.LARGE:
                self._panel.set_homogeneous(True)
                self._info_revealer.set_reveal_child(True)
            elif size == TracklistSize.SMALL:
                self._panel.set_homogeneous(False)
                self._info_revealer.set_reveal_child(True)
            else:
                self._panel.set_homogeneous(False)
                self._info_revealer.set_reveal_child(False)
        # Store size
        if store:
            self._tracklist_size = size
        # Notify signals
        if notify:
            self.emit('tracklist-size-changed', size)
        # Resize image
        GObject.idle_add(self._resize_image)


    def _playing(self):
        value = self._songs_scale.get_value() + 1
        self._songs_scale.set_value(value)

        return True


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


    def _get_default_image(self):
        return self._icon_theme.load_icon(
            Window.STOCK_ICON_DEFAULT,
            512,
            Gtk.IconLookupFlags.FORCE_SVG & Gtk.IconLookupFlags.FORCE_SIZE
        )




class PlaylistPanel(GObject.GObject):
    __gsignals__ = {
        'clear-playlist': (GObject.SIGNAL_RUN_FIRST, None, ()),
        'remove': (GObject.SIGNAL_RUN_FIRST, None, (GObject.TYPE_PYOBJECT,)),
        'remove-multiple': (GObject.SIGNAL_RUN_FIRST, None, (GObject.TYPE_PYOBJECT,)),
        'play': (GObject.SIGNAL_RUN_FIRST, None, (GObject.TYPE_PYOBJECT,))
    }


    def __init__(self, builder):
        GObject.GObject.__init__(self)
        self._host = None
        self._item_size = 150
        self._playlist = None
        self._playlist_albums = None
        self._playlist_lock = threading.Lock()
        self._playlist_stop = threading.Event()
        self._icon_theme = Gtk.IconTheme.get_default()
        self._standalone_pixbuf = None
        self._selected_albums = []

        # Widgets
        self._appwindow = builder.get_object('appwindow')
        self._panel = builder.get_object('playlist-panel')
        self._toolbar = builder.get_object('playlist-toolbar')
        self._headerbar = builder.get_object('headerbar')
        self._headerbar_standalone = builder.get_object('headerbar-playlist-standalone')
        self._panel_normal = builder.get_object('playlist-panel-normal')
        self._panel_standalone = builder.get_object('playlist-panel-standalone')
        self._actionbar_revealer = builder.get_object('playlist-actionbar-revealer')

        # Select button
        self._select_button = builder.get_object('playlist-toolbar-select')
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
        # Action bar (normal)
        actionbar = builder.get_object('playlist-actionbar')
        cancel_button = Gtk.Button('cancel')
        cancel_button.connect('clicked', self.on_selection_cancel_clicked)
        actionbar.pack_start(cancel_button)
        remove_button = Gtk.Button('remove')
        remove_button.connect('clicked', self.on_selection_remove_clicked)
        actionbar.pack_end(remove_button)

        # Standalone labels
        self._standalone_title = builder.get_object('headerbar-playlist-standalone-title')
        self._standalone_artist = builder.get_object('headerbar-playlist-standalone-artist')
        # Standalone Image
        self._standalone_stack = builder.get_object('playlist-standalone-stack')
        self._standalone_spinner = builder.get_object('playlist-standalone-spinner')
        self._standalone_scroll = builder.get_object('playlist-standalone-scroll')
        self._standalone_image = builder.get_object('playlist-standalone-image')
        # Action bar (standalone)
        actionbar_standalone = builder.get_object('playlist-standalone-actionbar')
        play_button = Gtk.Button('play')
        play_button.connect('clicked', self.on_standalone_play_clicked)
        actionbar_standalone.pack_end(play_button)
        remove_button = Gtk.Button('remove')
        remove_button.connect('clicked', self.on_standalone_remove_clicked)
        actionbar_standalone.pack_end(remove_button)


    def get(self):
        return self._panel


    def get_toolbar(self):
        return self._toolbar


    def get_signal_handlers(self):
        return {
            'on_playlist-toolbar-select_toggled': self.on_select_toggled,
            'on_playlist-toolbar-clear_clicked': self.clear_clicked,
            'on_playlist-iconview_item_activated': self.on_playlist_grid_clicked,
            'on_playlist-iconview_selection_changed': self.on_playlist_grid_selection_changed,
            'on_playlist-standalone-scroll_size_allocate': self.on_standalone_scroll_size_allocate,
            'on_headerbar-playlist-standalone-close_clicked': self.on_standalone_close_clicked
        }


    def on_select_toggled(self, widget):
        if widget.get_active():
            self._actionbar_revealer.set_reveal_child(True)
            self._playlist_grid.set_selection_mode(Gtk.SelectionMode.MULTIPLE)
            self._playlist_grid.get_style_context().add_class(Window._CSS_SELECTION)
        else:
            self._actionbar_revealer.set_reveal_child(False)
            self._playlist_grid.set_selection_mode(Gtk.SelectionMode.SINGLE)
            self._playlist_grid.get_style_context().remove_class(Window._CSS_SELECTION)


    def clear_clicked(self, widget):
        if widget is self._playlist_clear_button:
            self.emit('clear-playlist')


    def on_playlist_grid_clicked(self, widget, path):
        # Get selected album
        iter = self._playlist_grid_model.get_iter(path)
        hash = self._playlist_grid_model.get_value(iter, 2)
        album = self._playlist_albums[hash]
        self._selected_albums = [album]

        # Show standalone album
        if widget.get_selection_mode() == Gtk.SelectionMode.SINGLE:
            # Set labels
            self._standalone_title.set_text(album.get_title())
            self._standalone_artist.set_text(", ".join(album.get_albumartists()))

            # Show panel
            self._open_standalone()

            # Load cover
            threading.Thread(target=self._show_standalone_image, args=(album,)).start()


    def on_playlist_grid_selection_changed(self, widget):
        self._selected_albums = []
        for path in widget.get_selected_items():
            iter = self._playlist_grid_model.get_iter(path)
            hash = self._playlist_grid_model.get_value(iter, 2)
            self._selected_albums.append(self._playlist_albums[hash])


    def on_selection_cancel_clicked(self, widget):
        self._select_button.set_active(False)


    def on_selection_remove_clicked(self, widget):
        self.emit('remove-multiple', self._selected_albums)
        self._select_button.set_active(False)


    def on_standalone_scroll_size_allocate(self, widget, allocation):
        self._resize_standalone_image()


    def on_standalone_close_clicked(self, widget):
        self._close_standalone()


    def on_standalone_remove_clicked(self, widget):
        self.emit('remove', self._selected_albums[0])
        self._close_standalone()


    def on_standalone_play_clicked(self, widget):
        self.emit('play', self._selected_albums[0])
        self._close_standalone()


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
        self._playlist_albums = {}
        for album in playlist:
            self._playlist_albums[album.get_hash()] = album
        self._playlist_grid.set_model(None)
        self._playlist_grid.freeze_child_notify()
        self._playlist_grid_model.clear()
        GObject.idle_add(self._playlist_grid.set_item_padding, size / 100)

        cache = client.MCGCache(host, size)
        for album in playlist:
            pixbuf = None
            if album.get_cover() is not None:
                try:
                    pixbuf = Utils.load_thumbnail(cache, album, size)
                except Exception as e:
                    print(e)
            if pixbuf is None:
                pixbuf = self._icon_theme.load_icon(
                    Window.STOCK_ICON_DEFAULT,
                    self._item_size,
                    Gtk.IconLookupFlags.FORCE_SVG & Gtk.IconLookupFlags.FORCE_SIZE
                )
            if pixbuf is not None:
                self._playlist_grid_model.append([
                    pixbuf,
                    GObject.markup_escape_text("\n".join([
                        album.get_title(),
                        ', '.join(album.get_dates()),
                        Utils.create_artists_label(album)
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


    def _open_standalone(self):
        self._panel.set_visible_child(self._panel_standalone)
        self._appwindow.set_titlebar(self._headerbar_standalone)


    def _close_standalone(self):
        self._panel.set_visible_child(self._panel.get_children()[0])
        self._appwindow.set_titlebar(self._headerbar)


    def _show_standalone_image(self, album):
        self._standalone_stack.set_visible_child(self._standalone_spinner)
        self._standalone_spinner.start()
        url = album.get_cover()
        if url is not None and url is not "":
            # Load image and draw it
            self._standalone_pixbuf = Utils.load_cover(url)
            self._resize_standalone_image()
        else:
            # Reset image
            self._standalone_image.clear()
        self._standalone_stack.set_visible_child(self._standalone_scroll)
        self._standalone_spinner.stop()


    def _resize_standalone_image(self):
        """Diese Methode skaliert das geladene Bild aus dem Pixelpuffer
        auf die Größe des Fensters unter Beibehalt der Seitenverhältnisse
        """
        pixbuf = self._standalone_pixbuf
        size = self._standalone_scroll.get_allocation()
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
        self._standalone_image.set_allocation(self._standalone_scroll.get_allocation())
        self._standalone_image.set_from_pixbuf(pixbuf.scale_simple(width, height, GdkPixbuf.InterpType.HYPER))
        self._standalone_image.show()




class LibraryPanel(GObject.GObject):
    __gsignals__ = {
        'update': (GObject.SIGNAL_RUN_FIRST, None, ()),
        'play': (GObject.SIGNAL_RUN_FIRST, None, (str,)),
        'play-multiple': (GObject.SIGNAL_RUN_FIRST, None, (GObject.TYPE_PYOBJECT,)),
        'item-size-changed': (GObject.SIGNAL_RUN_FIRST, None, (int,)),
        'sort-order-changed': (GObject.SIGNAL_RUN_FIRST, None, (int,)),
        'sort-type-changed': (GObject.SIGNAL_RUN_FIRST, None, (Gtk.SortType,))
    }


    def __init__(self, builder):
        GObject.GObject.__init__(self)
        self._buttons = {}
        self._albums = None
        self._host = "localhost"
        self._filter_string = ""
        self._item_size = 150
        self._sort_order = SortOrder.YEAR
        self._sort_type = Gtk.SortType.DESCENDING
        self._grid_pixbufs = {}
        self._old_ranges = {}
        self._library_lock = threading.Lock()
        self._library_stop = threading.Event()
        self._icon_theme = Gtk.IconTheme.get_default()
        self._standalone_pixbuf = None
        self._selected_albums = []
        self._allocation = (0, 0)

        # Widgets
        self._appwindow = builder.get_object('appwindow')
        self._panel = builder.get_object('library-panel')
        self._toolbar = builder.get_object('library-toolbar')
        self._headerbar = builder.get_object('headerbar')
        self._headerbar_standalone = builder.get_object('headerbar-library-standalone')
        self._panel_normal = builder.get_object('library-panel-normal')
        self._panel_standalone = builder.get_object('library-panel-standalone')
        self._actionbar_revealer = builder.get_object('library-actionbar-revealer')

        # Select button
        self._select_button = builder.get_object('library-toolbar-select')
        # Filter/search bar
        self._filter_bar = builder.get_object('library-filter-bar')
        self._filter_entry = builder.get_object('library-filter')
        # Progress Bar
        self._progress_revealer = builder.get_object('library-progress-revealer')
        self._progress_bar = builder.get_object('library-progress')
        # Toolbar menu
        self._toolbar_search_bar = builder.get_object('library-toolbar-search')
        self._toolbar_popover = builder.get_object('library-toolbar-popover')
        self._toolbar_sort_buttons = {
            SortOrder.ARTIST: builder.get_object('library-toolbar-sort-artist'),
            SortOrder.TITLE: builder.get_object('library-toolbar-sort-title'),
            SortOrder.YEAR: builder.get_object('library-toolbar-sort-year')
        }
        self._toolbar_sort_order_button = builder.get_object('library-toolbar-sort-order')
        self._grid_scale = builder.get_object('library-toolbar-scale')
        self._grid_scale.set_value(self._item_size)
        self._grid_adjustment = builder.get_object('library-scale-adjustment')
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
        # Action bar (normal)
        actionbar = builder.get_object('library-actionbar')
        cancel_button = Gtk.Button('cancel')
        cancel_button.connect('clicked', self.on_selection_cancel_clicked)
        actionbar.pack_start(cancel_button)
        add_button = Gtk.Button('add')
        add_button.connect('clicked', self.on_selection_add_clicked)
        actionbar.pack_end(add_button)

        # Standalone labels
        self._standalone_title = builder.get_object('headerbar-library-standalone-title')
        self._standalone_artist = builder.get_object('headerbar-library-standalone-artist')
        # Standalone Image
        self._standalone_stack = builder.get_object('library-standalone-stack')
        self._standalone_spinner = builder.get_object('library-standalone-spinner')
        self._standalone_scroll = builder.get_object('library-standalone-scroll')
        self._standalone_image = builder.get_object('library-standalone-image')
        # Action bar (standalone)
        actionbar_standalone = builder.get_object('library-standalone-actionbar')
        play_button = Gtk.Button('play')
        play_button.connect('clicked', self.on_standalone_play_clicked)
        actionbar_standalone.pack_end(play_button)


    def get(self):
        return self._panel


    def get_toolbar(self):
        return self._toolbar


    def get_signal_handlers(self):
        return {
            'on_library-toolbar-search_toggled': self.on_search_toggled,
            'on_library-toolbar-select_toggled': self.on_select_toggled,
            'on_library-toolbar-scale_change_value': self.on_grid_scale_change,
            'on_library-toolbar-scale_button_release_event': self.on_grid_scale_changed,
            'on_library-toolbar-update_clicked': self.on_update_clicked,
            'on_library-toolbar-sort-toggled': self.on_sort_toggled,
            'on_library-toolbar-sort-order_toggled': self.on_sort_order_toggled,
            'on_library-filter-bar_notify': self.on_filter_bar_notify,
            'on_library-filter_search_changed': self.on_filter_entry_changed,
            'on_library-iconview_item_activated': self.on_library_grid_clicked,
            'on_library-iconview_selection_changed': self.on_library_grid_selection_changed,
            'on_library-standalone-scroll_size_allocate': self.on_standalone_scroll_size_allocate,
            'on_headerbar-library-standalone-close_clicked': self.on_standalone_close_clicked,
            'on_library-iconview_size_allocate': self.on_resize
        }


    def on_resize(self, widget, event):
        new_allocation = (widget.get_allocation().width, widget.get_allocation().height)
        if new_allocation == self._allocation:
            return
        self._allocation = new_allocation
        self._grid_scale.clear_marks()
        width = widget.get_allocation().width - 12

        lower = int(self._grid_adjustment.get_lower())
        upper = int(self._grid_adjustment.get_upper())
        countMin = max(int(width / upper), 1)
        countMax = max(int(width / lower), 1)
        for index in range(countMin, countMax):
            pixel = int(width / index)
            pixel = pixel - int(pixel / 100)
            self._grid_scale.add_mark(
                pixel,
                Gtk.PositionType.BOTTOM,
                None
            )


    def on_search_toggled(self, widget):
        self._filter_bar.set_search_mode(widget.get_active())


    def on_select_toggled(self, widget):
        if widget.get_active():
            self._actionbar_revealer.set_reveal_child(True)
            self._library_grid.set_selection_mode(Gtk.SelectionMode.MULTIPLE)
            self._library_grid.get_style_context().add_class(Window._CSS_SELECTION)
        else:
            self._actionbar_revealer.set_reveal_child(False)
            self._library_grid.set_selection_mode(Gtk.SelectionMode.SINGLE)
            self._library_grid.get_style_context().remove_class(Window._CSS_SELECTION)


    def on_grid_scale_change(self, widget, scroll, value):
        size = round(value)
        range =  self._grid_scale.get_adjustment()
        if size < range.get_lower() or size > range.get_upper():
            return
        self._item_size = size
        GObject.idle_add(self._set_widget_grid_size, self._library_grid, size, True)
        GObject.idle_add(self._library_grid.set_item_padding, size / 100)


    def on_grid_scale_changed(self, widget, event):
        size = round(self._grid_scale.get_value())
        range =  self._grid_scale.get_adjustment()
        if size < range.get_lower() or size > range.get_upper():
            return False
        self.emit('item-size-changed', size)
        self._toolbar_popover.popdown()
        self._redraw()
        return False


    def on_update_clicked(self, widget):
        self.emit('update')


    def on_sort_toggled(self, widget):
        if widget.get_active():
            sort = [key for key, value in self._toolbar_sort_buttons.items() if value is widget][0]
            self._change_sort(sort)


    def on_sort_order_toggled(self, button):
        if button.get_active():
            sort_type = Gtk.SortType.DESCENDING
        else:
            sort_type = Gtk.SortType.ASCENDING
        self._sort_type = sort_type
        self._library_grid_model.set_sort_column_id(2, sort_type)
        self.emit('sort-type-changed', sort_type)


    def on_filter_bar_notify(self, widget, value):
        if self._toolbar_search_bar.get_active() is not self._filter_bar.get_search_mode():
            self._toolbar_search_bar.set_active(self._filter_bar.get_search_mode())


    def on_filter_entry_changed(self, widget):
        self._filter_string = self._filter_entry.get_text()
        GObject.idle_add(self._library_grid_filter.refilter)


    def on_library_grid_clicked(self, widget, path):
        # Get selected album
        path = self._library_grid_filter.convert_path_to_child_path(path)
        iter = self._library_grid_model.get_iter(path)
        hash = self._library_grid_model.get_value(iter, 2)
        album = self._albums[hash]
        self._selected_albums = [album]

        # Show standalone album
        if widget.get_selection_mode() == Gtk.SelectionMode.SINGLE:
            # Set labels
            self._standalone_title.set_text(album.get_title())
            self._standalone_artist.set_text(", ".join(album.get_albumartists()))

            # Show panel
            self._open_standalone()

            # Load cover
            threading.Thread(target=self._show_standalone_image, args=(album,)).start()


    def on_library_grid_selection_changed(self, widget):
        self._selected_albums = []
        for path in widget.get_selected_items():
            path = self._library_grid_filter.convert_path_to_child_path(path)
            iter = self._library_grid_model.get_iter(path)
            hash = self._library_grid_model.get_value(iter, 2)
            self._selected_albums.insert(0, self._albums[hash])


    def on_filter_visible(self, model, iter, data):
        hash = model.get_value(iter, 2)
        if not hash in self._albums.keys():
            return
        album = self._albums[hash]
        return album.filter(self._filter_string)


    def on_selection_cancel_clicked(self, widget):
        self._select_button.set_active(False)


    def on_selection_add_clicked(self, widget):
        hashes = [album.get_hash() for album in self._selected_albums]
        self.emit('play-multiple', hashes)
        self._select_button.set_active(False)


    def on_standalone_scroll_size_allocate(self, widget, allocation):
        self._resize_standalone_image()


    def on_standalone_play_clicked(self, widget):
        self.emit('play', self._selected_albums[0].get_hash())
        self._close_standalone()


    def on_standalone_close_clicked(self, widget):
        self._close_standalone()


    def set_item_size(self, item_size):
        if self._item_size != item_size:
            self._item_size = item_size
            self._grid_scale.set_value(item_size)
            self._redraw()


    def get_item_size(self):
        return self._item_size


    def set_sort_order(self, sort):
        if self._sort_order != sort:
            button = self._toolbar_sort_buttons[sort]
            if button and not button.get_active():
                button.set_active(True)
                self._sort_order = sort
                self._library_grid_model.set_sort_func(2, self.compare_albums, self._sort_order)


    def get_sort_order(self):
        return self._sort_order


    def set_sort_type(self, sort_type):
        if self._sort_type != sort_type:
            if sort_type:
                sort_type_gtk = Gtk.SortType.DESCENDING
                self._toolbar_sort_order_button.set_active(True)
            else:
                sort_type_gtk = Gtk.SortType.ASCENDING
                self._toolbar_sort_order_button.set_active(False)
            if self._sort_type != sort_type_gtk:
                self._sort_type = sort_type_gtk
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
        return client.MCGAlbum.compare(self._albums[hash1], self._albums[hash2], criterion)


    def stop_threads(self):
        self._library_stop.set()


    def _change_sort(self, sort):
        self._sort_order = sort
        self._library_grid_model.set_sort_func(2, self.compare_albums, sort)
        self.emit('sort-order-changed', sort)


    def _set_albums(self, host, albums, size):
        self._library_lock.acquire()
        self._library_stop.clear()
        self._albums = albums
        GObject.idle_add(self._progress_revealer.set_reveal_child, True)
        GObject.idle_add(self._progress_bar.set_fraction, 0.0)
        GObject.idle_add(self._library_grid.set_item_padding, size / 100)
        self._library_grid.set_model(None)
        self._library_grid.freeze_child_notify()
        self._library_grid_model.clear()

        i = 0
        n = len(albums)
        cache = client.MCGCache(host, size)
        self._grid_pixbufs.clear()
        for hash in albums.keys():
            album = albums[hash]
            pixbuf = None
            try:
                pixbuf = Utils.load_thumbnail(cache, album, size)
            except Exception as e:
                print(e)
            if pixbuf is None:
                pixbuf = self._icon_theme.load_icon(
                    Window.STOCK_ICON_DEFAULT,
                    self._item_size,
                    Gtk.IconLookupFlags.FORCE_SVG & Gtk.IconLookupFlags.FORCE_SIZE
                )
            if pixbuf is not None:
                self._grid_pixbufs[album.get_hash()] = pixbuf
                self._library_grid_model.append([
                    pixbuf,
                    GObject.markup_escape_text("\n".join([
                        album.get_title(),
                        ', '.join(album.get_dates()),
                        Utils.create_artists_label(album)
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


    def _open_standalone(self):
        self._panel.set_visible_child(self._panel_standalone)
        self._appwindow.set_titlebar(self._headerbar_standalone)


    def _close_standalone(self):
        self._panel.set_visible_child(self._panel.get_children()[0])
        self._appwindow.set_titlebar(self._headerbar)


    def _show_standalone_image(self, album):
        self._standalone_stack.set_visible_child(self._standalone_spinner)
        self._standalone_spinner.start()
        url = album.get_cover()
        if url is not None and url is not "":
            # Load image and draw it
            self._standalone_pixbuf = Utils.load_cover(url)
            self._resize_standalone_image()
        else:
            # Reset image
            self._standalone_image.clear()
        self._standalone_stack.set_visible_child(self._standalone_scroll)
        self._standalone_spinner.stop()


    def _resize_standalone_image(self):
        """Diese Methode skaliert das geladene Bild aus dem Pixelpuffer
        auf die Größe des Fensters unter Beibehalt der Seitenverhältnisse
        """
        pixbuf = self._standalone_pixbuf
        size = self._standalone_scroll.get_allocation()
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
        self._standalone_image.set_allocation(self._standalone_scroll.get_allocation())
        self._standalone_image.set_from_pixbuf(pixbuf.scale_simple(width, height, GdkPixbuf.InterpType.HYPER))
        self._standalone_image.show()




class StackSwitcher(GObject.GObject):
    __gsignals__ = {
        'stack-switched': (GObject.SIGNAL_RUN_FIRST, None, ())
    }


    def __init__(self, builder):
        GObject.GObject.__init__(self)

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
            self.emit('stack-switched')


    def get(self):
        return self._stack_switcher
