#!/usr/bin/python
# -*- coding: utf-8 -*-

# Author: coderkun <olli@coderkun.de>




from gi.repository import Gtk, Gdk, GdkPixbuf, GObject
import mcg

class MCGGtk(Gtk.Window):

	def __init__(self):
		Gtk.Window.__init__(self, title="MPDCoverGrid (Gtk)")
		self._mcg = mcg.MCGClient()
		self._config = Configuration()
		self._maximized = False
		self._quit = False
		
		# Box
		self._main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
		self.add(self._main_box)
		# Toolbar
		self._toolbar = Toolbar()
		self._main_box.pack_start(self._toolbar, False, False, 0)
		# Connection Panel
		self._connection_panel = ConnectionPanel(self._config)
		self._main_box.pack_end(self._connection_panel, True, True, 0)
		# Cover Panel
		self._cover_panel = CoverPanel(self._config)

		# Signals
		self.connect('focus', self.focus)
		self.connect('size-allocate', self.save_size)
		self.connect('window-state-event', self.save_state)
		self.connect('delete-event', self.destroy)
		self._toolbar.connect_signal(Toolbar.SIGNAL_CONNECT, self.toolbar_connect_cb)
		self._toolbar.connect_signal(Toolbar.SIGNAL_UPDATE, self.toolbar_update_cb)
		self._toolbar.connect_signal(Toolbar.SIGNAL_PLAYPAUSE, self.toolbar_playpause_cb)
		self._toolbar.connect_signal(Toolbar.SIGNAL_NEXT, self.toolbar_next_cb)
		self._toolbar.connect_signal(Toolbar.SIGNAL_FILTER, self.toolbar_filter_cb)
		self._cover_panel.connect_signal(CoverPanel.SIGNAL_PLAY, self.cover_panel_play_cb)
		self._cover_panel.connect_signal(CoverPanel.SIGNAL_UPDATE_START, self.cover_panel_update_start_cb)
		self._cover_panel.connect_signal(CoverPanel.SIGNAL_UPDATE_END, self.cover_panel_update_end_cb)
		self._mcg.connect_signal(mcg.MCGClient.SIGNAL_CONNECT, self.mcg_connect_cb)
		self._mcg.connect_signal(mcg.MCGClient.SIGNAL_STATUS, self.mcg_status_cb)
		self._mcg.connect_signal(mcg.MCGClient.SIGNAL_UPDATE, self.mcg_update_cb)

		self.set_hide_titlebar_when_maximized(True)
		self.resize_to_geometry(self._config.window_width, self._config.window_height)
		if self._config.window_maximized:
			self.maximize()


	def focus(self, widget, state):
		self._connect()


	def save_size(self, widget, state):
		if not self._maximized:
			self._config.window_width = self.get_allocation().width
			self._config.window_height = self.get_allocation().height


	def save_state(self, widget, event):
		self._config.window_maximized = (event.new_window_state & Gdk.WindowState.MAXIMIZED > 0)
		self._maximized = (event.new_window_state & Gdk.WindowState.MAXIMIZED > 0)


	def destroy(self, widget, state):
		self._mcg.close()
		self._config.save()
		GObject.idle_add(Gtk.main_quit)


	# Toolbar callbacks

	def toolbar_connect_cb(self):
		self._connect()


	def toolbar_update_cb(self):
		self._toolbar.lock()
		self._mcg.update()


	def toolbar_playpause_cb(self):
		self._mcg.playpause()


	def toolbar_next_cb(self):
		self._mcg.next()


	def toolbar_filter_cb(self, filter_string):
		self._cover_panel.filter(filter_string)


	# Cover panel callbacks

	def cover_panel_play_cb(self, album):
		self._mcg.play_album(album)


	def cover_panel_update_start_cb(self):
		GObject.idle_add(self._toolbar.lock)


	def cover_panel_update_end_cb(self):
		GObject.idle_add(self._toolbar.unlock)


	# MCG callbacks

	def mcg_connect_cb(self, connected, message):
		if connected:
			GObject.idle_add(self._connect_connected)
		else:
			GObject.idle_add(self._connect_disconnected)


	def mcg_status_cb(self, state, album):
		if state == 'play':
			GObject.idle_add(self._toolbar.set_pause)
		elif state == 'pause' or state == 'stop':
			GObject.idle_add(self._toolbar.set_play)

		if album:
			GObject.idle_add(self._cover_panel.set_album, album.get_cover())


	def mcg_update_cb(self, albums):
		self._cover_panel.update(albums)


	# Private methods

	def _connect(self):
		if self._mcg.is_connected():
			self._mcg.disconnect()
		else:
			self._connection_panel.lock()
			host = self._connection_panel.get_host()
			port = self._connection_panel.get_port()
			password = self._connection_panel.get_password()
			self._mcg.connect(host, port, password)


	def _connect_connected(self):
		self._toolbar.connected()
		self._main_box.remove(self._connection_panel)
		self._main_box.pack_start(self._cover_panel, True, True, 0)
		self._main_box.show_all()


	def _connect_disconnected(self):
		self._main_box.remove(self._cover_panel)
		self._main_box.pack_start(self._connection_panel, True, True, 0)
		self._main_box.show_all()
		self._connection_panel.unlock()
		self._toolbar.disconnected()




