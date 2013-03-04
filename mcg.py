#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""MPDCoverGrid is a client for the Music Player Daemon, focused on albums instead of single tracks."""

__author__ = "coderkun"
__email__ = "<olli@coderkun.de>"
__license__ = "GPL"
__version__ = "0.2"
__status__ = "Development"


import configparser
import glob
import os
import queue
import threading
import urllib.request
from hashlib import md5

import mpd




class MCGBase():
	def __init__(self):
		self._callbacks = {}


	def connect_signal(self, signal, callback):
		"""Connects a callback function to a signal (event).
		"""
		self._callbacks[signal] = callback


	def disconnect_signal(self, signal):
		if self._has_callback(signal):
			del self._callbacks[signal]


	def _has_callback(self, signal):
		"""Checks if there is a registered callback function for a
		signal.
		"""
		return signal in self._callbacks


	def _callback(self, signal, *data):
		if signal in self._callbacks:
			callback = self._callbacks[signal]
			callback(*data)




class MCGClient(MCGBase, mpd.MPDClient):
	"""Client library for handling the connection to the Music Player Daemon.

	This class implements an album-based MPD client.
	It offers a non-blocking threaded worker model for use in graphical
	environments and is based on python-mpd2.
	"""
	# Signal: connect/disconnect event
	SIGNAL_CONNECT = 'connect'
	# Signal: status event
	SIGNAL_STATUS = 'status'
	# Signal: load albums
	SIGNAL_LOAD_ALBUMS = 'load-albums'
	# Signal: load playlist
	SIGNAL_LOAD_PLAYLIST = 'load-playlist'
	# Signal: error
	SIGNAL_ERROR = 'error'


	def __init__(self):
		"""Sets class variables and instantiates the MPDClient.
		"""
		MCGBase.__init__(self)
		mpd.MPDClient.__init__(self)
		self._connected = False
		self._state = None
		self._client_lock = threading.Lock()
		self._client_stop = threading.Event()
		self._actions = queue.Queue()
		self._worker = None
		self._albums = {}
		self._host = None
		self._image_dir = ""


	# Connection commands

	def connect(self, host="localhost", port="6600", password=None, image_dir=""):
		"""Connects to MPD with the given host, port and password or
		with standard values.
		"""
		self._host = host
		self._image_dir = image_dir
		self._add_action(self._connect, host, port, password)


	def is_connected(self):
		"""Returns the connection status.
		"""
		return self._connected


	def disconnect(self):
		"""Disconnects from the connected MPD.
		"""
		self._client_stop.set()
		self._add_action(self._disconnect)


	def join(self):
		self._actions.join()


	# Status commands

	def get_status(self):
		"""Determines the current status.
		"""
		self._add_action(self._get_status)


	# Playback option commands

	def set_volume(self, volume):
		self._add_action(self._set_volume, volume)


	# Playback control commands

	def playpause(self):
		"""Plays or pauses the current state.
		"""
		self._add_action(self._playpause)


	def play_album(self, album):
		"""Plays the given album.
		"""
		self._add_action(self._play_album, album)


	def stop(self):
		self._add_action(self._stop)


	# Playlist commands

	def load_playlist(self):
		self._add_action(self._load_playlist)


	def clear_playlist(self):
		"""Clear the current playlist"""
		self._add_action(self._clear_playlist)


	# Database commands

	def load_albums(self):
		self._add_action(self._load_albums)


	def update(self):
		self._add_action(self._update)


	# Private methods

	def _add_action(self, method, *args):
		"""Adds an action to the action list.
		"""
		action = [method, args]
		self._actions.put(action)
		self._start_worker()


	def _start_worker(self):
		"""Starts the worker thread which waits for action to be
		performed.
		"""
		if self._worker is None or not self._worker.is_alive():
			self._worker = threading.Thread(target=self._run, name='mcg-worker', args=())
			self._worker.setDaemon(True)
			self._worker.start()
		else:
			try:
				self._call('noidle')
			except BrokenPipeError:
				pass
			except ConnectionResetError as e:
				self._set_connection_status(False, e)
			except mpd.ConnectionError as e:
				self._set_connection_status(False, e)


	def _work(self, action):
		method = action[0]
		params = action[1]
		method(*params)


	def _call(self, command, *args):
		try:
			return getattr(super(), command)(*args)
		except mpd.CommandError as e:
			self._callback(MCGClient.SIGNAL_ERROR, e)
		except mpd.ConnectionError as e:
			self._set_connection_status(False, e)
		except ConnectionResetError as e:
			self._set_connection_status(False, e)
		except BrokenPipeError:
			pass


	def _run(self):
		while not self._client_stop.is_set() or not self._actions.empty():
			if self._actions.empty():
				self._actions.put([self._idle, ()])
			action = self._actions.get()
		
			self._client_lock.acquire()
			self._work(action)
			self._client_lock.release()
			self._actions.task_done()


	# Connection commands

	def _connect(self, host, port, password):
		try:
			self._call('connect', host, port)
			if password:
				try:
					self._call('password', password)
				except mpd.CommandError as e:
					self._disconnect()
					raise e
			self._set_connection_status(True)
		except OSError as e:
			self._set_connection_status(False, e)


	def _disconnect(self):
		self._call('noidle')
		self._call('disconnect')
		self._set_connection_status(False)


	# Status commands

	def _get_status(self):
		"""Action: Performs the real status determination
		"""
		# current status
		self._call('noidle')
		status = self._call('status')
		state = status['state']
		volume = int(status['volume'])
		error = None
		if 'error' in status:
			error = status['error']
		# current song
		self._call('noidle')
		song = self._call('currentsong')
		album = None
		pos = None
		if song:
			hash = MCGAlbum.hash(song['album'], song['date'])
			if hash in self._albums:
				album = self._albums[hash]
			pos = song['track']
			if type(pos) is list:
				pos = pos[0]
			if '/' in pos:
				pos = pos[0: pos.index('/')]
			pos = int(pos) - 1
		self._state = state
		self._callback(MCGClient.SIGNAL_STATUS, state, album, pos, volume, error)


	# Playback option commants

	def _set_volume(self, volume):
		self._call('setvol', volume)


	# Playback control commands

	def _playpause(self):
		"""Action: Performs the real play/pause command.
		"""
		status = self._call('status')
		state = status['state']
		if state == 'play':
			self._call('pause')
		else:
			self._call('play')


	def _play_album(self, album):
		if album not in self._albums:
			return
		track_ids = []
		for track in self._albums[album].get_tracks():
			track_id = self._call('addid', track.get_file())
			track_ids.append(track_id)
		if self._state != 'play':
			self._call('playid', track_ids[0])


	def _stop(self):
		self._call('stop')


	# Playlist commands

	def _load_playlist(self):
		playlist = []
		for song in self._call('playlistinfo'):
			try:
				hash = MCGAlbum.hash(song['album'], song['date'])
				if len(playlist) == 0 or playlist[len(playlist)-1].get_hash() != hash:
					date = ""
					if 'date' in song:
						date = song['date']
					album = MCGAlbum(song['album'], date, self._host, self._image_dir)
					playlist.append(album)
				else:
					album = playlist[len(playlist)-1]
				track = MCGTrack(song['artist'], song['title'], song['track'], song['time'], song['file'])
				album.add_track(track)
			except KeyError:
				pass
		self._callback(MCGClient.SIGNAL_LOAD_PLAYLIST, playlist, None)


	def _clear_playlist(self):
		"""Action: Performs the real clearing of the current
		playlist.
		"""
		self._call('clear')


	# Database commands

	def _load_albums(self):
		"""Action: Performs the real update.
		"""
		for song in self._call('listallinfo'):
			try:
				hash = MCGAlbum.hash(song['album'], song['date'])
				if hash in self._albums.keys():
					album = self._albums[hash]
				else:
					date = ""
					if 'date' in song:
						date = song['date']
					album = MCGAlbum(song['album'], date, self._host, self._image_dir)
					self._albums[album.get_hash()] = album
				track = MCGTrack(song['artist'], song['title'], song['track'], song['time'], song['file'])
				album.add_track(track)
			except KeyError:
				pass
		self._callback(MCGClient.SIGNAL_LOAD_ALBUMS, self._albums, None)


	def _update(self):
		self._call('update')

	def _set_connection_status(self, status, error=None):
		self._connected = status
		self._callback(MCGClient.SIGNAL_CONNECT, status, error)
		if not status:
			self._client_stop.set()


	def _idle(self):
		"""Reacts to idle events from MPD.
		"""
		modules = self._call('idle')
		if not modules:
			return
		if 'player' in modules:
			self.get_status()
		if 'mixer' in modules:
			self.get_status()
		if 'playlist' in modules:
			self.load_playlist()
		if 'database' in modules:
			self.load_albums()
			self.load_playlist()
			self.get_status()
		if 'update' in modules:
			self.load_albums()
			self.load_playlist()
			self.get_status()




