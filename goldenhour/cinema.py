"""The moving pictures behind the story beats.

Every beat is a painted scene that runs on a clock: the sky blends from one
time of night to the next, the moon sets, stars fade, ridgelines drift past
and the road keeps coming. It is the same vocabulary as the racing view —
gradient sky, layered ridges, a road in perspective — but driven by a beat
timer instead of by a bike, so a chapter can hand the player a sunrise
without anyone having to ride it.

Nothing in here reads game state. ``paint`` takes a spec and a time, which
makes the beats reproducible and cheap to preview.
"""
import math

import pygame

from .config import clamp, hexc, lerp, mix
from .track import Rng

# Six stops each, zenith first, horizon last, so any two palettes blend
# stop-for-stop without any matching logic.
SKIES = {
    "dusk": {
        "stops": ["#1B1038", "#3A1B54", "#6E2A5E", "#B8443F", "#E9743A", "#EFA168"],
        "sun": "#FFD27A", "stars": 50, "rise": 0.04, "warm": 0.85,
    },
    "night": {
        "stops": ["#05070F", "#0A0E22", "#131A38", "#1E2448", "#2C3059", "#43446B"],
        "sun": "#E6ECF8", "stars": 210, "rise": 0.52, "warm": 0.10,
    },
    "late": {
        "stops": ["#07060F", "#100E28", "#1E183A", "#2E1E46", "#41264E", "#563355"],
        "sun": "#DCE2F2", "stars": 190, "rise": 0.30, "warm": 0.18,
    },
    "predawn": {
        "stops": ["#0B1024", "#161F3E", "#293155", "#43456A", "#67566F", "#8B6A68"],
        "sun": "#FFE6C0", "stars": 95, "rise": -0.05, "warm": 0.45,
    },
    "dawn": {
        "stops": ["#11224A", "#254079", "#4E6FA6", "#94A0BE", "#E0A77E", "#FFD9A0"],
        "sun": "#FFF1C8", "stars": 0, "rise": 0.10, "warm": 1.00,
    },
}

INK = hexc("#0A0614")


def _stops(key):
    return [hexc(c) for c in SKIES[key]["stops"]]


