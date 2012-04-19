#!/usr/bin/python
# -*- coding: utf-8 -*-



import mpd
import os
from threading import Thread




class MPDCoverGrid:
	SIGNAL_CONNECT = 'connect'
	SIGNAL_IDLE = 'idle'
	SIGNAL_IDLE_PLAYER = 'idlePlayer'
	SIGNAL_UPDATE = 'update'


	def __init__(self, host="localhost", port=6600, password=None):
		self._host = host
		self._port = port
		self._password = password
		self._connected = False

		self._callbacks = {}
		self._threads = {}

		self._client = mpd.MPDClient()
		self._albums = {}


	def connect(self):
		self._start_thread(self.SIGNAL_CONNECT, self._connect)


	def disconnect(self):
		self._disconnect()


	def is_connected(self):
		return self._connected


	def _connect(self):
		try:
			self._client.connect(self._host, self._port)
			if self._password:
				self._client.password(self._password)
			# TODO Verbindung testen
			self._connected = True
			self._callback(self.SIGNAL_CONNECT, self._connected, None)
			#self._start_idle()
			self.update()
		except IOError as e:
			self._connected = False
			self._callback(self.SIGNAL_CONNECT, self._connected, e)


	def _disconnect(self):
		if not self.is_connected():
			return
		self._stop_idle()
		try:
			#self._client.close()
			self._client.disconnect()
		except:
			self._client = mpd.MPDClient()
		self._connected = False
		self._callback(self.SIGNAL_CONNECT, self._connected, None)


	def _start_idle(self):
		self._start_thread(self.SIGNAL_IDLE, self._idle)


	def _stop_idle(self):
		if not self._is_doing(self.SIGNAL_IDLE):
			return

		try:
			del self._threads[self.SIGNAL_IDLE]
			self._client.noidle()
		except TypeError as e:
			pass

	def _idle(self):
		while not self._is_doing(self.SIGNAL_IDLE):
			pass
		while self._client is not None and self._connected and self._is_doing(self.SIGNAL_IDLE):
			self._client.send_idle()
			if self._is_doing(self.SIGNAL_IDLE):
				modules = self._client.fetch_idle()
				if 'player' in modules:
					self._idlePlayer()
				if 'database' in modules:
					# TODO update DB
					# self.update()?
					pass
				if 'update' in modules:
					# TODO update
					#self._idleUpdate()
					pass
				if 'mixer' in modules:
					pass


	def _idlePlayer(self):
		if not self._has_callback(self.SIGNAL_IDLE_PLAYER):
			return
		status = self._client.status()
		state = status['state']
		song = self._client.currentsong()
		album = MCGAlbum(song['artist'], song['album'], os.path.dirname(song['file']))
		self._callback(self.SIGNAL_IDLE_PLAYER, state, album)


	def update(self):
		if self.is_connected():
			self._start_thread(self.SIGNAL_UPDATE, self._update)


	def _update(self):
		self._stop_idle()
		for song in self._client.listallinfo():
			try:
				if song['album'] not in self._albums:
					album = MCGAlbum(song['artist'], song['album'], os.path.dirname(song['file']))
					self._albums[song['album']] = album
					self._callback(self.SIGNAL_UPDATE, album)
			except KeyError:
				pass
		self._start_idle()





	def connect_signal(self, signal, callback):
		self._callbacks[signal] = callback


	def _has_callback(self, signal):
		return signal in self._callbacks


	def _callback(self, signal, *args):
		if self._has_callback(signal):
			callback = self._callbacks[signal]
			callback(*args)


	def _start_thread(self, signal, method):
		self._threads[signal] = Thread(target=method, args=()).start()


	def _is_doing(self, signal):
		return signal in self._threads





	def play(self):
		# TODO play()
		pass




class MCGAlbum:
	_file_names = ['folder', 'cover']
	_file_exts = ['jpg', 'jpeg', 'png']


	def __init__(self, artist, title, path):
		self._artist = artist
		if type(self._artist) is list:
			self._artist = self._artist[0]
		self._title = title
		self._path = path
		self._cover = None
		self._find_cover()


	def get_artist(self):
		return self._artist


	def get_title(self):
		return self._title


	def get_path(self):
		return self._path


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

