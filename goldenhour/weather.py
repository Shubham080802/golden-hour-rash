"""Airborne atmosphere — dust, spray, mist.

Particles stream radially outward from the vanishing point, which is what you
actually see from a moving vehicle, and their streak length scales with speed.
It costs one list of floats and sells motion better than anything else at this
price.
"""
import math
import random

import pygame


class Weather:
    def __init__(self, count=110):
        self.rng = random.Random(7)
        self.p = []
        self.count = count
        self._seed(count)

    def _seed(self, n):
        self.p = []
        for _ in range(n):
            self.p.append([self.rng.random() * math.tau,      # angle
                           self.rng.random(),                  # radius 0..1
                           0.35 + self.rng.random() * 0.9,     # size
                           0.6 + self.rng.random() * 0.8])     # speed scatter

    def update(self, dt, speed_pct, spec):
        want = spec["count"]
        if want != self.count:
            self.count = want
            self._seed(want)
        rate = (0.10 + speed_pct * 1.9) * dt
        for q in self.p:
            q[1] += rate * q[3] * (0.35 + q[1])   # accelerates as it nears you
            if q[1] > 1.25:
                q[0] = self.rng.random() * math.tau
                q[1] = self.rng.random() * 0.12
                q[2] = 0.35 + self.rng.random() * 0.9
                q[3] = 0.6 + self.rng.random() * 0.8

    def draw(self, surf, w, h, horizon, speed_pct, spec):
        col = spec["colour"]
        streak = spec["streak"] * (0.25 + speed_pct)
        cx, cy = w * 0.5, horizon
        maxr = math.hypot(w, h) * 0.75
        for ang, r, size, _s in self.p:
            if r < 0.04:
                continue
            ca, sa = math.cos(ang), math.sin(ang)
            d = r * maxr
            x, y = cx + ca * d, cy + sa * d * 0.72
            if not (-20 < x < w + 20 and -20 < y < h + 20):
                continue
            t = streak * d * 0.22
            px, py = x - ca * t, y - sa * t * 0.72
            wdt = max(1, int(size * spec["size"] * (0.5 + r * 2.2)))
            alpha = int(spec["alpha"] * min(1.0, r * 2.0))
            if alpha < 6:
                continue
            if t > 1.5:
                pygame.draw.line(surf, (*col, alpha), (px, py), (x, y), wdt)
            else:
                pygame.draw.circle(surf, (*col, alpha), (int(x), int(y)), wdt)
