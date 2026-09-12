"""Traffic, rivals, and the timing traces the classification is built from."""
import math

from .config import CENTRIFUGAL, KM, MAX_SPEED, PTS, clamp, hexc, lerp

# Each rider is a different person: how far ahead they read the road, how hard
# they push, how cleanly they corner, how much they want a fight.
# Colours are the Okabe-Ito set, which stays distinguishable under the common
# forms of colour blindness. The old red/green pair for VEX and DIZZY was the
# worst possible choice for the two dots you read fastest in the standings.
RIDER_SPECS = [
    {"name": "VEX",   "bike": "#D55E00", "suit": "#241B33",
     "skill": 0.52, "nerve": 0.95, "look": 1100, "aggro": 0.90, "line": -0.30},
    {"name": "MARLA", "bike": "#0072B2", "suit": "#1F2A3D",
     "skill": 0.92, "nerve": 0.88, "look": 2500, "aggro": 0.55, "line": 0.10},
    {"name": "HOYT",  "bike": "#F0E442", "suit": "#2E2416",
     "skill": 0.86, "nerve": 0.60, "look": 2300, "aggro": 0.30, "line": 0.34},
    {"name": "DIZZY", "bike": "#009E73", "suit": "#1B2E28",
     "skill": 0.46, "nerve": 0.68, "look": 1000, "aggro": 0.45, "line": -0.12},
    {"name": "KADE",  "bike": "#CC79A7", "suit": "#2A1B36",
     "skill": 0.71, "nerve": 0.82, "look": 1750, "aggro": 1.00, "line": 0.02},
]

CAR_COLOURS = ["#E8E2D4", "#5C6EDB", "#D8534F", "#3FAE8C", "#E0A93F", "#8A7FBE"]


def push_trace(trace, t, d):
    """Traces must be monotonic to read as timing: a rider losing ground on
    the standings has not travelled backwards."""
    trace.append((t, max(trace[-1][1], d) if trace else d))


def time_at_distance(trace, d):
    """When was this racer at distance ``d``? Linear interpolation.

    A gap to the leader is then "how long ago was the leader here", which is
    exactly what a timing screen reports at a real finish.
    """
    if not trace or len(trace) < 2:
        return None
    if d <= trace[0][1]:
        return trace[0][0]
    for i in range(1, len(trace)):
        if trace[i][1] >= d:
            (t0, d0), (t1, d1) = trace[i - 1], trace[i]
            span = d1 - d0
            return t1 if span <= 0 else t0 + (t1 - t0) * ((d - d0) / span)
    return None


def fastest_km(trace):
    """The quickest kilometre anyone strung together — the fastest-lap analogue."""
    if not trace or len(trace) < 2:
        return None
    best = math.inf
    j = 1
    n = len(trace)
    for i in range(n):
        if j < i + 1:
            j = i + 1
        while j < n and trace[j][1] - trace[i][1] < KM:
            j += 1
        if j >= n:
            break
        span = trace[j][0] - trace[i][0]
        if span < best:
            best = span
    return None if best is math.inf else best


class Car:
    """Traffic. Moves, gets hit, and is dodged."""

    kind = "car"

    def __init__(self, rng, track):
        oncoming = rng() < 0.42
        self.oncoming = oncoming
        self.z = rng() * track.length
        self.offset = (-1 if oncoming else 1) * (0.18 + rng() * 0.62)
        self.speed = ((-1 if oncoming else 1) * MAX_SPEED *
                      ((0.30 + rng() * 0.16) if oncoming else (0.22 + rng() * 0.28)))
        self.col = hexc(CAR_COLOURS[int(rng() * len(CAR_COLOURS))])
        self.w = 0.44
        self.near = False

    def update(self, dt, game):
        self.z = (self.z + self.speed * dt) % game.track.length