class Toolbar(Gtk.Toolbar):
	SIGNAL_CONNECT = 'connect'
	SIGNAL_UPDATE = 'update'
	SIGNAL_PLAYPAUSE = 'playpause'
	SIGNAL_NEXT = 'next'
	SIGNAL_FILTER = 'filter'

	def __init__(self):
		Gtk.Toolbar.__init__(self)
		self._callbacks = {}
		
		self.get_style_context().add_class(Gtk.STYLE_CLASS_PRIMARY_TOOLBAR)
		
		# Widgets
		self._connection_button = Gtk.ToolButton(Gtk.STOCK_DISCONNECT)
		self.add(self._connection_button)
		self._update_button = Gtk.ToolButton(Gtk.STOCK_REFRESH)
		self.add(self._update_button)
		self.add(Gtk.SeparatorToolItem())
		self._playpause_button = Gtk.ToolButton(Gtk.STOCK_MEDIA_PLAY)
		self.add(self._playpause_button)
		self._next_button = Gtk.ToolButton(Gtk.STOCK_MEDIA_NEXT)
		self.add(self._next_button)
		separator = Gtk.SeparatorToolItem()
		separator.set_draw(False)
		separator.set_expand(True)
		self.add(separator)
		self._filter_item = Gtk.ToolItem()
		self._filter_entry = Gtk.Entry()
		self._filter_item.add(self._filter_entry)
		self.add(self._filter_item)
		
		# Signals
		self._connection_button.connect('clicked', self._callback, self.SIGNAL_CONNECT)
		self._update_button.connect('clicked', self._callback, self.SIGNAL_UPDATE)
		self._playpause_button.connect('clicked', self._callback, self.SIGNAL_PLAYPAUSE)
		self._next_button.connect('clicked', self._callback, self.SIGNAL_NEXT)
		self._filter_entry.connect('changed', self._callback, self.SIGNAL_FILTER, self._filter_entry.get_text)


	def connect_signal(self, signal, callback):
		self._callbacks[signal] = callback


	def connected(self):
		self._connection_button.set_stock_id(Gtk.STOCK_CONNECT)


	def disconnected(self):
		self._connection_button.set_stock_id(Gtk.STOCK_DISCONNECT)


	def lock(self):
		self.set_sensitive(False)


	def unlock(self):
		self.set_sensitive(True)


	def set_play(self):
		self._playpause_button.set_stock_id(Gtk.STOCK_MEDIA_PLAY)


	def set_pause(self):
		self._playpause_button.set_stock_id(Gtk.STOCK_MEDIA_PAUSE)


	def lock_playpause(self):
		self._playpause_button.set_stock_id(Gtk.STOCK_MEDIA_PLAY)
		self._playpause_button.set_sensitive(False);


	def _callback(self, widget, signal, data_function=None):
		if signal in self._callbacks:
			callback = self._callbacks[signal]
			
			data = []
			if data_function is not None:
				data = {data_function()}
			callback(*data)




