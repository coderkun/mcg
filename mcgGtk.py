#!/usr/bin/python
# -*- coding: utf-8 -*-

# Author: coderkun <olli@coderkun.de>




from gi.repository import Gtk, Gdk, GdkPixbuf, GObject
import mcg
import urllib
from threading import Thread
import os


class MCGGtk(Gtk.Window):
	TITLE = "MPDCoverGrid (Gtk)"

	def __init__(self):
		Gtk.Window.__init__(self, title=MCGGtk.TITLE)
		self._mcg = mcg.MCGClient()
		self._config = Configuration()
		self._maximized = False
		self._fullscreened = False

		# Widgets
		#self._main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
		self._main_box = Gtk.VBox()
		self.add(self._main_box)
		self._toolbar = Toolbar(self._config.list_mode, self._config.item_size)
		self._main_box.pack_start(self._toolbar, False, False, 0)
		self._connection_panel = ConnectionPanel(self._config)
		self._main_box.pack_end(self._connection_panel, True, True, 0)
		self._cover_panel = CoverPanel(self._config)

		# Properties
		self.set_hide_titlebar_when_maximized(True)

		# Actions
		self.resize(self._config.window_width, self._config.window_height)
		if self._config.window_maximized:
			self.maximize()

		# Signals
		self.connect('size-allocate', self.on_resize)
		self.connect('window-state-event', self.on_state)
		self.connect('delete-event', self.on_destroy)
		self._toolbar.connect_signal(Toolbar.SIGNAL_CONNECT, self.on_toolbar_connect)
		self._toolbar.connect_signal(Toolbar.SIGNAL_UPDATE, self.on_toolbar_update)
		self._toolbar.connect_signal(Toolbar.SIGNAL_PLAYPAUSE, self.on_toolbar_playpause)
		self._toolbar.connect_signal(Toolbar.SIGNAL_LIST_MODE, self.on_toolbar_list_mode)
		self._toolbar.connect_signal(Toolbar.SIGNAL_FILTER, self.on_toolbar_filter)
		self._toolbar.connect_signal(Toolbar.SIGNAL_SORT, self.on_toolbar_sort)
		self._toolbar.connect_signal(Toolbar.SIGNAL_SORT_TYPE, self.on_toolbar_sort_type)
		self._toolbar.connect_signal(Toolbar.SIGNAL_GRID_SIZE_CHANGE, self.on_toolbar_grid_size_change)
		self._toolbar.connect_signal(Toolbar.SIGNAL_GRID_SIZE_CHANGED, self.on_toolbar_grid_size_changed)
		self._connection_panel.connect_signal(ConnectionPanel.SIGNAL_PROFILE_CHANGED, self.on_connection_profile_changed)
		self._cover_panel.connect_signal(CoverPanel.SIGNAL_ALBUMS_SET, self.on_albums_set)
		self._cover_panel.connect_signal(CoverPanel.SIGNAL_TOGGLE_FULLSCREEN, self.on_cover_panel_toggle_fullscreen)
		self._cover_panel.connect_signal(CoverPanel.SIGNAL_PLAY, self.on_cover_panel_play)
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


	def on_toolbar_update(self):
		self._mcg.update()


	def on_toolbar_playpause(self):
		self._mcg.playpause()


	def on_toolbar_list_mode(self):
		self._config.list_mode = self._toolbar.get_list_mode()
		self._cover_panel.set_list_mode(self._toolbar.get_list_mode())


	def on_toolbar_filter(self, filter_string):
		self._cover_panel.filter(filter_string)


	def on_toolbar_sort(self, sort_order):
		self._cover_panel.set_sort_order(sort_order)


	def on_toolbar_sort_type(self, sort_type):
		self._cover_panel.set_sort_type(sort_type)


	def on_toolbar_grid_size_change(self, size):
		self._cover_panel.set_grid_size(size)


	def on_toolbar_grid_size_changed(self, size):
		#self._cover_panel.set_grid_size(size)
		self._cover_panel.redraw()


	# Connection Panel callbacks

	def on_connection_profile_changed(self, index, profile):
		self._config.last_profile = index
		if ConnectionPanel.TAG_AUTOCONNECT in profile.get_tags():
			self._connect()


	# Cover Panel callbacks

	def on_albums_set(self):
		GObject.idle_add(self._toolbar.set_sensitive, True)


	def on_cover_panel_toggle_fullscreen(self):
		self._toggle_fullscreen()


	def on_cover_panel_play(self, album):
		self._mcg.play_album(album)


	# MCG callbacks

	def on_mcg_connect(self, connected, error):
		if connected:
			GObject.idle_add(self._connect_connected)
			GObject.idle_add(self._load_albums)
			GObject.idle_add(self._load_playlist)
			GObject.idle_add(self._mcg.get_status)
		else:
			if error:
				dialog = ErrorDialog(self, error)
				dialog.show_dialog()
			GObject.idle_add(self._connect_disconnected)


	def on_mcg_status(self, state, album, pos, error):
		if state == 'play':
			GObject.idle_add(self._toolbar.set_pause)
		elif state == 'pause' or state == 'stop':
			GObject.idle_add(self._toolbar.set_play)

		if album:
			GObject.idle_add(self._cover_panel.set_album, album)


	def on_mcg_load_playlist(self, playlist, error):
		self._cover_panel.set_playlist(self._connection_panel.get_host(), playlist)


	def on_mcg_load_albums(self, albums, error):
		self._cover_panel.set_albums(self._connection_panel.get_host(), albums)


	def on_mcg_error(self, error):
		# TODO on_mcg_error()
		pass


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
		self._connection_panel.set_sensitive(True)
		self._main_box.remove(self._connection_panel)
		self._main_box.pack_start(self._cover_panel, True, True, 0)
		self._main_box.show_all()


	def _connect_disconnected(self):
		self._toolbar.disconnected()
		self._toolbar.set_sensitive(True)
		self._connection_panel.set_sensitive(True)
		self._main_box.remove(self._main_box.get_children()[1])
		self._main_box.pack_end(self._connection_panel, True, True, 0)
		self._main_box.show_all()


	def _load_playlist(self):
		self._mcg.load_playlist()


	def _load_albums(self):
		self._toolbar.set_sensitive(False)
		self._mcg.load_albums()

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
				self._cover_panel.set_fullscreen_mode(True);
			else:
				self._toolbar.show()
				self._cover_panel.set_fullscreen_mode(False);




