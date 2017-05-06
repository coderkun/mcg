#!/usr/bin/env python3
# -*- coding: utf-8 -*-


import os
import subprocess

from setuptools import setup
from setuptools.command.build_py import build_py
from setuptools.dist import Distribution




class MCGDistribution(Distribution):
    global_options = Distribution.global_options + [
        ("no-compile-schemas", None, "Don't compile gsettings schemas")
    ]


    def __init__(self, *args, **kwargs):
        self.no_compile_schemas = False
        super(self.__class__, self).__init__(*args, **kwargs)




class build_mcg(build_py):


    def run(self, *args, **kwargs):
        super(self.__class__, self).run(*args, **kwargs)
        self._build_gresources()
        if not self.distribution.no_compile_schemas:
            self._build_gschemas()


    def _build_gresources(self):
        print("compiling gresources")
        subprocess.run(['glib-compile-resources', 'de.coderkun.mcg.gresource.xml'], cwd='data')


    def _build_gschemas(self):
        print("compiling gschemas")
        subprocess.run(['glib-compile-schemas', 'data'])




setup(
    distclass = MCGDistribution,
    cmdclass = {
        'build_py': build_mcg
    },
    name = "mcg",
    version = '1.0rc2',
    description = "CoverGrid (mcg) is a client for the Music Player Daemon, focusing on albums instead of single tracks.",
    url = "http://www.coderkun.de/codes/mcg",
    author = "coderkun",
    author_email = "olli@coderkun.de",
    license = "GPL",
    packages = [
        'mcg',
        'mcg/data'
    ],
    package_dir = {
        'mcg': 'mcg',
        'mcg/data': 'data'
    },
    package_data = {
        'mcg': [
            'LICENSE',
            'README.textile'
        ],
        'mcg/data': [
            'de.coderkun.mcg.gresource'
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
            "data/mcg.desktop"
        ]),
        (os.path.join('share', 'icons'), [
            "data/mcg.svg"
        ]),
        (os.path.join('share', 'glib-2.0', 'schemas'), [
            "data/de.coderkun.mcg.gschema.xml"
        ]),
        (os.path.join('share', 'locale', 'en', 'LC_MESSAGES'), [
            'locale/en/LC_MESSAGES/mcg.mo'
        ]),
        (os.path.join('share', 'locale', 'de', 'LC_MESSAGES'), [
            'locale/de/LC_MESSAGES/mcg.mo'
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
