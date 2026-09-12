"""Story mode: one night's ride, told in five legs.

A rider leaves town at last light and rides through the night to be on the
Ridge Pass overlook when the sun comes up. Each chapter is a leg of that
journey run on one of the four roads, with its own situation to get through,
and the legs are joined by animated beats drawn by :mod:`goldenhour.cinema`.

Nothing here touches the racing model. A chapter is a small table of settings
handed to ``Game.start_story`` — which road, how long, who else is out there —
plus a goal the game checks when the leg ends. That keeps the story a layer
over the game rather than a second game.

Goals come in four shapes:

``distance``  cover ``value`` metres before the clock runs out
``place``     finish ``value`` or better in the pack
``contacts``  finish having taken no more than ``value`` knocks
``arrive``    no way to fail; ride until the road ends
"""
from .config import KM

# Time of day for the cinematic beats, and for the tint over the road.
DUSK, NIGHT, LATE, PREDAWN, DAWN = "dusk", "night", "late", "predawn", "dawn"

CHAPTERS = [
    {
        "id": "leaving",
        "title": "Last Light Out of Town",
        "place": "Golden Coast",
        "locale": "coast",
        "sky": DUSK,
        "secs": 92.0,
        "traffic": 1.0,
        "riders": 0,
        "calm": False,
        # The opener is the forgiving one: even a scrappy ride clears it.
        # Re-measured after the road got busy — the same ride now covers
        # less ground, so the bar came down with it.
        "goal": {"kind": "distance", "value": 4.1 * KM,
                 "label": "Clear 4.1 km before the light goes"},
        "intro": [
            "You have been telling yourself this for a year.",
            "Tonight the bike is loaded and the tank is full,",
            "and the coast road is the only way out of town.",
            "Sunrise on the Ridge Pass is nine hours north.",
        ],
        "outro": [
            "The last streetlight falls away behind you.",
            "From here on it is just the headlight and the road.",
        ],
    },
    {
        "id": "saltflats",
        "title": "Salt Flats, Midnight",
        "place": "Salt & Sand",
        "locale": "dunes",
        "sky": NIGHT,
        "secs": 86.0,
        # Nearly deserted on purpose: this leg is about holding a line in a
        # crosswind, so the knock count has to mean the ground, not traffic.
        "traffic": 0.15,
        "riders": 0,
        "calm": True,
        "goal": {"kind": "contacts", "value": 3,
                 "label": "Reach the far side having taken 3 knocks or fewer"},
        "intro": [
            "Midnight. Nobody out here but the salt and the wind,",
            "and the wind has been pushing you sideways for an hour.",
            "Keep it upright. There is nothing to hit but the ground.",
        ],
        "outro": [
            "The flats end the way they began, all at once.",
            "Somewhere ahead there are headlights. Plural.",
        ],
    },
    {
        "id": "redmile",
        "title": "The Red Mile",
        "place": "Dry Canyon",
        "locale": "canyon",
        "sky": LATE,
        "secs": 100.0,
        "traffic": 0.5,
        "riders": 9,
        "calm": False,
        # The one leg that is a straight race. The bar is the top half of a
        # ten-bike field: the measuring bots land on P4 and P6 either side of
        # it, which is where a leg you are meant to retry belongs.
        "goal": {"kind": "place", "value": 5,
                 "label": "Come out of the canyon in the top half"},
        "intro": [
            "They were waiting at the fuel stop and they did not ask.",
            "Nine bikes, one canyon, and a hundred miles of red rock",
            "before anyone sees a town again.",
            "Fine. You were not going to sleep anyway.",
        ],
        "outro": [
            "SABLE lifts two fingers off the bar as you pull away.",
            "Not friendly, exactly. But not nothing.",
        ],
    },
    {
        "id": "climb",
        "title": "The Climb",
        "place": "Ridge Pass",
        "locale": "ridge",
        "sky": PREDAWN,
        "secs": 98.0,
        "traffic": 0.45,
        "riders": 4,
        "calm": False,
        "goal": {"kind": "distance", "value": 4.3 * KM,
                 "label": "Make 4.3 km up the pass before first light"},
        "intro": [
            "Four of them came with you. The air is thinner",
            "and the hairpins arrive faster than the headlight does.",
            "Forty minutes to sunrise. The overlook is at the top.",
        ],
        "outro": [
            "The gradient eases. The sky over the ridge has gone grey,",
            "which out here means you are nearly out of night.",
        ],
    },
    {
        "id": "firstlight",
        "title": "First Light",
        "place": "Ridge Pass Overlook",
        "locale": "ridge",
        "sky": DAWN,
        "secs": 95.0,
        "traffic": 0.15,
        "riders": 0,
        "calm": True,
        "goal": {"kind": "arrive", "value": 0,
                 "label": "Ride to the overlook"},
        "intro": [
            "Last few kilometres. No one to beat, nothing to prove.",
            "Roll it on, or do not. The sun comes up either way.",
        ],
        "outro": [
            "You park at the edge and kill the engine.",
            "For a minute there is no sound at all.",
            "Then the light comes over the ridge and lands on your hands,",
            "and it was worth every kilometre of the night.",
        ],
    },
]

BY_ID = {c["id"]: c for c in CHAPTERS}


def chapter(index):
    return CHAPTERS[max(0, min(len(CHAPTERS) - 1, index))]


def goal_text(ch):
    return ch["goal"]["label"]


def evaluate(ch, stats):
    """Did the leg go well enough to go on? Returns (passed, line).

    ``stats`` is whatever the game knows at the flag: metres covered,
    finishing place, contacts taken.
    """
    goal = ch["goal"]
    kind, want = goal["kind"], goal["value"]
    if kind == "distance":
        got = stats["dist"]
        ok = got >= want
        return ok, (f"{got / KM:.2f} km of {want / KM:.1f} km"
                    if not ok else f"{got / KM:.2f} km covered")
    if kind == "place":
        pos = stats["pos"]
        return pos <= want, f"Finished P{pos} of {stats['of']}"
    if kind == "contacts":
        n = stats["contacts"]
        return n <= want, (f"{n} knock{'' if n == 1 else 's'} taken"
                           + ("" if n <= want else f", {want} allowed"))
    return True, "Arrived"


def progress(data):
    """How far through the journey the rider has got."""
    st = data.setdefault("story", {"done": [], "best": {}})
    st.setdefault("done", [])
    st.setdefault("best", {})
    return st


def unlocked(data):
    """Index of the furthest chapter that may be ridden."""
    done = progress(data)["done"]
    n = 0
    for ch in CHAPTERS:
        if ch["id"] in done:
            n += 1
        else:
            break
    return min(n, len(CHAPTERS) - 1)


def finished(data):
    return all(ch["id"] in progress(data)["done"] for ch in CHAPTERS)


def complete(data, ch, stats, store):
    """Mark a leg ridden, keep the best attempt, and save."""
    st = progress(data)
    if ch["id"] not in st["done"]:
        st["done"].append(ch["id"])
    best = st["best"].get(ch["id"]) or {}
    if stats["score"] > best.get("score", -1):
        st["best"][ch["id"]] = {"score": stats["score"], "dist": stats["dist"],
                                "pos": stats.get("pos", 0),
                                "contacts": stats["contacts"],
                                "t": round(stats["t"], 2)}
    store.save(data)
    return st