class Cinema:
    """Paints one beat. Holds the caches; owns no state the caller can see."""

    def __init__(self):
        # Reduced motion keeps the sky's slow blend — that is the story —
        # and stills everything that moves for its own sake.
        self.reduced = False
        self._sky = None
        self._sky_key = None
        self._stars = None
        self._star_key = None
        self._layer = None
        self._layer_size = None

    # ---- pieces ----------------------------------------------------------
    def _sky_surface(self, w, h, a, b, u):
        """A six-stop vertical gradient, blended between two times of night.

        Painted at 96 pixels tall and scaled up: the gradient has no detail
        to lose and this costs a fraction of drawing every row.
        """
        key = (w, h, a, b, round(u * 40))
        if self._sky_key != key:
            ca, cb = _stops(a), _stops(b)
            cols = [mix(ca[i], cb[i], u) for i in range(len(ca))]
            n = 96
            strip = pygame.Surface((1, n))
            span = len(cols) - 1
            for y in range(n):
                f = y / (n - 1) * span
                i = min(span - 1, int(f))
                strip.set_at((0, y), mix(cols[i], cols[i + 1], f - i))
            self._sky = pygame.transform.smoothscale(strip, (w, h)).convert(24)
            self._sky_key = key
        return self._sky

    def _star_field(self, w, h):
        key = (w, h)
        if self._star_key != key:
            rng = Rng(0x5EED57A2)
            self._stars = [(rng() * w, rng() * h * 0.70,
                            1 + rng() * 1.6, rng() * math.tau)
                           for _ in range(150)]
            self._star_key = key
        return self._stars

    def _alpha_layer(self, w, h):
        if self._layer_size != (w, h):
            self._layer = pygame.Surface((w, h), pygame.SRCALPHA)
            self._layer_size = (w, h)
        return self._layer

    def _ridges(self, surf, w, h, horizon, base, warm, drift):
        """Three silhouettes, each nearer, darker and faster than the last."""
        for i, (amp, freq, lift, dark, speed) in enumerate((
                (0.085, 1.7, 0.010, 0.40, 0.10),
                (0.125, 1.1, 0.055, 0.62, 0.22),
                (0.180, 0.7, 0.115, 0.86, 0.42))):
            col = mix(base, INK, dark)
            col = mix(col, (255, 200, 150), warm * (0.10 - i * 0.03))
            off = drift * speed
            pts = [(w + 4, h), (-4, h)]
            steps = 34
            for s in range(steps + 1):
                x = -4 + (w + 8) * s / steps
                p = (x / w + off) * math.tau * freq
                y = (horizon + h * lift
                     - h * amp * (0.55 + 0.45 * math.sin(p)
                                  + 0.22 * math.sin(p * 2.3 + i)))
                pts.append((x, y))
            pygame.draw.polygon(surf, col, pts)

    def _sun(self, surf, w, h, horizon, col, rise, glow):
        """Sun or moon. ``rise`` is disc centres above the horizon, in
        fractions of the screen height; negative sits it below."""
        r = max(6, int(h * 0.085))
        cx = int(w * 0.62)
        cy = int(horizon - rise * h)
        if cy - r > h:
            return
        if glow > 0.01:
            layer = self._alpha_layer(w, h)
            layer.fill((0, 0, 0, 0))
            for i in range(7):
                a = int(30 * glow * (1 - i / 7))
                if a <= 1:
                    continue
                pygame.draw.circle(layer, (*col, a), (cx, cy), int(r * (1.3 + i * 0.55)))
            surf.blit(layer, (0, 0))
        pygame.draw.circle(surf, col, (cx, cy), r)
        pygame.draw.circle(surf, mix(col, (255, 255, 255), 0.45),
                           (cx, cy - r // 4), int(r * 0.55))

    def _road(self, surf, w, h, horizon, base, warm, scroll, moving=True):
        """A road in one-point perspective, with dashes that come at you."""
        far_w, near_w = w * 0.040, w * 0.92
        vy, by = horizon, h
        road = mix(base, INK, 0.72)
        road = mix(road, (60, 46, 70), 0.35)
        pygame.draw.polygon(surf, road, [
            (w / 2 - far_w / 2, vy), (w / 2 + far_w / 2, vy),
            (w / 2 + near_w / 2, by), (w / 2 - near_w / 2, by)])
        shoulder = mix(road, (255, 236, 210), 0.22 + warm * 0.18)
        for side in (-1, 1):
            pygame.draw.polygon(surf, shoulder, [
                (w / 2 + side * far_w * 0.54, vy),
                (w / 2 + side * far_w * 0.60, vy),
                (w / 2 + side * near_w * 0.56, by),
                (w / 2 + side * near_w * 0.50, by)])
        if not moving:
            return
        dash = mix((255, 241, 222), road, 0.30)
        for i in range(16):
            z = ((i / 16) + scroll) % 1.0
            z = z * z * z                      # perspective bunching near the top
            y0 = lerp(vy, by, z)
            # a dash is a length of road, so it stretches as it comes at you
            y1 = lerp(vy, by, min(1.0, z + 0.018 + 0.10 * z))
            if y1 - y0 < 1:
                continue
            t0 = (y0 - vy) / max(1.0, by - vy)
            t1 = (y1 - vy) / max(1.0, by - vy)
            wd0 = lerp(far_w, near_w, t0) * 0.011
            wd1 = lerp(far_w, near_w, t1) * 0.011
            pygame.draw.polygon(surf, dash, [
                (w / 2 - wd0, y0), (w / 2 + wd0, y0),
                (w / 2 + wd1, y1), (w / 2 - wd1, y1)])

    def _rider(self, surf, w, h, horizon, bob, headlight, warm):
        """The bike from behind, small against the road and clear of the text."""
        s = h * 0.0019
        cx = w / 2
        cy = h * 0.55 + bob * h * 0.005
        body = mix(INK, (40, 30, 60), 0.5)
        if headlight > 0.02:
            layer = self._alpha_layer(w, h)
            layer.fill((0, 0, 0, 0))
            # The beam is thrown in slices that fade with distance — one flat
            # polygon reads as a pane of glass leaning against the bike.
            y0, top = cy - 30 * s, horizon + h * 0.035
            slices = 9
            for i in range(slices):
                f0, f1 = i / slices, (i + 1) / slices
                a = int(34 * headlight * (1 - f0) ** 1.6)
                if a <= 1:
                    continue
                wa, wb = 7 * s + w * 0.052 * f0, 7 * s + w * 0.052 * f1
                ya, yb = lerp(y0, top, f0), lerp(y0, top, f1)
                pygame.draw.polygon(layer, (255, 236, 190, a), [
                    (cx - wa, ya), (cx + wa, ya), (cx + wb, yb), (cx - wb, yb)])
            surf.blit(layer, (0, 0))
        # shadow, wheels, bike, rider — flat shapes, read as a silhouette
        sh = self._alpha_layer(w, h)
        sh.fill((0, 0, 0, 0))
        pygame.draw.ellipse(sh, (0, 0, 0, 90),
                            pygame.Rect(cx - 46 * s, cy + 16 * s, 92 * s, 18 * s))
        surf.blit(sh, (0, 0))
        pygame.draw.rect(surf, body, pygame.Rect(cx - 9 * s, cy - 6 * s, 18 * s, 30 * s),
                         border_radius=int(max(1, 5 * s)))
        pygame.draw.rect(surf, mix(body, (255, 122, 60), 0.55),
                         pygame.Rect(cx - 22 * s, cy - 40 * s, 44 * s, 34 * s),
                         border_radius=int(max(1, 8 * s)))
        pygame.draw.circle(surf, mix(body, (255, 241, 222), 0.10 + warm * 0.10),
                           (int(cx), int(cy - 52 * s)), int(15 * s))
        for side in (-1, 1):
            pygame.draw.rect(surf, body,
                             pygame.Rect(cx + side * 30 * s - 6 * s, cy - 42 * s,
                                         12 * s, 26 * s),
                             border_radius=int(max(1, 4 * s)))

    def _overlook(self, surf, w, h, horizon, warm, t):
        """The last beat: the bike on its stand, the rider at the edge.

        Both are silhouettes with one warm edge — everything here is backlit
        by the thing they came to see, so the light does the describing.
        """
        s = h * 0.0024
        ground = mix(INK, (60, 44, 60), 0.55)
        pygame.draw.polygon(surf, ground, [
            (0, h * 0.545), (w * 0.24, h * 0.515), (w * 0.62, h * 0.535),
            (w, h * 0.565), (w, h), (0, h)])
        pygame.draw.polygon(surf, mix(ground, INK, 0.45), [
            (0, h * 0.60), (w * 0.35, h * 0.578), (w, h * 0.612), (w, h), (0, h)])

        body = mix(INK, (36, 28, 54), 0.6)
        rim = mix((255, 214, 160), (255, 255, 255), 0.15)
        lit = max(0.0, warm - 0.25)

        # ---- the bike, side on, front to the left ----------------------
        gx, gy = w * 0.30, h * 0.575
        for dx in (-26, 26):
            pygame.draw.circle(surf, body, (int(gx + dx * s), int(gy)), int(13 * s))
            pygame.draw.circle(surf, mix(body, rim, 0.25 * lit),
                               (int(gx + dx * s), int(gy)), int(13 * s), max(1, int(2 * s)))
        pygame.draw.polygon(surf, body, [                      # frame and seat
            (gx - 22 * s, gy - 10 * s), (gx + 2 * s, gy - 20 * s),
            (gx + 26 * s, gy - 17 * s), (gx + 28 * s, gy - 9 * s),
            (gx + 6 * s, gy - 5 * s)])
        pygame.draw.polygon(surf, mix(body, (255, 122, 60), 0.55), [   # tank
            (gx - 12 * s, gy - 19 * s), (gx + 6 * s, gy - 24 * s),
            (gx + 14 * s, gy - 19 * s), (gx + 2 * s, gy - 15 * s)])
        pygame.draw.line(surf, body, (gx - 26 * s, gy),
                         (gx - 18 * s, gy - 26 * s), max(1, int(3 * s)))   # fork
        pygame.draw.line(surf, body, (gx - 24 * s, gy - 26 * s),
                         (gx - 10 * s, gy - 28 * s), max(1, int(3 * s)))   # bar
        pygame.draw.circle(surf, mix(body, rim, 0.55 * lit),
                           (int(gx - 24 * s), int(gy - 21 * s)), int(4 * s))
        pygame.draw.line(surf, mix(body, rim, 0.30 * lit),
                         (gx + 6 * s, gy - 24 * s), (gx + 26 * s, gy - 17 * s),
                         max(1, int(2 * s)))

        # ---- the rider, back to us -------------------------------------
        rx, ry = w * 0.56, h * 0.583
        sway = math.sin(t * 0.6) * s * 0.8
        for dx in (-5, 4):
            pygame.draw.rect(surf, body,
                             pygame.Rect(rx + dx * s, ry - 17 * s, 5 * s, 17 * s))
        torso = pygame.Rect(rx - 9 * s + sway, ry - 44 * s, 18 * s, 29 * s)
        pygame.draw.rect(surf, body, torso, border_radius=int(max(1, 5 * s)))
        for dx in (-12, 9):                                     # arms
            pygame.draw.rect(surf, body,
                             pygame.Rect(rx + dx * s + sway, ry - 41 * s, 4 * s, 20 * s),
                             border_radius=int(max(1, 2 * s)))
        pygame.draw.rect(surf, body,                            # neck
                         pygame.Rect(rx - 3 * s + sway, ry - 48 * s, 6 * s, 6 * s))
        head = (int(rx + sway), int(ry - 53 * s))
        pygame.draw.circle(surf, mix(body, (90, 70, 60), 0.35), head, int(8 * s))
        if lit > 0.01:
            # The sun is off to the right, so that is the edge that catches —
            # a thin line on the outside of the silhouette, not a stripe
            # painted across it.
            edge = mix(body, rim, min(1.0, 0.55 * lit))
            pygame.draw.arc(surf, edge,
                            pygame.Rect(head[0] - 8 * s, head[1] - 8 * s,
                                        16 * s, 16 * s),
                            -1.0, 1.0, max(1, int(1.4 * s)))
            arm_x = rx + 13 * s + sway
            pygame.draw.line(surf, edge, (arm_x, ry - 40 * s), (arm_x, ry - 22 * s),
                             max(1, int(1.4 * s)))

    def _birds(self, surf, w, h, horizon, t, warm):
        if warm < 0.5:
            return
        col = mix(INK, (90, 70, 90), 0.5)
        for i in range(5):
            p = (t * 0.045 + i * 0.21) % 1.4 - 0.2
            x = w * p
            y = horizon - h * (0.16 + 0.045 * math.sin(t * 0.9 + i))
            flap = math.sin(t * 5.2 + i * 1.3) * h * 0.006
            sz = h * 0.010
            pygame.draw.lines(surf, col, False,
                              [(x - sz, y - flap), (x, y), (x + sz, y - flap)],
                              max(1, int(h * 0.0028)))

    # ---- the beat --------------------------------------------------------
    def paint(self, surf, w, h, spec, t):
        """Draw one frame of a beat.

        ``spec`` carries the two times of night to blend between, the length
        of the blend, and which scene to stage. ``t`` is seconds since the
        beat opened.
        """
        a = spec.get("from", spec.get("sky", "night"))
        b = spec.get("to", a)
        dur = max(0.5, spec.get("blend", 9.0))
        u = clamp(t / dur, 0.0, 1.0)
        u = u * u * (3 - 2 * u)                    # ease, so nothing snaps
        pa, pb = SKIES[a], SKIES[b]

        horizon = h * spec.get("horizon", 0.40)
        surf.blit(self._sky_surface(w, h, a, b, u), (0, 0))

        stars = lerp(pa["stars"], pb["stars"], u)
        if stars > 2:
            layer = self._alpha_layer(w, h)
            layer.fill((0, 0, 0, 0))
            for x, y, r, ph in self._star_field(w, h):
                if y > horizon - h * 0.04:
                    continue
                tw = 1.0 if self.reduced else 0.65 + 0.35 * math.sin(t * 1.7 + ph)
                pygame.draw.circle(layer, (255, 248, 232, int(stars * tw)),
                                   (int(x), int(y)), int(r))
            surf.blit(layer, (0, 0))

        warm = lerp(pa["warm"], pb["warm"], u)
        rise = lerp(pa["rise"], pb["rise"], u)
        if "rise" in spec:
            rise = lerp(spec["rise"][0], spec["rise"][1], u)
        sun_col = mix(hexc(pa["sun"]), hexc(pb["sun"]), u)
        horizon_col = mix(_stops(a)[-1], _stops(b)[-1], u)
        self._sun(surf, w, h, horizon, sun_col, rise, 0.35 + warm * 0.65)

        drift = spec.get("drift", 0.0) + (0.0 if self.reduced else t * 0.004)
        self._ridges(surf, w, h, horizon, horizon_col, warm, drift)
        if not self.reduced:
            self._birds(surf, w, h, horizon, t, warm)

        scene = spec.get("scene", "ride")
        if scene == "overlook":
            self._overlook(surf, w, h, horizon, warm, 0.0 if self.reduced else t)
        else:
            self._road(surf, w, h, horizon, horizon_col, warm,
                       0.4 if self.reduced else (t * 0.55) % 1.0,
                       moving=True)
            self._rider(surf, w, h, horizon,
                        0.0 if self.reduced else math.sin(t * 3.1), 1.0 - warm, warm)
