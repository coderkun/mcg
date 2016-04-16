#!/usr/bin/env python3

"""MPDCoverGrid is a client for the Music Player Daemon, focused on albums instead of single tracks."""

__version__ = "0.4"


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
        self._settings = Gio.Settings.new(Application.SETTINGS_BASE_KEY)

        # Signals
        self.connect('activate', self.on_activate)


    def on_activate(self, app):
        if not self._window:
            self._window = Window(self, Application.TITLE, self._settings)
        self._window.present()


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




class Window(Gtk.ApplicationWindow):
    STYLE_CLASS_BG_TEXTURE = 'bg-texture'
    STYLE_CLASS_NO_BG = 'no-bg'
    STYLE_CLASS_NO_BORDER = 'no-border'
    _PANEL_INDEX_CONNECTION = 0
    _PANEL_INDEX_COVER = 1
    _PANEL_INDEX_PLAYLIST = 2
    _PANEL_INDEX_LIBRARY = 3


    def __init__(self, app, title, settings):
        Gtk.ApplicationWindow.__init__(self, title=title, application=app)
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
        self._panels.append(ConnectionPanel())
        self._panels.append(CoverPanel())
        self._panels.append(PlaylistPanel())
        self._panels.append(LibraryPanel())

        # Widgets
        self._main_box = Gtk.VBox()
        self._main_box.get_style_context().add_class(Window.STYLE_CLASS_NO_BG)
        self.add(self._main_box)
        # InfoBar
        self._infobar = InfoBar()
        self._main_box.pack_start(self._infobar, False, True, 0)
        # Stack
        self._stack = Gtk.Stack()
        for panel in self._panels:
            self._stack.add_titled(panel, panel.get_name(), panel.get_title())
        self._stack.set_homogeneous(True)
        self._main_box.pack_end(self._stack, True, True, 0)
        # Header
        self._header_bar = HeaderBar(self._stack)
        self.set_titlebar(self._header_bar)

        # Properties
        self._header_bar.set_sensitive(False, False)
        styleProvider = Gtk.CssProvider()
        styleProvider.load_from_data(b"""
            .bg-texture {
                box-shadow:inset 4px 4px 10px rgba(0,0,0,0.3);
                background-image:url('data/noise-texture.png');
            }
            .no-bg {
                background:none;
            }
            .no-border {
                border:none;
            }
            iconview.view:selected,
            iconview.view:selected:focus,
            GtkIconView.cell:selected,
            GtkIconView.cell:selected:focus {
                background-color:@theme_selected_bg_color;
            }
        """)
        self.get_style_context().add_provider_for_screen(Gdk.Screen.get_default(), styleProvider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        self.get_style_context().add_class(Window.STYLE_CLASS_BG_TEXTURE)
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
        self.connect('size-allocate', self.on_resize)
        self.connect('window-state-event', self.on_state)
        self.connect('destroy', self.on_destroy)
        self._header_bar.connect_signal(HeaderBar.SIGNAL_STACK_SWITCHED, self.on_header_bar_stack_switched)
        self._header_bar.connect_signal(HeaderBar.SIGNAL_CONNECT, self.on_header_bar_connect)
        self._header_bar.connect_signal(HeaderBar.SIGNAL_PLAYPAUSE, self.on_header_bar_playpause)
        self._header_bar.connect_signal(HeaderBar.SIGNAL_SET_VOLUME, self.on_header_bar_set_volume)
        self._panels[Window._PANEL_INDEX_CONNECTION].connect_signal(ConnectionPanel.SIGNAL_CONNECTION_CHANGED, self.on_connection_panel_connection_changed)
        self._panels[Window._PANEL_INDEX_PLAYLIST].connect_signal(PlaylistPanel.SIGNAL_CLEAR_PLAYLIST, self.on_playlist_panel_clear_playlist)
        self._panels[Window._PANEL_INDEX_COVER].connect_signal(CoverPanel.SIGNAL_TOGGLE_FULLSCREEN, self.on_cover_panel_toggle_fullscreen)
        self._panels[Window._PANEL_INDEX_COVER].connect_signal(CoverPanel.SIGNAL_SET_SONG, self.on_cover_panel_set_song)
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

        # Actions
        self.resize(int(self._size[0]), int(self._size[1]))
        if self._maximized:
            self.maximize()
        self.show_all()
        self._infobar.hide()
        self._stack.set_visible_child(self._panels[Window._PANEL_INDEX_CONNECTION])
        if self._settings.get_boolean(Application.SETTING_CONNECTED):
            self._connect()


    def on_resize(self, widget, event):
        if not self._maximized:
            self._size = (self.get_allocation().width, self.get_allocation().height)


    def on_state(self, widget, state):
        self._maximized = (state.new_window_state & Gdk.WindowState.MAXIMIZED > 0)
        self._fullscreen((state.new_window_state & Gdk.WindowState.FULLSCREEN > 0))
        self._settings.set_boolean(Application.SETTING_WINDOW_MAXIMIZED, self._maximized)


    def on_destroy(self, window):
        self._settings.set_value(Application.SETTING_WINDOW_SIZE, GLib.Variant('ai', list(self._size)))


    # HeaderBar callbacks

    def on_header_bar_stack_switched(self, widget):
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
        self._stack.set_visible_child(self._panels[panel_index])


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
        connection_panel.set_sensitive(False)
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
        self._stack.set_visible_child(self._panels[self._settings.get_int(Application.SETTING_PANEL)])


    def _connect_disconnected(self):
        self._panels[Window._PANEL_INDEX_PLAYLIST].stop_threads();
        self._panels[Window._PANEL_INDEX_LIBRARY].stop_threads();
        self._header_bar.disconnected()
        self._header_bar.set_sensitive(False, False)
        self._save_visible_panel()
        self._stack.set_visible_child(self._panels[Window._PANEL_INDEX_CONNECTION])
        self._panels[Window._PANEL_INDEX_CONNECTION].set_sensitive(True)


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
        panel_index_selected = self._panels.index(self._stack.get_visible_child())
        if(panel_index_selected > 0):
            self._settings.set_int(Application.SETTING_PANEL, panel_index_selected)


    def _show_error(self, message):
        self._infobar.show_error(message)
        self._infobar.show()




class HeaderBar(mcg.Base, Gtk.HeaderBar):
    SIGNAL_STACK_SWITCHED = 'stack-switched'
    SIGNAL_CONNECT = 'connect'
    SIGNAL_PLAYPAUSE = 'playpause'
    SIGNAL_SET_VOLUME = 'set-volume'


    def __init__(self, stack):
        mcg.Base.__init__(self)
        Gtk.HeaderBar.__init__(self)
        self._stack = stack
        self._buttons = {}
        self._button_handlers = {}
        self._changing_volume = False
        self._setting_volume = False

        # Widgets
        # StackSwitcher
        self._stack_switcher = StackSwitcher()
        self._stack_switcher.set_stack(self._stack)
        self.set_custom_title(self._stack_switcher)
        # Buttons left
        self._left_toolbar = Gtk.Toolbar()
        self._left_toolbar.set_show_arrow(False)
        self._left_toolbar.get_style_context().add_class(Window.STYLE_CLASS_NO_BG)
        self.pack_start(self._left_toolbar)
        # Buttons left: Connection
        self._buttons[HeaderBar.SIGNAL_CONNECT] = Gtk.ToggleToolButton.new_from_stock(Gtk.STOCK_DISCONNECT)
        self._left_toolbar.add(self._buttons[HeaderBar.SIGNAL_CONNECT])
        # Buttons left: Separator
        self._left_toolbar.add(Gtk.SeparatorToolItem())
        # Buttons left: Playback
        self._buttons[HeaderBar.SIGNAL_PLAYPAUSE] = Gtk.ToggleToolButton.new_from_stock(Gtk.STOCK_MEDIA_PLAY)
        self._buttons[HeaderBar.SIGNAL_PLAYPAUSE].set_sensitive(False)
        self._left_toolbar.add(self._buttons[HeaderBar.SIGNAL_PLAYPAUSE])
        # Buttons right
        self._right_toolbar = Gtk.Toolbar()
        self._right_toolbar.set_show_arrow(False)
        self._right_toolbar.get_style_context().add_class(Window.STYLE_CLASS_NO_BG)
        self.pack_end(self._right_toolbar)
        # Buttons right: Volume
        item = Gtk.ToolItem()
        self._buttons[HeaderBar.SIGNAL_SET_VOLUME] = Gtk.VolumeButton()
        self._buttons[HeaderBar.SIGNAL_SET_VOLUME].set_sensitive(False)
        item.add(self._buttons[HeaderBar.SIGNAL_SET_VOLUME])
        self._right_toolbar.add(item)

        # Properties
        self.set_show_close_button(True)

        # Signals
        self._stack_switcher.connect_signal(StackSwitcher.SIGNAL_STACK_SWITCHED, self.on_stack_switched)
        self._button_handlers[HeaderBar.SIGNAL_CONNECT] = self._buttons[HeaderBar.SIGNAL_CONNECT].connect('toggled', self._callback_from_widget, self.SIGNAL_CONNECT)
        self._button_handlers[HeaderBar.SIGNAL_PLAYPAUSE] = self._buttons[HeaderBar.SIGNAL_PLAYPAUSE].connect('toggled', self._callback_from_widget, self.SIGNAL_PLAYPAUSE)
        self._buttons[HeaderBar.SIGNAL_SET_VOLUME].connect('value-changed', self.on_volume_changed)
        self._buttons[HeaderBar.SIGNAL_SET_VOLUME].connect('button-press-event', self.on_volume_set_active, True)
        self._buttons[HeaderBar.SIGNAL_SET_VOLUME].connect('button-release-event', self.on_volume_set_active, False)


    def set_sensitive(self, sensitive, connecting):
        for button_signal in self._buttons:
            self._buttons[button_signal].set_sensitive(sensitive)
        self._stack_switcher.set_sensitive(sensitive)
        self._buttons[HeaderBar.SIGNAL_CONNECT].set_sensitive(not connecting)


    def on_stack_switched(self, widget):
        self._callback(HeaderBar.SIGNAL_STACK_SWITCHED, widget)


    def on_volume_changed(self, widget, value):
        if not self._setting_volume:
            self._callback(self.SIGNAL_SET_VOLUME, int(value*100))


    def on_volume_set_active(self, widget, event, active):
        self._changing_volume = active


    def connected(self):
        self._buttons[HeaderBar.SIGNAL_CONNECT].set_stock_id(Gtk.STOCK_CONNECT)
        with self._buttons[HeaderBar.SIGNAL_CONNECT].handler_block(self._button_handlers[HeaderBar.SIGNAL_CONNECT]):
            self._buttons[HeaderBar.SIGNAL_CONNECT].set_active(True)


    def disconnected(self):
        self._buttons[HeaderBar.SIGNAL_CONNECT].set_stock_id(Gtk.STOCK_DISCONNECT)
        with self._buttons[HeaderBar.SIGNAL_CONNECT].handler_block(self._button_handlers[HeaderBar.SIGNAL_CONNECT]):
            self._buttons[HeaderBar.SIGNAL_CONNECT].set_active(False)


    def set_play(self):
        with self._buttons[HeaderBar.SIGNAL_PLAYPAUSE].handler_block(self._button_handlers[HeaderBar.SIGNAL_PLAYPAUSE]):
            self._buttons[HeaderBar.SIGNAL_PLAYPAUSE].set_active(True)


    def set_pause(self):
        with self._buttons[HeaderBar.SIGNAL_PLAYPAUSE].handler_block(self._button_handlers[HeaderBar.SIGNAL_PLAYPAUSE]):
            self._buttons[HeaderBar.SIGNAL_PLAYPAUSE].set_active(False)


    def set_volume(self, volume):
        if volume >= 0:
            self._buttons[HeaderBar.SIGNAL_SET_VOLUME].set_visible(True)
            if not self._changing_volume:
                self._setting_volume = True
                self._buttons[HeaderBar.SIGNAL_SET_VOLUME].set_value(volume / 100)
                self._setting_volume = False
        else:
            self._buttons[HeaderBar.SIGNAL_SET_VOLUME].set_visible(False)


    def _callback_from_widget(self, widget, signal, *data):
        self._callback(signal, *data)




class InfoBar(Gtk.InfoBar):
    _RESPONSE_CLOSE = 1


    def __init__(self):
        Gtk.InfoBar.__init__(self)
    
        # Widgets
        self.add_button(Gtk.STOCK_CLOSE, InfoBar._RESPONSE_CLOSE)
        self._message_label = Gtk.Label()
        self._message_label.show()
        self.get_content_area().add(self._message_label)

        # Signals
        self.connect('close', self.on_response, InfoBar._RESPONSE_CLOSE)
        self.connect('response', self.on_response)


    def on_response(self, widget, response):
        if response == InfoBar._RESPONSE_CLOSE:
            self.hide()


    def show_error(self, message):
        self.set_message_type(Gtk.MessageType.ERROR)
        self._message_label.set_text(message)




class Panel(mcg.Base):


    def __init__(self):
        mcg.Base.__init__(self)


    def get_name(self):
        raise NotImplementedError()


    def get_title(self):
        raise NotImplementedError()




class ConnectionPanel(Panel, Gtk.VBox):
    SIGNAL_CONNECTION_CHANGED = 'connection-changed'


    def __init__(self):
        Panel.__init__(self)
        Gtk.VBox.__init__(self)
        self._services = Gtk.ListStore(str, str, int)
        self._profile = None

        # Widgets
        hbox = Gtk.HBox()
        self.pack_start(hbox, True, False, 0)
        grid = Gtk.Grid()
        grid.set_column_spacing(5)
        grid.set_column_homogeneous(True)
        hbox.pack_start(grid, True, False, 0)
        # Zeroconf
        zeroconf_box = Gtk.HBox()
        grid.add(zeroconf_box)
        # Zeroconf list
        self._zeroconf_list = Gtk.TreeView(self._services)
        self._zeroconf_list.get_selection().set_mode(Gtk.SelectionMode.SINGLE)
        renderer = Gtk.CellRendererText()
        column = Gtk.TreeViewColumn("Zeroconf", renderer, text=0)
        self._zeroconf_list.append_column(column)
        zeroconf_box.pack_start(self._zeroconf_list, True, True, 0)
        # Separator
        separator = Gtk.Separator.new(Gtk.Orientation.VERTICAL)
        zeroconf_box.pack_end(separator, False, False, 5)
        # Connection grid
        connection_grid = Gtk.Grid()
        grid.attach_next_to(connection_grid, zeroconf_box, Gtk.PositionType.RIGHT, 1, 1)
        # Host
        host_label = Gtk.Label("Host:")
        host_label.set_alignment(0, 0.5)
        connection_grid.add(host_label)
        self._host_entry = Gtk.Entry()
        self._host_entry.set_text("localhost")
        connection_grid.attach_next_to(self._host_entry, host_label, Gtk.PositionType.BOTTOM, 1, 1)
        # Port
        port_label = Gtk.Label("Port:")
        port_label.set_alignment(0, 0.5)
        connection_grid.attach_next_to(port_label, self._host_entry, Gtk.PositionType.BOTTOM, 1, 1)
        adjustment = Gtk.Adjustment(6600, 1024, 9999, 1, 10, 10)
        self._port_spinner = Gtk.SpinButton()
        self._port_spinner.set_adjustment(adjustment)
        connection_grid.attach_next_to(self._port_spinner, port_label, Gtk.PositionType.BOTTOM, 1, 1)
        # Passwort
        password_label = Gtk.Label("Password:")
        password_label.set_alignment(0, 0.5)
        connection_grid.attach_next_to(password_label, self._port_spinner, Gtk.PositionType.BOTTOM, 1, 1)
        self._password_entry = Gtk.Entry()
        self._password_entry.set_input_purpose(Gtk.InputPurpose.PASSWORD)
        self._password_entry.set_visibility(False)
        connection_grid.attach_next_to(self._password_entry, password_label, Gtk.PositionType.BOTTOM, 1, 1)
        # Image dir
        image_dir_label = Gtk.Label("Image Dir:")
        image_dir_label.set_alignment(0, 0.5)
        connection_grid.attach_next_to(image_dir_label, self._password_entry, Gtk.PositionType.BOTTOM, 1, 1)
        self._image_dir_entry = Gtk.Entry()
        connection_grid.attach_next_to(self._image_dir_entry, image_dir_label, Gtk.PositionType.BOTTOM, 1, 1)

        # Zeroconf provider
        self._zeroconf_provider = ZeroconfProvider()
        self._zeroconf_provider.connect_signal(ZeroconfProvider.SIGNAL_SERVICE_NEW, self.on_new_service)

        # Signals
        self._zeroconf_list.get_selection().connect('changed', self.on_service_selected)
        self._zeroconf_list.connect('focus-out-event', self.on_zeroconf_list_outfocused)
        self._host_entry.connect('focus-out-event', self.on_host_entry_outfocused)
        self._port_spinner.connect('value-changed', self.on_port_spinner_value_changed)
        self._password_entry.connect('focus-out-event', self.on_password_entry_outfocused)
        self._image_dir_entry.connect('focus-out-event', self.on_image_dir_entry_outfocused)


    def get_name(self):
        return 'connection'


    def get_title(self):
        return "Server"


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




class CoverPanel(Panel, Gtk.VBox):
    SIGNAL_TOGGLE_FULLSCREEN = 'toggle-fullscreen'
    SIGNAL_SET_SONG = 'set-song'


    def __init__(self):
        Panel.__init__(self)
        Gtk.VBox.__init__(self)
        self._current_album = None
        self._cover_pixbuf = None
        self._timer = None
        self._properties = {}

        # Widgets
        self._current_box = Gtk.Box(Gtk.Orientation.HORIZONTAL)
        self._current_box.set_halign(Gtk.Align.FILL)
        self._current_box.set_homogeneous(True)
        self.pack_start(self._current_box, True, True, 10)
        # Cover
        self._cover_image = Gtk.Image()
        self._cover_box = Gtk.EventBox()
        self._cover_box.add(self._cover_image)
        self._cover_scroll = Gtk.ScrolledWindow()
        self._cover_scroll.add(self._cover_box)
        self._current_box.pack_start(self._cover_scroll, True, True, 10)
        # Songs
        self._songs_scale = Gtk.VScale()
        self._songs_scale.set_halign(Gtk.Align.START)
        self._songs_scale.set_vexpand(True)
        self._songs_scale.set_digits(0)
        self._songs_scale.set_draw_value(False)
        self._songs_scale.override_color(Gtk.StateFlags.NORMAL, Gdk.RGBA(0, 0, 0, 1))
        self._current_box.pack_end(self._songs_scale, True, True, 10)
        # Album Infos
        self._info_grid = Gtk.Grid()
        self._info_grid.set_halign(Gtk.Align.CENTER)
        self._info_grid.set_row_spacing(5)
        self._album_title_label = Gtk.Label()
        self._info_grid.add(self._album_title_label)
        self._album_date_label = Gtk.Label()
        self._info_grid.attach_next_to(self._album_date_label, self._album_title_label, Gtk.PositionType.BOTTOM, 1, 1)
        self._album_artist_label = Gtk.Label()
        self._info_grid.attach_next_to(self._album_artist_label, self._album_date_label, Gtk.PositionType.BOTTOM, 1, 1)
        self.pack_end(self._info_grid, False, True, 10)

        # Signals
        self._cover_box.connect('button-press-event',  self.on_cover_box_pressed)
        self._cover_scroll.connect('size-allocate', self.on_cover_size_allocate)
        self._songs_scale.connect('button-press-event', self.on_songs_start_change)
        self._songs_scale.connect('button-release-event', self.on_songs_change)


    def get_name(self):
        return 'cover'


    def get_title(self):
        return "Cover"


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
            self._songs_scale.add_mark(cur_length, Gtk.PositionType.RIGHT, track.get_title())
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




class PlaylistPanel(Panel, Gtk.VBox):
    SIGNAL_CLEAR_PLAYLIST = 'clear-playlist'


    def __init__(self):
        Panel.__init__(self)
        Gtk.VBox.__init__(self)
        self._host = None
        self._item_size = 150
        self._playlist = None
        self._playlist_lock = threading.Lock()
        self._playlist_stop = threading.Event()
        self._icon_theme = Gtk.IconTheme.get_default()

        # Toolbar
        self._playlist_toolbar = Gtk.Toolbar()
        self.pack_start(self._playlist_toolbar, False, True, 0)
        # Toolbar: Clear Button
        self._clear_playlist_button = Gtk.ToolButton(Gtk.STOCK_CLEAR)
        self._playlist_toolbar.add(self._clear_playlist_button)
        # Playlist Grid: Model
        self._playlist_grid_model = Gtk.ListStore(GdkPixbuf.Pixbuf, str, str)
        # Playlist Grid
        self._playlist_grid = Gtk.IconView(self._playlist_grid_model)
        self._playlist_grid.set_pixbuf_column(0)
        self._playlist_grid.set_text_column(-1)
        self._playlist_grid.set_tooltip_column(1)
        self._playlist_grid.set_margin(0)
        self._playlist_grid.set_spacing(0)
        self._playlist_grid.set_row_spacing(0)
        self._playlist_grid.set_column_spacing(0)
        self._playlist_grid.set_item_padding(5)
        self._playlist_grid.set_reorderable(False)
        self._playlist_grid.set_item_width(-1)
        self._playlist_grid.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self._playlist_scroll = Gtk.ScrolledWindow()
        self._playlist_scroll.add(self._playlist_grid)
        self.pack_end(self._playlist_scroll, True, True, 0)
        self.show_all();

        # Properties
        self._playlist_toolbar.get_style_context().add_class(Window.STYLE_CLASS_NO_BG)
        self._playlist_toolbar.get_style_context().add_class(Window.STYLE_CLASS_NO_BORDER)
        self._playlist_grid.get_style_context().add_class(Window.STYLE_CLASS_NO_BG)
        self._playlist_grid.get_style_context().add_class(Window.STYLE_CLASS_NO_BORDER)

        # Signals
        self._clear_playlist_button.connect('clicked' ,self._callback_from_widget, PlaylistPanel.SIGNAL_CLEAR_PLAYLIST)


    def get_name(self):
        return "playlist"


    def get_title(self):
        return "Playlist"


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


    def _callback_from_widget(self, widget, signal, *data):
        self._callback(signal, *data)




class LibraryPanel(Panel, Gtk.VBox):
    SIGNAL_UPDATE = 'update'
    SIGNAL_PLAY = 'play'
    SIGNAL_ITEM_SIZE_CHANGED = 'item-size-changed'
    SIGNAL_SORT_ORDER_CHANGED = 'sort-order-changed'
    SIGNAL_SORT_TYPE_CHANGED = 'sort-type-changed'


    def __init__(self):
        Panel.__init__(self)
        Gtk.VBox.__init__(self)
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
        # Progress Bar
        self._progress_bar = Gtk.ProgressBar()
        # Toolbar
        self._library_toolbar = Gtk.HeaderBar()
        self.pack_start(self._library_toolbar, False, True, 0)
        # Toolbar: buttons left
        # Toolbar: buttons left: Update Button
        self._buttons[LibraryPanel.SIGNAL_UPDATE] = Gtk.ToolButton(Gtk.STOCK_REFRESH)
        self._library_toolbar.pack_start(self._buttons[LibraryPanel.SIGNAL_UPDATE])
        # Toolbar: Filter Entry
        self._filter_entry = Gtk.SearchEntry()
        self._filter_entry.set_placeholder_text("search library")
        self._library_toolbar.set_custom_title(self._filter_entry)
        # Toolbar: buttons right
        self._right_toolbar = Gtk.Toolbar()
        self._right_toolbar.set_show_arrow(False)
        self._right_toolbar.get_style_context().add_class(Window.STYLE_CLASS_NO_BG)
        self._library_toolbar.pack_end(self._right_toolbar)
        # Toolbar: buttons right: Grid Scale
        self._grid_scale = Gtk.HScale()
        self._grid_scale.set_range(100, 1000)
        self._grid_scale.set_round_digits(0)
        self._grid_scale.set_value(self._item_size)
        self._grid_scale.set_size_request(100, -1)
        self._grid_scale.set_draw_value(False)
        item = Gtk.ToolItem()
        item.add(self._grid_scale)
        self._right_toolbar.add(item)
        # Toolbar: buttons right: Library Sort Menu
        library_sort_store = Gtk.ListStore(str, str)
        library_sort_store.append([mcg.MCGAlbum.SORT_BY_ARTIST, "sort by artist"])
        library_sort_store.append([mcg.MCGAlbum.SORT_BY_TITLE, "sort by title"])
        library_sort_store.append([mcg.MCGAlbum.SORT_BY_YEAR, "sort by year"])        
        self._library_sort_combo = Gtk.ComboBox.new_with_model(library_sort_store)
        renderer_text = Gtk.CellRendererText()
        self._library_sort_combo.pack_start(renderer_text, True)
        self._library_sort_combo.add_attribute(renderer_text, "text", 1)
        self._library_sort_combo.set_id_column(0)
        self._library_sort_combo.set_active_id(self._sort_order)
        item = Gtk.ToolItem()
        item.add(self._library_sort_combo)
        self._right_toolbar.add(item)
        # Toolbar: buttons right: Library Sort Type
        self._library_sort_type_button = Gtk.ToggleToolButton.new_from_stock(Gtk.STOCK_SORT_ASCENDING)
        self._library_sort_type_button.set_active(True)
        self._library_sort_type_button.set_stock_id(Gtk.STOCK_SORT_DESCENDING)
        self._right_toolbar.add(self._library_sort_type_button)
        # Library Grid: Model
        self._library_grid_model = Gtk.ListStore(GdkPixbuf.Pixbuf, str, str)
        self._library_grid_model.set_sort_func(2, self.compare_albums, self._sort_order)
        self._library_grid_model.set_sort_column_id(2, self._sort_type)
        self._library_grid_filter = self._library_grid_model.filter_new()
        self._library_grid_filter.set_visible_func(self.on_filter_visible)
        # Library Grid
        self._library_grid = Gtk.IconView(self._library_grid_filter)
#        self._library_grid.pack_end(text_renderer, False)
#        self._library_grid.add_attribute(text_renderer, "markup", 0)
        self._library_grid.set_pixbuf_column(0)
        self._library_grid.set_text_column(-1)
        self._library_grid.set_tooltip_column(1)
        self._library_grid.set_margin(0)
        self._library_grid.set_spacing(0)
        self._library_grid.set_row_spacing(0)
        self._library_grid.set_column_spacing(0)
        self._library_grid.set_item_padding(5)
        self._library_grid.set_reorderable(False)
        self._library_grid.set_item_width(-1)
        self._library_grid.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self._library_scroll = Gtk.ScrolledWindow()
        self._library_scroll.add(self._library_grid)
        self.pack_end(self._library_scroll, True, True, 0)

        # Properties
        self._library_toolbar.get_style_context().add_class(Window.STYLE_CLASS_NO_BG)
        self._library_toolbar.get_style_context().add_class(Window.STYLE_CLASS_NO_BORDER)
        self._library_grid.get_style_context().add_class(Window.STYLE_CLASS_NO_BG)
        self._library_grid.get_style_context().add_class(Window.STYLE_CLASS_NO_BORDER)

        # Signals
        self._buttons[LibraryPanel.SIGNAL_UPDATE].connect('clicked', self._callback_from_widget, self.SIGNAL_UPDATE)
        self._grid_scale.connect('change-value', self.on_grid_scale_change)
        self._grid_scale.connect('button-release-event', self.on_grid_scale_changed)
        self._library_sort_combo.connect("changed", self.on_library_sort_combo_changed)
        self._library_sort_type_button.connect('clicked', self.on_library_sort_type_button_activated)
        self._filter_entry.connect('search-changed', self.on_filter_entry_changed)
        self._library_grid.connect('item-activated', self.on_library_grid_clicked)


    def get_name(self):
        return "library"


    def get_title(self):
        return "Library"


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
            self._sort_order = sort_order
            self._library_sort_combo.set_active_id(sort_order)


    def get_sort_order(self):
        return self._sort_order


    def set_sort_type(self, sort_type):
        if self._sort_type != sort_type:
            if sort_type:
                self._sort_type = Gtk.SortType.DESCENDING
                self._library_sort_type_button.set_active(True)
            else:
                self._sort_type = Gtk.SortType.ASCENDING
                self._library_sort_type_button.set_active(False)


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
        if len(self.get_children()) > 1:
            GObject.idle_add(self.remove, self.get_children()[0])
        GObject.idle_add(self._progress_bar.set_fraction, 0.0)
        GObject.idle_add(self.pack_start, self._progress_bar, False, True, 0)
        GObject.idle_add(self.show_all)
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
        if len(self.get_children()) > 1:
            GObject.idle_add(self.remove, self.get_children()[0])
        GObject.idle_add(self.pack_start, self._library_toolbar, False, True, 0)
        GObject.idle_add(self.show_all)


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


    def _callback_from_widget(self, widget, signal, *data):
        self._callback(signal, *data)




class StackSwitcher(mcg.Base, Gtk.StackSwitcher):
    SIGNAL_STACK_SWITCHED = 'stack-switched'


    def __init__(self):
        mcg.Base.__init__(self)
        Gtk.StackSwitcher.__init__(self)
        self._temp_button = None


    def set_stack(self, stack):
        super().set_stack(stack)
        for child in self.get_children():
            if type(child) is Gtk.RadioButton:
                child.connect('clicked', self.on_clicked)


    def on_clicked(self, widget):
        if not self._temp_button:
            self._temp_button = widget
        else:
            self._temp_button = None
            self._callback(StackSwitcher.SIGNAL_STACK_SWITCHED, self)




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
