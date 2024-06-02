#!/usr/bin/env python3

from os import getenv
from uvicorn import run


def main():
    dev = getenv("DEV")
    host = "0.0.0.0"
    reload = False
    if dev:
        host = "127.0.0.1"
        reload = True
    try:
        run("app:app", host=host, reload=reload)
    except KeyboardInterrupt:
        print("Deleting temporary files before exiting")
        print("Exiting")
        exit(0)


if __name__ == "__main__":
    main()
