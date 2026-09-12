#!/usr/bin/env python3
"""Golden Hour Rash.

    python main.py

This is also the entry point the web build is compiled from, which is why it
runs the coroutine directly rather than calling into a wrapper: pygbag loads
this file and drives the loop from the browser's own scheduler.
"""
import asyncio
import sys

from goldenhour.app import run

if __name__ == "__main__":
    sys.exit(asyncio.run(run()))