class ErrorDialog(Gtk.MessageDialog):


	def __init__(self, parent, error):
		Gtk.MessageDialog.__init__(
			self,
			parent,
			0,
			Gtk.MessageType.ERROR,
			Gtk.ButtonsType.OK,
			type(error).__name__
		)
		self.format_secondary_text(error)
		self.set_modal(True)
		self.connect('response', self._handle_response)


	def show_dialog(self):
		GObject.idle_add(self._show_dialog)


	def _show_dialog(self):
		self.show_all()


	def _handle_response(self, *args):
		self.destroy()




class Toolbar(mcg.MCGBase, Gtk.Toolbar):
	SIGNAL_CONNECT = 'connect'
	SIGNAL_UPDATE = 'update'
	SIGNAL_PLAYPAUSE = 'playpause'
	SIGNAL_LIST_MODE = 'mode'
	SIGNAL_FILTER = 'filter'
	SIGNAL_SORT = 'sort'
	SIGNAL_SORT_TYPE = 'sort-type'
	SIGNAL_GRID_SIZE_CHANGE = 'grid-size-temp'
	SIGNAL_GRID_SIZE_CHANGED = 'grid-size'


	def __init__(self, list_mode, item_size):
		mcg.MCGBase.__init__(self)
		Gtk.Toolbar.__init__(self)

		# Widgets
		self._connection_button = Gtk.ToolButton(Gtk.STOCK_DISCONNECT)
		self.add(self._connection_button)
		self.add(Gtk.SeparatorToolItem())
		self._update_button = Gtk.ToolButton(Gtk.STOCK_REFRESH)
		self._update_button.set_sensitive(False)
		self.add(self._update_button)
		self._playpause_button = Gtk.ToolButton(Gtk.STOCK_MEDIA_PLAY)
		self._playpause_button.set_sensitive(False)
		self.add(self._playpause_button)
		self._list_mode_button = Gtk.ToggleToolButton(Gtk.STOCK_PAGE_SETUP)
		self._list_mode_button.set_sensitive(False)
		self.add(self._list_mode_button)
		separator = Gtk.SeparatorToolItem()
		separator.set_draw(False)
		separator.set_expand(True)
		self.add(separator)
		self._filter_item = Gtk.ToolItem()
		self._filter_entry = Gtk.SearchEntry()
		self._filter_entry.set_sensitive(False)
		self._filter_item.add(self._filter_entry)
		self.add(self._filter_item)
		self._grid_size_item = Gtk.ToolItem()
		self._grid_size_scale = Gtk.HScale()
		self._grid_size_scale.set_range(100,600)
		self._grid_size_scale.set_round_digits(0)
		self._grid_size_scale.set_value(item_size)
		self._grid_size_scale.set_size_request(100, -1)
		self._grid_size_scale.set_draw_value(False)
		self._grid_size_scale.set_sensitive(False)
		self._grid_size_item.add(self._grid_size_scale)
		self.add(self._grid_size_item)
		# Library grid menu
		self._library_grid_menu = Gtk.Menu()
		self._library_grid_menu.show()
		menu_item = Gtk.RadioMenuItem(label="sort by artist")
		menu_item.connect('activate', self.on_library_grid_menu_sort, mcg.MCGAlbum.SORT_BY_ARTIST)
		menu_item.show()
		library_grid_menu_group_sort = menu_item
		self._library_grid_menu.add(menu_item)
		menu_item = Gtk.RadioMenuItem(label="by title", group=library_grid_menu_group_sort)
		menu_item.set_active(True)
		menu_item.connect('activate', self.on_library_grid_menu_sort, mcg.MCGAlbum.SORT_BY_TITLE)
		menu_item.show()
		self._library_grid_menu.add(menu_item)
		menu_item = Gtk.RadioMenuItem(label="by year", group=library_grid_menu_group_sort)
		menu_item.connect('activate', self.on_library_grid_menu_sort, mcg.MCGAlbum.SORT_BY_YEAR)
		menu_item.show()
		self._library_grid_menu.add(menu_item)
		menu_item_separator = Gtk.SeparatorMenuItem()
		menu_item_separator.show()
		self._library_grid_menu.add(menu_item_separator)
		menu_item = Gtk.CheckMenuItem("Descending")
		menu_item.connect('activate', self.on_library_grid_menu_descending)
		menu_item.show()
		self._library_grid_menu.add(menu_item)
		self._menu_button = Gtk.MenuToolButton()
		self._menu_button.set_menu(self._library_grid_menu)
		self._menu_button.set_direction(Gtk.ArrowType.DOWN)
		self._menu_button.set_halign(Gtk.Align.END)
		self._menu_button.set_sensitive(False)
		self.add(self._menu_button)


		# Properties
		self.get_style_context().add_class(Gtk.STYLE_CLASS_PRIMARY_TOOLBAR)

		# Actions
		self.set_list_mode(list_mode)

		# Signals
		self._connection_button.connect('clicked', self.callback_with_function, self.SIGNAL_CONNECT)
		self._update_button.connect('clicked', self.callback_with_function, self.SIGNAL_UPDATE)
		self._playpause_button.connect('clicked', self.callback_with_function, self.SIGNAL_PLAYPAUSE)
		self._list_mode_button.connect('clicked', self.callback_with_function, self.SIGNAL_LIST_MODE)
		self._filter_entry.connect('changed', self.callback_with_function, self.SIGNAL_FILTER, self._filter_entry.get_text)
		self._grid_size_scale.connect('change-value', self.on_grid_size_change)
		self._grid_size_scale.connect('button-release-event', self.on_grid_size_changed)


	def on_grid_size_change(self, widget, scroll, value):
		value = round(value)
		range =  self._grid_size_scale.get_adjustment()
		if value < range.get_lower() or value > range.get_upper():
			return
		self._callback(self.SIGNAL_GRID_SIZE_CHANGE, value)


	def on_grid_size_changed(self, widget, event):
		value = round(self._grid_size_scale.get_value())
		range =  self._grid_size_scale.get_adjustment()
		if value < range.get_lower() or value > range.get_upper():
			return
		self._callback(self.SIGNAL_GRID_SIZE_CHANGED, value)


	def on_library_grid_menu_sort(self, widget, sort_order):
		self._callback(self.SIGNAL_SORT, sort_order)


	def on_library_grid_menu_descending(self, widget):
		if widget.get_active():
			self._callback(self.SIGNAL_SORT_TYPE, Gtk.SortType.DESCENDING)
		else:
			self._callback(self.SIGNAL_SORT_TYPE, Gtk.SortType.ASCENDING)


	def connected(self):
		self._connection_button.set_stock_id(Gtk.STOCK_CONNECT)
		self._update_button.set_sensitive(True)
		self._playpause_button.set_sensitive(True)
		self._list_mode_button.set_sensitive(True)
		self._filter_entry.set_sensitive(True)
		self._grid_size_scale.set_sensitive(True)
		self._menu_button.set_sensitive(True)


	def disconnected(self):
		self._connection_button.set_stock_id(Gtk.STOCK_DISCONNECT)
		self._update_button.set_sensitive(False)
		self._playpause_button.set_sensitive(False)
		self._list_mode_button.set_sensitive(False)
		self._filter_entry.set_sensitive(False)
		self._grid_size_scale.set_sensitive(False)
		self._menu_button.set_sensitive(False)


	def set_play(self):
		self._playpause_button.set_stock_id(Gtk.STOCK_MEDIA_PLAY)


	def set_pause(self):
		self._playpause_button.set_stock_id(Gtk.STOCK_MEDIA_PAUSE)


	def set_list_mode(self, active):
		self._list_mode_button.set_active(active)


	def get_list_mode(self):
		return self._list_mode_button.get_active()


	def callback_with_function(self, widget, signal, data_function=None):
		data = []
		if data_function is not None:
			data = {data_function()}
		self._callback(signal, *data)




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
			self._profiles.append([profile.__str__()])


	def _reload_config(self):
		self._profiles.clear()
		for profile in self._config.get_profiles():
			self._profiles.append([profile.__str__()])


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




