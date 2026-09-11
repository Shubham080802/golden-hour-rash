"""Seeded road generation.

The road is a list of segments, each carrying a curve rate and a world Y. The
3D view, the guided map and the rival AI all read the same segments, so they
can never disagree about where the road goes.
"""
import math

from .config import SEG_LEN, RUMBLE, clamp


class Rng:
    """mulberry32 — small, fast, and identical across runs for a given seed."""

    def __init__(self, seed):
        self.a = seed & 0xFFFFFFFF

    def __call__(self):
        self.a = (self.a + 0x6D2B79F5) & 0xFFFFFFFF
        t = self.a
        t = (t ^ (t >> 15)) * (t | 1) & 0xFFFFFFFF
        t ^= (t + ((t ^ (t >> 7)) * (t | 61) & 0xFFFFFFFF)) & 0xFFFFFFFF
        return (((t ^ (t >> 14)) & 0xFFFFFFFF)) / 4294967296.0


def hash_str(s):
    h = 2166136261
    for ch in s:
        h ^= ord(ch)
        h = (h * 16777619) & 0xFFFFFFFF
    return h


def ease_in(a, b, p):
    return a + (b - a) * p * p


def ease_in_out(a, b, p):
    return a + (b - a) * (-math.cos(p * math.pi) / 2 + 0.5)


class Segment:
    __slots__ = ("index", "p1", "p2", "curve", "props", "dark", "clip", "proj", "looped")

    def __init__(self, index, y0, y1, curve):
        # each point: [world_y, world_z, cam_z, screen_x, screen_y, screen_w]
        self.index = index
        self.p1 = {"wy": y0, "wz": index * SEG_LEN, "cz": 0.0, "x": 0.0, "y": 0.0, "w": 0.0}
        self.p2 = {"wy": y1, "wz": (index + 1) * SEG_LEN, "cz": 0.0, "x": 0.0, "y": 0.0, "w": 0.0}
        self.curve = curve
        self.props = []
        self.dark = (index // RUMBLE) % 2 == 1
        self.clip = 0.0
        self.proj = -1
        self.looped = False


class Track:
    def __init__(self, segments, length):
        self.segments = segments
        self.length = length

    def find(self, z):
        n = len(self.segments)
        return self.segments[int(z // SEG_LEN) % n]

    def rel_z(self, d):
        """Shortest signed distance on a looping road."""
        half = self.length / 2
        if d > half:
            d -= self.length
        if d < -half:
            d += self.length
        return d


def build_track(seed, locale):
    """Generate a road from the locale's terrain profile.

    ``terrain['climb']`` swaps random hills for one sustained ascent and
    descent per lap, which is what makes a mountain pass read as a pass
    rather than as bumpy ground.
    """
    rng = Rng(seed)
    terrain = locale["terrain"]
    segs = []

    def last_y():
        return segs[-1].p2["wy"] if segs else 0.0

    def add_segment(curve, y):
        segs.append(Segment(len(segs), last_y(), y, curve))

    def add_road(enter, hold, leave, curve, y):
        start_y = last_y()
        end_y = start_y + y * SEG_LEN
        total = enter + hold + leave
        for n in range(enter):
            add_segment(ease_in(0, curve, n / enter), ease_in_out(start_y, end_y, n / total))
        for n in range(hold):
            add_segment(curve, ease_in_out(start_y, end_y, (enter + n) / total))
        for n in range(leave):
            add_segment(ease_in_out(curve, 0, n / leave),
                        ease_in_out(start_y, end_y, (enter + hold + n) / total))

    add_road(50, 50, 50, 0, 0)

    sections = 26
    for i in range(sections):
        r = rng()
        ln = 30 + int(rng() * 70)
        if terrain["climb"]:
            hill = (math.sin((i / sections) * math.pi * 2) * 48 * terrain["hill_amp"]
                    + (rng() * 2 - 1) * 10 * terrain["hill_amp"])
        else:
            hill = (rng() * 2 - 1) * (20 + rng() * 40) * terrain["hill_amp"]

        def cv(m=1.0):
            raw = (2 + rng() * 3) * terrain["curve_amp"] * m
            return (-1 if rng() < 0.5 else 1) * min(raw, 6.0)

        if r < terrain["straight_bias"]:
            add_road(ln, int(ln * 2.4), ln, 0, hill * 0.7)
        elif r < terrain["straight_bias"] + 0.30:
            add_road(ln, ln, ln, cv(), hill)
        elif r < 1 - terrain["tight"]:
            add_road(ln, int(ln * 1.4), ln, cv(0.6), hill * 1.4)
        else:
            add_road(42, 26, 42, cv(1.7), hill * 0.4)

    add_road(60, 60, 60, 0, -last_y() / SEG_LEN)

    # scenery
    props = locale["props"]
    for n in range(12, len(segs)):
        if rng() < locale["prop_density"]:
            side = -1 if rng() < 0.5 else 1
            pick = props[int(rng() * len(props))]
            offset = side * ((3.2 + rng() * 5.5) if pick.get("far") else (1.25 + rng() * 3.2))
            segs[n].props.append({
                "kind": pick["kind"], "scale": pick["scale"],
                "f": rng(), "offset": offset,
            })

    return Track(segs, len(segs) * SEG_LEN)
