"""Game state, physics and the world render pass."""
import datetime
import math
import random

import pygame

from . import achievements, store
from .config import (ACCEL, BRAKE, CAM_DEPTH, CAM_H, CENTRIFUGAL, DECEL, DRAW_DIST,
                     FOG_STEPS, MAX_SPEED, OFF_DECEL, OFF_LIMIT, PLAYER_Z, PTS,
                     SEG_LEN, SONG_LEN, U_PER_M, clamp, lerp, mix)
from .locales import LOCALE_IDS, LOCALES
from .modifiers import NONE as MOD_NONE, offer as offer_mods
from .racers import (Car, RIDER_SPECS, Rider, fastest_km, push_trace,
                     time_at_distance)
from .render import project
from .track import Rng, build_track, hash_str
from .weather import Weather


def today_key():
    return datetime.date.today().isoformat()


def daily_locale():
    return LOCALE_IDS[hash_str("LOC-" + today_key()) % len(LOCALE_IDS)]


class Game:
    PLAYER_Z = PLAYER_Z

    def __init__(self, renderer, audio, data):
        self.renderer = renderer
        self.audio = audio
        self.data = data
        self.rnd = random.Random()          # menus, particles, pops
        self.sim_rnd = random.Random(0)     # anything that moves a racer

        self.phase = "title"          # title | playing | paused | ended
        self.screen = "title"         # title | diff | records | results | pause
        self.mode = "run"
        self.diff = "hard"
        self.guide = False
        self.rec_tab = "times"
        self.rec_road = "coast"
        self.rec_mode = "run"
        self.toasts = []
        self.mod = MOD_NONE
        self.reduced = False
        self.mod_choices = []
        self.photo = False

        self.picked_locale = data["settings"].get("locale", "coast")
        if self.picked_locale not in LOCALES:
            self.picked_locale = "coast"
        self.locale = self.picked_locale
        self.audio.muted = not data["settings"].get("music", True)

        self.seed = 0
        self.track = None
        self.frame = 0
        self.weather = Weather()
        self.start_attract()

    # ---------------------------------------------------------------- setup
    def make_actors(self):
        rng = Rng(self.seed ^ 0x9E3779B9)
        zen = self.mode == "zen"
        n_cars = 14 if zen else int(26 * self.mod.get("traffic", 1.0))
        self.cars = [Car(rng, self.track) for _ in range(n_cars)]
        self.riders = []
        if not zen:
            bump = LOCALES[self.locale]["terrain"]["ai_skill"]
            head = self.mod.get("head_start")
            for i, spec in enumerate(RIDER_SPECS):
                r = Rider(spec, i, rng, self.track, self.pos + PLAYER_Z, bump)
                if head:                       # slot in mid-pack, not at the back
                    r.dist -= 6000
                    r.z = (r.z - 6000) % self.track.length
                if self.mod.get("rival_pace"):
                    r.nerve = min(1.0, r.nerve * self.mod["rival_pace"])
                self.riders.append(r)
        self.actors = self.cars + self.riders
        for r in self.riders:
            r.ahead = r.dist > self.dist

    def reset_ride(self):
        self.pos = 0.0
        self.speed = MAX_SPEED * 0.55
        self.player_x = 0.0
        self.steer = 0
        self.throttle = 1.0
        self.braking = False
        self.t = 0.0
        self.dist = 0.0
        self.score = 0.0
        self.combo = 0
        self.combo_t = 0.0
        self.best_combo = 0
        self.hits = 0
        self.near = 0
        self.air = 0.0
        self.air_t = 0.0
        self.bump = 0.0
        self.prev_grad = 0.0
        self.swing = 0.0
        self.swing_cd = 0.0
        self.swing_side = 1
        self.dazed = 0.0
        self.shake = 0.0
        self.hit_stop = 0.0
        self.flash = 0.0
        self.flash_col = (255, 63, 107)
        self.shove = 0.0
        self.lean = 0.0
        self.particles = []
        self.pops = []
        self.ended = False
        self.trace = []
        self.sample_t = 0.0
        self.top_speed = 0.0
        self.clean = True
        self.contacts = 0
        self.overtakes = 0
        self.airs = 0
        self.knockdowns = 0
        self.clean_corners = 0
        self.corner = False
        self.corner_clean = True
        self.corner_speed = 0.0
        self.was_off = False
        self.off_for = 0.0
        self.off_for = 0.0
        self.clipped_count = 0
        self.passed_by = 0
        self.make_actors()

    def start_attract(self):
        self.audio.stop_music()
        self.mode = "run"
        self.locale = self.picked_locale
        self.seed = self.rnd.randrange(10 ** 9)
        self.track = build_track(self.seed, LOCALES[self.locale])
        self.pos = 0.0
        self.dist = 0.0
        self.reset_ride()
        self.phase = "title"
        self.screen = "title"
        self.guide = False

    def set_locale(self, loc_id):
        if loc_id not in LOCALES:
            return
        self.picked_locale = loc_id
        self.locale = loc_id
        self.data["settings"]["locale"] = loc_id
        store.save(self.data)
        self.seed = self.rnd.randrange(10 ** 9)
        self.track = build_track(self.seed, LOCALES[self.locale])
        self.reset_ride()

    def locale_data(self):
        return LOCALES[self.locale]

    def open_mods(self):
        """Offer the cards. Daily is excluded — its board must stay fair."""
        self.mod_choices = offer_mods(self.rnd)
        self.screen = "mods"
        self.audio.stop_music()

    def start_mode(self, mode, diff="hard", mod=None):
        self.mod = mod or MOD_NONE
        if mode != "run":
            self.mod = MOD_NONE
        self.mode = mode
        self.diff = diff if mode == "daily" else "hard"
        self.guide = (mode == "daily" and self.diff == "easy")
        self.locale = daily_locale() if mode == "daily" else self.picked_locale
        self.seed = (hash_str("GHR-" + today_key()) if mode == "daily"
                     else self.rnd.randrange(10 ** 9))
        self.track = build_track(self.seed, LOCALES[self.locale])
        # Everything that moves a racer draws from a stream seeded by the
        # track, so the same seed really is the same race for everyone.
        self.sim_rnd = random.Random(self.seed)
        self.pos = 0.0
        self.dist = 0.0
        self.reset_ride()
        self.phase = "playing"
        self.screen = "race"
        self.audio.start_music(LOCALES[self.locale], mode == "zen")
        self.pop("RIDE" if mode == "zen" else "GO", (255, 241, 222))

    # ------------------------------------------------------------- feedback
    def pop(self, text, col):
        self.pops.append({"text": text, "col": col, "life": 0.9, "max": 0.9,
                          "dx": (self.rnd.random() - 0.5) * 0.2})

    def burst(self, col, n, x=0.0):
        for _ in range(n):
            a = self.rnd.random() * math.tau
            s = 60 + self.rnd.random() * 280
            self.particles.append({"x0": x, "px": 0.0, "py": 0.0,
                                   "vx": math.cos(a) * s, "vy": math.sin(a) * s - 60,
                                   "r": 2 + self.rnd.random() * 4,
                                   "life": 0.4 + self.rnd.random() * 0.4,
                                   "max": 0.8, "col": col})

    def mult(self):
        return min(8, 1 + self.combo // 3)

    def add_combo(self, n, label, col, pts):
        self.combo += n
        self.best_combo = max(self.best_combo, self.combo)
        self.combo_t = 4.2 * self.mod.get("combo_t", 1.0)
        award = round((pts or 0) * self.mult() * self.mod.get("score", 1.0))
        self.score += award
        if label:
            self.pop(f"{label}  +{award}" if award else label, col)

    def break_clean(self):
        """Any contact ends a perfect run — traffic, a rival's fist, or the
        dirt off the edge of the road."""
        if self.phase != "playing" or self.mode == "zen":
            return
        self.contacts += 1
        if self.mod.get("contact_wipes"):
            self.combo = 0
        if not self.clean:
            return
        self.clean = False
        self.pop("CLEAN RUN LOST", (255, 122, 60))

    def collide(self, severity):
        self.break_clean()
        severity *= self.mod.get("collide", 1.0)
        self.speed *= (1 - severity * 0.42)
        self.dazed = 0.42
        self.shake = max(self.shake, severity)
        self.flash, self.flash_col = 0.7, (255, 122, 60)
        self.hit_stop = 0.05
        self.audio.sfx_bump()
        if self.mode != "zen" and self.phase == "playing" and self.combo > 2:
            self.pop("REBOUND — combo lost", (255, 122, 60))
        self.combo = 0
        self.burst((255, 122, 60), 14)

    def clipped(self, side, who=None):
        self.break_clean()
        self.clipped_count += 1
        self.speed *= 0.94
        self.shove = (side or 1) * 1.15
        self.dazed = 0.45
        self.shake = max(self.shake, 0.7)
        self.flash, self.flash_col = 0.85, (255, 63, 107)
        self.hit_stop = 0.07
        self.audio.sfx_clip()
        self.burst((255, 63, 107), 18)
        self.pop(f"CLIPPED BY {who}" if who else "CLIPPED", (255, 63, 107))
        self.combo = 0

    def try_swing(self):
        if self.phase != "playing" or self.mode == "zen" or self.swing_cd > 0:
            return
        self.swing = 0.26
        self.swing_cd = 0.34
        self.swing_side = (1 if self.steer > 0 else -1 if self.steer < 0
                           else (1 if self.lean >= 0 else -1))
        player_pos = self.pos + PLAYER_Z
        best, best_score = None, 1e9
        for a in self.riders:
            if a.stagger > 0:
                continue
            d = self.track.rel_z(a.z - player_pos)
            if d < -520 or d > 1150:
                continue
            lat = a.offset - self.player_x
            if abs(lat) > 0.52:
                continue
            if (1 if lat >= 0 else -1) != self.swing_side and abs(lat) > 0.13:
                continue
            sc = abs(d) + abs(lat) * 900
            if sc < best_score:
                best_score, best = sc, a
        if best:
            best.stagger = 0.85
            best.stagger_dir = self.swing_side
            best.tell = 0
            best.cd = 3.4
            best.knock = 1.15
            best.knock_tag = 2.0
            best.speed *= 0.66
            best.z = (best.z - 300) % self.track.length
            best.dist -= 300
            self.speed = min(MAX_SPEED, self.speed * 1.035)
            self.hits += 1
            self.hit_stop = 0.075
            self.shake = max(self.shake, 0.55)
            self.flash, self.flash_col = 0.4, (255, 194, 74)
            self.audio.sfx_hit()
            self.burst((255, 194, 74), 16, self.swing_side * 0.14)
            self.add_combo(1, "HIT · " + best.name, (255, 63, 107),
                           PTS["hit"] * self.mod.get("hit", 1.0))
        else:
            self.audio.sfx_whiff()

    # --------------------------------------------------------------- update
    def update(self, dt):
        self.audio.update(dt)
        self.flash = max(0.0, self.flash - dt * 3.2)
        self.shake = max(0.0, self.shake - dt * 3.4)
        for p in self.particles[:]:
            p["life"] -= dt
            p["px"] += p["vx"] * dt
            p["py"] += p["vy"] * dt
            p["vy"] += 900 * dt
            if p["life"] <= 0:
                self.particles.remove(p)
        for p in self.pops[:]:
            p["life"] -= dt
            if p["life"] <= 0:
                self.pops.remove(p)
        for t in self.toasts[:]:
            t["life"] -= dt
            if t["life"] <= 0:
                self.toasts.remove(t)

        if self.hit_stop > 0:
            self.hit_stop -= dt
            return
        if self.phase in ("paused", "ended"):
            return

        zen = self.mode == "zen"
        playing = self.phase == "playing"
        attract = self.phase == "title"
        self.frame += 1

        p_seg = self.track.find(self.pos + PLAYER_Z)
        speed_pct = self.speed / MAX_SPEED
        dx = dt * 2.4 * speed_pct

        steer = self.steer
        if attract:
            tt = pygame.time.get_ticks() / 1000.0
            want = math.sin(tt * 0.37) * 0.42 + math.sin(tt * 0.13) * 0.22 - p_seg.curve * 0.06
            steer = clamp((want - self.player_x) * 2.2, -1, 1)

        self.player_x += dx * steer
        self.player_x -= dx * speed_pct * p_seg.curve * CENTRIFUGAL
        if self.shove != 0:
            self.player_x += self.shove * dt * 2.6
            self.shove *= math.pow(0.015, dt)
            if abs(self.shove) < 0.03:
                self.shove = 0.0
        self.lean += ((steer * 0.8 + p_seg.curve * 0.10) - self.lean) * clamp(dt * 7, 0, 1)

        throttle = 0.86 if attract else (0.0 if self.braking else self.throttle)
        if self.braking and not attract:
            self.speed += BRAKE * dt
        elif throttle > 0:
            self.speed += ACCEL * dt * throttle
        else:
            self.speed += DECEL * dt
        if self.dazed > 0:
            self.dazed -= dt
            self.speed += DECEL * dt * 1.2

        # tyre scrub: leaning hard at speed costs you, so braking for a
        # corner is a real decision rather than a free one
        scrub = abs(p_seg.curve) * speed_pct
        if scrub > 2.2:
            self.speed -= ((scrub - 2.2) * MAX_SPEED * 0.055 * dt
                           * self.mod.get("scrub", 1.0))

        off = abs(self.player_x) > 0.97
        if off and self.speed > OFF_LIMIT * 0.5:
            # a wheel brushing the shoulder through an apex is not a crash;
            # only a genuine excursion ends a clean run
            self.off_for += dt
            if self.off_for > 0.20 and not self.was_off:
                self.was_off = True
                self.break_clean()
        elif not off:
            self.off_for = 0.0
            self.was_off = False
        if off and self.speed > OFF_LIMIT:
            self.speed += OFF_DECEL * dt
            self.shake = max(self.shake, 0.22)

        self.speed = clamp(self.speed, 0, MAX_SPEED * self.mod.get("speed", 1.0))
        self.player_x = clamp(self.player_x, -2.6, 2.6)

        self.pos = (self.pos + self.speed * dt) % self.track.length
        self.dist += self.speed * dt
        self.renderer.bg_x += p_seg.curve * speed_pct * dt * 260

        # airtime off crests
        grad = (p_seg.p2["wy"] - p_seg.p1["wy"]) / SEG_LEN
        if self.air <= 0 and self.prev_grad - grad > 0.055 and speed_pct > 0.62:
            self.air, self.air_t = 0.0001, 0.46
            self.audio.sfx_air()
            if playing and not zen:
                self.airs += 1
                self.add_combo(1, "AIR", (255, 194, 74), PTS["air"])
        self.prev_grad = grad
        if self.air_t > 0:
            self.air_t -= dt
            self.air = math.sin((1 - max(0.0, self.air_t) / 0.46) * math.pi) * 0.55
            if self.air_t <= 0:
                self.air, self.bump = 0.0, -18.0
        self.bump += (0 - self.bump) * clamp(dt * 9, 0, 1)

        if self.swing > 0:
            self.swing -= dt
        if self.swing_cd > 0:
            self.swing_cd -= dt

        # traffic against the player
        player_pos = self.pos + PLAYER_Z
        for c in self.cars:
            c.update(dt, self)
            d = self.track.rel_z(c.z - player_pos)
            lateral = abs(c.offset - self.player_x)
            if abs(d) < 380 and not c.near:
                if lateral < 0.30 and abs(self.player_x) < 1.4:
                    c.near = True
                    self.collide(0.52 if c.oncoming else 0.34)
                elif lateral < 0.72 and playing and not zen:
                    c.near = True
                    self.near += 1
                    self.add_combo(1, "NEAR MISS", (255, 241, 222),
                                   PTS["near"] * self.mod.get("near", 1.0))
                    self.audio.sfx_near()
            if abs(d) > 900:
                c.near = False

        for r in self.riders:
            if self.mod.get("always_fight"):
                r.fight = max(r.fight, 1.0)
            r.update(dt, self)

        if self.combo_t > 0:
            self.combo_t -= dt
            if self.combo_t <= 0:
                self.combo = 0

        if playing and not zen:
            self.score += (self.speed / MAX_SPEED) * 9 * dt * self.mult()

            hard = abs(p_seg.curve) >= 3.2
            if hard and not self.corner:
                self.corner, self.corner_clean, self.corner_speed = True, True, 0.0
            if self.corner:
                if off or self.dazed > 0:
                    self.corner_clean = False
                self.corner_speed = max(self.corner_speed, speed_pct)
            if not hard and self.corner:
                self.corner = False
                if self.corner_clean and self.corner_speed > 0.62:
                    self.clean_corners += 1
                    self.add_combo(1, "CLEAN CORNER", (87, 227, 180), PTS["corner"])

            if self.speed > self.top_speed:
                self.top_speed = self.speed
            self.weather.update(dt, self.speed / MAX_SPEED,
                                LOCALES[self.locale]["weather"])
            self.sample_t += dt
            if self.sample_t >= 0.15:
                self.sample_t = 0.0
                push_trace(self.trace, self.t, self.dist)
                for r in self.riders:
                    push_trace(r.trace, self.t, r.dist)

        if playing:
            self.t += dt
            if not zen and self.t >= SONG_LEN:
                self.finish()

    # --------------------------------------------------------------- finish
    def finish(self):
        if self.ended:
            return
        self.ended = True
        if self.mode != "zen":
            push_trace(self.trace, self.t, self.dist)
            for r in self.riders:
                push_trace(r.trace, self.t, r.dist)
        self.phase = "ended"
        self.screen = "results"
        self.audio.stop_music()
        self.results = self.build_results()

    def pack_order(self):
        rows = [{"name": "YOU", "dist": self.dist, "col": (255, 122, 60), "you": True,
                 "trace": self.trace, "top": self.top_speed,
                 "trouble": False, "hunting": False}]
        for r in self.riders:
            rows.append({"name": r.name, "dist": r.dist, "col": r.bike, "you": False,
                         "trace": r.trace, "top": r.top_speed,
                         "trouble": r.in_trouble, "hunting": r.fight > 0})
        rows.sort(key=lambda r: -r["dist"])
        return rows

    def classify(self):
        rows = self.pack_order()
        winner = rows[0]
        best_km = None
        for r in rows:
            r["kmh"] = round(r["top"] / U_PER_M * 3.6)
            r["fkm"] = fastest_km(r["trace"])
            if r["fkm"] is not None and (best_km is None or r["fkm"] < best_km["fkm"]):
                best_km = r
        prev = 0.0
        for i, r in enumerate(rows):
            if i == 0:
                r["gap"], r["int"] = 0.0, 0.0
            else:
                tw = time_at_distance(winner["trace"], r["dist"])
                r["gap"] = None if tw is None else max(0.0, self.t - tw)
                r["int"] = (None if (r["gap"] is None or prev is None)
                            else max(0.0, r["gap"] - prev))
            prev = r["gap"]
            r["purple"] = (best_km is r)
        return rows

    def build_results(self):
        zen = self.mode == "zen"
        no_bonus = self.mod.get("no_perfect")
        perfect = (not zen) and self.clean and not no_bonus
        tidy = (not zen) and (not perfect) and self.contacts <= 2 and not no_bonus
        if perfect:
            self.score += PTS["perfect"]
        elif tidy:
            self.score += PTS["clean"]
        res = {"zen": zen, "perfect": perfect, "tidy": tidy,
               "contacts": self.contacts, "score": int(self.score),
               "rows": [], "pos": 0, "of": 0, "pb": None}
        if zen:
            res["dist_km"] = self.dist / (1000 * U_PER_M)
            return res

        rows = self.classify()
        mine = next(i for i, r in enumerate(rows) if r["you"])
        me = rows[mine]
        res["rows"] = rows
        res["pos"] = mine + 1
        res["of"] = len(rows)
        res["pb"] = store.personal_best(self.data, self.mode, self.locale,
                                        self.diff, int(self.score))

        run = {"pos": mine + 1, "of": len(rows), "clean": self.clean,
               "contacts": self.contacts, "hits": self.hits,
               "knockdowns": self.knockdowns, "near": self.near, "airs": self.airs,
               "combo": self.best_combo, "clipped": self.clipped_count,
               "passed_by": self.passed_by, "overtakes": self.overtakes,
               "mode": self.mode, "diff": self.diff, "locale": self.locale,
               "mod": self.mod["id"],
               "score": int(self.score), "fkm": me["fkm"]}
        for ident, name, desc in achievements.check(self.data, run):
            self.toasts.append({"name": name, "desc": desc, "life": 5.0})
        store.record_run(self.data, self.mode, self.locale, self.diff, {
            "ts": store.now_ts(), "score": int(self.score), "combo": self.best_combo,
            "hits": self.hits, "pos": mine + 1, "fkm": me["fkm"], "kmh": me["kmh"]})
        return res

    # ---------------------------------------------------------------- world
    def draw_world(self, surf, w, h):
        r = self.renderer
        loc_id = self.locale
        loc = LOCALES[loc_id]
        fog = r.fog_table(loc_id)

        base = self.track.find(self.pos)
        base_pct = (self.pos % SEG_LEN) / SEG_LEN
        p_seg = self.track.find(self.pos + PLAYER_Z)
        p_pct = ((self.pos + PLAYER_Z) % SEG_LEN) / SEG_LEN
        player_y = lerp(p_seg.p1["wy"], p_seg.p2["wy"], p_pct) + self.air * 900 + self.bump

        segs = self.track.segments
        ahead = segs[(p_seg.index + 40) % len(segs)]
        slope = (ahead.p1["wy"] - p_seg.p1["wy"]) / (40 * SEG_LEN)
        r.smooth_slope += (slope - r.smooth_slope) * 0.06
        horizon = clamp(h * 0.50 - r.smooth_slope * h * 2.6, h * 0.24, h * 0.72)

        r.draw_sky(surf, loc_id, horizon, w, h, self.audio.beat, self.mode == "zen")

        maxy = float(h)
        x = 0.0
        ddx = -(base.curve * base_pct)
        cam_x = self.player_x * 2200
        cam_y = player_y + CAM_H
        n_segs = len(segs)
        drawn = []

        for n in range(DRAW_DIST):
            seg = segs[(base.index + n) % n_segs]
            seg.looped = seg.index < base.index
            seg.clip = maxy
            seg.proj = self.frame
            cam_z = self.pos - (self.track.length if seg.looped else 0)
            project(seg.p1, cam_x - x, cam_y, cam_z, w, h)
            project(seg.p2, cam_x - x - ddx, cam_y, cam_z, w, h)
            x += ddx
            ddx += seg.curve

            if seg.p1["cz"] <= CAM_DEPTH:
                continue
            if seg.p2["y"] >= seg.p1["y"] or seg.p2["y"] >= maxy:
                continue
            fi = min(FOG_STEPS - 1, int(n * FOG_STEPS / DRAW_DIST))
            r.draw_segment(surf, seg, fog[fi]["dark" if seg.dark else "light"],
                           n < 110, w, loc["lanes"], loc["rails"])
            maxy = seg.p2["y"]
            drawn.append((n, seg))

        # actors bucketed by segment, drawn far to near
        bucket = {}
        for a in self.actors:
            si = int(a.z // SEG_LEN) % n_segs
            bucket.setdefault(si, []).append(a)

        for n, seg in reversed(drawn):
            clip = pygame.Rect(0, 0, w, max(0, int(seg.clip)))
            surf.set_clip(clip)
            fog_t = min(0.92, (n / DRAW_DIST) ** 1.4 * 1.25)
            c1 = mix(loc["hill"], loc["horizon"], fog_t)
            c2 = mix(loc["hill2"], loc["horizon"], fog_t)
            for p in seg.props:
                sx = seg.p1["x"] + seg.p1["w"] * p["offset"]
                sw = seg.p1["w"] * 0.42 * p["scale"]
                if sw < 0.6 or sx < -w * 1.6 or sx > w * 2.6:
                    continue
                r.draw_prop(surf, p["kind"], sx, seg.p1["y"], sw, p["f"], c1, c2)

            for a in bucket.get(seg.index, ()):
                pct = (a.z % SEG_LEN) / SEG_LEN
                sx = (lerp(seg.p1["x"], seg.p2["x"], pct)
                      + lerp(seg.p1["w"], seg.p2["w"], pct) * a.offset)
                sy = lerp(seg.p1["y"], seg.p2["y"], pct)
                sw = lerp(seg.p1["w"], seg.p2["w"], pct)
                if sw < 1:
                    continue
                if a.kind == "car":
                    col = mix(a.col, loc["horizon"], fog_t)
                    r.draw_car(surf, sx, sy, sw * a.w, col, a.oncoming)
                else:
                    r.draw_rider(surf, sx, sy, sw * 0.21,
                                 mix(a.bike, loc["horizon"], fog_t),
                                 mix(a.suit, loc["horizon"], fog_t),
                                 a.lean, a.swing, a.swing_side, a.tell, a.tell_side)
        surf.set_clip(None)

        spec = loc["weather"]
        pct = self.speed / MAX_SPEED
        air = r.air_layer(w, h)
        air.fill((0, 0, 0, 0))
        self.weather.draw(air, w, h, horizon, pct, spec)
        surf.blit(air, (0, 0))

        self.draw_player(surf, w, h)

    def shake_offset(self, w, h):
        """Camera kick for impacts. Driven by the frame counter rather than a
        random draw, so it cannot perturb the simulation's number stream."""
        if self.reduced or self.shake <= 0.01:
            return (0, 0)
        amp = self.shake * min(w, h) * 0.022
        return (int(math.sin(self.frame * 37.1) * amp),
                int(math.cos(self.frame * 23.7) * amp * 0.7))

    def draw_player(self, surf, w, h):
        bounce = (0.0 if self.reduced
                  else math.sin(self.frame * 0.42) * (self.speed / MAX_SPEED) * h * 0.006)
        pw = w * 0.15
        y = h * 0.90 + bounce - self.air * h * 0.16
        lean = self.lean + (math.sin(self.dazed * 30) * 0.5 if self.dazed > 0 else 0)
        self.renderer.draw_rider(
            surf, w / 2, y, pw, (255, 122, 60), (34, 24, 51),
            lean, (1 - self.swing / 0.26) if self.swing > 0 else 0.0, self.swing_side)
