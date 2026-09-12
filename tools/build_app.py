#!/usr/bin/env python3
"""Build a standalone app with PyInstaller.

    python tools/build_app.py

Produces dist/GoldenHourRash (a .app bundle on macOS) and a zip beside it,
named with the version and the platform. PyInstaller is a build-time
dependency only — it is not needed to run the game from source.
"""
import platform
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from goldenhour import __version__          # noqa: E402

NAME = "GoldenHourRash"


def main():
    try:
        import PyInstaller                    # noqa: F401
    except ImportError:
        print("PyInstaller is not installed:  pip install pyinstaller")
        return 1

    dist = ROOT / "dist"
    build = ROOT / "build"
    for path in (dist, build):
        shutil.rmtree(path, ignore_errors=True)

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name", NAME,
        "--noconfirm", "--clean",
        "--windowed",                        # no terminal window behind it
        "--osx-bundle-identifier", "com.goldenhour.rash",
        "--distpath", str(dist),
        "--workpath", str(build),
        "--specpath", str(build),
        # numpy and pygame both ship their own binaries; PyInstaller finds
        # them, but the mixer's SDL backends need the hook to be explicit
        "--hidden-import", "pygame.mixer",
        "--hidden-import", "numpy",
        str(ROOT / "main.py"),
    ]
    print("$ " + " ".join(cmd))
    if subprocess.call(cmd) != 0:
        return 1

    system = platform.system().lower()
    arch = platform.machine()
    bundle = dist / f"{NAME}.app"
    target = bundle if bundle.exists() else dist / NAME
    if not target.exists():
        print(f"build produced nothing at {target}")
        return 1

    out = dist / f"{NAME}-{__version__}-{system}-{arch}.zip"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        if target.is_dir():
            for p in sorted(target.rglob("*")):
                if p.is_symlink() or p.is_file():
                    z.write(p, p.relative_to(dist))
        else:
            z.write(target, target.name)
    print(f"\n{target}")
    print(f"{out}  ({out.stat().st_size / 1e6:.1f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