class MCGAlbum:
	SORT_BY_ARTIST = 'artist'
	SORT_BY_TITLE = 'title'
	SORT_BY_YEAR = 'year'
	_FILE_NAMES = ['folder', 'cover']
	_FILE_EXTS = ['jpg', 'png', 'jpeg']


	def __init__(self, title, date, host, image_dir):
		self._artists = []
		self._pathes = []
		if type(title) is list:
			title = title[0]
		self._title = title
		if type(date) is list:
			date = date[0]
		self._date = date
		self._host = host
		self._image_dir = image_dir
		self._tracks = []
		self._cover = None
		self._cover_searched = False
		self._set_hash()


	def get_artists(self):
		return self._artists


	def get_title(self):
		return self._title


	def get_date(self):
		return self._date


	def get_path(self):
		return self._path


	def add_track(self, track):
		if track not in self._tracks:
			self._tracks.append(track)
			for artist in track.get_artists():
				if artist not in self._artists:
					self._artists.append(artist)
			path = os.path.dirname(track.get_file())
			if path not in self._pathes:
				self._pathes.append(path)


	def get_tracks(self):
		return self._tracks


	def get_cover(self):
		if self._cover is None and not self._cover_searched:
			self._find_cover()
		return self._cover


	def hash(title, date):
		if type(title) is list:
			title = title[0]
		if type(date) is list:
			date = date[0]
		return md5(title.encode('utf-8')+date.encode('utf-8')).hexdigest()


	def get_hash(self):
		return self._hash


	def filter(self, filter_string):
		values = self._artists + [self._title, self._date]
		values.extend(map(lambda track: track.get_title(), self._tracks))
		for value in values:
			if filter_string.lower() in value.lower():
				return True
		return False


	def compare(album1, album2, criterion=None):
		if criterion == None:
			criterion = MCGAlbum.SORT_BY_TITLE
		if criterion == MCGAlbum.SORT_BY_ARTIST:
			value_function = "get_artists"
		elif criterion == MCGAlbum.SORT_BY_TITLE:
			value_function = "get_title"
		elif criterion == MCGAlbum.SORT_BY_YEAR:
			value_function = "get_date"

		if getattr(album1, value_function)() < getattr(album2, value_function)():
			return -1
		elif getattr(album1, value_function)() == getattr(album2, value_function)():
			return 0
		else:
			return 1


	def _set_hash(self):
		self._hash = MCGAlbum.hash(self._title, self._date)


	def _find_cover(self):
		names = list(MCGAlbum._FILE_NAMES)
		names.append(self._title)
		names.append(' - '.join([self._artists[0], self._title]))

		if self._host == "localhost" or self._host == "127.0.0.1":
			self._cover = self._find_cover_local(names)
		else:
			self._cover = self._find_cover_web(names)
		self._cover_searched = True


	def _find_cover_web(self, names):
		for path in self._pathes:
			for name in names:
				for ext in self._FILE_EXTS:
					url = '/'.join([
						'http:/',
						self._host,
						urllib.request.quote(path),
						urllib.request.quote('.'.join([name, ext]))
					])
					request = urllib.request.Request(url)
					try:
						response = urllib.request.urlopen(request)
						return url
					except urllib.error.URLError as e:
						pass


	def _find_cover_local(self, names):
		for path in self._pathes:
			for name in names:
				for ext in self._FILE_EXTS:
					filename = os.path.join(self._image_dir, path, '.'.join([name, ext]))
					if os.path.isfile(filename):
						return filename
		return self._find_cover_local_fallback()


	def _find_cover_local_fallback(self):
		for path in self._pathes:
			for ext in self._FILE_EXTS:
				filename = os.path.join(self._image_dir, path, "*."+ext)
				files = glob.glob(filename)
				if len(files) > 0:
					return files[0]