class ConnectionPanel(Gtk.Box):

	def __init__(self, config):
		Gtk.HBox.__init__(self)
		self._callbacks = {}
		self._config = config
		
		vbox = Gtk.VBox()
		self.pack_start(vbox, True, False, 0)
		self._table = Gtk.Table(3, 2, False)
		vbox.pack_start(self._table, True, False, 0)
		# Host
		host_label = Gtk.Label("Host:")
		host_label.set_alignment(0, 0.5)
		self._table.attach(host_label, 0, 1, 0, 1)
		self._host_entry = Gtk.Entry()
		self._host_entry.set_text("localhost")
		self._table.attach(self._host_entry, 1, 2, 0, 1)
		# Port
		port_label = Gtk.Label("Port:")
		port_label.set_alignment(0, 0.5)
		self._table.attach(port_label, 0, 1, 1, 2)
		adjustment = Gtk.Adjustment(6600, 1024, 9999, 1, 10, 10)
		self._port_spinner = Gtk.SpinButton()
		self._port_spinner.set_adjustment(adjustment)
		self._table.attach(self._port_spinner, 1, 2, 1, 2)
		# Passwort
		password_label = Gtk.Label("Password:")
		password_label.set_alignment(0, 0.5)
		self._table.attach(password_label, 0, 1, 2, 3)
		self._password_entry = Gtk.Entry()
		self._password_entry.set_visibility(False)
		self._table.attach(self._password_entry, 1, 2, 2, 3)

		# Signals
		self._host_entry.connect('focus-out-event', self._lost_focus)
		self._port_spinner.connect('focus-out-event', self._lost_focus)
		self._password_entry.connect('focus-out-event', self._lost_focus)
		
		self._load_config()


	def _lost_focus(self, widget, data):
		self._save_config()


	def _load_config(self):
		self.set_host(self._config.host)
		self.set_port(self._config.port)
		self.set_password(self._config.password)


	def _save_config(self):
		self._config.host = self._host_entry.get_text()
		self._config.port = self._port_spinner.get_value_as_int()
		self._config.password = self._password_entry.get_text()
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


	def lock(self):
		self._lock(False)


	def unlock(self):
		self._lock(True)


	def _lock(self, sensitive):
		self._table.set_sensitive(sensitive)




from threading import Thread

class CoverPanel(Gtk.HPaned):
	SIGNAL_UPDATE_START = 'update-start'
	SIGNAL_UPDATE_END = 'update-end'
	SIGNAL_PLAY = 'play'
	_default_cover_size = 128


	def __init__(self, config):
		Gtk.HPaned.__init__(self)
		self._config = config
		self._callbacks = {}
		self._albums = []
		self._filter_string = ""
		
		# Image
		self._cover_pixbuf = None
		self._cover_image = Gtk.Image()
		# EventBox
		self._cover_box = Gtk.EventBox()
		self._cover_box.add(self._cover_image)
		self.pack1(self._cover_box, resize=True)
		# GridModel
		self._cover_grid_model = Gtk.ListStore(GdkPixbuf.Pixbuf, str, str, str)
		self._cover_grid_filter = self._cover_grid_model.filter_new()
		self._cover_grid_filter.set_visible_func(self.filter_visible_cb)
		# GridView
		self._cover_grid = Gtk.IconView(self._cover_grid_filter)
		self._cover_grid.set_pixbuf_column(0)
		self._cover_grid.set_text_column(-1)
		self._cover_grid.set_tooltip_column(2)
		self._cover_grid.set_columns(-1)
		self._cover_grid.set_margin(0)
		self._cover_grid.set_row_spacing(0)
		self._cover_grid.set_column_spacing(0)
		self._cover_grid.set_item_padding(1)
		self._cover_grid.set_reorderable(False)
		self._cover_grid.set_selection_mode(Gtk.SelectionMode.SINGLE)
		# Scroll
		self._cover_grid_scroll = Gtk.ScrolledWindow()
		self._cover_grid_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
		self._cover_grid_scroll.add(self._cover_grid)
		self.pack2(self._cover_grid_scroll, resize=False)
		# Progress Bar
		self._progress_box = Gtk.VBox()
		self._progress_bar = Gtk.ProgressBar()
		self._progress_box.pack_start(self._progress_bar, True, False, 0)

		# Signals
		self.connect('size-allocate', self.resize_pane_callback)
		self._cover_image.connect('size-allocate', self.resize_image_callback)
		self._cover_grid.connect('item-activated', self.click_grid_callback)

		self.set_position(self._config.pane_position)


	def connect_signal(self, signal, callback):
		self._callbacks[signal] = callback


	def _callback(self, signal, *args):
		if signal in self._callbacks:
			callback = self._callbacks[signal]
			callback(*args)


	def update(self, albums):
		self._go = True
		self._albums = albums
		Thread(target=self._update, args=(albums,)).start()


	def _update(self, albums):
		self._callback(self.SIGNAL_UPDATE_START)
		Gdk.threads_enter()
		self.remove(self._cover_grid_scroll)
		self._progress_bar.set_fraction(0.0)
		self.pack2(self._progress_box, False)
		self.show_all()
		self._cover_grid.set_model(None)
		self._cover_grid.freeze_child_notify()
		self._cover_grid_model.clear()
		Gdk.threads_leave()
		
		i = 0
		n = len(albums)
		for hash in albums.keys():
			album = albums[hash]
			file = album.get_cover()
			if file is None:
				continue
			pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(file, self._default_cover_size, self._default_cover_size)
			if pixbuf is None:
				continue
			self._cover_grid_model.append([pixbuf, album.get_title(), GObject.markup_escape_text("\n".join([album.get_title(), album.get_artist()])), hash])
			i += 1
			GObject.idle_add(self._progress_bar.set_fraction, i/n)
			
		Gdk.threads_enter()
		self._cover_grid.set_model(self._cover_grid_filter)
		self._cover_grid.thaw_child_notify()
		self.remove(self._progress_box)
		self.pack2(self._cover_grid_scroll, False)
		Gdk.threads_leave()
		self._callback(self.SIGNAL_UPDATE_END)


	def set_album(self, url):
		# Check path
		if url is not None and url != "":
			# Load image and draw it
			self._cover_pixbuf = GdkPixbuf.Pixbuf.new_from_file(url)
			self._resize_image()
		else:
			# Reset image
			self._cover_pixbuf = None
			self._cover_image.clear()


	def resize_pane_callback(self, widget, allocation):
		self._config.pane_position = self.get_position()


	def resize_image_callback(self, widget, allocation):
		self._resize_image()


	def _resize_image(self):
		"""Diese Methode skaliert das geladene Bild aus dem Pixelpuffer
		auf die Größe des Fensters unter Beibehalt der Seitenverhältnisse
		"""
		pixbuf = self._cover_pixbuf
		size = self._cover_image.get_allocation()
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


	def click_grid_callback(self, widget, path):
		iter = self._cover_grid_model.get_iter(path)
		self._callback(self.SIGNAL_PLAY, self._cover_grid_model.get_value(iter, 3))


	def filter(self, filter_string):
		self._filter_string = filter_string
		self._cover_grid_filter.refilter()


	def filter_visible_cb(self, model, iter, data):
		hash = model.get_value(iter, 3)
		album = self._albums[hash]
		return album.filter(self._filter_string)




