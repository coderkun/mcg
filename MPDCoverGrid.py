#!/usr/bin/python
# -*- coding: utf-8 -*-



from mpd import MPDClient
import os




class MPDCoverGrid:
	client = MPDClient()
	albums = {}


	def __init__(self, host='localhost', port='6600', password=None):
		self._host = host
		self._port = port
		self._password = password


	def connect(self):
		try:
			self.client.connect(self._host, self._port)
			if self._password:
				self.client.password(self._password)
		except IOError as e:
			# TODO Error
			print(e)


	def disconnect(self):
		try:
			self.client.disconnect()
		except IOError as e:
			# TODO Error
			print(e)
			self.client = MPDClient()


	def getAlbums(self):
		self.update()
		return self.albums


	def update(self):
		for song in self.client.listallinfo():
			try:
				if song['album'] not in self.albums:
					self.albums[song['album']] = MCGAlbum(song['artist'], song['album'], os.path.dirname(song['file']))
				
				album = self.albums[song['album']]
				album.addTrack(song['title'])
			except KeyError:
				pass




class MCGAlbum():
	fileNames = ['folder', 'cover']
	fileExts = ['jpg', 'jpeg', 'png']


	def __init__(self, artist, title, path):
		self.artist = artist
		if type(self.artist) is list:
			self.artist = self.artist[0]
		self.title = title
		self.path = path
		self.tracks = []
		self.cover = None
		self._findCover()


	def getArtist(self):
		return self.artist


	def getTitle(self):
		return self.title


	def getPath(self):
		return self.path


	def addTrack(self, track):
		self.tracks.append(track)


	def getTracks(self):
		return self.tracks


	def getCover(self):
		return self.cover


	def _findCover(self):
		names = list(self.fileNames)
		names.append(self.title)
		names.append(' - '.join((self.artist, self.title)))
		
		
		for name in names:
			for ext in self.fileExts:
				filename = os.path.join('/home/oliver/Musik/', self.path, '.'.join([name, ext]))
				if os.path.isfile(filename):
					self.cover = filename
					break
			if self.cover is not None:
				break


