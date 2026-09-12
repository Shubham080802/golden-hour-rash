"""Segment-based pseudo-3D rendering.

The road is a list of segments projected to screen space every frame — the
technique OutRun and Road Rash used, with no real geometry anywhere.

Two things differ from the browser build. Canvas has gradients; pygame does
not, so the sky is pre-rendered to a cached surface and vehicle shading is
approximated with flat bands. Canvas fades distant sprites with alpha; here
they are mixed toward the horizon colour instead, which costs nothing and
reads the same.
"""
import math
import random

import pygame

from .config import CAM_DEPTH, FOG_STEPS, LANES, ROAD_W, clamp, mix, shade
from .locales import LOCALES


def project(p, cam_x, cam_y, cam_z, w, h):
    p["cz"] = p["wz"] - cam_z
    if p["cz"] < 1:
        p["cz"] = 1
    sc = CAM_DEPTH / p["cz"]
    p["x"] = (w / 2) + (sc * (-cam_x) * w / 2)
    p["y"] = (h / 2) - (sc * (p["wy"] - cam_y) * h / 2)
    p["w"] = sc * ROAD_W * w / 2


class Renderer:
    def __init__(self, fonts):
        self.fonts = fonts
        self._sky = None
        self._sky_key = None
        self._vig = None
        self._vig_key = None
        self._bloom = {}
        self._clouds = None
        self._air = None
        self._flash = None
        self._stars_cache = None
        self._stars_surf = None
        self._star_t = 0
        self._fog = {}
        self.bg_x = 0.0
        self.smooth_slope = 0.0

    # ---- cached surfaces ------------------------------------------------
    def fog_table(self, loc_id):
        """Depth fog baked into the road's own colours, so the road recedes
        because it is far away rather than hiding behind a curtain."""
        tbl = self._fog.get(loc_id)
        if tbl:
            return tbl
        loc = LOCALES[loc_id]
        horizon = loc["horizon"]
        tbl = []
        for i in range(FOG_STEPS):
            t = (i / (FOG_STEPS - 1)) ** 1.5 * 0.90
            entry = {}
            for band in ("light", "dark"):
                src = loc[band]
                entry[band] = {k: (None if v is None else mix(v, horizon, t))
                               for k, v in src.items()}
            tbl.append(entry)
        self._fog[loc_id] = tbl
        return tbl

    def sky(self, loc_id, w, h):
        key = (loc_id, w, h)
        if self._sky_key == key:
            return self._sky
        loc = LOCALES[loc_id]
        stops = loc["sky_stops"]
        strip = pygame.Surface((1, h))
        for y in range(h):
            u = y / max(1, h - 1)
            c = stops[-1][1]
            for i in range(len(stops) - 1):
                a, b = stops[i], stops[i + 1]
                if a[0] <= u <= b[0]:
                    span = b[0] - a[0] or 1
                    c = mix(a[1], b[1], (u - a[0]) / span)
                    break
            strip.set_at((0, y), c)
        self._sky = pygame.transform.scale(strip, (w, h))
        self._sky_key = key
        return self._sky

    def flash_layer(self, w, h):
        if self._flash is None or self._flash.get_size() != (w, h):
            self._flash = pygame.Surface((w, h), pygame.SRCALPHA)
        return self._flash

    def air_layer(self, w, h):
        """Scratch alpha surface reused each frame — allocating one per frame
        at scene resolution is not free."""
        if self._air is None or self._air.get_size() != (w, h):
            self._air = pygame.Surface((w, h), pygame.SRCALPHA)
        return self._air

    def _cloud_layer(self, w, h):
        if self._clouds is None or self._clouds.get_size() != (w, h):
            self._clouds = pygame.Surface((w, h), pygame.SRCALPHA)
        return self._clouds

    def vignette(self, w, h):
        key = (w, h)
        if self._vig_key == key:
            return self._vig
        # A vignette darkens the EDGES. pygame.draw overwrites alpha rather
        # than blending it, so: flood the surface at full strength, then lay
        # successively smaller and fainter discs over it. Each pixel ends up
        # with the alpha of the smallest disc that covers it, which falls to
        # nothing in the middle and leaves the corners at full strength.
        peak = 96
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        surf.fill((8, 4, 16, peak))
        cx, cy = w // 2, int(h * 0.56)
        maxr = math.hypot(w, h) * 0.62
        steps = 26
        for i in range(steps):
            r = maxr * (1 - i / steps)
            a = int(peak * (r / maxr) ** 2.2)
            pygame.draw.circle(surf, (8, 4, 16, a), (cx, cy), int(r))
        self._vig = surf
        self._vig_key = key
        return surf

    # ---- sky ------------------------------------------------------------
    def draw_sky(self, surf, loc_id, horizon, w, h, beat, zen):
        loc = LOCALES[loc_id]
        surf.blit(self.sky(loc_id, w, h), (0, 0))

        zenith = loc["sky_stops"][0][1]
        if sum(zenith) < 190:
            self._stars(surf, w, h, horizon, sum(zenith))

        sun_r = int(h * 0.115 * (1 + beat * 0.03))
        sx = int(w * 0.5 - self.bg_x * 0.30)
        sy = int(horizon - sun_r * 1.45)

        pygame.draw.circle(surf, loc["sun"], (sx, sy), sun_r)
        pygame.draw.circle(surf, shade(loc["sun"], 0.45), (sx, sy - sun_r // 5),
                           int(sun_r * 0.55))

        # stratus bands catching the last light, drawn translucently on their
        # own layer so they read as haze rather than as cut-out shapes
        layer = self._cloud_layer(w, h)
        layer.fill((0, 0, 0, 0))
        hi = mix(loc["cloud_lo"], loc["cloud_hi"], 0.65)
        for i in range(9):
            cy = horizon - h * (0.085 + i * 0.042)
            cw = w * (0.30 + ((i * 53) % 46) / 100)
            cx = ((i * 263 + self.bg_x * 0.22) % (w * 1.9)) - w * 0.45
            alpha = int(64 - i * 5)
            if alpha <= 4:
                continue
            for band, squash in ((0.026, 1.0), (0.014, 0.72)):
                rect = pygame.Rect(int(cx + cw * (1 - squash) / 2), int(cy - h * band / 2),
                                   int(cw * squash), max(2, int(h * band)))
                pygame.draw.ellipse(layer, (*hi, alpha), rect)
        surf.blit(layer, (0, 0))

        # five ridgelines, each hazier and slower-parallaxing than the last
        self._ridge(surf, loc["ridge_far"], loc["horizon"], horizon, 0.76, 0.16,
                    h * 0.190, 0.7, 130, w, snow=loc.get("snow"))
        self._ridge(surf, loc["ridge_far"], loc["horizon"], horizon, 0.62, 0.30,
                    h * 0.150, 1.0, 0, w, snow=loc.get("snow"))
        self._ridge(surf, loc["ridge_far"], loc["horizon"], horizon, 0.44, 0.46,
                    h * 0.126, 1.35, 260, w)
        self._ridge(surf, loc["ridge_far"], loc["horizon"], horizon, 0.28, 0.62,
                    h * 0.104, 1.7, 430, w)
        self._ridge(surf, loc["ridge_near"], loc["horizon"], horizon, 0.12, 1.05,
                    h * 0.064, 2.8, 910, w)



    def _stars(self, surf, w, h, horizon, darkness):
        """Fixed field, faint, only in the part of the sky dark enough to hold
        them. Twinkle comes from the frame counter, not from a random call."""
        if self._stars_cache is None or self._stars_cache[0] != (w, h):
            rng = random.Random(99)
            pts = [(rng.random(), rng.random(), rng.random()) for _ in range(90)]
            self._stars_cache = ((w, h), pts)
        self._star_t += 1
        top = max(0.0, 1.0 - darkness / 190.0)
        # the scene has no alpha channel, so faint stars need a layer of their
        # own — drawn straight onto it, every one came out fully opaque
        layer = self._star_layer(w, h)
        layer.fill((0, 0, 0, 0))
        for i, (fx, fy, mag) in enumerate(self._stars_cache[1]):
            y = fy * horizon * 0.62
            a = int(30 + 120 * mag * top * (0.75 + 0.25 * math.sin(self._star_t * 0.05 + i)))
            if a < 8:
                continue
            r = 1 if mag < 0.8 else 2
            pygame.draw.circle(layer, (255, 250, 236, a), (int(fx * w), int(y)), r)
        surf.blit(layer, (0, 0))

    def _star_layer(self, w, h):
        if self._stars_surf is None or self._stars_surf.get_size() != (w, h):
            self._stars_surf = pygame.Surface((w, h), pygame.SRCALPHA)
        return self._stars_surf

    def _sample_sky(self, loc, u):
        stops = loc["sky_stops"]
        u = clamp(u, 0, 1)
        for i in range(len(stops) - 1):
            a, b = stops[i], stops[i + 1]
            if a[0] <= u <= b[0]:
                span = b[0] - a[0] or 1
                return mix(a[1], b[1], (u - a[0]) / span)
        return stops[-1][1]

    def _ridge(self, surf, base, horizon_col, hy, fog_t, par, amp, freq, phase, w,
               snow=None):
        col = mix(base, horizon_col, fog_t)
        pts = [(0, hy + 2)]
        ridge = []
        off = self.bg_x * par + phase
        x = 0
        while x <= w:
            u = (x + off) / w
            y = hy - amp * (0.44
                            + 0.30 * math.sin(u * freq * 5.1)
                            + 0.16 * math.sin(u * freq * 11.3 + 1.7)
                            + 0.09 * math.sin(u * freq * 23.7 + 3.1))
            pts.append((x, y))
            ridge.append((x, y))
            x += 9
        pts.append((w, hy + 2))
        pygame.draw.polygon(surf, col, pts)

        if snow:
            # cap the peaks: anywhere the ridge climbs past a threshold gets a
            # small wedge of snow, so a mountain reads as a mountain
            line = hy - amp * 0.78
            cap = mix(snow, horizon_col, fog_t * 0.55)
            for i in range(1, len(ridge) - 1):
                x0, y0 = ridge[i]
                if y0 < line and ridge[i - 1][1] >= y0 <= ridge[i + 1][1]:
                    drop = min(amp * 0.26, line - y0 + amp * 0.10)
                    pygame.draw.polygon(surf, cap, [
                        (x0, y0), (x0 + drop * 0.9, y0 + drop),
                        (x0 + drop * 0.25, y0 + drop * 0.72),
                        (x0 - drop * 0.35, y0 + drop),
                        (x0 - drop * 0.9, y0 + drop)])

    # ---- road -----------------------------------------------------------
    def draw_segment(self, surf, seg, c, near, w, lanes_on, rails_on):
        p1, p2 = seg.p1, seg.p2
        y1, y2 = p1["y"], p2["y"]
        pygame.draw.rect(surf, c["grass"], pygame.Rect(0, int(y2), w, int(y1 - y2) + 1))

        r1, r2 = p1["w"] / 11, p2["w"] / 11
        poly = pygame.draw.polygon
        poly(surf, c["rumble"], [(p1["x"] - p1["w"] - r1, y1), (p1["x"] - p1["w"], y1),
                                 (p2["x"] - p2["w"], y2), (p2["x"] - p2["w"] - r2, y2)])
        poly(surf, c["rumble"], [(p1["x"] + p1["w"] + r1, y1), (p1["x"] + p1["w"], y1),
                                 (p2["x"] + p2["w"], y2), (p2["x"] + p2["w"] + r2, y2)])
        poly(surf, c["road"], [(p1["x"] - p1["w"], y1), (p1["x"] + p1["w"], y1),
                               (p2["x"] + p2["w"], y2), (p2["x"] - p2["w"], y2)])

        if near:
            t, tw = 0.36, 0.19
            for s in (-1, 1):
                poly(surf, c["trackw"],
                     [(p1["x"] + p1["w"] * (s * t - tw), y1), (p1["x"] + p1["w"] * (s * t + tw), y1),
                      (p2["x"] + p2["w"] * (s * t + tw), y2), (p2["x"] + p2["w"] * (s * t - tw), y2)])
            e1, e2 = p1["w"] * 0.028, p2["w"] * 0.028
            poly(surf, c["edge"], [(p1["x"] - p1["w"] + e1, y1), (p1["x"] - p1["w"] + e1 * 3, y1),
                                   (p2["x"] - p2["w"] + e2 * 3, y2), (p2["x"] - p2["w"] + e2, y2)])
            poly(surf, c["edge"], [(p1["x"] + p1["w"] - e1 * 3, y1), (p1["x"] + p1["w"] - e1, y1),
                                   (p2["x"] + p2["w"] - e2, y2), (p2["x"] + p2["w"] - e2 * 3, y2)])

        if lanes_on and c["lane"]:
            l1, l2 = p1["w"] * 2 / LANES / 34, p2["w"] * 2 / LANES / 34
            lw1, lw2 = p1["w"] * 2 / LANES, p2["w"] * 2 / LANES
            lx1, lx2 = p1["x"] - p1["w"] + lw1, p2["x"] - p2["w"] + lw2
            for _ in range(LANES - 1):
                poly(surf, c["lane"], [(lx1 - l1, y1), (lx1 + l1, y1),
                                       (lx2 + l2, y2), (lx2 - l2, y2)])
                lx1 += lw1
                lx2 += lw2

        if rails_on:
            g1, g2 = p1["w"] * 0.10, p2["w"] * 0.10
            h1, h2 = p1["w"] * 0.052, p2["w"] * 0.052
            for s in (-1, 1):
                x1 = p1["x"] + s * (p1["w"] + g1)
                x2 = p2["x"] + s * (p2["w"] + g2)
                poly(surf, c["rail"], [(x1, y1 - h1), (x1, y1 - h1 * 0.42),
                                       (x2, y2 - h2 * 0.42), (x2, y2 - h2)])

    # ---- sprites ---------------------------------------------------------
    # ---- sprites ---------------------------------------------------------
    # Everything is still drawn from primitives, but built as the real object
    # is built — a motorcycle has a swingarm, cans and a tail unit; a car has
    # a rake to its rear screen and arches over its wheels. Detail is dropped
    # by on-screen size, so the twenty machines in the distance stay cheap.

    def draw_car(self, surf, x, base_y, w, col, oncoming):
        h = w * 0.70
        rr = pygame.draw.rect
        poly = pygame.draw.polygon
        dark = shade(col, -0.45)
        mid = shade(col, -0.16)
        top = shade(col, 0.16)

        # contact shadow, wider than the car and squashed
        pygame.draw.ellipse(surf, (12, 7, 20),
                            pygame.Rect(x - w * 0.62, base_y - h * 0.10, w * 1.24, h * 0.26))

        if w < 14:                                   # far away: a lit block
            rr(surf, mid, pygame.Rect(x - w / 2, base_y - h * 0.8, w, h * 0.8),
               border_radius=max(1, int(w * 0.12)))
            lc = (255, 246, 216) if oncoming else (255, 74, 85)
            rr(surf, lc, pygame.Rect(x - w * 0.40, base_y - h * 0.45, w * 0.22, h * 0.14))
            rr(surf, lc, pygame.Rect(x + w * 0.18, base_y - h * 0.45, w * 0.22, h * 0.14))
            return

        # wheels, tucked under the arches
        for sx in (-1, 1):
            rr(surf, (14, 10, 20),
               pygame.Rect(x + sx * w * 0.40 - w * 0.06, base_y - h * 0.26, w * 0.12, h * 0.26),
               border_radius=max(1, int(w * 0.03)))

        roof_y = base_y - h
        belt_y = base_y - h * 0.52          # window line
        sill_y = base_y - h * 0.30

        # greenhouse: roof narrower than the body, rear screen raked
        poly(surf, top, [(x - w * 0.30, belt_y), (x + w * 0.30, belt_y),
                         (x + w * 0.23, roof_y), (x - w * 0.23, roof_y)])
        glass_hi = (196, 214, 232) if oncoming else (52, 36, 74)
        glass_lo = (120, 132, 158) if oncoming else (22, 14, 38)
        poly(surf, glass_hi, [(x - w * 0.255, belt_y - h * 0.03),
                              (x + w * 0.255, belt_y - h * 0.03),
                              (x + w * 0.20, roof_y + h * 0.04),
                              (x - w * 0.20, roof_y + h * 0.04)])
        poly(surf, glass_lo, [(x - w * 0.255, belt_y - h * 0.03),
                              (x + w * 0.255, belt_y - h * 0.03),
                              (x + w * 0.225, belt_y - h * 0.14),
                              (x - w * 0.225, belt_y - h * 0.14)])

        # body: shoulder above the belt line, bumper below the sill
        poly(surf, mid, [(x - w * 0.48, sill_y), (x + w * 0.48, sill_y),
                         (x + w * 0.44, belt_y), (x - w * 0.44, belt_y)])
        poly(surf, dark, [(x - w * 0.50, base_y - h * 0.10), (x + w * 0.50, base_y - h * 0.10),
                          (x + w * 0.48, sill_y), (x - w * 0.48, sill_y)])
        # boot lid catching the light
        rr(surf, shade(col, 0.05),
           pygame.Rect(x - w * 0.42, belt_y - h * 0.02, w * 0.84, h * 0.06))

        # lamps
        ly, lw, lh = sill_y + h * 0.04, w * 0.24, h * 0.11
        lc = (255, 246, 216) if oncoming else (255, 62, 74)
        for sx in (-1, 1):
            box = pygame.Rect(x + (0.44 * sx - (0.24 if sx > 0 else 0)) * w, ly, lw, lh)
            rr(surf, shade(lc, -0.55), box, border_radius=max(1, int(w * 0.02)))
            rr(surf, lc, box.inflate(-w * 0.04, -h * 0.03),
               border_radius=max(1, int(w * 0.02)))
        # plate and pipe
        rr(surf, (222, 216, 198), pygame.Rect(x - w * 0.12, ly + h * 0.02, w * 0.24, h * 0.07))
        if not oncoming:
            rr(surf, (40, 34, 46),
               pygame.Rect(x + w * 0.26, base_y - h * 0.12, w * 0.09, h * 0.05))
        if w > 26:                                   # rim light along the top
            pygame.draw.line(surf, (255, 214, 160), (x - w * 0.21, roof_y + 1),
                             (x + w * 0.21, roof_y + 1), max(1, int(w * 0.018)))

    # ---- motorcycle + rider ----------------------------------------------
    def draw_rider(self, surf, x, base_y, w, bike, suit, lean=0.0, swing=0.0,
                   swing_side=1, tell=0.0, tell_side=1):
        """Seen from behind: wheel, swingarm, cans, tail unit, then a rider
        sitting *in* the machine with legs on the pegs and arms out to the
        bars. Lean shears the whole stack about the contact patch."""
        h = w * 1.40
        k = lean * 0.30 * h                 # horizontal travel at full height

        def P(lx, ly):
            return (x + lx * w + k * ly, base_y - ly * h)

        poly = pygame.draw.polygon
        rr = pygame.draw.rect
        tyre = (16, 13, 22)
        metal = (108, 104, 118)
        dark_bike = shade(bike, -0.42)
        lit_bike = shade(bike, 0.22)

        pygame.draw.ellipse(surf, (12, 7, 20),
                            pygame.Rect(x - w * 0.46, base_y - h * 0.035, w * 0.92, h * 0.075))

        if w < 12:                                   # distant: a legible blob
            poly(surf, bike, [P(-0.26, 0.10), P(0.26, 0.10), P(0.20, 0.46), P(-0.20, 0.46)])
            poly(surf, suit, [P(-0.22, 0.44), P(0.22, 0.44), P(0.17, 0.74), P(-0.17, 0.74)])
            pygame.draw.circle(surf, lit_bike, P(0, 0.86), max(1, int(w * 0.17)))
            return

        # --- rear wheel, swingarm, cans -----------------------------------
        poly(surf, tyre, [P(-0.13, 0.0), P(0.13, 0.0), P(0.13, 0.30), P(-0.13, 0.30)])
        pygame.draw.ellipse(surf, shade(tyre, 0.28),
                            pygame.Rect(*P(-0.085, 0.245), max(1, w * 0.17), max(1, h * 0.10)))
        for sx in (-1, 1):
            poly(surf, shade(metal, -0.35),
                 [P(sx * 0.12, 0.16), P(sx * 0.30, 0.30), P(sx * 0.30, 0.35), P(sx * 0.12, 0.21)])
            # exhaust can, angled up and out
            poly(surf, metal,
                 [P(sx * 0.30, 0.17), P(sx * 0.46, 0.24), P(sx * 0.45, 0.32), P(sx * 0.29, 0.25)])
        # --- tail unit, plate, light ---------------------------------------
        poly(surf, dark_bike, [P(-0.17, 0.28), P(0.17, 0.28), P(0.13, 0.46), P(-0.13, 0.46)])
        rr(surf, (226, 220, 204),
           pygame.Rect(*P(-0.085, 0.365), max(1, w * 0.17), max(1, h * 0.055)))
        rr(surf, (255, 58, 70),
           pygame.Rect(*P(-0.10, 0.475), max(1, w * 0.20), max(1, h * 0.045)))

        # --- bodywork and tank flares --------------------------------------
        poly(surf, bike, [P(-0.30, 0.42), P(0.30, 0.42), P(0.24, 0.62), P(-0.24, 0.62)])
        poly(surf, lit_bike, [P(-0.24, 0.60), P(0.24, 0.60), P(0.19, 0.68), P(-0.19, 0.68)])
        for sx in (-1, 1):                            # seat cowl shoulders
            poly(surf, dark_bike,
                 [P(sx * 0.30, 0.44), P(sx * 0.37, 0.50), P(sx * 0.33, 0.58), P(sx * 0.25, 0.56)])

        # --- legs: thighs forward, boots on the pegs ------------------------
        boot = shade(suit, -0.30)
        for sx in (-1, 1):
            poly(surf, boot,
                 [P(sx * 0.22, 0.30), P(sx * 0.40, 0.26), P(sx * 0.42, 0.36), P(sx * 0.24, 0.40)])
            poly(surf, suit,
                 [P(sx * 0.20, 0.40), P(sx * 0.38, 0.34), P(sx * 0.40, 0.50), P(sx * 0.22, 0.56)])
            if abs(lean) > 0.25 and (sx > 0) == (lean > 0):   # knee out into it
                poly(surf, shade(suit, 0.18),
                     [P(sx * 0.38, 0.40), P(sx * 0.52, 0.44), P(sx * 0.46, 0.52), P(sx * 0.36, 0.50)])

        # --- torso: wide shoulders, narrow waist, spine hump ----------------
        poly(surf, suit, [P(-0.19, 0.60), P(0.19, 0.60), P(0.25, 0.80), P(-0.25, 0.80)])
        poly(surf, shade(suit, 0.14), [P(-0.07, 0.66), P(0.07, 0.66), P(0.09, 0.83), P(-0.09, 0.83)])
        poly(surf, shade(suit, -0.25), [P(-0.25, 0.80), P(0.25, 0.80), P(0.20, 0.845), P(-0.20, 0.845)])

        # --- arms out to the bars ------------------------------------------
        aw = max(1, int(w * 0.15))
        sh_l, sh_r = P(-0.22, 0.795), P(0.22, 0.795)
        if swing > 0:
            ext = math.sin(swing * math.pi)
            fist = P(swing_side * (0.30 + ext * 0.62), 0.80 + ext * 0.05)
            pygame.draw.line(surf, suit, sh_r if swing_side > 0 else sh_l, fist, aw)
            pygame.draw.circle(surf, (232, 188, 147), (int(fist[0]), int(fist[1])),
                               max(1, int(w * 0.12)))
            other = sh_l if swing_side > 0 else sh_r
            pygame.draw.line(surf, suit, other, P(-swing_side * 0.34, 0.70), aw)
        elif tell > 0:
            pygame.draw.line(surf, suit, sh_r if tell_side > 0 else sh_l,
                             P(tell_side * 0.36, 0.80 + 0.12 * tell), aw)
            pygame.draw.line(surf, suit, sh_l if tell_side > 0 else sh_r,
                             P(-tell_side * 0.34, 0.70), aw)
        else:
            pygame.draw.line(surf, suit, sh_l, P(-0.36, 0.70), aw)
            pygame.draw.line(surf, suit, sh_r, P(0.36, 0.70), aw)
            for sx in (-1, 1):                        # bar ends and mirrors
                pygame.draw.circle(surf, metal, (int(P(sx * 0.40, 0.70)[0]),
                                                 int(P(sx * 0.40, 0.70)[1])),
                                   max(1, int(w * 0.055)))
                if w > 30:
                    pygame.draw.line(surf, shade(metal, -0.2), P(sx * 0.40, 0.71),
                                     P(sx * 0.47, 0.80), max(1, int(w * 0.035)))

        # --- helmet: rounded front, flat back, spoiler, visor band ----------
        hx, hy = P(0, 0.93)
        hr = w * 0.20
        pygame.draw.circle(surf, lit_bike, (int(hx), int(hy)), max(2, int(hr)))
        poly(surf, shade(bike, -0.10),
             [P(-0.19, 0.855), P(0.19, 0.855), P(0.15, 0.90), P(-0.15, 0.90)])
        if w > 22:
            poly(surf, dark_bike, [P(-0.10, 1.00), P(0.10, 1.00), P(0.14, 1.03), P(-0.14, 1.03)])
        rr(surf, (18, 12, 30),
           pygame.Rect(*P(-0.155, 0.955), max(1, w * 0.31), max(1, h * 0.055)))
        if w > 26:
            pygame.draw.line(surf, (255, 208, 152), P(-0.14, 1.005), P(0.05, 1.02),
                             max(1, int(w * 0.03)))

    # ---- scenery ----------------------------------------------------------
    def draw_prop(self, surf, kind, x, y, w, f, c1, c2):
        if kind == "palm":
            self._palm(surf, x, y, w, f, c1)
        elif kind == "pine":
            self._pine(surf, x, y, w, f, c1)
        elif kind == "cactus":
            self._cactus(surf, x, y, w, c1)
        elif kind == "grass":
            self._grass(surf, x, y, w, c1)
        elif kind == "driftwood":
            self._driftwood(surf, x, y, w, c2)
        elif kind == "mesa":
            self._mesa(surf, x, y, w, c2)
        elif kind in ("rock", "boulder"):
            self._rock(surf, x, y, w, f, c2)
        else:
            self._sign(surf, x, y, w, c1)

    @staticmethod
    def _quad(surf, col, p0, p1, p2, width, steps=5):
        """Quadratic curve as a short polyline — canvas has curves, we don't."""
        pts = []
        for i in range(steps + 1):
            t = i / steps
            u = 1 - t
            pts.append((u * u * p0[0] + 2 * u * t * p1[0] + t * t * p2[0],
                        u * u * p0[1] + 2 * u * t * p1[1] + t * t * p2[1]))
        pygame.draw.lines(surf, col, False, pts, width)

    def _palm(self, surf, x, y, w, f, col):
        h = w * 2.7
        d = -1 if f < 0.5 else 1
        tx, ty = x + w * 0.32 * d, y - h
        self._quad(surf, col, (x, y), (x + w * 0.17 * d, y - h * 0.55), (tx, ty),
                   max(1, int(w * 0.14)), steps=6)
        if w > 16:                                   # trunk segments
            for i in range(1, 7):
                t = i / 7.0
                px = x + (tx - x) * t * t
                py = y - h * t
                pygame.draw.line(surf, shade(col, 0.18), (px - w * 0.06, py),
                                 (px + w * 0.06, py), 1)
        lw = max(1, int(w * 0.085))
        for i in range(8):
            a = -math.pi + (i / 7) * math.pi
            ca, sa = math.cos(a), math.sin(a)
            tip = (tx + ca * w * 0.92, ty + sa * w * 0.28 + w * 0.34)
            self._quad(surf, col, (tx, ty),
                       (tx + ca * w * 0.54, ty + sa * w * 0.36 - w * 0.28), tip, lw, steps=4)
        pygame.draw.circle(surf, shade(col, -0.2), (int(tx), int(ty)), max(1, int(w * 0.10)))

    def _pine(self, surf, x, y, w, f, col):
        h = w * 3.0
        lean = (f - 0.5) * w * 0.10
        pygame.draw.line(surf, shade(col, -0.25), (x, y), (x + lean, y - h * 0.30),
                         max(1, int(w * 0.10)))
        tiers = 5 if w > 14 else 3
        for i in range(tiers):
            t = i / tiers
            ty = y - h * (0.14 + t * 0.72)
            tw = w * (0.56 - t * 0.40)
            cx = x + lean * (0.3 + t)
            pygame.draw.polygon(surf, col if i % 2 == 0 else shade(col, 0.10),
                                [(cx, ty - h * 0.30), (cx + tw, ty), (cx + tw * 0.4, ty),
                                 (cx + tw * 0.55, ty + h * 0.03),
                                 (cx - tw * 0.55, ty + h * 0.03), (cx - tw * 0.4, ty),
                                 (cx - tw, ty)])

    def _cactus(self, surf, x, y, w, col):
        h, bw = w * 2.3, max(1, w * 0.26)
        rr = pygame.draw.rect
        rr(surf, col, pygame.Rect(x - bw / 2, y - h, bw, h), border_radius=max(1, int(bw / 2)))
        rr(surf, col, pygame.Rect(x - w * 0.46, y - h * 0.64, max(1, w * 0.21), h * 0.34),
           border_radius=max(1, int(w * 0.10)))
        rr(surf, col, pygame.Rect(x - w * 0.46, y - h * 0.66, max(1, w * 0.46), max(1, w * 0.20)),
           border_radius=max(1, int(w * 0.09)))
        rr(surf, col, pygame.Rect(x + w * 0.25, y - h * 0.50, max(1, w * 0.21), h * 0.26),
           border_radius=max(1, int(w * 0.10)))
        rr(surf, col, pygame.Rect(x, y - h * 0.52, max(1, w * 0.46), max(1, w * 0.20)),
           border_radius=max(1, int(w * 0.09)))
        if w > 14:                                    # ribs
            for i in (-1, 0, 1):
                pygame.draw.line(surf, shade(col, 0.16), (x + i * bw * 0.28, y - h * 0.96),
                                 (x + i * bw * 0.28, y - h * 0.06), 1)

    def _grass(self, surf, x, y, w, col):
        h = w * 1.7
        for i in range(6):
            a = (i / 5 - 0.5) * 1.7
            self._quad(surf, col, (x, y), (x + math.sin(a) * w * 0.34, y - h * 0.62),
                       (x + math.sin(a) * w * 0.86, y - h), max(1, int(w * 0.10)), steps=3)

    def _driftwood(self, surf, x, y, w, col):
        h = w * 1.35
        pygame.draw.line(surf, col, (x - w * 0.22, y), (x + w * 0.18, y - h), max(1, int(w * 0.17)))
        pygame.draw.line(surf, col, (x + w * 0.02, y - h * 0.50),
                         (x + w * 0.44, y - h * 0.74), max(1, int(w * 0.10)))
        pygame.draw.line(surf, shade(col, 0.2), (x - w * 0.10, y - h * 0.30),
                         (x - w * 0.40, y - h * 0.44), max(1, int(w * 0.08)))

    def _mesa(self, surf, x, y, w, col):
        h = w * 0.70
        pygame.draw.polygon(surf, col, [
            (x - w * 0.52, y), (x - w * 0.37, y - h * 0.84), (x - w * 0.30, y - h),
            (x + w * 0.30, y - h), (x + w * 0.37, y - h * 0.84), (x + w * 0.52, y)])
        if w > 30:                                    # strata
            for i in range(1, 4):
                t = i / 4.0
                yy = y - h * t * 0.8
                half = w * (0.52 - 0.20 * t)
                pygame.draw.line(surf, shade(col, 0.13 if i % 2 else -0.13),
                                 (x - half, yy), (x + half, yy), max(1, int(h * 0.035)))
            pygame.draw.polygon(surf, shade(col, 0.14), [
                (x + w * 0.30, y - h), (x + w * 0.37, y - h * 0.84),
                (x + w * 0.52, y), (x + w * 0.34, y)])

    def _rock(self, surf, x, y, w, f, col):
        pygame.draw.polygon(surf, col, [
            (x - w * 0.5, y), (x - w * 0.24, y - w * 0.60), (x + w * 0.02, y - w * 0.82),
            (x + w * 0.30, y - w * 0.52), (x + w * 0.5, y)])
        if w > 12:                                    # a lit face
            pygame.draw.polygon(surf, shade(col, 0.20), [
                (x + w * 0.02, y - w * 0.82), (x + w * 0.30, y - w * 0.52),
                (x + w * 0.10, y - w * 0.40)])

    def _sign(self, surf, x, y, w, col):
        h = w * 1.6
        pygame.draw.line(surf, col, (x, y), (x, y - h * 0.70), max(1, int(w * 0.09)))
        pygame.draw.rect(surf, col, pygame.Rect(x - w * 0.46, y - h, max(1, w * 0.92), h * 0.36),
                         border_radius=max(1, int(w * 0.05)))
        if w > 12:
            pygame.draw.rect(surf, shade(col, 0.35),
                             pygame.Rect(x - w * 0.34, y - h * 0.90, max(1, w * 0.68),
                                         max(1, h * 0.07)))
