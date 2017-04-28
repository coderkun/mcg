#!/usr/bin/env python3


import gi
try:
    gi.require_version('Avahi', '0.6')
    from gi.repository import Avahi
    use_avahi = True
except:
    use_avahi = False
import logging

from mcg import client




class ZeroconfProvider(client.Base):
    KEYRING_SYSTEM = 'mcg'
    KEYRING_USERNAME = 'mpd'
    SIGNAL_SERVICE_NEW = 'service-new'
    TYPE = '_mpd._tcp'


    def __init__(self):
        client.Base.__init__(self)
        self._service_resolvers = []
        self._services = {}
        self._logger = logging.getLogger(__name__)
        # Client
        if use_avahi:
            self._start_client()


    def on_new_service(self, browser, interface, protocol, name, type, domain, flags):
        #if not (flags & Avahi.LookupResultFlags.GA_LOOKUP_RESULT_LOCAL):
        service_resolver = Avahi.ServiceResolver(interface=interface, protocol=protocol, name=name, type=type, domain=domain, aprotocol=Avahi.Protocol.GA_PROTOCOL_UNSPEC, flags=0,)
        service_resolver.connect('found', self.on_found)
        service_resolver.connect('failure', self.on_failure)
        service_resolver.attach(self._client)
        self._service_resolvers.append(service_resolver)


    def on_found(self, resolver, interface, protocol, name, type, domain, host, date, port, *args):
        if (host, port) not in self._services.keys():
            service = (name,host,port)
            self._services[(host,port)] = service
            self._callback(ZeroconfProvider.SIGNAL_SERVICE_NEW, service)


    def on_failure(self, resolver, date):
        if resolver in self._service_resolvers:
            self._service_resolvers.remove(resolver)


    def _start_client(self):
        self._logger.info("Starting Avahi client")
        self._client = Avahi.Client(flags=0,)
        try:
            self._client.start()
            # Browser
            self._service_browser = Avahi.ServiceBrowser(domain='local', flags=0, interface=-1, protocol=Avahi.Protocol.GA_PROTOCOL_UNSPEC, type=ZeroconfProvider.TYPE)
            self._service_browser.connect('new_service', self.on_new_service)
            self._service_browser.attach(self._client)
        except Exception as e:
            self._logger.info(e)
