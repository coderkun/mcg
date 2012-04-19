#!/usr/bin/python
# -*- coding: utf-8 -*-



from gi.repository import Gtk, Gdk, GdkPixbuf, GObject
import mcg




UI_INFO = """
<ui>
	<toolbar name='ToolBar'>
		<toolitem action='Connect' />
		<toolitem action='Update' />
	</toolbar>
</ui>
"""


class MCGGtk(Gtk.Window):
	_default_cover_size = 128


	def __init__(self):
		Gtk.Window.__init__(self, title="MPDCoverGridGTK")
		self._mcg = mcg.MCGClient()
		self._cover_pixbuf = None
		self.set_default_size(600, 400)

		# Box
		_main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
		self.add(_main_box)
		# UIManager
		action_group = Gtk.ActionGroup("toolbar")
		ui_manager = Gtk.UIManager()
		ui_manager.add_ui_from_string(UI_INFO)
		accel_group = ui_manager.get_accel_group()
		self.add_accel_group(accel_group)
		ui_manager.insert_action_group(action_group)
		self._action_connect = Gtk.Action("Connect", "_Connect", "Connect to server", Gtk.STOCK_DISCONNECT)
		self._action_connect.connect("activate", self.toolbar_callback)
		action_group.add_action_with_accel(self._action_connect, None)
		self._action_update = Gtk.Action("Update", "_Update", "Update library", Gtk.STOCK_REFRESH)
		self._action_update.connect("activate", self.toolbar_callback)
		action_group.add_action_with_accel(self._action_update, None)
		# Toolbar
		toolbar = ui_manager.get_widget("/ToolBar")
		toolbar_context = toolbar.get_style_context()
		toolbar_context.add_class(Gtk.STYLE_CLASS_PRIMARY_TOOLBAR)
		_main_box.pack_start(toolbar, False, False, 0)
		# HPaned
		hpaned = Gtk.HPaned()
		_main_box.pack_start(hpaned, True, True, 0)
		# Image
		self._cover_image = Gtk.Image()
		self._cover_image.connect('size-allocate', self.on_resize)
		# EventBox
		self._cover_box = Gtk.EventBox()
		self._cover_box.add(self._cover_image)
		hpaned.pack1(self._cover_box, resize=True)
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
		self._cover_grid.set_item_padding(0)
		self._cover_grid.set_reorderable(False)
		self._cover_grid.set_selection_mode(Gtk.SelectionMode.SINGLE)
		#color = self.get_style_context().lookup_color('bg_color')[1]
		#self._cover_grid.override_background_color(Gtk.StateFlags.NORMAL, Gdk.RGBA(color.red, color.green, color.blue, 1))
		# Scroll
		_cover_grid_scroll = Gtk.ScrolledWindow()
		_cover_grid_scroll.add_with_viewport(self._cover_grid)
		hpaned.pack2(_cover_grid_scroll, resize=False)

		# Signals
		self.connect("focus", self.focus)
		self.connect("delete-event", self.destroy)
		#self.coverGrid.connect("selection-changed", self.coverGridShow)
		self._cover_grid.connect("item-activated", self._cover_grid_play)
		self._mcg.connect_signal(mcg.MCGClient.SIGNAL_CONNECT, self.connect_callback)
		self._mcg.connect_signal(mcg.MCGClient.SIGNAL_IDLE_PLAYER, self.idle_player_callback)
		self._mcg.connect_signal(mcg.MCGClient.SIGNAL_UPDATE, self.update_callback)


	def destroy(self, widget, state):
		if self._mcg is not None:
			self._mcg.disconnect()
		Gtk.main_quit()


	def focus(self, widget, state):
		self._update()


	def toolbar_callback(self, widget):
		if widget == self._action_connect:
			if self._mcg.is_connected():
				self._mcg.disconnect()
			else:
				self._mcg.connect()
		elif widget == self._action_update:
			self._update()


	def on_resize(self, widget, allocation):
		self._resize_image()


	def connect_callback(self, connected, message):
		if connected:
			self._action_connect.set_stock_id(Gtk.STOCK_CONNECT)
		else:
			self._action_connect.set_stock_id(Gtk.STOCK_DISCONNECT)


	def idle_player_callback(self, state, album):
		self._set_album(album.get_cover())


	def update_callback(self, album):
		if album.get_cover() is not None:
			pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(album.get_cover(), self._default_cover_size, self._default_cover_size)
			if pixbuf is not None:
				self._cover_grid_model.append([pixbuf, album.get_title(), GObject.markup_escape_text("\n".join([album.get_title(), album.get_artist()]))])
			else:
				print("pixbuf none: "+album.get_title())


	def _update(self):
		if self._mcg is None or not self._mcg.is_connected():
			return
		self._mcg.update()


	def _set_album(self, url):
		# Pfad überprüfen
		if url is not None and url != "":
			# Bild laden und zeichnen
			self._cover_pixbuf = GdkPixbuf.Pixbuf.new_from_file(url)
			self._resize_image()
		else:
			# Bild zurücksetzen
			self._cover_pixbuf = None
			self._cover_image.clear()


	def _resize_image(self):
		"""Diese Methode skaliert das geladene Bild aus dem Pixelpuffer
		auf die Größe des Fensters unter Beibehalt der Seitenverhältnisse
		"""
		pixbuf = self._cover_pixbuf
		size = self._cover_image.get_allocation()
		## Pixelpuffer überprüfen
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


	def _cover_grid_play(self, widget, item):
		# TODO coverGridPlay()
		pass




if __name__ == "__main__":
	GObject.threads_init()
	mcgg = MCGGtk()
	mcgg.show_all()
	try:
		Gtk.main()
	except (KeyboardInterrupt, SystemExit):
		pass

