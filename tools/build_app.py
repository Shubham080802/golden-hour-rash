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
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from goldenhour import __version__          # noqa: E402

NAME = "GoldenHourRash"


def main():
    try:
        __import__("PyInstaller")
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
    out.unlink(missing_ok=True)
    if system == "darwin":
        # ditto, not zipfile: an .app is full of symlinks (the Python
        # framework's Versions/Current among them) and Python's zipfile
        # FOLLOWS them, writing the target's bytes as a plain file. The
        # bundle unzips looking complete and dies with "No module named
        # _struct" the moment it runs. ditto preserves links and modes.
        rc = subprocess.call(["ditto", "-c", "-k", "--sequesterRsrc",
                              "--keepParent", str(target), str(out)])
        if rc != 0:
            print("ditto failed")
            return 1
    else:
        shutil.make_archive(str(out.with_suffix("")), "zip",
                            root_dir=str(dist), base_dir=target.name)

    if not verify(out, target, dist):
        return 1
    print(f"\n{target}")
    print(f"{out}  ({out.stat().st_size / 1e6:.1f} MB)")
    return 0


def verify(archive, target, dist):
    """Unpack what we just wrote and run it.

    Building an archive that unpacks into something that will not start is
    the whole failure mode this guards, so the build does not claim success
    until a copy extracted from the archive has actually booted.
    """
    import os
    import time
    check = dist / "_verify"
    shutil.rmtree(check, ignore_errors=True)
    check.mkdir(parents=True)
    if platform.system().lower() == "darwin":
        rc = subprocess.call(["ditto", "-x", "-k", str(archive), str(check)])
    else:
        shutil.unpack_archive(str(archive), str(check))
        rc = 0
    if rc != 0:
        print("could not unpack the archive we just wrote")
        return False

    app = check / target.name
    exe = (app / "Contents" / "MacOS" / NAME) if app.suffix == ".app" else app
    if not exe.exists():
        print(f"unpacked archive has no executable at {exe}")
        return False
    env = dict(os.environ, SDL_VIDEODRIVER="dummy", SDL_AUDIODRIVER="dummy",
               GOLDENHOUR_HOME=str(check / "home"))
    proc = subprocess.Popen([str(exe)], env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    for _ in range(60):
        time.sleep(0.25)
        if proc.poll() is not None:
            out = (proc.stdout.read() or b"").decode(errors="replace")
            print("the packaged build exited instead of running:\n" + out[-1500:])
            return False
    proc.terminate()
    shutil.rmtree(check, ignore_errors=True)
    print("verified: a copy extracted from the archive boots and runs")
    return True


if __name__ == "__main__":
    sys.exit(main())
