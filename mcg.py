#!/usr/bin/python
# -*- coding: utf-8 -*-



import mpd
import os
from hashlib import md5
from threading import Thread




class MCGClient:
	SIGNAL_CONNECT = 'connect'
	SIGNAL_IDLE = 'idle'
	SIGNAL_IDLE_PLAYER = 'idle_player'
	SIGNAL_UPDATE = 'update'


	def __init__(self):
		self._connected = False
		self._albums = {}
		self._callbacks = {}
		self._actions = []
		self._worker = None
		self._client = mpd.MPDClient()
		self._go = True


	def connect(self, host="localhost", port="6600", password=None):
		# TODO als Parameter an _add_action() übergeben, nicht speichern
		self._host = host
		self._port = port
		self._password = password
		self._add_action(self._connect)


	def _connect(self):
		try:
			self._client.connect(self._host, self._port)
			if self._password:
				self._client.password(self._password)
			# TODO Verbindung testen
			self._connected = True
			self._callback(self.SIGNAL_CONNECT, self._connected, None)
			self.update()
			self.idle_player()
		except IOError as e:
			self._connected = False
			self._callback(self.SIGNAL_CONNECT, self._connected, e)


	def is_connected(self):
		return self._connected


	def disconnect(self):
		self._add_action(self._disconnect)


	def _disconnect(self):
		if not self.is_connected():
			return
		try:
			#self._client.close()
			self._client.disconnect()
		except:
			self._client = mpd.MPDClient()
		self._connected = False
		self._callback(self.SIGNAL_CONNECT, self._connected, None)


	def close(self):
		if not self.is_connected():
			return
		try:
			self._go = False
			self._client.noidle()
			self._client.disconnect()
		except TypeError as e:
			pass


	def update(self):
		self._add_action(self._update)


	def _update(self):
		for song in self._client.listallinfo():
			try:
				if song['album'] not in self._albums:
					album = MCGAlbum(song['artist'], song['album'], song['date'], os.path.dirname(song['file']))
					self._albums[album.get_hash()] = album
				else:
					album = self._albums[MCGAlbum.hash(song['artist'], song['album'])]

				track = MCGTrack(song['title'], song['track'], song['time'], song['file'])
				album.add_track(track)
			except KeyError:
				pass
		# TODO Alben sortieren
		self._callback(self.SIGNAL_UPDATE, self._albums)


	def play(self, album):
		# TODO play()
		print("play: ", self._albums[album].get_title())


	def _idle(self, modules):
		if not modules:
			return

		if 'player' in modules:
			self._idle_player()
		if 'database' in modules:
			# TODO update DB
			pass
		if 'update' in modules:
			# TODO update
			pass
		if 'mixer' in modules:
			# TODO mixer
			pass


	def idle_player(self):
		self._add_action(self._idle_player)


	def _idle_player(self):
		if not self._has_callback(self.SIGNAL_IDLE_PLAYER):
			return
		status = self._client.status()
		state = status['state']
		song = self._client.currentsong()
		album = MCGAlbum(song['artist'], song['album'], song['date'], os.path.dirname(song['file']))
		self._callback(self.SIGNAL_IDLE_PLAYER, state, album)



	def connect_signal(self, signal, callback):
		self._callbacks[signal] = callback


	def _has_callback(self, signal):
		return signal in self._callbacks


	def _callback(self, signal, *args):
		if self._has_callback(signal):
			callback = self._callbacks[signal]
			callback(*args)


	def _add_action(self, method):
		self._actions.append(method)
		self._start_worker()


	def _start_worker(self):
		if self._worker is None or not self._worker.is_alive():
			self._worker = Thread(target=self._work, name='worker', args=())
			self._worker.start()
		else:
			try:
				self._client.noidle()
			except TypeError as e:
				pass


	def _work(self):
		while True:
			if self._actions:
				action = self._actions.pop(0)
				action()
			else:
				if not self.is_connected():
					break
				modules = self._client.idle()
				if not self._go:
					break
				self._idle(modules)




class MCGAlbum:
	_file_names = ['folder', 'cover']
	_file_exts = ['jpg', 'jpeg', 'png']


	def __init__(self, artist, title, date, path):
		self._artist = artist
		if type(self._artist) is list:
			self._artist = self._artist[0]
		self._title = title
		self._date = date
		self._path = path
		self._tracks = []
		self._cover = None
		
		self._set_hash()
		self._find_cover()


	def get_artist(self):
		return self._artist


	def get_title(self):
		return self._title


	def get_date(self):
		return self._date


	def get_path(self):
		return self._path


	def add_track(self, track):
		if track not in self._tracks:
			self._tracks.append(track)


	def get_tracks(self):
		return self._tracks


	def get_cover(self):
		return self._cover


	def _find_cover(self):
		names = list(self._file_names)
		names.append(self._title)
		names.append(' - '.join((self._artist, self._title)))
		
		
		for name in names:
			for ext in self._file_exts:
				filename = os.path.join('/home/oliver/Musik/', self._path, '.'.join([name, ext]))
				if os.path.isfile(filename):
					self._cover = filename
					break
			if self._cover is not None:
				break


	def hash(self, artist, title):
		return md5(artist.encode('utf-8')+title.encode('utf-8')).hexdigest()


	def _set_hash(self):
		self._hash = self.hash(self._artist, self._title)


	def get_hash(self):
		return self._hash




class MCGTrack:
	def __init__(self, title, track, time, file):
		self._title = title
		self._track = track
		self._time = time
		self._file = file


	def get_title(self):
		return self._title


	def get_track(self):
		return self._track


	def get_time(self):
		return self._time


	def get_file(self):
		return self._file

