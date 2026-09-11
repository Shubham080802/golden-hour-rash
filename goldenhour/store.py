"""Persistence.

The browser build used localStorage. Here everything lives in one JSON file
under the user's home directory, so records survive between sessions without
needing a server. The shared Daily board has no equivalent offline, so Daily
scores are kept locally like the rest.
"""
import json
import os
import time
from pathlib import Path

SAVE_DIR = Path(os.environ.get("GOLDENHOUR_HOME", Path.home() / ".golden-hour-rash"))
SAVE_FILE = SAVE_DIR / "save.json"

_DEFAULT = {
    "settings": {"locale": "coast", "music": True},
    "records": {},
    "best": {},
    "achievements": {"won": {}, "tally": {"races": 0, "hits": 0, "roads": {}}},
}


def load():
    try:
        with SAVE_FILE.open(encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return json.loads(json.dumps(_DEFAULT))
    for k, v in _DEFAULT.items():
        data.setdefault(k, json.loads(json.dumps(v)))
    data["achievements"].setdefault("won", {})
    data["achievements"].setdefault("tally", {"races": 0, "hits": 0, "roads": {}})
    data["achievements"]["tally"].setdefault("roads", {})
    return data


def save(data):
    try:
        SAVE_DIR.mkdir(parents=True, exist_ok=True)
        tmp = SAVE_FILE.with_suffix(".tmp")
        with tmp.open("w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=1)
        tmp.replace(SAVE_FILE)          # atomic, so a crash cannot truncate it
    except OSError:
        pass


def format_key(mode, locale, diff):
    return f"daily:{locale}:{diff}" if mode == "daily" else f"{mode}:{locale}"


def record_run(data, mode, locale, diff, entry):
    """Two capped lists rather than one: a top ten by score alone would bound
    the split table to whatever those ten runs happened to do."""
    key = format_key(mode, locale, diff)
    f = data["records"].setdefault(
        key, {"scores": [], "splits": [], "runs": 0, "best_pos": 99, "best_combo": 0})
    f["runs"] = f.get("runs", 0) + 1
    f["scores"] = sorted(f["scores"] + [entry], key=lambda e: -e["score"])[:10]
    if entry.get("fkm") is not None:
        f["splits"] = sorted([e for e in f["splits"] + [entry] if e.get("fkm") is not None],
                             key=lambda e: e["fkm"])[:10]
    f["best_pos"] = min(f.get("best_pos", 99), entry["pos"])
    f["best_combo"] = max(f.get("best_combo", 0), entry["combo"])
    save(data)
    return f


def get_records(data, mode, locale, diff):
    return data["records"].get(
        format_key(mode, locale, diff),
        {"scores": [], "splits": [], "runs": 0, "best_pos": 0, "best_combo": 0})


def personal_best(data, mode, locale, diff, score):
    key = format_key(mode, locale, diff)
    prev = data["best"].get(key, 0)
    if score > prev:
        data["best"][key] = score
        save(data)
        return None                      # None means "this run is the best"
    return prev


def now_ts():
    return int(time.time())
