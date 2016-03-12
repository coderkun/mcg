#!/usr/bin/env python3
# -*- coding: utf-8 -*-


from setuptools import setup




setup(
    name = "MPD Cover Grid",
    version = "0.4",
    description = "MPDCoverGrid is a client for the Music Player Daemon, focused on albums instead of single tracks."
    url = "http://www.coderkun.de/codes/mcg",
    author = "coderkun",
    author_email = "olli@coderkun.de",
    license = "GPL",
    packages = [
        "mcg"
    ],
    scripts = [],
    install_requires = [
        "python-gobject"
    ],
    extras_require = {
        'keyring support': ["python-keyring"]
    },
    entry_points = {
        "gui_scripts": [
            "frontend = mcgGtk:main"
        ]
    },
    data_files = [
        "data/MPDCoverGridGTK.desktop",
        "gschemas.compiled",
        "noise-texture.png"
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