class Rider:
    """A rival.

    They are not on rails. Each only reads the road as far ahead as their own
    look-ahead, fights the same centrifugal force the player does, hits the
    same traffic, and pays the same price for running wide. Mistakes are
    emergent: carry more speed into a corner than your skill supports and the
    corner throws you off the outside.
    """

    kind = "rider"

    def __init__(self, spec, index, rng, track, player_pos, ai_bump):
        def jitter():
            return rng() * 2 - 1

        self.name = spec["name"]
        self.bike = hexc(spec["bike"])
        self.suit = hexc(spec["suit"])
        self.skill = clamp(spec["skill"] + ai_bump + jitter() * 0.07, 0.30, 0.97)
        self.nerve = clamp(spec["nerve"] + jitter() * 0.07, 0.35, 1.00)
        self.look = spec["look"] * (1 + jitter() * 0.15)
        self.aggro = clamp(spec["aggro"] + jitter() * 0.10, 0.15, 1.00)
        self.line = spec["line"] + jitter() * 0.10

        lead = 3400 + index * 2400
        self.dist = float(lead)
        self.z = (player_pos + lead) % track.length
        self.offset = self.line
        self.speed = MAX_SPEED * (0.62 + rng() * 0.14)

        self.steer_v = 0.0
        self.stagger = 0.0
        self.stagger_dir = 1
        self.swing = 0.0
        self.swing_side = 1
        self.tell = 0.0
        self.tell_side = 1
        self.knock = 0.0
        self.knock_tag = 0.0
        self.off_time = 0.0
        self.hit_cd = 0.0
        self.wobble = 0.0
        self.fight = 0.0
        self.cd = 2.5 + rng() * 3
        self.drift = rng() * math.pi * 2
        self.lean = 0.0
        self.prev_offset = self.offset
        self.ahead = True
        self.pass_cd = 0.0
        self.trace = []
        self.top_speed = 0.0

    def update(self, dt, game):
        track = game.track
        player_pos = game.pos + game.PLAYER_Z
        d = track.rel_z(self.z - player_pos)
        spd = self.speed / MAX_SPEED
        racing = game.phase == "playing" and game.mode != "zen"

        here = track.find(self.z)
        ahead_seg = track.find((self.z + self.look) % track.length)
        curve_now = here.curve
        curve_seen = ahead_seg.curve

        # --- pace, in three layers -------------------------------------
        if self.fight > 0:
            self.fight -= dt
        nerve_now = min(1.05, self.nerve + (0.30 if self.fight > 0 else 0.0))
        far = 0.0
        target = MAX_SPEED * (0.70 + nerve_now * 0.30)

        drafting = -5200 < d < 0 and abs(self.offset - game.player_x) < 0.60
        if drafting:
            target *= 1.10

        if d > 16000:
            target = min(target, max(MAX_SPEED * 0.55, game.speed * 0.92))
        elif d < -9000:
            far = clamp((-d - 9000) / 36000, 0, 1)
            ceil = MAX_SPEED * (1.06 + far * 0.34)
            target = max(target, min(ceil, game.speed * (1.12 + far * 0.44) + 500))

        # A corner speed limit should only exist where there is a corner.
        limit = (MAX_SPEED * (0.92 + self.skill * 0.14)
                 / (1 + abs(curve_seen) * 0.13 * (1.6 - self.skill)))
        if far > 0:
            limit *= 1.12 + far * 0.60
        if self.fight > 0:
            limit *= 1.10
        if target > limit:
            target = lerp(target, limit, self.skill)

        if self.knock > 0:
            self.knock -= dt
            target *= 0.55
        if self.off_time > 0:
            target *= 0.60
        if self.hit_cd > 0:
            self.hit_cd -= dt

        self.speed += (target - self.speed) * clamp(dt * 1.15, 0, 1)
        self.speed = clamp(self.speed, MAX_SPEED * 0.22, MAX_SPEED * (1.06 + far * 0.36))
        if far <= 0 and self.speed > self.top_speed:
            self.top_speed = self.speed

        # --- traffic: dodge what they see, wear what they do not --------
        dodge = 0.0
        for c in game.cars:
            cz = track.rel_z(c.z - self.z)
            lat = c.offset - self.offset
            if 0 < cz < self.look * 0.75 and abs(lat) < 0.34:
                dodge -= (1 if lat >= 0 else -1) * (1 - cz / (self.look * 0.75)) * self.skill
            if self.hit_cd <= 0 and abs(cz) < 340 and abs(lat) < 0.28:
                self.hit_cd = 1.1
                self.speed *= 0.60 if c.oncoming else 0.74
                self.stagger = 0.55
                self.stagger_dir = 1 if self.offset >= c.offset else -1
                self.wobble = 1.0
                self.dist -= 140

        # --- steering, with reaction lag --------------------------------
        self.drift += dt * 0.7
        if self.stagger > 0:
            self.stagger -= dt
            self.offset += self.stagger_dir * 1.5 * dt
        else:
            if abs(self.offset) > 0.95:
                want, react, authority = 0.0, 6.0, 2.1
            else:
                want = self.line + math.sin(self.drift) * 0.22 + clamp(dodge, -0.9, 0.9) * 0.55
                want += ((1 if curve_seen >= 0 else -1)
                         * min(0.50, abs(curve_seen) * 0.075) * self.skill)
                aggro_now = self.aggro * (1.6 if self.fight > 0 else 1.0)
                if abs(d) < 2100:
                    want += (game.player_x - self.offset) * 0.24 * aggro_now
                want = clamp(want, -0.92, 0.92)
                react = 1.1 + self.skill * 2.6
                authority = 1.9
            self.steer_v += (clamp(want - self.offset, -1, 1) - self.steer_v) * clamp(dt * react, 0, 1)
            self.offset += self.steer_v * dt * authority

        over = max(0.0, self.speed - limit) / MAX_SPEED
        self.offset -= (dt * 1.8 * spd * curve_now * CENTRIFUGAL
                        * (1.7 - self.skill) * (1 + over * 2.0))
        self.offset = clamp(self.offset, -1.40, 1.40)

        # --- running wide costs them ground -----------------------------
        if abs(self.offset) > 1.0:
            self.off_time += dt
            self.speed *= (1 - dt * 1.5)
            self.wobble = min(1.0, self.wobble + dt * 3)
            if self.off_time > 1.8:
                self.offset += (-1 if self.offset > 0 else 1) * dt * 1.8
        else:
            self.off_time = max(0.0, self.off_time - dt * 2)
        self.wobble = max(0.0, self.wobble - dt * 1.6)

        self.z = (self.z + self.speed * dt) % track.length
        self.dist += self.speed * dt

        # --- overtakes, hysteresis and a cooldown ------------------------
        if racing:
            if self.pass_cd > 0:
                self.pass_cd -= dt
            lead = self.dist - game.dist
            if self.ahead and lead < -900 and self.pass_cd <= 0:
                self.ahead = False
                self.pass_cd = 2.5
                self.fight = 7.5           # they have something to prove now
                game.overtakes += 1
                game.add_combo(1, "OVERTAKE · " + self.name, (255, 194, 74), PTS["overtake"])
            elif (not self.ahead) and lead > 900 and self.pass_cd <= 0:
                self.ahead = True
                self.pass_cd = 2.5
                game.passed_by += 1
                game.pop("PASSED BY " + self.name, (168, 150, 188))

            if self.knock_tag > 0:
                self.knock_tag -= dt
                if self.off_time > 0.2:
                    self.knock_tag = 0
                    game.knockdowns += 1
                    game.add_combo(1, "KNOCKDOWN · " + self.name, (255, 63, 107),
                                   PTS["knockdown"])

        self.lean = (clamp((self.offset - self.prev_offset) * 30, -1, 1)
                     + self.wobble * math.sin(game.frame * 0.9) * 0.5)
        self.prev_offset = self.offset
        if self.swing > 0:
            self.swing -= dt * 3.6

        # --- attacks: telegraphed, dodgeable, never fatal ----------------
        if racing:
            close = abs(d) < 620 and abs(self.offset - game.player_x) < 0.42
            if self.tell > 0:
                self.tell += dt * 2.4
                if self.tell >= 1:
                    self.tell = 0
                    self.cd = 3.2 + game.sim_rnd.random() * 3
                    if close and game.dazed <= 0:
                        game.clipped(1 if game.player_x >= self.offset else -1, self.name)
                    else:
                        self.swing = 1.0
                        self.swing_side = -1 if self.offset > game.player_x else 1
            else:
                self.cd -= dt
                if (self.cd <= 0 and close and self.stagger <= 0
                        and self.off_time <= 0 and self.wobble < 0.2):
                    self.tell = 0.01
                    self.tell_side = -1 if self.offset > game.player_x else 1

    @property
    def in_trouble(self):
        return self.knock > 0 or self.off_time > 0.15 or self.hit_cd > 0.5
