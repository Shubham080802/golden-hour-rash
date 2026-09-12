#!/usr/bin/env python3
"""Build the browser version with pygbag.

    python tools/build_web.py           # build into build/web
    python tools/build_web.py --serve   # build, then serve it on :8000

The output is static files, so anything that hosts static files will do.
The CPython runtime, pygame and numpy are fetched from the pygame-web CDN
at load time, which is why the build itself is only a few hundred KB.
"""
import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WIDTH, HEIGHT = 1000, 640          # matches WIN_W / WIN_H


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--serve", action="store_true",
                    help="serve the build instead of exiting")
    args = ap.parse_args()
    try:
        __import__("pygbag")
    except ImportError:
        print("pygbag is not installed:  pip install pygbag")
        return 1

    # Build from a staging copy holding only what the browser needs.
    # pygbag packs everything under the folder it is pointed at, and the repo
    # also carries a 60 MB desktop app bundle in dist/ and the old browser
    # prototype in web/ — pointing it at the repo root makes it choke.
    stage = ROOT / "build" / "golden-hour-rash"
    shutil.rmtree(stage, ignore_errors=True)
    (stage / "goldenhour").mkdir(parents=True)
    shutil.copy2(ROOT / "main.py", stage / "main.py")
    for src in sorted((ROOT / "goldenhour").glob("*.py")):
        shutil.copy2(src, stage / "goldenhour" / src.name)

    cmd = [sys.executable, "-m", "pygbag",
           "--ume_block", "0",          # no click-to-start gate
           "--width", str(WIDTH), "--height", str(HEIGHT),
           "--app_name", "golden-hour-rash",
           "--title", "Golden Hour Rash"]
    if not args.serve:
        cmd.append("--build")
    cmd.append(str(stage))
    print("$ " + " ".join(cmd))
    rc = subprocess.call(cmd, cwd=str(ROOT))
    if rc != 0:
        return rc

    built = stage / "build" / "web"
    out = ROOT / "build" / "web"
    if not args.serve:
        if not built.exists() or not any(built.iterdir()):
            print("pygbag produced nothing")
            return 1
        shutil.rmtree(out, ignore_errors=True)
        shutil.copytree(built, out)
        files = sorted(p.name for p in out.iterdir())
        size = sum(p.stat().st_size for p in out.iterdir()) / 1e6
        print(f"\n{out}  ({size:.1f} MB): " + ", ".join(files))
    return 0


if __name__ == "__main__":
    sys.exit(main())
