#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""MPDCoverGrid is a client for the Music Player Daemon, focused on albums instead of single tracks."""

__author__ = "coderkun"
__email__ = "<olli@coderkun.de>"
__license__ = "GPL"
__version__ = "0.3"
__status__ = "Development"


import math
import os
import time
import threading
import urllib

from gi.repository import Gtk, Gdk, GdkPixbuf, GObject

import mcg




class MCGGtk(Gtk.Window):
	TITLE = "MPDCoverGrid (Gtk)"
	VIEW_COVER = 'cover'
	VIEW_PLAYLIST = 'playlist'
	VIEW_LIBRARY = 'library'
	STYLE_CLASS_BG_TEXTURE = 'bg-texture'
	STYLE_CLASS_NO_BG = 'no-bg'


	def __init__(self):
		Gtk.Window.__init__(self, title=MCGGtk.TITLE)
		self._mcg = mcg.MCGClient()
		self._config = Configuration()
		self._maximized = False
		self._fullscreened = False
		self._albums = {}
		
		# Widgets
		self._main_box = Gtk.VBox()
		self.add(self._main_box)
		self._bar_box = Gtk.VBox()
		self._main_box.pack_start(self._bar_box, False, False, 0)
		self._toolbar = Toolbar(self._config)
		self._bar_box.pack_start(self._toolbar, True, True, 0)
		self._infobar = InfoBar()
		self._infobar.show()
		self._view_box = Gtk.EventBox()
		self._main_box.pack_end(self._view_box, True, True, 0)
		self._connection_panel = ConnectionPanel(self._config)
		self._view_box.add(self._connection_panel)
		
		# Views
		self._cover_panel = CoverPanel()
		self._playlist_panel = PlaylistPanel(self._config)
		self._library_panel = LibraryPanel(self._config)

		# Properties
		self.set_hide_titlebar_when_maximized(True)
		self._view_box.get_style_context().add_class(MCGGtk.STYLE_CLASS_BG_TEXTURE)
		provider = Gtk.CssProvider()
		provider.load_from_data(b"""
			GtkWidget.bg-texture {
				box-shadow:inset 4px 4px 10px rgba(0,0,0,0.3);
				background-image:url('gui/noise-texture.png');
			}
			GtkWidget.no-bg {
				background:none;
			}
			GtkIconView.cell:selected,
			GtkIconView.cell:selected:focus {
				background-color:@theme_selected_bg_color;
			}
			GtkToolbar.primary-toolbar {
				background:none;
				border:none;
				box-shadow:none;
			}
		""")
		self.get_style_context().add_provider_for_screen(Gdk.Screen.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

		# Actions
		self.resize(self._config.window_width, self._config.window_height)
		if self._config.window_maximized:
			self.maximize()

		# Signals
		self.connect('size-allocate', self.on_resize)
		self.connect('window-state-event', self.on_state)
		self.connect('delete-event', self.on_destroy)
		self._toolbar.connect_signal(Toolbar.SIGNAL_CONNECT, self.on_toolbar_connect)
		self._toolbar.connect_signal(Toolbar.SIGNAL_PLAYPAUSE, self.on_toolbar_playpause)
		self._toolbar.connect_signal(Toolbar.SIGNAL_VIEW, self.on_toolbar_view)
		self._toolbar.connect_signal(Toolbar.SIGNAL_SET_VOLUME, self.on_toolbar_set_volume)
		self._infobar.connect_signal(InfoBar.SIGNAL_CLOSE, self.on_infobar_close)
		self._connection_panel.connect_signal(ConnectionPanel.SIGNAL_PROFILE_CHANGED, self.on_connection_profile_changed)
		self._cover_panel.connect_signal(CoverPanel.SIGNAL_TOGGLE_FULLSCREEN, self.on_cover_panel_toggle_fullscreen)
		self._playlist_panel.connect_signal(PlaylistPanel.SIGNAL_CLEAR_PLAYLIST, self.on_playlist_panel_clear_playlist)
		self._library_panel.connect_signal(LibraryPanel.SIGNAL_PLAY, self.on_library_panel_play)
		self._library_panel.connect_signal(LibraryPanel.SIGNAL_UPDATE, self.on_library_panel_update)
		# View panels
		self._mcg.connect_signal(mcg.MCGClient.SIGNAL_CONNECT, self.on_mcg_connect)
		self._mcg.connect_signal(mcg.MCGClient.SIGNAL_STATUS, self.on_mcg_status)
		self._mcg.connect_signal(mcg.MCGClient.SIGNAL_LOAD_PLAYLIST, self.on_mcg_load_playlist)
		self._mcg.connect_signal(mcg.MCGClient.SIGNAL_LOAD_ALBUMS, self.on_mcg_load_albums)
		self._mcg.connect_signal(mcg.MCGClient.SIGNAL_ERROR, self.on_mcg_error)


	def on_resize(self, widget, event):
		self._save_size()


	def on_state(self, widget, state):
		self._fullscreen((state.new_window_state & Gdk.WindowState.FULLSCREEN > 0))
		self._save_state(state)


	def on_destroy(self, widget, state):
		self._mcg.disconnect_signal(mcg.MCGClient.SIGNAL_CONNECT)
		self._mcg.disconnect_signal(mcg.MCGClient.SIGNAL_STATUS)
		if self._mcg.is_connected():
			self._mcg.disconnect()
			self._mcg.join()
		self._config.save()
		self._connection_panel.save_profiles()
		GObject.idle_add(Gtk.main_quit)


	# Toolbar callbacks

	def on_toolbar_connect(self):
		self._connect()


	def on_toolbar_playpause(self):
		self._mcg.playpause()


	def on_toolbar_view(self, view):
		self._config.view = view
		self._view_box.remove(self._view_box.get_children()[0])
		if view == MCGGtk.VIEW_COVER:
			self._view_box.add(self._cover_panel)
		elif view == MCGGtk.VIEW_PLAYLIST:
			self._view_box.add(self._playlist_panel)
		elif view == MCGGtk.VIEW_LIBRARY:
			self._view_box.add(self._library_panel)
		self._view_box.show_all()


	def on_toolbar_set_volume(self, volume):
		self._mcg.set_volume(volume)


	# Infobar callbacks

	def on_infobar_close(self):
		self._hide_message()


	# Connection Panel callbacks

	def on_connection_profile_changed(self, index, profile):
		self._config.last_profile = index
		if ConnectionPanel.TAG_AUTOCONNECT in profile.get_tags():
			self._connect()


	# Cover Panel callbacks

	def on_cover_panel_toggle_fullscreen(self):
		self._toggle_fullscreen()


	# Playlist Panel callbacks

	def on_playlist_panel_clear_playlist(self):
		self._mcg.clear_playlist()


	# Library Panel callbacks

	def on_library_panel_update(self):
		self._mcg.update()


	def on_library_panel_play(self, album):
		self._mcg.play_album(album)


	# MCG callbacks

	def on_mcg_connect(self, connected, error):
		if connected:
			GObject.idle_add(self._connect_connected)
			self._mcg.load_playlist()
			self._mcg.load_albums()
			self._mcg.get_status()
		else:
			if error:
				self._show_error(str(error))
			GObject.idle_add(self._connect_disconnected)


	def on_mcg_status(self, state, album, pos, time, volume, error):
		# Album
		if album:
			GObject.idle_add(self._cover_panel.set_album, album)
		# State
		if state == 'play':
			GObject.idle_add(self._toolbar.set_play)
			GObject.idle_add(self._cover_panel.set_play, pos, time)
		elif state == 'pause' or state == 'stop':
			GObject.idle_add(self._toolbar.set_pause)
			GObject.idle_add(self._cover_panel.set_pause)
		# Volume
		GObject.idle_add(self._toolbar.set_volume, volume)
		# Error
		if error is None:
			self._hide_message()
		else:
			self._show_error(error)


	def on_mcg_load_playlist(self, playlist, error):
		self._playlist_panel.set_playlist(self._connection_panel.get_host(), playlist)


	def on_mcg_load_albums(self, albums, error):
		self._albums = {}
		self._library_panel.set_albums(self._connection_panel.get_host(), albums)


	def on_mcg_error(self, error):
		self._show_error(str(error))


	# Private methods

	def _connect(self):
		self._connection_panel.set_sensitive(False)
		self._toolbar.set_sensitive(False)
		if self._mcg.is_connected():
			self._mcg.disconnect()
		else:
			host = self._connection_panel.get_host()
			port = self._connection_panel.get_port()
			password = self._connection_panel.get_password()
			image_dir = self._connection_panel.get_image_dir()
			self._mcg.connect(host, port, password, image_dir)


	def _connect_connected(self):
		self._toolbar.connected()
		self._toolbar.set_sensitive(True)
		self._view_box.remove(self._view_box.get_children()[0])
		if self._config.view == MCGGtk.VIEW_COVER:
			self._view_box.add(self._cover_panel)
		elif self._config.view == MCGGtk.VIEW_PLAYLIST:
			self._view_box.add(self._playlist_panel)
		elif self._config.view == MCGGtk.VIEW_LIBRARY:
			self._view_box.add(self._library_panel)
		self._view_box.show_all()


	def _connect_disconnected(self):
		self._toolbar.disconnected()
		self._toolbar.set_sensitive(True)
		self._connection_panel.set_sensitive(True)
		self._view_box.remove(self._view_box.get_children()[0])
		self._view_box.add(self._connection_panel)
		self._view_box.show_all()


	def _save_size(self):
		if not self._maximized:
			self._config.window_width = self.get_allocation().width
			self._config.window_height = self.get_allocation().height


	def _save_state(self, state):
		self._config.window_maximized = (state.new_window_state & Gdk.WindowState.MAXIMIZED > 0)
		self._maximized = (state.new_window_state & Gdk.WindowState.MAXIMIZED > 0)


	def _toggle_fullscreen(self):
		if not self._fullscreened:
			self.fullscreen()
		else:
			self.unfullscreen()


	def _fullscreen(self, fullscreened_new):
		if fullscreened_new != self._fullscreened:
			self._fullscreened = fullscreened_new
			if self._fullscreened:
				self._toolbar.hide()
				self._cover_panel.set_fullscreen(True)
			else:
				self._toolbar.show()
				self._cover_panel.set_fullscreen(False)


	def _show_error(self, message):
		self._infobar.show_error(message)
		if len(self._bar_box.get_children()) > 1:
			self._bar_box.remove(self._infobar)
		self._bar_box.pack_end(self._infobar, False, True, 0)


	def _hide_message(self):
		if len(self._bar_box.get_children()) > 1:
			self._bar_box.remove(self._infobar)


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





class Toolbar(mcg.MCGBase, Gtk.Toolbar):
	SIGNAL_CONNECT = 'connect'
	SIGNAL_VIEW = 'view'
	SIGNAL_PLAYPAUSE = 'playpause'
	SIGNAL_SET_VOLUME = 'set-volume'


	def __init__(self, config):
		mcg.MCGBase.__init__(self)
		Gtk.Toolbar.__init__(self)
		self._config = config
		self._changing_volume = False
		self._setting_volume = False

		# Widgets
		# Connection
		self._connection_button = Gtk.ToggleToolButton.new_from_stock(Gtk.STOCK_CONNECT)
		self.add(self._connection_button)
		# Separator
		self.add(Gtk.SeparatorToolItem())
		# Playback
		self._playpause_button = Gtk.ToggleToolButton.new_from_stock(Gtk.STOCK_MEDIA_PAUSE)
		self._playpause_button.set_sensitive(False)
		self.add(self._playpause_button)
		# Separator
		separator = Gtk.SeparatorToolItem()
		separator.set_draw(False)
		separator.set_expand(True)
		self.add(separator)
		# View Buttons
		item = Gtk.ToolItem()
		item.get_style_context().add_class(Gtk.STYLE_CLASS_RAISED);
		self._view_box = Gtk.ButtonBox()
		self._view_box.set_layout(Gtk.ButtonBoxStyle.CENTER)
		self._view_box.get_style_context().add_class(Gtk.STYLE_CLASS_RAISED);
		self._view_box.get_style_context().add_class(Gtk.STYLE_CLASS_LINKED);
		self._view_box.set_sensitive(False)
		self._view_cover_button = Gtk.RadioButton(label="Cover")
		self._view_cover_button.set_mode(False)
		self._view_cover_button.set_active(self._config.view == MCGGtk.VIEW_COVER)
		self._view_box.add(self._view_cover_button)
		self._view_playlist_button = Gtk.RadioButton.new_with_label_from_widget(self._view_cover_button, "Playlist")
		self._view_playlist_button.set_mode(False)
		self._view_playlist_button.set_active(self._config.view == MCGGtk.VIEW_PLAYLIST)
		self._view_box.add(self._view_playlist_button)
		self._view_library_button = Gtk.RadioButton.new_with_label_from_widget(self._view_playlist_button, "Library")
		self._view_library_button.set_mode(False)
		self._view_library_button.set_active(self._config.view == MCGGtk.VIEW_LIBRARY)
		self._view_box.add(self._view_library_button)
		item.add(self._view_box)
		item.show_all()
		self.add(item)
		# Separator
		separator = Gtk.SeparatorToolItem()
		separator.set_draw(False)
		separator.set_expand(True)
		self.add(separator)
		# Volume
		item = Gtk.ToolItem()
		self._volume_button = Gtk.VolumeButton()
		self._volume_button.set_sensitive(False)
		item.add(self._volume_button)
		self.add(item)

		# Properties
		self.get_style_context().add_class(Gtk.STYLE_CLASS_PRIMARY_TOOLBAR)

		# Signals
		self._connection_button_handler = self._connection_button.connect('toggled', self._callback_from_widget, self.SIGNAL_CONNECT)
		self._playpause_button_handler = self._playpause_button.connect('toggled', self._callback_from_widget, self.SIGNAL_PLAYPAUSE)
		self._view_cover_button.connect('toggled', self.on_set_view, MCGGtk.VIEW_COVER)
		self._view_playlist_button.connect('toggled', self.on_set_view, MCGGtk.VIEW_PLAYLIST)
		self._view_library_button.connect('toggled', self.on_set_view, MCGGtk.VIEW_LIBRARY)
		self._volume_button.connect('value-changed', self.on_volume_changed)
		self._volume_button.connect('button-press-event', self.on_volume_set_active, True)
		self._volume_button.connect('button-release-event', self.on_volume_set_active, False)


	def on_set_view(self, button, view):
		if button.get_active():
			self._callback(self.SIGNAL_VIEW, view)


	def on_volume_changed(self, widget, value):
		if not self._setting_volume:
			self._callback(self.SIGNAL_SET_VOLUME, int(value*100))


	def on_volume_set_active(self, widget, event, active):
		self._changing_volume = active


	def connected(self):
		self._connection_button.set_stock_id(Gtk.STOCK_CONNECT)
		with self._connection_button.handler_block(self._connection_button_handler):
			self._connection_button.set_active(True)
		self._playpause_button.set_sensitive(True)
		self._view_box.set_sensitive(True)
		self._volume_button.set_sensitive(True)


	def disconnected(self):
		self._connection_button.set_stock_id(Gtk.STOCK_DISCONNECT)
		self._connection_button.set_active(False)
		self._playpause_button.set_sensitive(False)
		self._view_box.set_sensitive(False)
		self._volume_button.set_sensitive(False)


	def set_play(self):
		self._playpause_button.set_stock_id(Gtk.STOCK_MEDIA_PLAY)
		with self._playpause_button.handler_block(self._playpause_button_handler):
			self._playpause_button.set_active(True)


	def set_pause(self):
		self._playpause_button.set_stock_id(Gtk.STOCK_MEDIA_PAUSE)
		self._playpause_button.set_active(False)


	def set_volume(self, volume):
		if not self._changing_volume:
			self._setting_volume = True
			self._volume_button.set_value(volume / 100)
			self._setting_volume = False


	def _callback_from_widget(self, widget, signal, *data):
		self._callback(signal, *data)




class InfoBar(mcg.MCGBase, Gtk.InfoBar):
	SIGNAL_CLOSE = 'close'
	RESPONSE_CLOSE = 1


	def __init__(self):
		mcg.MCGBase.__init__(self)
		Gtk.InfoBar.__init__(self)
	
		# Widgets
		self.add_button(Gtk.STOCK_CLOSE, InfoBar.RESPONSE_CLOSE)
		self._message_label = Gtk.Label()
		self._message_label.show()
		self.get_content_area().add(self._message_label)

		# Signals
		self.connect('close', self.on_response, InfoBar.RESPONSE_CLOSE)
		self.connect('response', self.on_response)


	def on_response(self, widget, response):
		if response == InfoBar.RESPONSE_CLOSE:
			self._callback(InfoBar.SIGNAL_CLOSE)


	def show_error(self, message):
		self.set_message_type(Gtk.MessageType.ERROR)
		self._message_label.set_text(message)
		#Thread(target=self._wait_and_close).start()


	def _wait_and_close(self):
		time.sleep(5)
		self._callback(InfoBar.SIGNAL_CLOSE)




class ConnectionPanel(mcg.MCGBase, Gtk.Box):
	SIGNAL_PROFILE_CHANGED = 'change-profile'
	TAG_AUTOCONNECT = 'autoconnect'


	def __init__(self, config):
		mcg.MCGBase.__init__(self)
		Gtk.HBox.__init__(self)
		self._config = mcg.MCGProfileConfig()
		self._profiles = Gtk.ListStore(str)
		self._profile = None

		# Widgets
		vbox = Gtk.VBox()
		self.pack_start(vbox, True, False, 0)
		self._table = Gtk.Table(6, 2, False)
		vbox.pack_start(self._table, True, False, 0)
		# Profile
		profile_box = Gtk.HBox()
		self._table.attach(profile_box, 0, 2, 0, 1)
		# Profile Selection
		self._profile_combo = Gtk.ComboBox.new_with_model(self._profiles)
		self._profile_combo.set_entry_text_column(0)
		self._profile_combo.connect("changed", self.on_profile_combo_changed)
		renderer = Gtk.CellRendererText()
		self._profile_combo.pack_start(renderer, True)
		self._profile_combo.add_attribute(renderer, "text", 0)
		profile_box.pack_start(self._profile_combo, True, True, 0)
		# Profile Management
		profile_button_box = Gtk.HBox()
		profile_box.pack_end(profile_button_box, False, True, 0)
		# New Profile
		self._profile_new_button = Gtk.Button()
		self._profile_new_button.set_image(Gtk.Image.new_from_stock(Gtk.STOCK_ADD, Gtk.IconSize.BUTTON))
		self._profile_new_button.connect('clicked', self.on_profile_new_clicked)
		profile_button_box.add(self._profile_new_button)
		# Delete Profile
		self._profile_delete_button = Gtk.Button()
		self._profile_delete_button.set_image(Gtk.Image.new_from_stock(Gtk.STOCK_DELETE, Gtk.IconSize.BUTTON))
		self._profile_delete_button.connect('clicked', self.on_profile_delete_clicked)
		profile_button_box.add(self._profile_delete_button)
		# Host
		host_label = Gtk.Label("Host:")
		host_label.set_alignment(0, 0.5)
		self._table.attach(host_label, 0, 1, 1, 2)
		self._host_entry = Gtk.Entry()
		self._host_entry.set_text("localhost")
		self._table.attach(self._host_entry, 1, 2, 1, 2)
		# Port
		port_label = Gtk.Label("Port:")
		port_label.set_alignment(0, 0.5)
		self._table.attach(port_label, 0, 1, 2, 3)
		adjustment = Gtk.Adjustment(6600, 1024, 9999, 1, 10, 10)
		self._port_spinner = Gtk.SpinButton()
		self._port_spinner.set_adjustment(adjustment)
		self._table.attach(self._port_spinner, 1, 2, 2, 3)
		# Passwort
		password_label = Gtk.Label("Password:")
		password_label.set_alignment(0, 0.5)
		self._table.attach(password_label, 0, 1, 3, 4)
		self._password_entry = Gtk.Entry()
		self._table.attach(self._password_entry, 1, 2, 3, 4)
		# Image dir
		image_dir_label = Gtk.Label("Image Dir:")
		image_dir_label.set_alignment(0, 0.5)
		self._table.attach(image_dir_label, 0, 1, 4, 5)
		self._image_dir_entry = Gtk.Entry()
		self._table.attach(self._image_dir_entry, 1, 2, 4, 5)
		# Autoconnect
		self._autoconnect_button = Gtk.CheckButton("Autoconnect")
		self._table.attach(self._autoconnect_button, 1, 2, 5, 6)

		# Signals
		self._host_entry.connect('focus-out-event', self.on_host_entry_outfocused)
		self._port_spinner.connect('value-changed', self.on_port_spinner_value_changed)
		self._password_entry.connect('focus-out-event', self.on_password_entry_outfocused)
		self._image_dir_entry.connect('focus-out-event', self.on_image_dir_entry_outfocused)
		self._autoconnect_button.connect('toggled', self.on_autoconnect_button_toggled)

		# Actions
		self._load_config()
		GObject.idle_add(self._select_last_profile, config.last_profile)


	def on_profile_combo_changed(self, combo):
		(index, profile) = self._get_selected_profile()
		if profile is not None:
			self._profile = profile
			self.set_host(self._profile.get('host'))
			self.set_port(int(self._profile.get('port')))
			self.set_password(self._profile.get('password'))
			self.set_image_dir(self._profile.get('image_dir'))
			self._autoconnect_button.set_active(ConnectionPanel.TAG_AUTOCONNECT in self._profile.get_tags())
			self._callback(ConnectionPanel.SIGNAL_PROFILE_CHANGED, index, self._profile)


	def on_profile_new_clicked(self, widget):
		profile = mcg.MCGProfile()
		self._config.add_profile(profile)
		self._reload_config()
		self._profile_combo.set_active(len(self._profiles)-1)


	def on_profile_delete_clicked(self, widget):
		(index, profile) = self._get_selected_profile()
		if profile is not None:
			self._config.delete_profile(profile)
			self._reload_config()
			self._profile_combo.set_active(0)


	def on_host_entry_outfocused(self, widget, event):
		self._profile.set('host', widget.get_text())
		self._profiles.set(self._profile_combo.get_active_iter(), 0, widget.get_text())


	def on_port_spinner_value_changed(self, widget):
		self._profile.set('port', self.get_port())


	def on_password_entry_outfocused(self, widget, event):
		self._profile.set('password', widget.get_text())


	def on_image_dir_entry_outfocused(self, widget, event):
		self._profile.set('image_dir', widget.get_text())


	def on_autoconnect_button_toggled(self, widget):
		tags = self._profile.get_tags()
		if widget.get_active():
			if ConnectionPanel.TAG_AUTOCONNECT not in tags:
				tags.append(ConnectionPanel.TAG_AUTOCONNECT)
		else:
			if ConnectionPanel.TAG_AUTOCONNECT in tags:
				tags.remove(ConnectionPanel.TAG_AUTOCONNECT)
		self._profile.set_tags(tags)


	def save_profiles(self):
		self._config.save()


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


	def _load_config(self):
		self._config.load()
		for profile in self._config.get_profiles():
			self._profiles.append([str(profile)])


	def _reload_config(self):
		self._profiles.clear()
		for profile in self._config.get_profiles():
			self._profiles.append([str(profile)])


	def set_sensitive(self, sensitive):
		self._table.set_sensitive(sensitive)


	def _get_selected_profile(self):
		index = self._profile_combo.get_active()
		if index >= 0:
			profiles = self._config.get_profiles()
			if index < len(profiles):
				return (index, profiles[index])
		return (-1, None)


	def _select_last_profile(self, index):
		if len(self._profiles) <= index:
			index = 0
		self._profile_combo.set_active(index)




class CoverPanel(mcg.MCGBase, Gtk.VBox):
	SIGNAL_TOGGLE_FULLSCREEN = 'toggle-fullscreen'


	def __init__(self):
		mcg.MCGBase.__init__(self)
		Gtk.VBox.__init__(self)
		self._current_album = None
		self._cover_pixbuf = None
		self._timer = None

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



	def on_cover_box_pressed(self, widget, event):
		if event.type == Gdk.EventType._2BUTTON_PRESS:
			self._callback(self.SIGNAL_TOGGLE_FULLSCREEN)

	def on_cover_size_allocate(self, widget, allocation):
		self._resize_image()


	def set_album(self, album):
		self._album_title_label.set_markup("<b><big>{}</big></b>".format(album.get_title()))
		self._album_date_label.set_markup("<big>{}</big>".format(album.get_date()))
		self._album_artist_label.set_markup("<big>{}</big>".format(', '.join(album.get_artists())))
		self._set_cover(album)
		self._set_tracks(album)


	def set_play(self, pos, time):
		if self._timer is not None:
			GObject.source_remove(self._timer)
		for index in range(0, pos):
			time = time + self._current_album.get_tracks()[index].get_time()
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
			self._songs_scale.add_mark(length, Gtk.PositionType.RIGHT, track.get_title())
			length = length + track.get_time()
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
		## Check pixelbuffer
		if pixbuf is None:
			return

		# Skalierungswert für Breite und Höhe ermitteln
		ratioW = float(size.width) / float(pixbuf.get_width())
		ratioH = float(size.height) / float(pixbuf.get_height())
		# Kleineren beider Skalierungswerte nehmen, nicht Hochskalieren
		ratio = min(ratioW, ratioH)
		ratio = min(ratio, 1)
		# Neue Breite und Höhe berechnen
		width = int(round(pixbuf.get_width()*ratio))
		height = int(round(pixbuf.get_height()*ratio))
		# Pixelpuffer auf Oberfläche zeichnen
		self._cover_image.set_from_pixbuf(pixbuf.scale_simple(width, height, GdkPixbuf.InterpType.HYPER))




class PlaylistPanel(mcg.MCGBase, Gtk.VBox):
	SIGNAL_CLEAR_PLAYLIST = 'clear-playlist'


	def __init__(self, config):
		mcg.MCGBase.__init__(self)
		Gtk.VBox.__init__(self)
		self._config = config
		self._host = None
		self._playlist = []
		self._playlist_lock = threading.Lock()
		self._playlist_stop = threading.Event()

		# Widgets
		# Toolbar
		self._playlist_toolbar = Gtk.Toolbar()
		self.pack_start(self._playlist_toolbar, False, True, 5)
		# Clear button
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
		self._playlist_grid.set_item_padding(10)
		self._playlist_grid.set_reorderable(False)
		self._playlist_grid.set_item_width(-1)
		#self._playlist_grid.set_selection_mode(Gtk.SelectionMode.SINGLE)
		self._playlist_scroll = Gtk.ScrolledWindow()
		self._playlist_scroll.add(self._playlist_grid)
		self.pack_end(self._playlist_scroll, True, True, 0)
		self.show_all();

		# Properties
		self._playlist_toolbar.get_style_context().add_class(MCGGtk.STYLE_CLASS_NO_BG)
		self._playlist_grid.get_style_context().add_class(MCGGtk.STYLE_CLASS_NO_BG)

		# Signals
		self._clear_playlist_button.connect('clicked' ,self._callback_from_widget, self.SIGNAL_CLEAR_PLAYLIST)


	def set_playlist(self, host, playlist):
		self._host = host
		self._playlist = playlist
		self._playlist_stop.set()
		threading.Thread(target=self._set_playlist, args=(host, playlist, self._config.item_size,)).start()


	def _set_playlist(self, host, playlist, size):
		self._playlist_lock.acquire()
		self._playlist_stop.clear()
		Gdk.threads_enter()
		self._playlist_grid.set_model(None)
		self._playlist_grid.freeze_child_notify()
		self._playlist_grid_model.clear()
		Gdk.threads_leave()

		cache = mcg.MCGCache(host, size)
		for album in playlist:
			pixbuf = None
			if album.get_cover() is not None:
				try:
					pixbuf = MCGGtk.load_thumbnail(cache, album, size)
				except Exception as e:
					print(e)
			if pixbuf is None:
				pixbuf = self._playlist_grid.render_icon_pixbuf(Gtk.STOCK_MISSING_IMAGE, Gtk.IconSize.DIALOG)
			if pixbuf is not None:
				self._playlist_grid_model.append([
					pixbuf,
					GObject.markup_escape_text("\n".join([
						album.get_title(),
						album.get_date(),
						', '.join(album.get_artists())
					])),
					album.get_hash()
				])

			if self._playlist_stop.is_set():
				self._playlist_lock.release()
				return

		Gdk.threads_enter()
		self._playlist_grid.set_model(self._playlist_grid_model)
		self._playlist_grid.thaw_child_notify()
		self._playlist_grid.set_columns(len(playlist))
		Gdk.threads_leave()
		self._playlist_lock.release()


	def _callback_from_widget(self, widget, signal, *data):
		self._callback(signal, *data)




class LibraryPanel(mcg.MCGBase, Gtk.VBox):
	SIGNAL_UPDATE = 'update'
	SIGNAL_PLAY = 'play'


	def __init__(self, config):
		mcg.MCGBase.__init__(self)
		Gtk.VBox.__init__(self)
		self._config = config
		self._host = None
		self._albums = []
		self._filter_string = ""
		self._grid_pixbufs = {}
		self._old_ranges = {}
		self._library_lock = threading.Lock()
		self._library_stop = threading.Event()

		# Widgets
		# Toolbar
		self._library_toolbar = Gtk.Toolbar()
		self.pack_start(self._library_toolbar, False, True, 5)
		# Update Button
		self._update_library_button = Gtk.ToolButton(Gtk.STOCK_REFRESH)
		self._library_toolbar.add(self._update_library_button)
		# Separator
		separator = Gtk.SeparatorToolItem()
		separator.set_draw(False)
		separator.set_expand(True)
		self._library_toolbar.add(separator)
		# Filter Entry
		self._filter_entry = Gtk.SearchEntry()
		self._filter_entry.set_placeholder_text("Bibliothek durchsuchen")
		item = Gtk.ToolItem()
		item.add(self._filter_entry)
		self._library_toolbar.add(item)
		# Separator
		separator = Gtk.SeparatorToolItem()
		separator.set_draw(False)
		separator.set_expand(True)
		self._library_toolbar.add(separator)
		# Grid Scale
		self._grid_scale = Gtk.HScale()
		self._grid_scale.set_range(100,600)
		self._grid_scale.set_round_digits(0)
		self._grid_scale.set_value(self._config.item_size)
		self._grid_scale.set_size_request(100, -1)
		self._grid_scale.set_draw_value(False)
		item = Gtk.ToolItem()
		item.add(self._grid_scale)
		self._library_toolbar.add(item)
		# Library Sort Menu
		library_sort_store = Gtk.ListStore(str, str)
		library_sort_store.append([mcg.MCGAlbum.SORT_BY_ARTIST, "sort by artist"])
		library_sort_store.append([mcg.MCGAlbum.SORT_BY_TITLE, "sort by title"])
		library_sort_store.append([mcg.MCGAlbum.SORT_BY_YEAR, "sort by year"])		
		self._library_sort_combo = Gtk.ComboBox.new_with_model(library_sort_store)
		renderer_text = Gtk.CellRendererText()
		self._library_sort_combo.pack_start(renderer_text, True)
		self._library_sort_combo.add_attribute(renderer_text, "text", 1)
		self._library_sort_combo.set_id_column(0)
		self._library_sort_combo.set_active_id(self._config.library_sort_order)
		item = Gtk.ToolItem()
		item.add(self._library_sort_combo)
		self._library_toolbar.add(item)
		# Library Sort Type
		self._library_sort_type_button = Gtk.ToggleToolButton.new_from_stock(Gtk.STOCK_SORT_ASCENDING)	
		if self._config.library_sort_type == Gtk.SortType.DESCENDING:
			self._library_sort_type_button.set_active(True)
			self._library_sort_type_button.set_stock_id(Gtk.STOCK_SORT_DESCENDING)
		self._library_toolbar.add(self._library_sort_type_button)
		# Progress Bar
		self._progress_bar = Gtk.ProgressBar()
		# Library Grid: TextRenderer
#		text_renderer = Gtk.CellRendererText()
#		text_renderer.props.alignment = Pango.Alignment.CENTER
#		text_renderer.props.wrap_mode = Pango.WrapMode.WORD
#		text_renderer.props.xalign = 0.5
#		text_renderer.props.yalign = 0
#		text_renderer.props.width = 150
#		text_renderer.props.wrap_width = 150
		# Library Grid: Model
		self._library_grid_model = Gtk.ListStore(GdkPixbuf.Pixbuf, str, str)
		self._library_grid_model.set_sort_func(2, self.compare_albums, self._config.library_sort_order)
		self._library_grid_model.set_sort_column_id(2, self._config.library_sort_type)
		self._library_grid_filter = self._library_grid_model.filter_new()
		self._library_grid_filter.set_visible_func(self.on_filter_visible)
		# Library Grid
		self._library_grid = Gtk.IconView(self._library_grid_filter)
#		self._library_grid.pack_end(text_renderer, False)
#		self._library_grid.add_attribute(text_renderer, "markup", 0)
		self._library_grid.set_pixbuf_column(0)
		self._library_grid.set_text_column(-1)
		self._library_grid.set_tooltip_column(1)
		self._library_grid.set_margin(0)
		self._library_grid.set_spacing(0)
		self._library_grid.set_row_spacing(0)
		self._library_grid.set_column_spacing(0)
		self._library_grid.set_item_padding(10)
		self._library_grid.set_reorderable(False)
		self._library_grid.set_item_width(-1)
		self._library_grid.set_selection_mode(Gtk.SelectionMode.SINGLE)
		self._library_scroll = Gtk.ScrolledWindow()
		self._library_scroll.add(self._library_grid)
		self.pack_end(self._library_scroll, True, True, 0)
		#self.show_all();

		# Properties
		self._library_grid.get_style_context().add_class(MCGGtk.STYLE_CLASS_NO_BG)
		self._library_toolbar.get_style_context().add_class(MCGGtk.STYLE_CLASS_NO_BG)

		# Signals
		self._update_library_button.connect('clicked', self._callback_from_widget, self.SIGNAL_UPDATE)
		self._filter_entry.connect('changed', self.on_filter_entry_changed)
		self._grid_scale.connect('change-value', self.on_grid_scale_change)
		self._grid_scale.connect('button-release-event', self.on_grid_scale_changed)
		self._library_sort_combo.connect("changed", self.on_library_sort_combo_changed)
		self._library_sort_type_button.connect('clicked', self.on_library_sort_type_button_activated)
		self._library_grid.connect('item-activated', self.on_library_grid_clicked)


	def on_filter_entry_changed(self, widget):
		self._filter_string = self._filter_entry.get_text()
		GObject.idle_add(self._library_grid_filter.refilter)


	def on_filter_visible(self, model, iter, data):
		hash = model.get_value(iter, 2)
		if not hash in self._albums.keys():
			return
		album = self._albums[hash]
		return album.filter(self._filter_string)


	def on_grid_scale_change(self, widget, scroll, value):
		size = round(value)
		range =  self._grid_scale.get_adjustment()
		if size < range.get_lower() or size > range.get_upper():
			return
		self._config.item_width = size
		GObject.idle_add(self._set_widget_grid_size, self._library_grid, size, True)


	def on_grid_scale_changed(self, widget, event):
		size = round(self._grid_scale.get_value())
		range =  self._grid_scale.get_adjustment()
		if size < range.get_lower() or size > range.get_upper():
			return
		self._redraw()


	def on_library_sort_combo_changed(self, combo):
		sort_order = combo.get_active_id()
		self._config.library_sort_order = sort_order
		self._library_grid_model.set_sort_func(2, self.compare_albums, sort_order)


	def on_library_sort_type_button_activated(self, button):
		if button.get_active():
			sort_type = Gtk.SortType.DESCENDING
			button.set_stock_id(Gtk.STOCK_SORT_DESCENDING)
		else:
			sort_type = Gtk.SortType.ASCENDING
			button.set_stock_id(Gtk.STOCK_SORT_ASCENDING)
		self._config.library_sort_type = sort_type
		self._library_grid_model.set_sort_column_id(2, sort_type)


	def on_library_grid_clicked(self, widget, path):
		path = self._library_grid_filter.convert_path_to_child_path(path)
		iter = self._library_grid_model.get_iter(path)
		self._callback(self.SIGNAL_PLAY, self._library_grid_model.get_value(iter, 2))


	def set_albums(self, host, albums):
		self._host = host
		self._albums = albums
		self._library_stop.set()
		threading.Thread(target=self._set_albums, args=(host, albums, self._config.item_size,)).start()


	def compare_albums(self, model, row1, row2, criterion):
		hash1 = model.get_value(row1, 2)
		hash2 = model.get_value(row2, 2)

		if hash1 == "" or hash2 == "":
			return
		return mcg.MCGAlbum.compare(self._albums[hash1], self._albums[hash2], criterion)


	def _set_albums(self, host, albums, size):
		self._library_lock.acquire()
		self._library_stop.clear()
		self.remove(self._library_toolbar)
		self._progress_bar.set_fraction(0.0)
		self.pack_start(self._progress_bar, False, True, 5)
		self.show_all()
		Gdk.threads_enter()
		self._library_grid.set_model(None)
		self._library_grid.freeze_child_notify()
		self._library_grid_model.clear()
		Gdk.threads_leave()

		i = 0
		n = len(albums)
		cache = mcg.MCGCache(host, size)
		self._grid_pixbufs.clear()
		for hash in albums.keys():
			album = albums[hash]
			pixbuf = None
			try:
				pixbuf = MCGGtk.load_thumbnail(cache, album, size)
			except Exception as e:
				print(e)
			if pixbuf is None:
				pixbuf = self._library_grid.render_icon_pixbuf(Gtk.STOCK_MISSING_IMAGE, Gtk.IconSize.DIALOG)
			if pixbuf is not None:
				self._grid_pixbufs[album.get_hash()] = pixbuf
				self._library_grid_model.append([
					pixbuf,
					GObject.markup_escape_text("\n".join([
						album.get_title(),
						album.get_date(),
						', '.join(album.get_artists())
					])),
					hash
				])

			i += 1
			GObject.idle_add(self._progress_bar.set_fraction, i/n)
			if self._library_stop.is_set():
				self._library_lock.release()
				return

		Gdk.threads_enter()
		self._library_grid.set_model(self._library_grid_filter)
		self._library_grid.thaw_child_notify()
		Gdk.threads_leave()
		self._library_lock.release()
		self.remove(self._progress_bar)
		self.pack_start(self._library_toolbar, False, True, 5)
		self.show_all()


	def _set_widget_grid_size(self, grid_widget, size, vertical):
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

		self._old_ranges[grid_widget_id] = vis_range
		grid_widget.set_item_width(size)
		#self._config.item_size = size


	def _redraw(self):
		threading.Thread(target=self._set_albums, args=(self._host, self._albums, self._config.item_size,)).start()


	def _callback_from_widget(self, widget, signal, *data):
		self._callback(signal, *data)



class Configuration(mcg.MCGConfig):
	CONFIG_FILE = 'mcggtk.conf'


	def __init__(self):
		mcg.MCGConfig.__init__(self, Configuration.CONFIG_FILE)
		self._setup()
		self.load()


	def load(self):
		super().load()
		self.last_profile = self.getint('default', 'last-profile')
		self.window_width = self.getint('gui', 'window-width')
		self.window_height = self.getint('gui', 'window-height')
		self.window_maximized = self.getboolean('gui', 'window-maximized')
		self.item_size = self.getint('gui', 'item-size')
		self.view = self.get('gui', 'view')
		self.library_sort_order = self.get('gui', 'library-sort-order')
		if self.getint('gui', 'library-sort-type') == 0:
			self.library_sort_type = Gtk.SortType.ASCENDING
		else:
			self.library_sort_type = Gtk.SortType.DESCENDING
		self.save()


	def save(self):
		self.set('default', 'last-profile', str(self.last_profile))
		self.set('gui', 'window-width', str(self.window_width))
		self.set('gui', 'window-height', str(self.window_height))
		self.set('gui', 'window-maximized', str(self.window_maximized))
		self.set('gui', 'item-size', str(self.item_size))
		self.set('gui', 'view', str(self.view))
		self.set('gui', 'library-sort-order', str(self.library_sort_order))
		if self.library_sort_type == Gtk.SortType.ASCENDING:
			self.set('gui', 'library-sort-type', str(0))
		else:
			self.set('gui', 'library-sort-type', str(1))
		super().save()


	def _setup(self):
		if not self.has_section('default'):
			self.add_section('default')
		self.set('default', 'last-profile', str(0))
		if not self.has_section('gui'):
			self.add_section('gui')
		self.set('gui', 'window-width', str(800))
		self.set('gui', 'window-height', str(600))
		self.set('gui', 'window-maximized', str(False))
		self.set('gui', 'item-size', str(100))
		self.set('gui', 'view', MCGGtk.VIEW_COVER)
		self.set('gui', 'library-sort-order', mcg.MCGAlbum.SORT_BY_YEAR)
		self.set('gui', 'library-sort-type', str(1))

