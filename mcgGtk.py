#!/usr/bin/python
# -*- coding: utf-8 -*-



from gi.repository import Gtk, Gdk, GdkPixbuf, GObject
import mcg




class MCGGtk(Gtk.Window):

	def __init__(self):
		Gtk.Window.__init__(self, title="MPDCoverGridGTK")
		self._mcg = mcg.MCGClient()
		self._config = Configuration()
		self._quit = False
		
		# Box
		self._main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
		self.add(self._main_box)
		# Toolbar
		self._toolbar = Toolbar()
		self._main_box.pack_start(self._toolbar, False, False, 0)
		# Connection Panel
		self.set_default_size(600, 400)
		self._connection_panel = ConnectionPanel(self._config)
		self._main_box.pack_end(self._connection_panel, True, True, 0)
		# Cover Panel
		self._cover_panel = CoverPanel()

		# Signals
		self.connect("focus", self.focus)
		self.connect("delete-event", self.destroy)
		self._toolbar.connect_signal(Toolbar.SIGNAL_CONNECT, self._connect)
		self._mcg.connect_signal(mcg.MCGClient.SIGNAL_CONNECT, self.connect_callback)
		self._mcg.connect_signal(mcg.MCGClient.SIGNAL_UPDATE, self.update_callback)
		self._mcg.connect_signal(mcg.MCGClient.SIGNAL_IDLE_PLAYER, self.idle_player_callback)


	def focus(self, widget, state):
		self._connect()


	def destroy(self, widget, state):
		self._mcg.close()
		GObject.idle_add(Gtk.main_quit)


	def _connect(self):
		if self._mcg.is_connected():
			self._cover_panel.stop_update()
			self._mcg.disconnect()
		else:
			self._connection_panel.lock()
			host = self._connection_panel.get_host()
			port = self._connection_panel.get_port()
			password = self._connection_panel.get_password()
			self._mcg.connect(host, port, password)


	def connect_callback(self, connected, message):
		if connected:
			GObject.idle_add(self._connect_connected)
		else:
			GObject.idle_add(self._connect_disconnected)
			


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



	def update_callback(self, albums):
		self._cover_panel.update(albums)


	def idle_player_callback(self, state, album):
		GObject.idle_add(self._cover_panel.set_album, album.get_cover())




class Toolbar(Gtk.Toolbar):
	SIGNAL_CONNECT = 'connect'

	def __init__(self):
		Gtk.Toolbar.__init__(self)
		
		self._callbacks = {}
		
		self.get_style_context().add_class(Gtk.STYLE_CLASS_PRIMARY_TOOLBAR)
		self._connection_button = Gtk.ToolButton(Gtk.STOCK_DISCONNECT)
		self._connection_button.connect("clicked", self._callback)
		self.add(self._connection_button)


	def connect_signal(self, signal, callback):
		self._callbacks[signal] = callback


	def connected(self):
		self._connection_button.set_stock_id(Gtk.STOCK_CONNECT)


	def disconnected(self):
		self._connection_button.set_stock_id(Gtk.STOCK_DISCONNECT)


	def _callback(self, widget):
		signal = None
		if widget == self._connection_button:
			signal = self.SIGNAL_CONNECT

		if signal in self._callbacks:
			callback = self._callbacks[signal]
			callback()




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
		self._host_entry.connect("focus-out-event", self._lost_focus)
		self._table.attach(self._host_entry, 1, 2, 0, 1)
		# Port
		port_label = Gtk.Label("Port:")
		port_label.set_alignment(0, 0.5)
		self._table.attach(port_label, 0, 1, 1, 2)
		adjustment = Gtk.Adjustment(6600, 1024, 9999, 1, 10, 10)
		self._port_spinner = Gtk.SpinButton()
		self._port_spinner.set_adjustment(adjustment)
		self._port_spinner.connect("focus-out-event", self._lost_focus)
		self._table.attach(self._port_spinner, 1, 2, 1, 2)
		# Passwort
		password_label = Gtk.Label("Password:")
		password_label.set_alignment(0, 0.5)
		self._table.attach(password_label, 0, 1, 2, 3)
		self._password_entry = Gtk.Entry()
		self._password_entry.set_visibility(False)
		self._password_entry.connect("focus-out-event", self._lost_focus)
		self._table.attach(self._password_entry, 1, 2, 2, 3)
		
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
	_default_cover_size = 128


	def __init__(self):
		Gtk.HPaned.__init__(self)
		
		# Image
		self._cover_pixbuf = None
		self._cover_image = Gtk.Image()
		self._cover_image.connect('size-allocate', self.on_resize)
		# EventBox
		self._cover_box = Gtk.EventBox()
		self._cover_box.add(self._cover_image)
		self.pack1(self._cover_box, resize=True)
		# GridModel
		self._cover_grid_model = Gtk.ListStore(GdkPixbuf.Pixbuf, str, str)
		# GridView
		self._cover_grid = Gtk.IconView.new_with_model(self._cover_grid_model)
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


	def update(self, albums):
		self._go = True
		Thread(target=self._update, args=(albums,)).start()


	def stop_update(self):
		self._go = False


	def _update(self, albums):
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
			self._cover_grid_model.append([pixbuf, album.get_title(), GObject.markup_escape_text("\n".join([album.get_title(), album.get_artist()]))])
			i += 1
			GObject.idle_add(self._progress_bar.set_fraction, i/n)

			if not self._go:
				self._cover_grid_model.clear()
				break
			
		Gdk.threads_enter()
		self._cover_grid.set_model(self._cover_grid_model)
		self._cover_grid.thaw_child_notify()
		self.remove(self._progress_box)
		self.pack2(self._cover_grid_scroll, False)
		Gdk.threads_leave()


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


	def on_resize(self, widget, allocation):
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




import os
import configparser

class Configuration:
	CONFIG_FILE = '~/.config/mcggtk.config'


	def __init__(self):
		self._config = configparser.RawConfigParser()
		
		self.host = 'localhost'
		self.port = 6600
		self.password = ""
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


	def save(self):
		if not self._config.has_section('connection'):
			self._config.add_section('connection')
		self._config.set('connection', 'host', self.host)
		self._config.set('connection', 'port', self.port)
		self._config.remove_option('connection', 'password')
		if self.password is not "":
			self._config.set('connection', 'password', self.password)
			

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

