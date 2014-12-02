#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""MPDCoverGrid is a client for the Music Player Daemon, focused on albums instead of single tracks."""

__author__ = "coderkun"
__email__ = "<olli@coderkun.de>"
__license__ = "GPL"
__version__ = "0.3"
__status__ = "Development"


import configparser
import glob
import logging
import os
import queue
import socket
import sys
import threading
import urllib.request
from hashlib import md5




class MPDException(Exception):
    pass


class ConnectionException(MPDException):
    pass


class ProtocolException(MPDException):
    pass


class CommandException(MPDException):
    pass




class Base():
    def __init__(self):
        self._callbacks = {}


    def connect_signal(self, signal, callback):
        """Connect a callback function to a signal (event)."""
        self._callbacks[signal] = callback


    def disconnect_signal(self, signal):
        """Disconnect a callback function from a signal (event)."""
        if self._has_callback(signal):
            del self._callbacks[signal]


    def _has_callback(self, signal):
        """Check if there is a registered callback function for a signal."""
        return signal in self._callbacks


    def _callback(self, signal, *data):
        if signal in self._callbacks:
            callback = self._callbacks[signal]
            callback(*data)




class Client(Base):
    """Client library for handling the connection to the Music Player Daemon.

    This class implements an album-based MPD client. It offers a non-blocking
    threaded worker model for use in graphical environments.
    """
    # Protocol: greeting mark
    PROTOCOL_GREETING = 'OK MPD '
    # Protocol: completion mark
    PROTOCOL_COMPLETION = 'OK'
    # Protocol: error mark
    PROTOCOL_ERROR = 'ACK '
    # Signal: connection status
    SIGNAL_CONNECTION = 'connection'
    # Signal: status
    SIGNAL_STATUS = 'status'
    # Signal: load albums
    SIGNAL_LOAD_ALBUMS = 'load-albums'
    # Signal: load playlist
    SIGNAL_LOAD_PLAYLIST = 'load-playlist'
    # Signal: error
    SIGNAL_ERROR = 'error'


    def __init__(self):
        """Set class variables and instantiates the Client."""
        Base.__init__(self)
        self._logger = logging.getLogger(__name__)
        self._sock = None
        self._sock_read = None
        self._sock_write = None
        self._stop = threading.Event()
        self._actions = queue.Queue()
        self._worker = None
        self._idling = False
        self._host = None
        self._albums = {}
        self._playlist = []
        self._image_dir = ""
        self._state = None


    def get_logger(self):
        return self._logger


    # Client commands

    def connect(self, host, port, password=None, image_dir=""):
        """Connect to MPD with the given host, port and password or with
        standard values.
        """
        self._logger.info("connect")
        self._host = host
        self._image_dir = image_dir
        self._add_action(self._connect, host, port, password)
        self._stop.clear()
        self._start_worker()


    def is_connected(self):
        """Return the connection status."""
        return self._worker is not None and self._worker.is_alive()


    def disconnect(self):
        """Disconnect from the connected MPD."""
        self._logger.info("disconnect")
        self._stop.set()
        self._add_action(self._disconnect)


    def join(self):
        self._actions.join()


    def get_status(self):
        """Determine the current status."""
        self._logger.info("get status")
        self._add_action(self._get_status)


    def load_albums(self):
        self._logger.info("load albums")
        self._add_action(self._load_albums)


    def update(self):
        self._logger.info("update")
        self._add_action(self._update)


    def load_playlist(self):
        self._logger.info("load playlist")
        self._add_action(self._load_playlist)


    def clear_playlist(self):
        """Clear the current playlist"""
        self._logger.info("clear playlist")
        self._add_action(self._clear_playlist)


    def playpause(self):
        """Play or pauses the current state."""
        self._logger.info("playpause")
        self._add_action(self._playpause)


    def play_album(self, album):
        """Play the given album."""
        self._logger.info("play album")
        self._add_action(self._play_album, album)


    def seek(self, pos, time):
        """Seeks to a song at a position"""
        self._logger.info("seek")
        self._add_action(self._seek, pos, time)


    def stop(self):
        self._logger.info("stop")
        self._add_action(self._stop)


    def set_volume(self, volume):
        self._logger.info("set volume")
        self._add_action(self._set_volume, volume)


    # Private methods

    def _connect(self, host, port, password):
        self._logger.info("connecting to host %r, port %r", host, port)
        if self._sock is not None:
            return
        try:
            self._sock = self._connect_socket(host, port)
            self._sock_read = self._sock.makefile("r", encoding="utf-8")
            self._sock_write = self._sock.makefile("w", encoding="utf-8")
            self._greet()
            self._logger.info("connected")
            if password:
                self._logger.info("setting password")
                self._call("password", password)
            self._set_connection_status(True)
        except OSError as e:
            raise ConnectionException("connection failed: {}".format(e))


    def _connect_socket(self, host, port):
        sock = None
        error = None
        for res in socket.getaddrinfo(host, port, socket.AF_UNSPEC, socket.SOCK_STREAM, socket.IPPROTO_TCP):
            af, socktype, proto, canonname, sa = res
            try:
                sock = socket.socket(af, socktype, proto)
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
                sock.connect(sa)
                return sock
            except Exception as e:
                error = e
                if sock is not None:
                    sock.close()
                break
        if error is not None:
            raise ConnectionException("connection failed: {}".format(error))
        else:
            raise ConnectionException("no suitable socket")


    def _greet(self):
        greeting = self._sock_read.readline()
        self._logger.debug("greeting: %s", greeting.strip())
        if not greeting.endswith("\n"):
            self._disconnect_socket()
            raise ConnectionException("incomplete line")
        if not greeting.startswith(Client.PROTOCOL_GREETING):
            self._disconnect_socket()
            raise ProtocolException("invalid greeting: {}".format(greeting))
        self._protocol_version = greeting[len(Client.PROTOCOL_GREETING):].strip()
        self._logger.debug("protocol version: %s", self._protocol_version)


    def _disconnect(self):
        self._logger.info("disconnecting")
        self._disconnect_socket()


    def _disconnect_socket(self):
        if self._sock_read is not None:
            self._sock_read.close()
        self._sock_read = None
        if self._sock_write is not None:
            self._sock_write.close()
        self._sock_write = None
        if self._sock is not None:
            self._sock.close()
        self._sock = None
        self._logger.info("disconnected")
        self._set_connection_status(False)


    def _idle(self):
        """React to idle events from MPD."""
        self._logger.info("idle")
        self._idling = True
        subsystems = self._parse_dict(self._call("idle"))
        self._idling = False
        self._logger.info("idle subsystems: %r", subsystems)
        if subsystems:
            if subsystems['changed'] == 'player':
                self.get_status()
            if subsystems['changed'] == 'mixer':
                self.get_status()
            if subsystems['changed'] == 'playlist':
                self.load_playlist()
            if subsystems['changed'] == 'database':
                self.load_albums()
                self.load_playlist()
                self.get_status()
            if subsystems['changed'] == 'update':
                self.load_albums()
                self.load_playlist()
                self.get_status()


    def _noidle(self):
        if self._idling:
            self._logger.debug("noidle")
            self._write("noidle")


    def _get_status(self):
        """Action: Perform the real status determination."""
        self._logger.info("getting status")
        status = self._parse_dict(self._call("status"))
        self._logger.debug("status: %r", status)

        # State
        state = None
        if 'state' in status:
            state = status['state']
        self._state = state
        # Time
        time = 0
        if 'time' in status:
            time = int(status['time'].split(':')[0])
        # Volume
        volume = 0
        if 'volume' in status:
            volume = int(status['volume'])
        # Error
        error = None
        if 'error' in status:
            error = status['error']
        # Album
        album = None
        pos = 0
        song = self._parse_dict(self._call("currentsong"))
        if song:
            # Album
            if 'album' not in song:
                song['album'] = MCGAlbum.DEFAULT_ALBUM
            hash = MCGAlbum.hash(song['album'])
            if hash in self._albums.keys():
                album = self._albums[hash]
            # Position
            if 'pos' in song:
                pos = int(song['pos'])
            for palbum in self._playlist:
                if palbum == album and len(palbum.get_tracks()) >= pos:
                    album = palbum
                    break
                pos = pos - len(palbum.get_tracks())
        self._callback(Client.SIGNAL_STATUS, state, album, pos, time, volume, error)


    def _load_albums(self):
        """Action: Perform the real update."""
        self._albums = {}
        for song in self._parse_list(self._call('listallinfo'), ['file', 'directory']):
            self._logger.debug("song: %r", song)
            if 'file' in song:
                # Track
                track = None
                if 'artist' in song and 'title' in song and 'file' in song:
                    if 'track' not in song:
                        song['track'] = None
                    if 'time' not in song:
                        song['time'] = 0
                    if 'date' not in song:
                        song['date'] = None
                    track = MCGTrack(song['artist'], song['title'], song['track'], song['time'], song['date'], song['file'])
                self._logger.debug("track: %r", track)
                # Album
                if 'album' not in song:
                    song['album'] = MCGAlbum.DEFAULT_ALBUM
                hash = MCGAlbum.hash(song['album'])
                if hash in self._albums.keys():
                    album = self._albums[hash]
                else:
                    album = MCGAlbum(song['album'], self._host, self._image_dir)
                    self._albums[album.get_hash()] = album
                self._logger.debug("album: %r", album)
                # Add track to album
                if track:
                    album.add_track(track)
        self._callback(Client.SIGNAL_LOAD_ALBUMS, self._albums)


    def _update(self):
        self._call('update')


    def _load_playlist(self):
        self._playlist = []
        for song in self._parse_list(self._call('playlistinfo'), ['file', 'playlist']):
            self._logger.debug("song: %r", song)
            # Track
            track = None
            if 'artist' in song and 'title' in song and 'file' in song:
                if 'track' not in song:
                    song['track'] = None
                if 'time' not in song:
                    song['time'] = 0
                if 'date' not in song:
                    song['date'] = None
                track = MCGTrack(song['artist'], song['title'], song['track'], song['time'], song['date'], song['file'])
                self._logger.debug("track: %r", track)
            # Album
            if 'album' not in song:
                song['album'] = MCGAlbum.DEFAULT_ALBUM
            hash = MCGAlbum.hash(song['album'])
            if len(self._playlist) == 0 or self._playlist[len(self._playlist)-1].get_hash() != hash:
                album = MCGAlbum(song['album'], self._host, self._image_dir)
                self._playlist.append(album)
            else:
                album = self._playlist[len(self._playlist)-1]
            self._logger.debug("album: %r", album)
            if track:
                album.add_track(track)
        self._callback(Client.SIGNAL_LOAD_PLAYLIST, self._playlist)


    def _clear_playlist(self):
        """Action: Perform the real clearing of the current playlist."""
        self._call('clear')


    def _playpause(self):
        """Action: Perform the real play/pause command."""
        #status = self._parse_dict(self._call('status'))
        #if 'state' in status:
        if self._state == 'play':
            self._call('pause')
        else:
            self._call('play')


    def _play_album(self, album):
        if album in self._albums:
            track_ids = []
            for track in self._albums[album].get_tracks():
                self._logger.info("addid: %r", track.get_file())
                track_id = None
                track_id_response = self._parse_dict(self._call('addid', track.get_file()))
                if 'id' in track_id_response:
                    track_id = track_id_response['id']
                self._logger.debug("track id: %r", track_id)
                if track_id is not None:
                    track_ids.append(track_id)
            if self._state != 'play' and track_ids:
                self._call('playid', track_ids[0])


    def _seek(self, pos, time):
        self._call('seek', pos, time)


    def _stop(self):
        self._call('stop')


    def _set_volume(self, volume):
        self._call('setvol', volume)


    def _start_worker(self):
        """Start the worker thread which waits for action to be performed."""
        self._logger.debug("start worker")
        self._worker = threading.Thread(target=self._run, name='mcg-worker', args=())
        self._worker.setDaemon(True)
        self._worker.start()
        self._logger.debug("worker started")


    def _run(self):
        while not self._stop.is_set() or not self._actions.empty():
            if self._sock is not None and self._actions.empty():
                self._add_action(self._idle)
            action = self._actions.get()
            self._logger.debug("next action: %r", action)
            self._work(action)
            self._actions.task_done()
            self._logger.debug("action done")
        self._logger.debug("worker finished")


    def _add_action(self, method, *args):
        """Add an action to the action list."""
        self._logger.debug("add action %r (%r)", method.__name__, args)
        action = (method, args)
        self._actions.put(action)
        self._noidle()


    def _work(self, action):
        (method, args) = action
        self._logger.debug("work: %r", method.__name__)
        try:
            method(*args)
        except ConnectionException as e:
            self._logger.exception(e)
            self._callback(Client.SIGNAL_ERROR, e)
            self._disconnect_socket()
        except Exception as e:
            self._logger.exception(e)
            self._callback(Client.SIGNAL_ERROR, e)


    def _call(self, command, *args):
        try:
            self._write(command, args)
            return self._read()
        except MPDException as e:
            self._callback(Client.SIGNAL_ERROR, e)


    def _write(self, command, args=None):
        if args is not None and len(args) > 0:
            line = '{} "{}"\n'.format(command, '" "'.join(str(x).replace('"', '\\\"') for x in args))
        else:
            line = '{}\n'.format(command)
        self._logger.debug("write: %r", line)
        self._sock_write.write(line)
        self._sock_write.flush()


    def _read(self):
        self._logger.debug("reading response")
        response = []
        line = self._sock_read.readline()
        if not line.endswith("\n"):
            self._disconnect_socket()
            raise ConnectionException("incomplete line")
        while not line.startswith(Client.PROTOCOL_COMPLETION) and not line.startswith(Client.PROTOCOL_ERROR):
            response.append(line.strip())
            line = self._sock_read.readline()
            if not line.endswith("\n"):
                self._disconnect_socket()
                raise ConnectionException("incomplete line")
        if line.startswith(Client.PROTOCOL_COMPLETION):
            self._logger.debug("response complete")
        if line.startswith(Client.PROTOCOL_ERROR):
            error = line[len(Client.PROTOCOL_ERROR):].strip()
            self._logger.debug("command failed: %r", error)
            raise CommandException(error)
        self._logger.debug("response: %r", response)
        return response


    def _parse_dict(self, response):
        dict = {}
        for line in response:
            key, value = self._split_line(line)
            dict[key] = value
        return dict


    def _parse_list(self, response, delimiters):
        entry = {}
        for line in response:
            key, value = self._split_line(line)
            if entry and key in delimiters:
                yield entry
                entry = {}
            entry[key] = value
        if entry:
            yield entry


    def _split_line(self, line):
        parts = line.split(': ')
        return parts[0].lower(), ': '.join(parts[1:])


    def _set_connection_status(self, status):
        self._callback(Client.SIGNAL_CONNECTION, status)