class CoverPanel(mcg.MCGBase, Gtk.HPaned):
	SIGNAL_ALBUMS_SET = 'albums-set'
	SIGNAL_TOGGLE_FULLSCREEN = 'toggle-fullscreen'
	SIGNAL_PLAY = 'play'
	MODE_GRID = 'grid'
	MODE_LIST = 'list'
	MODE_PROGRESS = 'progress'
	MODE_FULLSCREEN = 'fullscreen'


	def __init__(self, config):
		mcg.MCGBase.__init__(self)
		Gtk.HPaned.__init__(self)
		self._config = config
		self._mode = None
		self._cache = None
		self._current_album = None
		self._cover_pixbuf = None
		self._host = None
		self._albums = []
		self._playlist = []
		self._grid_pixbufs = {}
		self._filter_string = ""
		self._old_ranges = {}
		self._cover_background_color = None

		# Widgets
		self._current = Gtk.VPaned()
		# Cover
		self._cover_image = Gtk.Image()
		self._cover_box = Gtk.EventBox()
		self._cover_background_color = self._cover_box.get_style_context().get_background_color(Gtk.StateFlags.NORMAL)
		self._cover_box.add(self._cover_image)
		self._cover_scroll = Gtk.ScrolledWindow()
		self._cover_scroll.add_with_viewport(self._cover_box)
		# Playlist
		self._playlist_scroll = Gtk.ScrolledWindow()
		# Playlist: GridModel
		self._playlist_grid_model = Gtk.ListStore(GdkPixbuf.Pixbuf, str, str, str)
		self._playlist_grid_filter = self._playlist_grid_model.filter_new()
		# Playlist: GridView
		self._playlist_grid = Gtk.IconView(self._playlist_grid_filter)
		self._playlist_grid.set_pixbuf_column(0)
		self._playlist_grid.set_text_column(-1)
		self._playlist_grid.set_tooltip_column(2)
		self._playlist_grid.set_columns(-1)
		self._playlist_grid.set_margin(0)
		self._playlist_grid.set_spacing( 0)
		self._playlist_grid.set_row_spacing(0)
		self._playlist_grid.set_column_spacing(0)
		self._playlist_grid.set_item_padding(0)
		self._playlist_grid.set_reorderable(False)
		self._playlist_grid.set_selection_mode(Gtk.SelectionMode.SINGLE)
		# Playlist: ListModel
		self._playlist_list_model = Gtk.ListStore(str, str, str, str, str, str)
		# Playlist: ListView
		self._playlist_list = Gtk.TreeView(self._playlist_list_model)
		renderer = Gtk.CellRendererText()
		column_artist = Gtk.TreeViewColumn("Artist", renderer, text=0)
		column_album = Gtk.TreeViewColumn("Album", renderer, text=1)
		column_track = Gtk.TreeViewColumn("Track", renderer, text=2)
		column_title = Gtk.TreeViewColumn("Title", renderer, text=3)
		column_date = Gtk.TreeViewColumn("Year", renderer, text=4)
		self._playlist_list.append_column(column_artist)
		self._playlist_list.append_column(column_album)
		self._playlist_list.append_column(column_track)
		self._playlist_list.append_column(column_title)
		self._playlist_list.append_column(column_date)
		# Library
		self._library_scroll = Gtk.ScrolledWindow()
		# Library: GridModel
		self._library_grid_model = Gtk.ListStore(GdkPixbuf.Pixbuf, str, str, str)
		self._library_grid_model.set_sort_func(3, self.compare_albums, mcg.MCGAlbum.SORT_BY_TITLE)
		self._library_grid_model.set_sort_column_id(3, Gtk.SortType.ASCENDING)
		self._library_grid_filter = self._library_grid_model.filter_new()
		self._library_grid_filter.set_visible_func(self.on_filter_visible)
		# Library: GridView
		self._library_grid = Gtk.IconView(self._library_grid_filter)
		self._library_grid.set_pixbuf_column(0)
		self._library_grid.set_text_column(-1)
		self._library_grid.set_tooltip_column(2)
		self._library_grid.set_columns(-1)
		self._library_grid.set_margin(0)
		self._library_grid.set_spacing( 0)
		self._library_grid.set_row_spacing(0)
		self._library_grid.set_column_spacing(0)
		self._library_grid.set_item_padding(0)
		self._library_grid.set_reorderable(False)
		self._library_grid.set_selection_mode(Gtk.SelectionMode.SINGLE)
		# Library: ListModel
		self._library_list_model = Gtk.ListStore(str, str, str, str, str, str)
		self._library_list_filter = self._library_list_model.filter_new()
		self._library_list_filter.set_visible_func(self.on_filter_visible)
		# Library: ListView
		self._library_list = Gtk.TreeView(self._library_list_filter)
		renderer = Gtk.CellRendererText()
		column_artist = Gtk.TreeViewColumn("Artist", renderer, text=0)
		column_album = Gtk.TreeViewColumn("Album", renderer, text=1)
		column_track = Gtk.TreeViewColumn("Track", renderer, text=2)
		column_title = Gtk.TreeViewColumn("Title", renderer, text=3)
		column_date = Gtk.TreeViewColumn("Year", renderer, text=4)
		self._library_list.append_column(column_artist)
		self._library_list.append_column(column_album)
		self._library_list.append_column(column_track)
		self._library_list.append_column(column_title)
		self._library_list.append_column(column_date)
		# Progress Bar
		self._progress_bar = Gtk.ProgressBar()
		# Layout
		self.pack1(self._current, True, True)
		self._current.pack1(self._cover_scroll, True, True)
		self._current.pack2(self._playlist_scroll, False, False)
		self.pack2(self._library_scroll, False, False)
		
		# Actions
		self.set_list_mode(self._config.list_mode)
		self.set_position(self._config.library_position)
		self._current.set_position(self._config.playlist_position)

		# Signals
		self.connect('size-allocate', self.on_size_allocate)
		self._current.connect('size-allocate', self.on_size_allocate)
		self._cover_scroll.connect('size-allocate', self.on_cover_size_allocate)
		self._cover_box.connect('button-press-event',  self.on_cover_box_pressed)
		self._library_grid.connect('item-activated', self.on_library_grid_clicked)


	def on_size_allocate(self, widget, allocation):
		if widget is self:
			self._config.library_position = self.get_position()
		elif widget is self._current:
			self._config.playlist_position = self._current.get_position()


	def on_cover_size_allocate(self, widget, allocation):
		self._resize_image()


	def on_cover_box_pressed(self, widget, event):
		if event.type == Gdk.EventType._2BUTTON_PRESS:
			self._callback(self.SIGNAL_TOGGLE_FULLSCREEN)


	def on_library_grid_clicked(self, widget, path):
		path = self._library_grid_filter.convert_path_to_child_path(path)
		iter = self._library_grid_model.get_iter(path)
		self._callback(self.SIGNAL_PLAY, self._library_grid_model.get_value(iter, 3))


	def on_filter_visible(self, model, iter, data):
		if model is self._library_grid_model:
			hash = model.get_value(iter, 3)
		elif model is self._library_list_model:
			hash = model.get_value(iter, 5)
		if not hash in self._albums.keys():
			return
		album = self._albums[hash]
		return album.filter(self._filter_string)


	def set_list_mode(self, active):
		mode = CoverPanel.MODE_GRID
		if active:
			mode = CoverPanel.MODE_LIST
		self.set_mode(mode)


	def set_fullscreen_mode(self, active):
		mode = CoverPanel.MODE_FULLSCREEN
		if not active:
			mode = self._mode
		self._set_mode(mode)


	def set_mode(self, mode):
		if mode != self._mode:
			self._mode = mode
			GObject.idle_add(self._set_mode, mode)


	def set_album(self, album):
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


	def set_playlist(self, host, playlist):
		self._host = host
		self._playlist = playlist
		Thread(target=self._set_playlist, args=(host, playlist, self._config.item_size,)).start()


	def set_albums(self, host, albums):
		self._host = host
		self._albums = albums
		Thread(target=self._set_albums, args=(host, albums, self._config.item_size,)).start()


	def filter(self, filter_string):
		self._filter_string = filter_string
		GObject.idle_add(self._library_grid_filter.refilter)
		GObject.idle_add(self._library_list_filter.refilter)


	def set_sort_order(self, sort_order):
		self._library_grid_model.set_sort_func(3, self.compare_albums, sort_order)


	def set_sort_type(self, sort_type):
		self._library_grid_model.set_sort_column_id(3, sort_type)


	def set_grid_size(self, size):
		self._config.item_width = size
		GObject.idle_add(self._set_grid_size, size)


	def _set_grid_size(self, size):
		self._set_widget_grid_size(self._playlist_grid, size, False)
		self._set_widget_grid_size(self._library_grid, size, True)


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
				hash = grid_model.get_value(iter, 3)
				pixbuf = self._grid_pixbufs[hash]
				pixbuf = pixbuf.scale_simple(size, size, GdkPixbuf.InterpType.NEAREST)
			else:
				pixbuf = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, False, 8, 1, 1)
			grid_model.set_value(iter, 0, pixbuf)

		self._old_ranges[grid_widget_id] = vis_range
		grid_widget.set_item_width(size)
		self._config.item_size = size


	def redraw(self):
		Thread(target=self._set_playlist_and_albums, args=(self._host, self._playlist, self._albums, self._config.item_size,)).start()


	def compare_albums(self, model, row1, row2, criterion):
		hash1 = model.get_value(row1, 3)
		hash2 = model.get_value(row2, 3)

		if hash1 == "" or hash2 == "":
			return
		return mcg.MCGAlbum.compare(self._albums[hash1], self._albums[hash2], criterion)


	def _set_mode(self, mode):
		# Layout
		if len(self.get_children()) > 1:
			self.remove(self.get_children()[1])
		if len(self._current.get_children()) > 1:
			self._current.remove(self._current.get_children()[1])
		if mode != CoverPanel.MODE_FULLSCREEN:
			self._current.pack2(self._playlist_scroll, False, False)
			self.pack2(self._library_scroll, False, False)

		# Scroll content
		if self._playlist_scroll.get_child() is not None:
			self._playlist_scroll.remove(self._playlist_scroll.get_child())
		if self._library_scroll.get_child() is not None:
			self._library_scroll.remove(self._library_scroll.get_child())
		if mode == CoverPanel.MODE_GRID:
			self._playlist_scroll.add(self._playlist_grid)
			self._playlist_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.NEVER)
			self._library_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
			self._library_scroll.add(self._library_grid)
		elif mode == CoverPanel.MODE_LIST:
			self._playlist_scroll.add(self._playlist_list)
			self._playlist_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
			self._library_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
			self._library_scroll.add(self._library_list)
		elif mode == CoverPanel.MODE_PROGRESS:
			self._playlist_scroll.add(self._playlist_grid)
			self._library_scroll.add_with_viewport(self._progress_bar)
		elif mode == CoverPanel.MODE_FULLSCREEN:
			self._library_scroll.hide()

		# Cover background
		if mode == CoverPanel.MODE_FULLSCREEN:
			self._cover_box.override_background_color(Gtk.StateFlags.NORMAL, Gdk.RGBA(0, 0, 0, 1))
		else:
			self._cover_box.override_background_color(Gtk.StateFlags.NORMAL, self._cover_background_color)

		self.show_all()


	def _set_playlist_and_albums(self, host, playlist, albums, size):
		self._set_playlist(host, playlist, size)
		self._set_albums(host, albums, size)


	def _set_playlist(self, host, playlist, size):
		Gdk.threads_enter()
		self._playlist_grid.set_model(None)
		self._playlist_list.set_model(None)
		self._playlist_grid.freeze_child_notify()
		self._playlist_list.freeze_child_notify()
		self._playlist_grid_model.clear()
		self._playlist_list_model.clear()
		Gdk.threads_leave()

		cache = mcg.MCGCache(host, size)
		for album in playlist:
			for track in album.get_tracks():
				self._playlist_list_model.append([
					', '.join(track.get_artists()),
					album.get_title(),
					track.get_track(),
					track.get_title(),
					album.get_date(),
					album.get_hash()
				])
			pixbuf = None
			if album.get_cover() is not None:
				try:
					pixbuf = self._load_thumbnail(cache, album, size)
				except Exception as e:
					print(e)
			if pixbuf is None:
				pixbuf = self._playlist_grid.render_icon_pixbuf(Gtk.STOCK_MISSING_IMAGE, Gtk.IconSize.DIALOG)
			if pixbuf is not None:
				self._playlist_grid_model.append([
					pixbuf,
					album.get_title(),
					GObject.markup_escape_text("\n".join([
						album.get_title(),
						album.get_date(),
						', '.join(album.get_artists())
					])),
					album.get_hash()
				])

		Gdk.threads_enter()
		self._playlist_grid.set_model(self._playlist_grid_filter)
		self._playlist_list.set_model(self._playlist_list_model)
		self._playlist_grid.thaw_child_notify()
		self._playlist_list.thaw_child_notify()
		self._playlist_grid.set_columns(len(playlist))
		Gdk.threads_leave()


	def _set_albums(self, host, albums, size):
		Gdk.threads_enter()
		self._library_grid.set_model(None)
		self._library_list.set_model(None)
		self._library_grid.freeze_child_notify()
		self._library_list.freeze_child_notify()
		self._library_grid_model.clear()
		self._library_list_model.clear()
		self._progress_bar.set_fraction(0.0)
		self._set_mode(CoverPanel.MODE_PROGRESS)
		Gdk.threads_leave()

		i = 0
		n = len(albums)
		cache = mcg.MCGCache(host, size)
		self._grid_pixbufs.clear()
		for hash in albums.keys():
			album = albums[hash]
			pixbuf = None
			for track in album.get_tracks():
				self._library_list_model.append([
					', '.join(track.get_artists()),
					album.get_title(),
					track.get_track(),
					track.get_title(),
					album.get_date(),
					hash
				])
			try:
				pixbuf = self._load_thumbnail(cache, album, size)
			except Exception as e:
				print(e)
			if pixbuf is None:
				pixbuf = self._library_grid.render_icon_pixbuf(Gtk.STOCK_MISSING_IMAGE, Gtk.IconSize.DIALOG)
			if pixbuf is not None:
				self._grid_pixbufs[album.get_hash()] = pixbuf
				self._library_grid_model.append([
					pixbuf,
					album.get_title(),
					GObject.markup_escape_text("\n".join([
						album.get_title(),
						album.get_date(),
						', '.join(album.get_artists())
					])),
					hash
				])

			i += 1
			GObject.idle_add(self._progress_bar.set_fraction, i/n)

		Gdk.threads_enter()
		self._library_grid.set_model(self._library_grid_filter)
		self._library_list.set_model(self._library_list_filter)
		self._library_grid.thaw_child_notify()
		self._library_list.thaw_child_notify()
		self._set_mode(self._mode)
		Gdk.threads_leave()
		self._callback(self.SIGNAL_ALBUMS_SET)


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


	def _load_thumbnail(self, cache, album, size):
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
		self.list_mode = self.getboolean('gui', 'list-mode')
		self.library_position = self.getint('gui', 'library-position')
		self.playlist_position = self.getint('gui', 'playlist-position')
		# TODO sort order
		# TODO sort type


	def save(self):
		self.set('default', 'last-profile', str(self.last_profile))
		self.set('gui', 'window-width', str(self.window_width))
		self.set('gui', 'window-height', str(self.window_height))
		self.set('gui', 'window-maximized', str(self.window_maximized))
		self.set('gui', 'item-size', str(self.item_size))
		self.set('gui', 'list-mode', str(self.list_mode))
		self.set('gui', 'library-position', str(self.library_position))
		self.set('gui', 'playlist-position', str(self.playlist_position))
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
		self.set('gui', 'list-mode', str(False))
		self.set('gui', 'library-position', str(450))
		self.set('gui', 'playlist-position', str(450))




if __name__ == "__main__":
	GObject.threads_init()
	Gdk.threads_init()
	mcgg = MCGGtk()
	mcgg.show_all()
	try:
		Gtk.main()
	except (KeyboardInterrupt, SystemExit):
		pass

