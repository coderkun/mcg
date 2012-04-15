#!/usr/bin/python
# -*- coding: utf-8 -*-



from gi.repository import Gtk, Gdk, GdkPixbuf, GObject
from MPDCoverGrid import MPDCoverGrid
import inspect




class MPDCoverGridGTK(Gtk.Window):
	size = 128


	def __init__(self):
		Gtk.Window.__init__(self, title="MPDCoverGridGTK")
		self.set_default_size(600, 400)
		self.connect("focus", self.updateSignal)
		self.connect("delete-event", self._destroy)
		GObject.threads_init()

		# VPaned
		VPaned = Gtk.VPaned()
		self.add(VPaned)
		# HPaned
		HPaned = Gtk.HPaned()
		VPaned.pack1(HPaned, resize=True)
		
		# Image
		self.coverImage = Gtk.Image()
		# EventBox
		self.coverBox = Gtk.EventBox()
		self.coverBox.add(self.coverImage)
		# Viewport
		self.coverView = Gtk.Viewport()
		self.coverView.add(self.coverBox)
		HPaned.pack1(self.coverView, resize=True)
		
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
		#color = self.get_style_context().lookup_color('bg_color')[1]
		#self.coverGrid.override_background_color(Gtk.StateFlags.NORMAL, Gdk.RGBA(color.red, color.green, color.blue, 1))
		# Scroll
		coverGridScroll = Gtk.ScrolledWindow()
		coverGridScroll.add_with_viewport(self.coverGrid)
		HPaned.pack2(coverGridScroll, resize=False)
		
		# ListModel
		self.songListModel = Gtk.ListStore(str, str)
		# ListView
		self.songList = Gtk.TreeView(self.songListModel)
		renderer = Gtk.CellRendererText()
		column1 = Gtk.TreeViewColumn("Artist", renderer, text=0)
		column2 = Gtk.TreeViewColumn("Album", renderer, text=0)
		self.songList.append_column(column1)
		self.songList.append_column(column2)
		self.songList.set_headers_visible(True)
		VPaned.pack2(self.songList, resize=False)
		
		# Signals
		self.coverGrid.connect("selection-changed", self.coverGridShow)
		self.coverGrid.connect("item-activated", self.coverGridPlay)

		self._initClient()
		self.mcg.connectUpdate(self.updateCallback)


	def _initClient(self):
		self.mcg = MPDCoverGrid()
		self.mcg.connect()


	def _destroy(self, widget, state):
		if self.mcg is not None:
			self.mcg.disconnect()
		Gtk.main_quit()


	def updateSignal(self, widget, state):
		self.update()


	def update(self):
		if self.mcg is None:
			return
		self.mcg.update()


	def updateCallback(self, album):
		if album.getCover() is not None:
			pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(album.getCover(), self.size, self.size)
			if pixbuf is not None:
				self.coverGridModel.append([pixbuf, album.getTitle(), ' von '.join([album.getTitle(), album.getArtist()])])
			else:
				print("pixbuf none: "+album.getTitle())


	def coverGridShow(self, widget):
		# TODO coverGridShow()
		pass


	def coverGridSelected(self, widget, index, data):
		# TODO coverGridSelected()
		pass


	def coverGridPlay(self, widget, item):
		# TODO coverGridPlay()
		pass




if __name__ == "__main__":
	mcgg = MPDCoverGridGTK()
	mcgg.show_all()
	Gtk.main()

