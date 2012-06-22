#!/usr/bin/python
# -*- coding: utf-8 -*-

# Author: coderkun <olli@coderkun.de>




import mpd
import os
from hashlib import md5
from threading import Thread

class MCGClient:
	"""Client library for handling the connection to the Music Player Daemon.

	This class implements an album-based MPD client.
	It offers a non-blocking threaded worker model for use in graphical
	environments and is based on python-mpd2.
	"""
	# Signal: connect/disconnect event
	SIGNAL_CONNECT = 'connect'
	# Signal: general idle event
	SIGNAL_IDLE = 'idle'
	# Signal: player idle event
	SIGNAL_IDLE_PLAYER = 'idle_player'
	# Signal: update event
	SIGNAL_UPDATE = 'update'


	def __init__(self):
		"""Sets class variables and instantiates the MPDClient.
		"""
		self._connected = False
		self._albums = {}
		self._callbacks = {}
		self._actions = []
		self._worker = None
		self._client = mpd.MPDClient()
		self._go = True


	def connect(self, host="localhost", port="6600", password=None):
		"""Connects to MPD with the given host, port and password or
		with standard values.
		"""
		# TODO als Parameter an _add_action() übergeben, nicht speichern
		self._host = host
		self._port = port
		self._password = password
		self._add_action(self._connect)


	def is_connected(self):
		"""Returns the connection status.
		"""
		return self._connected


	def disconnect(self):
		"""Disconnects from the connected MPD.
		"""
		self._add_action(self._disconnect)


	def close(self):
		"""Closes the connection and stops properly the worker thread.
		This method is to stop the whole appliction.
		"""
		if not self.is_connected():
			return
		try:
			self._go = False
			self._client.noidle()
			self._client.disconnect()
		except TypeError as e:
			pass


	def update(self):
		"""Updates the album list.
		"""
		self._add_action(self._update)


	def play(self, album):
		"""Plays the given album.
		"""
		# TODO play()
		# mpd-Befehle: add, play
		# https://github.com/Mic92/python-mpd2/blob/master/mpd.py
		print("play: ", self._albums[album].get_title())


	def connect_signal(self, signal, callback):
		"""Connects a callback function to a signal (event).
		"""
		self._callbacks[signal] = callback


	def _has_callback(self, signal):
		"""Checks if there is a registered callback function for a
		signal.
		"""
		return signal in self._callbacks


	def _callback(self, signal, *args):
		"""Calls the callback function for a signal.
		"""
		if self._has_callback(signal):
			callback = self._callbacks[signal]
			callback(*args)


	def _add_action(self, method):
		"""Adds an action to the action list.
		"""
		self._actions.append(method)
		self._start_worker()


	def _start_worker(self):
		"""Starts the worker thread which waits for action to be
		performed.
		"""
		if self._worker is None or not self._worker.is_alive():
			self._worker = Thread(target=self._work, name='worker', args=())
			self._worker.start()
		else:
			try:
				self._client.noidle()
			except TypeError as e:
				pass


	def _work(self):
		"""Performs the next action or waits for an idle event.
		"""
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


	def _idle(self, modules):
		"""Reacts to idle events from MPD.
		"""
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


	def _connect(self):
		"""Action: Performs the real connect to MPD.
		"""
		try:
			self._client.connect(self._host, self._port)
			if self._password:
				self._client.password(self._password)
			# TODO Verbindung testen
			self._connected = True
			self._callback(self.SIGNAL_CONNECT, self._connected, None)
			self.update()
			self._add_action(self._idle_player)
		except IOError as e:
			self._connected = False
			self._callback(self.SIGNAL_CONNECT, self._connected, e)


	def _disconnect(self):
		"""Action: Performs the real disconnect from MPD.
		"""
		if not self.is_connected():
			return
		try:
			#self._client.close()
			self._client.disconnect()
		except:
			self._client = mpd.MPDClient()
		self._connected = False
		self._callback(self.SIGNAL_CONNECT, self._connected, None)


	def _update(self):
		"""Action: Performs the real update.
		"""
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


	def _idle_player(self):
		"""Reacts on the player idle event.
		"""
		if not self._has_callback(self.SIGNAL_IDLE_PLAYER):
			return
		status = self._client.status()
		state = status['state']
		song = self._client.currentsong()
		album = MCGAlbum(song['artist'], song['album'], song['date'], os.path.dirname(song['file']))
		self._callback(self.SIGNAL_IDLE_PLAYER, state, album)




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

