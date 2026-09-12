"""What is lying in the road in Survival.

Hazards are not scenery and they are not traffic: they do not move, they are
laid down ahead of the rider as the run goes on, and each one hurts in its own
way. A skip stops you dead; a slick takes the bike away from you without
touching your health much, which is worse at the wrong moment.

**No pattern.** Gaps between hazards are drawn from an exponential
distribution rather than a fixed spacing, and the lane each one sits in is
drawn independently, so there is no rhythm to learn and no safe line to
memorise — only what you can read of the road in front of you. The draws come
from the run's own seeded stream, so a given seed is still a repeatable run.

Density and damage ramp with ``pressure``, which runs 0 to 1 across the five
minutes: the way out gets worse the closer you get to it.
"""
import math

from .config import KM, SEG_LEN, U_PER_M, clamp

# kind: damage, speed kept, sideways shove, hit width, drawn size, weight
KINDS = {
    "cone":    {"dmg": 5,  "keep": 0.93, "shove": 0.25, "hw": 0.20, "size": 0.26,
                "label": "CONE",    "w": 1.50},
    "pothole": {"dmg": 9,  "keep": 0.88, "shove": 0.35, "hw": 0.24, "size": 0.40,
                "label": "POTHOLE", "w": 1.30},
    "debris":  {"dmg": 13, "keep": 0.80, "shove": 0.55, "hw": 0.32, "size": 0.44,
                "label": "RUBBLE",  "w": 1.25},
    "oil":     {"dmg": 4,  "keep": 0.97, "shove": 1.55, "hw": 0.40, "size": 0.78,
                "label": "OIL",     "w": 0.95},
    "barrier": {"dmg": 17, "keep": 0.66, "shove": 0.70, "hw": 0.42, "size": 0.56,
                "label": "BARRIER", "w": 0.85},
    "barrel":  {"dmg": 15, "keep": 0.70, "shove": 0.85, "hw": 0.26, "size": 0.34,
                "label": "BARREL",  "w": 0.70},
    "skip":    {"dmg": 23, "keep": 0.52, "shove": 0.95, "hw": 0.38, "size": 0.54,
                "label": "SKIP",    "w": 0.55},
}
ORDER = list(KINDS)

# Stocked further up the road than the camera reaches (400 m), so nothing
# ever appears out of nothing inside the view.
AHEAD = 520.0 * U_PER_M
BEHIND = 60.0 * U_PER_M

# Spacing, in METRES of road. These are the numbers that decide whether the
# mode is playable, and they are written in metres on purpose: the first cut
# of this file had them in world units, which are 210 to the metre, and put a
# hazard every quarter of a second.
GAP_OPEN = 118.0           # at the gate
GAP_CLOSED = 38.0          # at the five-minute mark
GAP_FLOOR = 34.0           # never closer than this, whatever the difficulty


class Hazard:
    """One object in the road."""

    kind = "hazard"

    def __init__(self, kind, z, offset, spin):
        self.hz = kind
        self.z = z
        self.offset = offset
        self.spin = spin              # a look seed, so two skips differ
        self.w = 0.5
        self.hit = False              # only ever charges once

    @property
    def spec(self):
        return KINDS[self.hz]

    def update(self, dt, game):       # actors are all ticked; this one sits
        return


class HazardField:
    """Lays hazards down ahead of the rider and clears them up behind.

    Owns its own draws from the simulation stream. Nothing here reads the
    wall clock, so a run is reproducible from its seed.
    """

    def __init__(self, rnd, pressure=0.0):
        self.rnd = rnd
        self.items = []
        self.frontier = 0.0           # how far up the road we have stocked
        self.laid = 0

    def reset(self, from_z):
        self.items = []
        # nothing for the first 300 m: you get a moment to find the road
        self.frontier = from_z + 300.0 * U_PER_M
        self.laid = 0

    def mean_gap(self, pressure, density):
        """Average spacing in world units. Tightens as the run goes on."""
        metres = GAP_OPEN + (GAP_CLOSED - GAP_OPEN) * clamp(pressure, 0, 1)
        return max(GAP_FLOOR * U_PER_M, metres * U_PER_M / max(0.35, density))

    def _pick(self, pressure):
        """Weighted choice, with the heavy things getting likelier late."""
        weights = []
        for k in ORDER:
            w = KINDS[k]["w"]
            if KINDS[k]["dmg"] >= 13:
                w *= 0.55 + pressure * 1.30
            weights.append(w)
        total = sum(weights)
        r = self.rnd.random() * total
        for k, w in zip(ORDER, weights):
            r -= w
            if r <= 0:
                return k
        return ORDER[-1]

    def update(self, player_z, track, pressure, density, dt):
        """Stock the road ahead, drop what is behind."""
        # An exponential gap has no rhythm to it: the next one is as likely to
        # be right there as a long way off, whatever the last gap was.
        target = player_z + AHEAD
        guard = 0
        while self.frontier < target and guard < 60:
            guard += 1
            gap = -math.log(max(1e-6, 1.0 - self.rnd.random())) * self.mean_gap(
                pressure, density)
            self.frontier += max(GAP_FLOOR * U_PER_M, gap)
            kind = self._pick(pressure)
            # Lane, drawn on its own. Slicks sprawl, skips sit where a skip
            # sits, and nothing is nailed to the centre line.
            if kind == "oil":
                offset = (self.rnd.random() * 2 - 1) * 0.82
            elif kind in ("skip", "barrier"):
                offset = (self.rnd.random() * 2 - 1) * 0.74
            else:
                offset = (self.rnd.random() * 2 - 1) * 0.90
            z = self.frontier % track.length
            self.items.append(Hazard(kind, z, offset, self.rnd.random()))
            self.laid += 1

        if len(self.items) > 4:
            keep = []
            for h in self.items:
                d = track.rel_z(h.z - player_z)
                if d < -BEHIND or h.hit:
                    continue
                keep.append(h)
            self.items = keep

    def near(self, player_z, track, window=SEG_LEN * 14):
        """Anything close enough ahead to be worth a warning."""
        out = []
        for h in self.items:
            d = track.rel_z(h.z - player_z)
            if 0 < d < window:
                out.append((d, h))
        out.sort(key=lambda p: p[0])
        return out


def damage_for(hz, pressure, edge):
    """What one of these costs, given how far into the run you are."""
    spec = KINDS[hz]
    return spec["dmg"] * (0.90 + pressure * 0.60) * edge


def survival_km(dist):
    return dist / KM