class MCGTrack:
	def __init__(self, artists, title, track, time, file):
		if type(artists) is not list:
			artists = [artists]
		self._artists = artists
		if type(title) is list:
			title = title[0]
		self._title = title
		if type(track) is list:
			track = track[0]
		self._track = track
		self._time = time
		self._file = file


	def get_artists(self):
		return self._artists


	def get_title(self):
		return self._title


	def get_track(self):
		return self._track


	def get_time(self):
		return self._time


	def get_file(self):
		return self._file




class MCGConfig(configparser.ConfigParser):
	CONFIG_DIR = '~/.config/mcg/'


	def __init__(self, filename):
		configparser.ConfigParser.__init__(self)
		self._filename = os.path.expanduser(os.path.join(MCGConfig.CONFIG_DIR, filename))
		self._create_dir()


	def load(self):
		if os.path.isfile(self._filename):
			self.read(self._filename)


	def save(self):
		with open(self._filename, 'w') as configfile:
			self.write(configfile)


	def _create_dir(self):
		dirname = os.path.dirname(self._filename)
		if not os.path.exists(dirname):
			os.makedirs(dirname)




class MCGProfileConfig(MCGConfig):
	CONFIG_FILE = 'profiles.conf'


	def __init__(self):
		MCGConfig.__init__(self, MCGProfileConfig.CONFIG_FILE)
		self._profiles = []


	def add_profile(self, profile):
		self._profiles.append(profile)


	def delete_profile(self, profile):
		if profile in self._profiles:
			self._profiles.remove(profile)
			self._force_default_profile()


	def get_profiles(self):
		return self._profiles


	def load(self):
		super().load()
		count = 0
		if self.has_section('profiles'):
			if self.has_option('profiles', 'count'):
				count = self.getint('profiles', 'count')
		for index in range(count):
			section = 'profile'+str(index+1)
			if self.has_section(section):
				profile = MCGProfile()
				for attribute in profile.get_attributes():
					if self.has_option(section, attribute):
						profile.set(attribute, self.get(section, attribute))
				self._profiles.append(profile)
		self._force_default_profile()


	def save(self):
		if not self.has_section('profiles'):
			self.add_section('profiles')
		self.set('profiles', 'count', str(len(self._profiles)))

		for index in range(len(self._profiles)):
			profile = self._profiles[index]
			section = 'profile'+str(index+1)
			if not self.has_section(section):
				self.add_section(section)
			for attribute in profile.get_attributes():
				self.set(section, attribute, str(profile.get(attribute)))
		super().save()


	def _force_default_profile(self):
		if len(self._profiles) == 0:
			self._profiles.append(MCGProfile())




