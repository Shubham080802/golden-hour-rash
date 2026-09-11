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

import pygame

from .config import (CAM_DEPTH, CAM_H, DRAW_DIST, FOG_STEPS, LANES, MAX_SPEED,
                     PLAYER_Z, ROAD_W, SEG_LEN, clamp, lerp, mix, shade)
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

    def bloom(self, colour, radius, peak=34):
        """Additive glow. Concentric circles accumulate, so the per-ring alpha
        has to stay low or the whole sky saturates to white."""
        key = (colour, radius, peak)
        surf = self._bloom.get(key)
        if surf:
            return surf
        d = radius * 2
        surf = pygame.Surface((d, d), pygame.SRCALPHA)
        steps = 18
        for i in range(steps, 0, -1):
            t = i / steps
            r = int(radius * t)
            a = int(peak * (1 - t) ** 2.6)
            if r > 0 and a > 0:
                pygame.draw.circle(surf, (*colour, a), (radius, radius), r)
        self._bloom[key] = surf
        return surf

    def vignette(self, w, h):
        key = (w, h)
        if self._vig_key == key:
            return self._vig
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        steps = 22
        cx, cy = w // 2, int(h * 0.55)
        maxr = int(h * 0.95)
        for i in range(steps, 0, -1):
            t = i / steps
            a = int(118 * (t ** 2.4))
            pygame.draw.circle(surf, (8, 4, 16, a), (cx, cy), int(maxr * t))
        # invert: we drew the dark in the middle, so redo as rings outward
        surf.fill((0, 0, 0, 0))
        for i in range(steps):
            t = i / steps
            r = int(maxr * (1 - t))
            a = int(118 * (t ** 1.8))
            pygame.draw.circle(surf, (8, 4, 16, a), (cx, cy), r)
        self._vig = surf
        self._vig_key = key
        return surf

    # ---- sky ------------------------------------------------------------
    def draw_sky(self, surf, loc_id, horizon, w, h, beat, zen):
        loc = LOCALES[loc_id]
        surf.blit(self.sky(loc_id, w, h), (0, 0))

        sun_r = int(h * 0.115 * (1 + beat * 0.03))
        sx = int(w * 0.5 - self.bg_x * 0.30)
        sy = int(horizon - sun_r * 1.45)

        br = int(sun_r * 2.6)
        surf.blit(self.bloom(loc["sun"], br), (sx - br, sy - br),
                  special_flags=pygame.BLEND_RGBA_ADD)
        pygame.draw.circle(surf, loc["sun"], (sx, sy), sun_r)
        pygame.draw.circle(surf, shade(loc["sun"], 0.45), (sx, sy - sun_r // 5), int(sun_r * 0.55))

        # stratus bands catching the last light
        for i in range(9):
            cy = horizon - h * (0.085 + i * 0.042)
            cw = w * (0.30 + ((i * 53) % 46) / 100)
            cx = ((i * 263 + self.bg_x * 0.22) % (w * 1.9)) - w * 0.45
            fade = 0.16 - i * 0.012
            if fade <= 0.01:
                continue
            col = mix(loc["cloud_lo"], loc["cloud_hi"], 0.6)
            band = mix(self._sample_sky(loc, cy / max(1, h)), col, fade * 3)
            rect = pygame.Rect(int(cx), int(cy - h * 0.013), int(cw), int(h * 0.026))
            pygame.draw.ellipse(surf, band, rect)

        self._ridge(surf, loc["ridge_far"], loc["horizon"], horizon, 0.62, 0.30, h * 0.150, 1.0, 0, w)
        self._ridge(surf, loc["ridge_far"], loc["horizon"], horizon, 0.34, 0.62, h * 0.108, 1.7, 430, w)
        self._ridge(surf, loc["ridge_near"], loc["horizon"], horizon, 0.14, 1.05, h * 0.064, 2.8, 910, w)

        # a little glare spilling back over the ridges
        gr = int(sun_r * 1.9)
        surf.blit(self.bloom(loc["sun"], gr, peak=16), (sx - gr, sy - gr),
                  special_flags=pygame.BLEND_RGBA_ADD)

    def _sample_sky(self, loc, u):
        stops = loc["sky_stops"]
        u = clamp(u, 0, 1)
        for i in range(len(stops) - 1):
            a, b = stops[i], stops[i + 1]
            if a[0] <= u <= b[0]:
                span = b[0] - a[0] or 1
                return mix(a[1], b[1], (u - a[0]) / span)
        return stops[-1][1]

    def _ridge(self, surf, base, horizon_col, hy, fog_t, par, amp, freq, phase, w):
        col = mix(base, horizon_col, fog_t)
        pts = [(0, hy + 2)]
        off = self.bg_x * par + phase
        x = 0
        while x <= w:
            u = (x + off) / w
            y = hy - amp * (0.44
                            + 0.30 * math.sin(u * freq * 5.1)
                            + 0.16 * math.sin(u * freq * 11.3 + 1.7)
                            + 0.09 * math.sin(u * freq * 23.7 + 3.1))
            pts.append((x, y))
            x += 9
        pts.append((w, hy + 2))
        pygame.draw.polygon(surf, col, pts)

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
    def draw_car(self, surf, x, base_y, w, col, oncoming):
        h = w * 0.66
        top = base_y - h
        rr = pygame.draw.rect
        pygame.draw.ellipse(surf, (14, 8, 24),
                            pygame.Rect(x - w * 0.6, base_y - h * 0.1, w * 1.2, h * 0.25))
        rr(surf, (12, 8, 20), pygame.Rect(x - w * 0.53, base_y - h * 0.22, w * 0.11, h * 0.22))
        rr(surf, (12, 8, 20), pygame.Rect(x + w * 0.42, base_y - h * 0.22, w * 0.11, h * 0.22))
        rr(surf, shade(col, 0.18), pygame.Rect(x - w * 0.34, top, w * 0.68, h * 0.50),
           border_radius=max(1, int(w * 0.08)))
        glass = (228, 200, 170) if oncoming else (34, 20, 52)
        rr(surf, glass, pygame.Rect(x - w * 0.28, top + h * 0.06, w * 0.56, h * 0.32),
           border_radius=max(1, int(w * 0.05)))
        rr(surf, col, pygame.Rect(x - w / 2, top + h * 0.40, w, h * 0.60),
           border_radius=max(1, int(w * 0.07)))
        rr(surf, shade(col, -0.34), pygame.Rect(x - w / 2, top + h * 0.80, w, h * 0.20),
           border_radius=max(1, int(w * 0.06)))
        ly, lw, lh = base_y - h * 0.26, w * 0.17, h * 0.13
        lc = (255, 246, 216) if oncoming else (255, 74, 85)
        rr(surf, lc, pygame.Rect(x - w * 0.44, ly, lw, lh))
        rr(surf, lc, pygame.Rect(x + w * 0.44 - lw, ly, lw, lh))

    def draw_rider(self, surf, x, base_y, w, bike, suit, lean=0.0, swing=0.0,
                   swing_side=1, tell=0.0, tell_side=1):
        h = w * 1.26
        dx = lean * h * 0.10
        rr = pygame.draw.rect
        pygame.draw.ellipse(surf, (14, 8, 24),
                            pygame.Rect(x - w * 0.5, base_y - h * 0.05, w, h * 0.11))
        rr(surf, (16, 12, 26), pygame.Rect(x - w * 0.16, base_y - h * 0.42, w * 0.32, h * 0.42),
           border_radius=max(1, int(w * 0.14)))
        body = [(x - w * 0.42, base_y - h * 0.30), (x + w * 0.42, base_y - h * 0.30),
                (x + w * 0.30 + dx, base_y - h * 0.60), (x - w * 0.30 + dx, base_y - h * 0.60)]
        pygame.draw.polygon(surf, bike, body)
        pygame.draw.polygon(surf, shade(bike, -0.34),
                            [(x - w * 0.27 + dx, base_y - h * 0.64),
                             (x + w * 0.27 + dx, base_y - h * 0.64),
                             (x + w * 0.27 + dx, base_y - h * 0.54),
                             (x - w * 0.27 + dx, base_y - h * 0.54)])
        rr(surf, suit, pygame.Rect(x - w * 0.24 + dx, base_y - h * 0.90, w * 0.48, h * 0.34),
           border_radius=max(1, int(w * 0.11)))
        arm_y = base_y - h * 0.78
        lw = max(1, int(w * 0.15))
        if swing > 0:
            ext = math.sin(swing * math.pi) * w * 0.95
            pygame.draw.line(surf, shade(suit, 0.06), (x + dx, arm_y),
                             (x + dx + swing_side * ext, arm_y - w * 0.10), lw)
            pygame.draw.circle(surf, (232, 188, 147),
                               (int(x + dx + swing_side * ext), int(arm_y - w * 0.10)),
                               max(1, int(w * 0.13)))
        elif tell > 0:
            pygame.draw.line(surf, shade(suit, 0.06), (x + dx, arm_y),
                             (x + dx + tell_side * w * 0.34, arm_y - w * 0.42 * tell), lw)
        else:
            pygame.draw.line(surf, shade(suit, 0.06), (x + dx, arm_y),
                             (x + dx - w * 0.34, arm_y + w * 0.20), lw)
            pygame.draw.line(surf, shade(suit, 0.06), (x + dx, arm_y),
                             (x + dx + w * 0.34, arm_y + w * 0.20), lw)
        pygame.draw.circle(surf, shade(bike, 0.20), (int(x + dx), int(base_y - h * 0.99)),
                           max(1, int(w * 0.20)))
        rr(surf, (16, 9, 30), pygame.Rect(x - w * 0.17 + dx, base_y - h * 1.03, w * 0.34, w * 0.11),
           border_radius=max(1, int(w * 0.04)))

    def draw_prop(self, surf, kind, x, y, w, f, c1, c2):
        if kind == "palm":
            self._palm(surf, x, y, w, f, c1)
        elif kind == "pine":
            self._pine(surf, x, y, w, c1)
        elif kind == "cactus":
            self._cactus(surf, x, y, w, c1)
        elif kind == "grass":
            self._grass(surf, x, y, w, c1)
        elif kind == "driftwood":
            self._driftwood(surf, x, y, w, c2)
        elif kind == "mesa":
            self._mesa(surf, x, y, w, c2)
        elif kind in ("rock", "boulder"):
            self._rock(surf, x, y, w, c2)
        else:
            self._sign(surf, x, y, w, c1)

    def _palm(self, surf, x, y, w, f, col):
        h = w * 2.6
        d = -1 if f < 0.5 else 1
        tx, ty = x + w * 0.30 * d, y - h
        pygame.draw.line(surf, col, (x, y), (tx, ty), max(1, int(w * 0.13)))
        for i in range(7):
            a = -math.pi + (i / 6) * math.pi
            pygame.draw.line(surf, col, (tx, ty),
                             (tx + math.cos(a) * w * 0.98, ty + math.sin(a) * w * 0.30 + w * 0.24),
                             max(1, int(w * 0.095)))

    def _pine(self, surf, x, y, w, col):
        h = w * 2.9
        pygame.draw.rect(surf, col, pygame.Rect(x - w * 0.055, y - h * 0.20, max(1, w * 0.11), h * 0.20))
        for i in range(3):
            ty = y - h * 0.16 - i * h * 0.25
            tw = w * (0.50 - i * 0.11)
            pygame.draw.polygon(surf, col, [(x, ty - h * 0.42), (x + tw, ty), (x - tw, ty)])

    def _cactus(self, surf, x, y, w, col):
        h, bw = w * 2.2, max(1, w * 0.24)
        rr = pygame.draw.rect
        rr(surf, col, pygame.Rect(x - bw / 2, y - h, bw, h), border_radius=max(1, int(bw / 2)))
        rr(surf, col, pygame.Rect(x - w * 0.44, y - h * 0.66, max(1, w * 0.20), h * 0.36),
           border_radius=max(1, int(w * 0.10)))
        rr(surf, col, pygame.Rect(x - w * 0.44, y - h * 0.68, max(1, w * 0.44), max(1, w * 0.19)),
           border_radius=max(1, int(w * 0.09)))
        rr(surf, col, pygame.Rect(x + w * 0.24, y - h * 0.52, max(1, w * 0.20), h * 0.28),
           border_radius=max(1, int(w * 0.10)))

    def _grass(self, surf, x, y, w, col):
        h = w * 1.6
        for i in range(5):
            a = (i / 4 - 0.5) * 1.6
            pygame.draw.line(surf, col, (x, y),
                             (x + math.sin(a) * w * 0.78, y - h), max(1, int(w * 0.11)))

    def _driftwood(self, surf, x, y, w, col):
        h = w * 1.35
        pygame.draw.line(surf, col, (x - w * 0.22, y), (x + w * 0.18, y - h), max(1, int(w * 0.17)))
        pygame.draw.line(surf, col, (x + w * 0.02, y - h * 0.50),
                         (x + w * 0.44, y - h * 0.74), max(1, int(w * 0.10)))

    def _mesa(self, surf, x, y, w, col):
        h = w * 0.66
        pygame.draw.polygon(surf, col, [
            (x - w * 0.52, y), (x - w * 0.37, y - h * 0.84), (x - w * 0.30, y - h),
            (x + w * 0.30, y - h), (x + w * 0.37, y - h * 0.84), (x + w * 0.52, y)])

    def _rock(self, surf, x, y, w, col):
        pygame.draw.polygon(surf, col, [
            (x - w * 0.5, y), (x - w * 0.24, y - w * 0.60), (x + w * 0.02, y - w * 0.82),
            (x + w * 0.30, y - w * 0.52), (x + w * 0.5, y)])

    def _sign(self, surf, x, y, w, col):
        h = w * 1.5
        pygame.draw.line(surf, col, (x, y), (x, y - h * 0.72), max(1, int(w * 0.09)))
        pygame.draw.rect(surf, col, pygame.Rect(x - w * 0.44, y - h, max(1, w * 0.88), h * 0.34),
                         border_radius=max(1, int(w * 0.05)))
