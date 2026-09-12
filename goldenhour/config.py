"""Constants shared across the game.

World units are arbitrary; ``U_PER_M`` pins them to metres so speed, gaps and
split times all agree with the km/h shown on the HUD.
"""
import math

# ---- road geometry -------------------------------------------------------
SEG_LEN = 200
RUMBLE = 3
ROAD_W = 2200
LANES = 3
DRAW_DIST = 420
CAM_H = 1380
FOV = 92
CAM_DEPTH = 1.0 / math.tan(math.radians(FOV / 2))
PLAYER_Z = CAM_H * CAM_DEPTH

# ---- movement ------------------------------------------------------------
MAX_SPEED = SEG_LEN * 60
ACCEL = MAX_SPEED / 4.2
BRAKE = -MAX_SPEED / 1.1
DECEL = -MAX_SPEED / 6
OFF_DECEL = -MAX_SPEED / 1.6
OFF_LIMIT = MAX_SPEED / 3.4
CENTRIFUGAL = 0.32

# ---- run ------------------------------------------------------------------
SONG_LEN = 100.0
U_PER_M = 210.0
KM = 1000 * U_PER_M
FOG_STEPS = 22

# ---- scoring --------------------------------------------------------------
PTS = {
    "hit": 130,
    "knockdown": 260,
    "near": 70,
    "air": 60,
    "overtake": 180,
    "corner": 90,
    "clean": 800,
    "perfect": 2500,
}

# ---- difficulty -----------------------------------------------------------
# The edge value is how much better than their baseline the rivals ride: it
# lifts
# cornering skill, nerve and appetite for a fight together, so a harder race
# is a field of better riders rather than a field with more horsepower.
DIFFICULTIES = [
    ("steady",   "Steady",   1.00),
    ("racer",    "Racer",    1.16),
    ("ruthless", "Ruthless", 1.32),
]
DEFAULT_DIFFICULTY = "racer"


def difficulty_edge(ident):
    for key, _name, edge in DIFFICULTIES:
        if key == ident:
            return edge
    return 1.0


def difficulty_name(ident):
    for key, name, _edge in DIFFICULTIES:
        if key == ident:
            return name
    return "Racer"


# ---- window ---------------------------------------------------------------
WIN_W, WIN_H = 1000, 640
FPS = 60

# ---- palette used by the interface chrome ---------------------------------
INK = (18, 10, 34)
INK2 = (28, 17, 52)
CREAM = (255, 241, 222)
MUTED = (168, 150, 188)
HOT = (255, 63, 107)
SUN = (255, 194, 74)
EMBER = (255, 122, 60)
MINT = (87, 227, 180)
LINE = (52, 40, 74)


def hexc(h):
    """'#RRGGBB' -> (r, g, b)."""
    h = h.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def mix(a, b, t):
    """Blend two RGB tuples. ``t`` of 0 returns ``a``, 1 returns ``b``."""
    if t <= 0:
        return a
    if t >= 1:
        return b
    return (
        int(a[0] + (b[0] - a[0]) * t),
        int(a[1] + (b[1] - a[1]) * t),
        int(a[2] + (b[2] - a[2]) * t),
    )


def shade(c, amt):
    """Lighten (amt > 0) or darken (amt < 0) an RGB tuple."""
    if amt > 0:
        return tuple(min(255, int(v + (255 - v) * amt)) for v in c)
    return tuple(max(0, int(v * (1 + amt))) for v in c)


def clamp(v, lo, hi):
    return lo if v < lo else (hi if v > hi else v)


def lerp(a, b, t):
    return a + (b - a) * t