class MCGConfigurable:
	def __init__(self):
		self._attributes = []


	def get(self, attribute):
		return getattr(self, attribute)


	def set(self, attribute, value):
		setattr(self, attribute, value)
		if attribute not in self._attributes:
			self._attributes.append(attribute)


	def get_attributes(self):
		return self._attributes




class MCGProfile(MCGConfigurable):

	def __init__(self):
		MCGConfigurable.__init__(self)
		self.set('host', "localhost")
		self.set('port', 6600)
		self.set('password', "")
		self.set('image_dir', "")
		self.set('tags', "")


	def __str__(self):
		return self.get("host")


	def get_tags(self):
		return self.get('tags').split(',')


	def set_tags(self, tags):
		self.set('tags', ','.join(tags))




class MCGCache():
	DIRNAME = '~/.cache/mcg/'
	SIZE_FILENAME = 'size'


	def __init__(self, host, size):
		self._dirname = os.path.expanduser(os.path.join(MCGCache.DIRNAME, host))
		if not os.path.exists(self._dirname):
			os.makedirs(self._dirname)
		self._size = size
		self._read_size()


	def create_filename(self, album):
		return os.path.join(self._dirname, '-'.join([album.get_hash()]))


	def _read_size(self):
		size = 100
		filename = os.path.join(self._dirname, MCGCache.SIZE_FILENAME)
		if os.path.exists(filename):
			with open(filename, 'r') as f:
				size = int(f.readline())
		if size != self._size:
			self._clear()
			with open(filename, 'w') as f:
				f.write(str(self._size))


	def _clear(self):
		for filename in os.listdir(self._dirname):
			path = os.path.join(self._dirname, filename)
			try:
				if os.path.isfile(path):
					os.unlink(path)
			except Exception as e:
				print("clear:", e)

