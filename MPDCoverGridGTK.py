#!/usr/bin/python
# -*- coding: utf-8 -*-



from gi.repository import Gtk, Gdk, GdkPixbuf
from MPDCoverGrid import MPDCoverGrid
import inspect




class MPDCoverGridGTK(Gtk.Window):
	size = 128


	def __init__(self):
		Gtk.Window.__init__(self, title="MPDCoverGridGTK")
		self.set_default_size(400, 400)
		self.connect("delete-event", Gtk.main_quit)

		# GridModel
		self.coverGridModel = Gtk.ListStore(GdkPixbuf.Pixbuf, str, str)
		# GridView
		self.coverGrid = Gtk.IconView.new_with_model(self.coverGridModel)
		self.coverGrid.set_pixbuf_column(0)
		self.coverGrid.set_text_column(-1)
		self.coverGrid.set_tooltip_column(2)
		self.coverGrid.set_columns(-1)
		self.coverGrid.set_margin(0)
		self.coverGrid.set_row_spacing(0)
		self.coverGrid.set_column_spacing(0)
		self.coverGrid.set_item_padding(0)
		self.coverGrid.set_reorderable(False)
		self.coverGrid.set_selection_mode(Gtk.SelectionMode.SINGLE)
		color = self.get_style_context().lookup_color('bg_color')[1]
		self.coverGrid.override_background_color(Gtk.StateFlags.NORMAL, Gdk.RGBA(color.red, color.green, color.blue, 1))
		# Scroll
		coverGridScroll = Gtk.ScrolledWindow()
		coverGridScroll.add_with_viewport(self.coverGrid)
		self.add(coverGridScroll)

		self._initClient()


	def __del__(self):
		#if self.mcg is not None:
			#self.mcg.disconnect()
		pass


	def _initClient(self):
		self.mcg = MPDCoverGrid()
		self.mcg.connect()


	def update(self):
		if self.mcg is None:
			return

		for title, album in self.mcg.getAlbums().items():
			if album.getCover() is not None:
				pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(album.getCover(), self.size, self.size)
				if pixbuf is not None:
					self.coverGridModel.append([pixbuf, album.getTitle(), ' von '.join([album.getTitle(), album.getArtist()])])
				else:
					print("pixbuf none: "+album.getTitle())




if __name__ == "__main__":
	mcgg = MPDCoverGridGTK()
	mcgg.show_all()
	mcgg.update()
	Gtk.main()