class MCGAlbum:
    DEFAULT_ALBUM = 'Various'
    SORT_BY_ARTIST = 'artist'
    SORT_BY_TITLE = 'title'
    SORT_BY_YEAR = 'year'
    _FILE_NAMES = ['folder', 'cover']
    _FILE_EXTS = ['jpg', 'png', 'jpeg']


    def __init__(self, title, host, image_dir):
        self._artists = []
        self._pathes = []
        if type(title) is list:
            title = title[0]
        self._title = title
        self._dates = []
        self._host = host
        self._image_dir = image_dir
        self._tracks = []
        self._length = 0
        self._cover = None
        self._cover_searched = False
        self._set_hash()


    def __eq__(self, other):
        return self._hash == other.get_hash()


    def get_artists(self):
        return self._artists


    def get_title(self):
        return self._title


    def get_dates(self):
        return self._dates


    def get_date(self):
        if len(self._dates) == 0:
            return None
        return self._dates[0]


    def get_path(self):
        return self._path


    def add_track(self, track):
        self._tracks.append(track)
        self._length = self._length + track.get_length()
        for artist in track.get_artists():
            if artist not in self._artists:
                self._artists.append(artist)
        if track.get_date() is not None and track.get_date() not in self._dates:
            self._dates.append(track.get_date())
        path = os.path.dirname(track.get_file())
        if path not in self._pathes:
            self._pathes.append(path)


    def get_tracks(self):
        return self._tracks


    def get_length(self):
        return self._length


    def get_cover(self):
        if self._cover is None and not self._cover_searched:
            self._find_cover()
        return self._cover


    def hash(title):
        if type(title) is list:
            title = title[0]
        return md5(title.encode('utf-8')).hexdigest()


    def get_hash(self):
        return self._hash


    def filter(self, filter_string):
        values = self._artists + [self._title]
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

        value1 = getattr(album1, value_function)()
        value2 = getattr(album2, value_function)()
        if value1 is None and value2 is None:
            return 0
        elif value1 is None:
            return -1
        elif value2 is None:
            return 1
        if value1 < value2:
            return -1
        elif value1 == value2:
            return 0
        else:
            return 1


    def _set_hash(self):
        self._hash = MCGAlbum.hash(self._title)


    def _find_cover(self):
        names = list(MCGAlbum._FILE_NAMES)
        names.append(self._title)
        names.append(' - '.join([self._artists[0], self._title]))

        if self._host == "localhost" or self._host == "127.0.0.1" or self._host == "::1":
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
                        urllib.request.quote(self._image_dir.strip("/")),
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
    def __init__(self, artists, title, track, length, date, file):
        if type(artists) is not list:
            artists = [artists]
        self._artists = artists
        if type(title) is list:
            title = title[0]
        self._title = title
        if type(track) is list:
            track = track[0]
        if track is not None and '/' in track:
            track = track[0: track.index('/')]
        if track is not None:
            track = int(track)
        self._track = track
        self._length = int(length)
        if type(date) is list:
            date = date[0]
        self._date = date
        if type(file) is list:
            file = file[0]
        self._file = file


    def __eq__(self, other):
        return self._file == other.get_file()


    def get_artists(self):
        return self._artists


    def get_title(self):
        return self._title


    def get_track(self):
        return self._track


    def get_length(self):
        return self._length


    def get_date(self):
        return self._date


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
        for section in self.sections()[len(self._profiles)+1:]:
            self.remove_section(section)
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
    _lock = threading.Lock()


    def __init__(self, host, size):
        self._host = host
        self._size = size
        self._dirname = os.path.expanduser(os.path.join(MCGCache.DIRNAME, host))
        if not os.path.exists(self._dirname):
            os.makedirs(self._dirname)
        self._read_size()


    def create_filename(self, album):
        return os.path.join(self._dirname, '-'.join([album.get_hash()]))


    def _read_size(self):
        size = 100
        MCGCache._lock.acquire()
        # Read old size
        filename = os.path.join(self._dirname, MCGCache.SIZE_FILENAME)
        if os.path.exists(filename):
            with open(filename, 'r') as f:
                size = int(f.readline())
        # Clear cache if size has changed
        if size != self._size:
            self._clear()
        # Write new size
        with open(filename, 'w') as f:
            f.write(str(self._size))
        MCGCache._lock.release()


    def _clear(self):
        for filename in os.listdir(self._dirname):
            path = os.path.join(self._dirname, filename)
            if os.path.isfile(path):
                try:
                    os.unlink(path)
                except Exception as e:
                    print("clear:", e)
