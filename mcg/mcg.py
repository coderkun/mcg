#!/usr/bin/env python3


import sys

from mcg.application import Application




def main():
    # Start application
    app = Application()
    exit_status = app.run(sys.argv)
    sys.exit(exit_status)


if __name__ == "__main__":
    main()
