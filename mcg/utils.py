#!/usr/bin/env python3


import gi
gi.require_version('Gtk', '3.0')
import os
import urllib

from gi.repository import GdkPixbuf




class Utils:
    def load_cover(url):
        if not url:
            return None
        if url.startswith('/'):
            try:
                return GdkPixbuf.Pixbuf.new_from_file(url)
            except Exception as e:
                print(e)
                return None
        else:
            try:
                response = urllib.request.urlopen(url)
                loader = GdkPixbuf.PixbufLoader()
                loader.write(response.read())
                loader.close()
                return loader.get_pixbuf()
            except Exception as e:
                print(e)
                return None


    def load_thumbnail(cache, album, size):
        cache_url = cache.create_filename(album)
        pixbuf = None

        if os.path.isfile(cache_url):
            try:
                pixbuf = GdkPixbuf.Pixbuf.new_from_file(cache_url)
            except Exception as e:
                print(e)
        else:
            url = album.get_cover()
            pixbuf = Utils.load_cover(url)
            if pixbuf is not None:
                pixbuf = pixbuf.scale_simple(size, size, GdkPixbuf.InterpType.HYPER)
                filetype = os.path.splitext(url)[1][1:]
                if filetype == 'jpg':
                    filetype = 'jpeg'
                pixbuf.savev(cache.create_filename(album), filetype, [], [])
        return pixbuf
