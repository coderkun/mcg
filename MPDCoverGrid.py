#!/usr/bin/python
# -*- coding: utf-8 -*-



from mpd import MPDClient




class MPDCoverGrid:
	def __init__(self, host='localhost', port='6600', password=None):
		self._host = host
		self._port = port
		self._password = password
		self.client = MPDClient()


	def connect(self):
		self.client.connect(self._host, self._port)
		if self._password:
			self.client.password(self._password)


	def disconnect(self):
		self.client.disconnect()

