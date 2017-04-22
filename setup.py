#!/usr/bin/env python3
# -*- coding: utf-8 -*-


import os

from setuptools import setup




setup(
    name = "MPDCoverGrid",
    version = "0.6",
    description = "MPDCoverGrid is a client for the Music Player Daemon, focused on albums instead of single tracks.",
    url = "http://www.coderkun.de/codes/mcg",
    author = "coderkun",
    author_email = "olli@coderkun.de",
    license = "GPL",
    packages = [
        "mcg"
    ],
    package_dir = {
        'mcg': 'mcg'
    },
    package_data = {
        'mcg': [
            'LICENSE',
            'README.textile'
        ]
    },
    install_requires = [
        "pygobject"
    ],
    extras_require = {
        'keyring support': ["python-keyring"]
    },
    entry_points = {
        "gui_scripts": [
            "mcg = mcg.mcg:main"
        ]
    },
    data_files = [
        (os.path.join('share', 'applications'), [
            "data/MPDCoverGridGTK.desktop"
        ]),
        (os.path.join('share', 'glib-2.0', 'schemas'), [
            "data/de.coderkun.mcg.gschema.xml"
        ]),
        (os.path.join('share', 'mcg'), [
            "data/de.coderkun.mcg.gresource",
            "data/gtk.glade",
            "data/mcg.css",
            "data/noise-texture.png"
        ])
    ],
    classifiers = [
        "Development Status :: 3 - Alpha",
        "Environment :: X11 Applications :: GTK"
        "Intended Audience :: End Users/Desktop"
        "License :: OSI Approved :: GNU General Public License (GPL)"
        "Operating System :: OS Independent"
        "Programming Language :: Python :: 3"
        "Topic :: Desktop Environment :: Gnome"
        "Topic :: Multimedia :: Sound/Audio"
        "Topic :: Multimedia :: Sound/Audio :: Players"
    ]
)
