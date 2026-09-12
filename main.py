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

async def _guarded():
    """Run the game, and make a failure visible in a browser."""
    try:
        return await run()
    except Exception:
        import traceback
        from goldenhour.app import weblog
        for line in traceback.format_exc().splitlines():
            weblog(line)
        raise


if sys.platform == "emscripten":
    # In the browser the page owns the event loop: asyncio.run hands it the
    # coroutine and returns straight away rather than blocking, so wrapping
    # it in sys.exit — which is right on the desktop — raises SystemExit
    # immediately and the game never gets driven.
    asyncio.run(_guarded())
elif __name__ == "__main__":
    sys.exit(asyncio.run(_guarded()))
