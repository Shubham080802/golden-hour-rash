#!/usr/bin/env python3
"""Golden Hour Rash — run the game from a checkout.

    python main.py

The game itself lives in the goldenhour package; this is here so the repo
stays runnable without installing anything.
"""
import sys

from goldenhour.app import main

if __name__ == "__main__":
    sys.exit(main())