import os
import configparser

class Configuration:
	CONFIG_FILE = '~/.config/mcggtk.config'


	def __init__(self):
		self._config = configparser.RawConfigParser()
		
		self.host = "localhost"
		self.port = 6600
		self.password = ""
		self.window_width = 600
		self.window_height = 400
		self.window_maximized = False
		self.pane_position = 300
		self.load()


	def load(self):
		if not os.path.isfile(self._get_filename()):
			return

		self._config.read(self._get_filename())
		if self._config.has_section('connection'):
			if self._config.has_option('connection', 'host'):
				self.host = self._config.get('connection', 'host')
			if self._config.has_option('connection', 'port'):
				self.port = self._config.getint('connection', 'port')
			if self._config.has_option('connection', 'password'):
				self.password = self._config.get('connection', 'password')
		if self._config.has_section('gui'):
			if self._config.has_option('gui', 'window_width'):
				self.window_width = self._config.getint('gui', 'window_width')
			if self._config.has_option('gui', 'window_height'):
				self.window_height = self._config.getint('gui', 'window_height')
			if self._config.has_option('gui', 'window_maximized'):
				self.window_maximized = self._config.getboolean('gui', 'window_maximized')
			if self._config.has_option('gui', 'pane_position'):
				self.pane_position = self._config.getint('gui', 'pane_position')


	def save(self):
		if not self._config.has_section('connection'):
			self._config.add_section('connection')
		self._config.set('connection', 'host', self.host)
		self._config.set('connection', 'port', self.port)
		self._config.remove_option('connection', 'password')
		if self.password is not "":
			self._config.set('connection', 'password', self.password)
		if not self._config.has_section('gui'):
			self._config.add_section('gui')
		self._config.set('gui', 'window_width', self.window_width)
		self._config.set('gui', 'window_height', self.window_height)
		self._config.set('gui', 'window_maximized', self.window_maximized)
		self._config.set('gui', 'pane_position', self.pane_position)
			

		with open(self._get_filename(), 'w') as configfile:
			self._config.write(configfile)


	def _get_filename(self):
		#return os.path.expanduser(self.CONFIG_FILE)
		return 'config'




if __name__ == "__main__":
	GObject.threads_init()
	Gdk.threads_init()
	mcgg = MCGGtk()
	mcgg.show_all()
	try:
		Gtk.main()
	except (KeyboardInterrupt, SystemExit):
		pass

