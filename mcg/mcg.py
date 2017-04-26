#!/usr/bin/env python3

"""MPDCoverGrid is a client for the Music Player Daemon, focusing on albums instead of single tracks."""


import sys

from mcg.application import Application




def main():
    # Start application
    app = Application()
    exit_status = app.run(sys.argv)
    sys.exit(exit_status)


if __name__ == "__main__":
    main()
