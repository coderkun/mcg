#!/usr/bin/env python3

"""MPDCoverGrid is a client for the Music Player Daemon, focused on albums instead of single tracks."""


import os
import sys

from mcg.application import Application




if __name__ == "__main__":
    # Start application
    app = Application()
    exit_status = app.run(sys.argv)
    sys.exit(exit_status)
