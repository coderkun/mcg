#!/usr/bin/env python3
# -*- coding: utf-8 -*-


import os




# Set environment
srcdir = os.path.abspath(os.path.dirname(__file__))
datadir = os.path.join(srcdir, 'data')
datadirdev = os.path.join(srcdir, '..', 'data')
if os.path.exists(datadirdev):
    datadir = datadirdev
localedir = None
localedirdev = os.path.join(srcdir, '..', 'locale')
if os.path.exists(localedirdev):
    localedir = datadirdev

# Set GSettings schema dir (if not set already)
if not os.environ.get('GSETTINGS_SCHEMA_DIR'):
    os.environ['GSETTINGS_SCHEMA_DIR'] = datadirdev




class Environment:
    """Wrapper class to access environment settings."""


    def get_srcdir():
        return srcdir


    def get_data(subdir):
        return os.path.join(datadir, subdir)


    def get_locale():
        return localedir
