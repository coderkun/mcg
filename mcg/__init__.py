#!/usr/bin/env python3
# -*- coding: utf-8 -*-


import os




# Set environment
srcdir = os.path.abspath(os.path.dirname(__file__))
datadir = os.path.join(srcdir, '..', 'data')

# Set GSettings schema dir (if not set already)
if not os.environ.get('GSETTINGS_SCHEMA_DIR'):
    os.environ['GSETTINGS_SCHEMA_DIR'] = datadir
