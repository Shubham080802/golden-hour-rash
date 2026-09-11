"""Fifteen achievements.

Each test gets the finished run plus a lifetime tally, so an achievement can
be about one great race or about everything you have ever done.
"""
from .store import now_ts, save

ACHIEVEMENTS = [
    ("first_blood", "First Blood",   "Land your first hit",
     lambda r, t: t["hits"] >= 1),
    ("winner",      "Race Winner",   "Finish a race in first",
     lambda r, t: r["pos"] == 1),
    ("podium",      "On the Podium", "Finish in the top three",
     lambda r, t: r["pos"] <= 3),
    ("perfect",     "Not a Mark",    "Finish a race with no contact at all",
     lambda r, t: r["clean"]),
    ("untouched",   "Untouchable",   "Finish without a rival landing one on you",
     lambda r, t: r["clipped"] == 0),
    ("brawler",     "Brawler",       "Land eight hits in a single race",
     lambda r, t: r["hits"] >= 8),
    ("demolition",  "Demolition",    "Put three rivals in the dirt in one race",
     lambda r, t: r["knockdowns"] >= 3),
    ("threader",    "Threader",      "Twenty near misses in a single race",
     lambda r, t: r["near"] >= 20),
    ("aviator",     "Aviator",       "Catch eight crests in one race",
     lambda r, t: r["airs"] >= 8),
    ("combo20",     "On a Roll",     "Reach a twenty-hit combo",
     lambda r, t: r["combo"] >= 20),
    ("comeback",    "Comeback",      "Win after being passed at least four times",
     lambda r, t: r["pos"] == 1 and r["passed_by"] >= 4),
    ("blind_win",   "Blind Faith",   "Win a Daily on Blind",
     lambda r, t: r["pos"] == 1 and r["mode"] == "daily" and r["diff"] == "hard"),
    ("tourist",     "Road Tripper",  "Race all four roads",
     lambda r, t: len(t["roads"]) >= 4),
    ("grinder",     "Long Hauler",   "Finish twenty races",
     lambda r, t: t["races"] >= 20),
    ("century",     "Century",       "Land a hundred hits across all your races",
     lambda r, t: t["hits"] >= 100),
]


def check(data, run):
    """Returns the achievements earned by this run, and records them."""
    ach = data["achievements"]
    tally = ach["tally"]
    tally["races"] = tally.get("races", 0) + 1
    tally["hits"] = tally.get("hits", 0) + run["hits"]
    tally["roads"][run["locale"]] = True

    earned = []
    for ident, name, desc, test in ACHIEVEMENTS:
        if ident in ach["won"]:
            continue
        try:
            ok = test(run, tally)
        except (KeyError, TypeError):
            ok = False
        if ok:
            ach["won"][ident] = now_ts()
            earned.append((ident, name, desc))
    save(data)
    return earned


def progress(data):
    won = data["achievements"]["won"]
    return sum(1 for a in ACHIEVEMENTS if a[0] in won), len(ACHIEVEMENTS)
