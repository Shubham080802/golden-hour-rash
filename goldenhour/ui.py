"""HUD and screens.

The browser build layered DOM elements over the canvas. Here everything is
drawn, and buttons are immediate-mode: each frame registers its rectangles and
a click is resolved against them.
"""
import datetime
import math

import pygame

from .achievements import ACHIEVEMENTS, progress
from .config import (CREAM, EMBER, HOT, INK, KM, LINE, MINT, MUTED, PTS,
                     camera_by_id, difficulty_name,
                     SUN, U_PER_M, clamp, lerp)
from . import story
from .game import daily_locale
from .locales import LOCALE_IDS, LOCALES
from . import store

REC_MODES = [("run", "Run"), ("daily:easy", "Daily · Guided"), ("daily:hard", "Daily · Blind")]


def _font(names, size, bold=False):
    f = pygame.font.SysFont(names, size, bold=bold)
    return f


BASE_H = 640          # the height the sizes below were chosen against


class Fonts:
    """Sizes scale with the window. Fixed pixel sizes looked fine at 640 high
    and became unreadable the moment the window grew."""

    def __init__(self, scale=1.0):
        self.scale = scale
        disp = "anton,impact,haettenschweiler,arialnarrow,dejavusans"
        ui = "ibmplexsanscondensed,helveticaneue,arialnarrow,arial,dejavusans"
        mono = "ibmplexmono,menlo,dejavusansmono,couriernew,monospace"
        z = lambda n: max(9, int(round(n * scale)))
        self.title = _font(disp, z(42))
        self.h2 = _font(disp, z(31))
        self.big = _font(disp, z(60))
        self.num = _font(disp, z(26))
        self.body = _font(ui, z(17))
        self.small = _font(ui, z(15))
        self.mono = _font(mono, z(14))
        self.tiny = _font(mono, z(12))
        self.tag = _font(mono, z(12))
        self.key = _font(mono, z(14))


class Ui:
    def __init__(self, fonts):
        self.f = fonts
        self.hot = []
        self._grads = {}
        self._font_scale = getattr(fonts, "scale", 1.0)

    def px(self, n):
        """Scale a hand-tuned pixel measurement along with the type."""
        return max(1, int(round(n * self._font_scale)))

    def clip(self, text, font, width):
        """Trim to fit, with an ellipsis, so a long string never runs into
        whatever sits beside it."""
        if font.size(text)[0] <= width:
            return text
        out = text
        while out and font.size(out + "…")[0] > width:
            out = out[:-1]
        return (out.rstrip() + "…") if out else ""

    def wrap(self, text, font, width):
        words, line, out = text.split(), "", []
        for word in words:
            trial = (line + " " + word).strip()
            if font.size(trial)[0] > width and line:
                out.append(line)
                line = word
            else:
                line = trial
        out.append(line)
        return out

    def ensure_fonts(self, h):
        """Rebuild the faces when the window height changes enough to matter."""
        want = round(clamp(h / BASE_H, 0.85, 2.4), 2)
        if abs(want - self._font_scale) > 0.06:
            self._font_scale = want
            self.f = Fonts(want)
        return self.f

    # ---- primitives -----------------------------------------------------
    def begin(self):
        self.hot = []

    def click(self, pos):
        for rect, action in reversed(self.hot):
            if rect.collidepoint(pos):
                return action
        return None

    def text(self, s, txt, font, col, x, y, anchor="topleft"):
        img = font.render(txt, True, col)
        r = img.get_rect(**{anchor: (x, y)})
        s.blit(img, r)
        return r

    def panel(self, s, rect, alpha=225):
        box = pygame.Surface(rect.size, pygame.SRCALPHA)
        box.fill((12, 6, 24, alpha))
        s.blit(box, rect.topleft)
        pygame.draw.rect(s, LINE, rect, 1, border_radius=5)

    def button(self, s, rect, label, action, active=False, font=None, accent=CREAM):
        font = font or self.f.small
        if active:
            pygame.draw.rect(s, accent, rect, border_radius=4)
            col = INK
        else:
            box = pygame.Surface(rect.size, pygame.SRCALPHA)
            box.fill((255, 241, 222, 14))
            s.blit(box, rect.topleft)
            pygame.draw.rect(s, LINE, rect, 1, border_radius=4)
            col = CREAM
        self.text(s, label, font, col, rect.centerx, rect.centery, "center")
        self.hot.append((rect, action))
        return rect

    def scrim(self, s, w, h):
        veil = pygame.Surface((w, h), pygame.SRCALPHA)
        veil.fill((12, 6, 24, 178))
        s.blit(veil, (0, 0))

    # ---- HUD -------------------------------------------------------------
    def _gradient(self, w, band, flip):
        """Cached dark fade, so HUD text keeps its contrast over a bright road
        like Salt & Sand as well as over a dusk one."""
        key = (w, band, flip)
        surf = self._grads.get(key)
        if surf is None:
            surf = pygame.Surface((w, band), pygame.SRCALPHA)
            for i in range(band):
                t = (i / band) if flip else (1 - i / band)
                surf.fill((12, 6, 24, int(210 * (t ** 1.5))), pygame.Rect(0, i, w, 1))
            self._grads[key] = surf
        return surf

    def hud(self, s, g, w, h):
        zen = g.mode == "zen"
        s.blit(self._gradient(w, self.px(74), False), (0, 0))
        s.blit(self._gradient(w, self.px(190), True), (0, h - self.px(190)))

        # The corners are stacks, not fixed offsets: the readout font grows
        # with the window and used to run over its own unit label.
        pad = self.px(16)
        top = self.px(10)
        self.text(s, "SPEED", self.f.tag, MUTED, pad, top)
        ny = top + self.f.tag.get_height() + self.px(1)
        kmh = str(round(g.speed / U_PER_M * 3.6))
        self.text(s, kmh, self.f.num, CREAM, pad, ny)
        self.text(s, "km/h", self.f.tiny, MUTED,
                  pad + self.f.num.size(kmh)[0] + self.px(6),
                  ny + self.f.num.get_height() - self.f.tiny.get_height() - self.px(2))

        self.text(s, "SCORE", self.f.tag, MUTED, w - pad, top, "topright")
        self.text(s, "—" if zen else f"{int(g.score):,}", self.f.num, SUN,
                  w - pad, ny, "topright")

        bar = pygame.Rect(w // 2 - self.px(150),
                          top + self.f.tag.get_height() + self.px(6),
                          self.px(300), max(3, self.px(5)))
        self.text(s, "NOW PLAYING", self.f.tag, MUTED, bar.centerx, top, "midtop")
        pygame.draw.rect(s, (46, 35, 66), bar, border_radius=3)
        pct = ((g.t * 3) % 100) / 100 if zen else clamp(g.t / g.time_limit, 0, 1)
        pygame.draw.rect(s, SUN, pygame.Rect(bar.x, bar.y, int(bar.w * pct), bar.h),
                         border_radius=3)
        name = "Long Way Home (Pad)" if zen else LOCALES[g.locale]["track"]
        if g.mode == "story":
            left = max(0.0, g.time_limit - g.t)
            name = g.story_ch["title"]
        clock = (f"-{int(left // 60)}:{int(left % 60):02d}" if g.mode == "story"
                 else f"{int(g.t // 60)}:{int(g.t % 60):02d}")
        ty = bar.bottom + self.px(4)
        # The clock owns its end of the bar; the track title gets what is left.
        cw = self.f.tiny.size(clock)[0]
        self.text(s, self.clip(name, self.f.tiny, bar.w - cw - self.px(10)),
                  self.f.tiny, MUTED, bar.x, ty)
        self.text(s, clock, self.f.tiny, MUTED, bar.right, ty, "topright")

        if g.mode == "story":
            self._objective(s, g, w, h)
        if not zen:
            if g.riders:                      # nothing behind you to watch for
                self._mirror(s, g, w, h)
                self._standings(s, g, w, h)
            self._combo(s, g, w, h)
            self._clean_pip(s, g, h)
            if g.guide:
                self._guide_map(s, g, w, h)
                self._callout(s, g, w, h)

        self._keys(s, w, h, [("← →", "Steer"), ("↓", "Brake"),
                             ("J / Space", "Punch"), ("Esc", "Pause")])

        if not zen:
            lab = self.f.tiny.render(
                difficulty_name(g.race_difficulty).upper() + "  ·  "
                + camera_by_id(g.camera)["name"].upper(), True, MUTED)
            lb = lab.get_rect(topleft=(self.px(16), self.px(86)))
            pygame.draw.rect(s, LINE, lb.inflate(self.px(14), self.px(10)), 1,
                             border_radius=3)
            s.blit(lab, lb)

        if g.mod["id"] != "none" and not zen:
            chip = self.f.tiny.render(g.mod["name"].upper(), True, SUN)
            box = chip.get_rect(topleft=(self.px(16), self.px(116)))
            pygame.draw.rect(s, SUN, box.inflate(self.px(14), self.px(10)), 1,
                             border_radius=3)
            s.blit(chip, box)

        self._pops(s, g, w, h)
        self.toasts(s, g, w)

    def _objective(self, s, g, w, h):
        """The chapter's goal, and where you stand against it right now."""
        ch = g.story_ch
        if not ch:
            return
        goal = ch["goal"]
        kind = goal["kind"]
        if kind == "distance":
            pct = clamp(g.dist / goal["value"], 0, 1)
            state = f"{g.dist / KM:.2f} / {goal['value'] / KM:.1f} km"
            ok = pct >= 1.0
        elif kind == "place":
            rows = g.pack_order()
            pos = next((i + 1 for i, r in enumerate(rows) if r["you"]), 1)
            pct = clamp(1.0 - (pos - 1) / max(1, len(rows) - 1), 0, 1)
            state = f"P{pos} of {len(rows)}  ·  top {goal['value']} to pass"
            ok = pos <= goal["value"]
        elif kind == "contacts":
            pct = clamp(1.0 - g.contacts / max(1, goal["value"] + 1), 0, 1)
            state = (f"{g.contacts} knock{'' if g.contacts == 1 else 's'}"
                     f"  ·  {goal['value']} allowed")
            ok = g.contacts <= goal["value"]
        else:
            pct, state, ok = clamp(g.t / g.time_limit, 0, 1), "Ride on", True

        pad = self.px(10)
        bw = self.px(250)
        label = self.wrap(goal["label"], self.f.tiny, bw - pad * 2)[:2]
        box = pygame.Rect(w - bw - self.px(16), self.px(150), bw,
                          self.f.tag.get_height()
                          + self.f.tiny.get_height() * (1 + len(label))
                          + self.px(20))
        self.panel(s, box, 190)
        pygame.draw.rect(s, MINT if ok else SUN, pygame.Rect(box.x, box.y,
                                                             self.px(3), box.h))
        y = box.y + self.px(6)
        self.text(s, "THIS LEG", self.f.tag, MINT if ok else SUN, box.x + pad, y)
        y += self.f.tag.get_height() + self.px(1)
        for line in label:
            self.text(s, line, self.f.tiny, CREAM, box.x + pad, y)
            y += self.f.tiny.get_height()
        y += self.px(2)
        self.text(s, state, self.f.tiny, MUTED, box.x + pad, y)
        rail = pygame.Rect(box.x + pad, box.bottom - self.px(7), bw - pad * 2,
                           max(2, self.px(3)))
        pygame.draw.rect(s, (46, 35, 66), rail, border_radius=2)
        pygame.draw.rect(s, MINT if ok else SUN,
                         pygame.Rect(rail.x, rail.y, int(rail.w * pct), rail.h),
                         border_radius=2)

    def _mirror(self, s, g, w, h):
        """Who is behind, and on which side.

        Not a true mirror — that would want a second render pass. It is a read
        of the road behind you, which is the part you actually need: the
        standings tell you a rival is close, this tells you which shoulder to
        expect them over.
        """
        rect = pygame.Rect(w // 2 - self.px(118), self.px(64), self.px(236), self.px(50))
        self.panel(s, rect, 170)
        lip = rect.y + self.f.tiny.get_height() + self.px(2)
        pygame.draw.polygon(s, (32, 22, 52), [
            (rect.centerx - self.px(78), rect.bottom - self.px(3)),
            (rect.centerx + self.px(78), rect.bottom - self.px(3)),
            (rect.centerx + self.px(30), lip), (rect.centerx - self.px(30), lip)])

        player_pos = g.pos + g.PLAYER_Z
        closest = None
        for r in g.riders:
            d = g.track.rel_z(r.z - player_pos)
            if not (-9000 < d < -120):
                continue
            t = clamp((-d) / 9000.0, 0, 1)         # 0 right behind, 1 far back
            y = rect.bottom - self.px(6) - t * (rect.height - self.px(20))
            half = lerp(self.px(74), self.px(28), t)
            x = rect.centerx + (r.offset - g.player_x) * half * 0.9
            sz = max(2, int(lerp(self.px(8), self.px(3), t)))
            pygame.draw.circle(s, r.bike, (int(x), int(y)), sz)
            if r.fight > 0:                         # coming for the place back
                pygame.draw.circle(s, SUN, (int(x), int(y)), sz + self.px(3), 1)
            if closest is None or t < closest:
                closest = t
        label = "CLEAR BEHIND" if closest is None else (
            "CLOSING" if closest < 0.25 else "BEHIND")
        col = MUTED if closest is None else (HOT if closest < 0.25 else CREAM)
        self.text(s, label, self.f.tiny, col, rect.centerx, rect.y + self.px(1), "midtop")

    def _keys(self, s, w, h, rows):
        """Control hints. The old single-line-of-tiny-mono version was the
        least legible thing on screen."""
        pad = int(10 * self._font_scale)
        lh = self.f.key.get_height() + int(5 * self._font_scale)
        kw = max(self.f.key.size(k)[0] for k, _ in rows)
        vw = max(self.f.small.size(v)[0] for _, v in rows)
        box = pygame.Rect(0, 0, kw + vw + pad * 3, lh * len(rows) + pad)
        box.bottomright = (w - int(14 * self._font_scale), h - int(12 * self._font_scale))
        pane = pygame.Surface(box.size, pygame.SRCALPHA)
        pane.fill((12, 6, 24, 170))
        s.blit(pane, box.topleft)
        pygame.draw.rect(s, LINE, box, 1, border_radius=4)
        y = box.y + pad // 2
        for key, label in rows:
            self.text(s, key, self.f.key, SUN, box.x + pad + kw, y, "topright")
            self.text(s, label, self.f.small, CREAM, box.x + pad * 2 + kw, y - 1)
            y += lh

    def _combo(self, s, g, w, h):
        col = HOT if g.combo else MUTED
        pad = self.px(16)
        rail = pygame.Rect(pad, h - self.px(36), self.px(190), max(3, self.px(4)))
        num = str(g.combo)
        ny = rail.y - self.px(10) - self.f.big.get_height()
        self.text(s, num, self.f.big, col, pad, ny)
        self.text(s, f"×{g.mult()}", self.f.body, CREAM if g.combo else MUTED,
                  pad + self.f.big.size(num)[0] + self.px(8),
                  rail.y - self.px(10) - self.f.body.get_height())
        pygame.draw.rect(s, (46, 35, 66), rail, border_radius=2)
        pygame.draw.rect(s, HOT, pygame.Rect(rail.x, rail.y,
                                             int(rail.w * clamp(g.combo_t / 4.2, 0, 1)), rail.h),
                         border_radius=2)
        return ny

    def _clean_pip(self, s, g, h):
        label = "CLEAN RUN" if g.clean else "CONTACT MADE"
        col = MINT if g.clean else MUTED
        img = self.f.tiny.render(label, True, col)
        top = h - self.px(46) - self.f.big.get_height() - self.px(12) - img.get_height()
        r = img.get_rect(topleft=(self.px(16), top))
        pygame.draw.rect(s, col, r.inflate(self.px(14), self.px(10)), 1, border_radius=3)
        s.blit(img, r)

    def _standings(self, s, g, w, h):
        rows = g.pack_order()
        mine = next(i for i, r in enumerate(rows) if r["you"])
        colw = self.px(158)
        rowh = self.f.tiny.get_height() + self.px(5)
        x = self.px(16)
        # a ten-strong field needs more room; start high enough to clear the
        # combo counter at the bottom
        y = min(int(h * 0.24), h - self.px(150) - rowh * len(rows))
        self.text(s, "PACK", self.f.tag, MUTED, x, y)
        self.text(s, f"P{mine + 1}/{len(rows)}", self.f.mono, SUN, x + colw, y, "topright")
        y += self.f.tag.get_height() + self.px(3)
        for i, r in enumerate(rows):
            rect = pygame.Rect(x, y, colw, rowh)
            if r["you"]:
                pygame.draw.rect(s, (74, 56, 30), rect, border_radius=3)
            elif r["trouble"]:
                pygame.draw.rect(s, (74, 26, 42), rect, border_radius=3)
            elif r["hunting"]:
                pygame.draw.rect(s, (70, 54, 22), rect, border_radius=3)
            else:
                pygame.draw.rect(s, (24, 15, 42), rect, border_radius=3)
            self.text(s, str(i + 1), self.f.tiny, MUTED, x + self.px(5), y + 2)
            pygame.draw.circle(s, r["col"], (x + self.px(24), rect.centery),
                               max(3, self.px(4)))
            self.text(s, r["name"], self.f.tiny, CREAM if r["you"] else MUTED,
                      x + self.px(34), y + 2)
            gap = round((r["dist"] - g.dist) / U_PER_M)
            self.text(s, "—" if r["you"] else f"{gap:+d}m", self.f.tiny, MUTED,
                      x + colw - self.px(5), y + 2, "topright")
            y += rowh

    def _guide_map(self, s, g, w, h):
        """Top-down ribbon of the road ahead, integrated from the same
        per-segment curve data the 3D view is projected from."""
        bw, bh = clamp(w * 0.068, 52, 92), h * 0.46
        bx, by = w - bw - clamp(w * 0.018, 12, 26), h * 0.28
        rect = pygame.Rect(bx, by, bw, bh)
        self.panel(s, rect, 150)

        segs = g.track.segments
        base = g.track.find(g.pos + g.PLAYER_Z).index
        n, step = 46, 4
        head = px = py = 0.0
        pts = [(0.0, 0.0, 0.0)]
        for i in range(1, n + 1):
            seg = segs[(base + i * step) % len(segs)]
            head += seg.curve * step * 0.0062
            px += math.sin(head)
            py += math.cos(head)
            pts.append((px, py, (seg.p2["wy"] - seg.p1["wy"]) / 200.0))
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        pad = 11
        sc = min((bw - pad * 2) / max(0.6, max(xs) - min(xs)),
                 (bh - pad * 2) / max(0.6, max(ys) - min(ys)))
        ox = bx + bw / 2 - ((min(xs) + max(xs)) / 2) * sc
        oy = by + bh - pad
        scr = [(ox + p[0] * sc, oy - (p[1] - min(ys)) * sc) for p in pts]
        if len(scr) > 1:
            pygame.draw.lines(s, (110, 98, 130), False, scr, max(2, int(bw * 0.10)))
            pygame.draw.lines(s, LOCALES[g.locale]["sun"], False, scr[:13],
                              max(2, int(bw * 0.10)))
        for i in range(2, len(pts)):
            if pts[i - 1][2] - pts[i][2] > 0.045:
                pygame.draw.circle(s, HOT, (int(scr[i][0]), int(scr[i][1])),
                                   max(2, int(bw * 0.035)))
        pygame.draw.circle(s, CREAM, (int(scr[0][0]), int(scr[0][1])), max(3, int(bw * 0.055)))
        self.text(s, "ROAD AHEAD", self.f.tiny, MUTED, rect.centerx, by - 14, "midtop")

    def _callout(self, s, g, w, h):
        look = clamp(g.speed * 1.8, 3200, 15000)
        segs = g.track.segments
        base = g.track.find(g.pos + g.PLAYER_Z).index
        frm = int(look / 200)
        curve = grad = 0.0
        for i in range(max(0, frm - 8), frm + 18):
            seg = segs[(base + i) % len(segs)]
            if abs(seg.curve) > abs(curve):
                curve = seg.curve
            gr = (seg.p2["wy"] - seg.p1["wy"]) / 200.0
            if abs(gr) > abs(grad):
                grad = gr
        if abs(curve) >= 1.3:
            left = curve < 0
            sev = int(clamp(round(abs(curve)), 1, 6))
            arrows = ("<" if left else ">") * int(clamp(math.ceil(sev / 1.5), 1, 4))
            col = HOT if sev >= 4 else SUN
            label = ("Left " if left else "Right ") + str(sev) + (" · over a crest" if grad < -0.05 else "")
        elif grad < -0.06:
            arrows, col, label = "^", SUN, "Crest"
        else:
            return
        self.text(s, arrows, self.f.h2, col, w // 2, int(h * 0.26), "center")
        self.text(s, label, self.f.mono, CREAM, w // 2, int(h * 0.26) + 22, "center")

    def _pops(self, s, g, w, h):
        """Newest at the top of the stack, older ones pushed down. They used to
        share one line and pile on top of each other illegibly."""
        lh = self.f.h2.get_height() + 4
        for i, p in enumerate(reversed(g.pops[-5:])):
            a = clamp(p["life"] / p["max"], 0, 1)
            y = h * 0.46 + i * lh - (1 - a) * 26
            img = self.f.h2.render(p["text"], True, p["col"])
            img.set_alpha(int(255 * a))
            s.blit(img, img.get_rect(center=(w / 2, y)))
        for p in g.particles:
            a = clamp(p["life"] / p["max"], 0, 1)
            pygame.draw.circle(s, p["col"],
                               (int(w / 2 + p["x0"] * w + p["px"]), int(h * 0.78 + p["py"])),
                               max(1, int(p["r"] * a)))

    def toast_rail(self):
        """Width the achievement toasts reserve down the right-hand edge."""
        return self.px(250)

    def toasts(self, s, g, w):
        pad = self.px(12)
        th = self.f.tiny.get_height() * 2 + self.f.body.get_height() + self.px(14)
        for i, t in enumerate(g.toasts):
            rect = pygame.Rect(w - self.toast_rail(), self.px(80) + i * (th + self.px(8)),
                               self.toast_rail() - self.px(16), th)
            self.panel(s, rect, 225)
            pygame.draw.rect(s, SUN, pygame.Rect(rect.x, rect.y, self.px(3), rect.h))
            ty = rect.y + self.px(6)
            self.text(s, "ACHIEVEMENT", self.f.tiny, SUN, rect.x + pad, ty)
            ty += self.f.tiny.get_height() + self.px(2)
            self.text(s, t["name"], self.f.body, CREAM, rect.x + pad, ty)
            ty += self.f.body.get_height() + self.px(1)
            self.text(s, self.clip(t["desc"], self.f.tiny, rect.w - pad * 2),
                       self.f.tiny, MUTED, rect.x + pad, ty)

    def fx_note(self, s, fx, w, h):
        img = self.f.tiny.render(fx.last_note, True, CREAM)
        img.set_alpha(int(220 * fx.note_alpha))
        box = pygame.Rect(0, 0, img.get_width() + 20, 24)
        box.center = (w // 2, h - 34)
        pane = pygame.Surface(box.size, pygame.SRCALPHA)
        pane.fill((12, 6, 24, int(200 * fx.note_alpha)))
        s.blit(pane, box.topleft)
        s.blit(img, img.get_rect(center=box.center))

    # ---- screens ---------------------------------------------------------
    def title(self, s, g, w, h):
        self.scrim(s, w, h)
        cx = w // 2
        self.text(s, "GOLDEN HOUR RASH", self.f.tag, SUN, cx, int(h * 0.10), "midtop")
        self.text(s, "PICK A ROAD, THEN PICK YOUR STAKES", self.f.title, CREAM, cx,
                  int(h * 0.13), "midtop")

        pad, gap = self.px(10), self.px(6)
        m = self.px(60)
        lh_t, lh_b = self.f.tiny.get_height() + 2, self.f.body.get_height()

        self.text(s, "ROAD", self.f.tag, MUTED, m, int(h * 0.245))
        cw = (w - m * 2 - gap * 3) // 4
        card_h = pad * 2 + lh_b + lh_t * 2
        y_road = int(h * 0.275)
        for i, lid in enumerate(LOCALE_IDS):
            r = pygame.Rect(m + i * (cw + gap), y_road, cw, card_h)
            self.button(s, r, "", ("locale", lid), active=(lid == g.picked_locale))
            loc = LOCALES[lid]
            col = INK if lid == g.picked_locale else CREAM
            sub2 = INK if lid == g.picked_locale else MUTED
            self.text(s, loc["name"], self.f.body, col, r.centerx, r.y + pad, "midtop")
            for j, line in enumerate(self.wrap(loc["blurb"], self.f.tiny, cw - pad * 2)[:2]):
                self.text(s, line, self.f.tiny, sub2, r.centerx,
                          r.y + pad + lh_b + j * lh_t, "midtop")

        y_mode = y_road + card_h + self.px(26)
        self.text(s, "MODE", self.f.tag, MUTED, m, y_mode - self.px(16))
        done = len(story.progress(g.data)["done"])
        modes = [("run", "RUN", "One song, one road, one score.", EMBER),
                 ("zen", "ZEN", "No rivals, no timer, no score.", MINT),
                 ("daily", "DAILY", "Today's road, shared board.", SUN),
                 ("story", "STORY", f"Ride to the sunrise. {done}/"
                                    f"{len(story.CHAPTERS)} legs.", (200, 139, 240))]
        mw = (w - m * 2 - gap * 3) // 4
        mode_h = pad * 2 + self.f.h2.get_height() + lh_t * 2
        for i, (mid, name, desc, accent) in enumerate(modes):
            r = pygame.Rect(m + i * (mw + gap), y_mode, mw, mode_h)
            self.button(s, r, "", ("mode", mid))
            self.text(s, name, self.f.h2, accent, r.centerx, r.y + pad // 2, "midtop")
            self.text(s, desc, self.f.tiny, MUTED, r.centerx,
                      r.y + pad // 2 + self.f.h2.get_height(), "midtop")
            self.text(s, f"PRESS {i + 1}", self.f.tiny, MUTED, r.centerx,
                      r.y + pad // 2 + self.f.h2.get_height() + lh_t, "midtop")
        self._after_modes = y_mode + mode_h

        y = self._after_modes + self.px(18)
        self.button(s, pygame.Rect(cx - self.px(100), y, self.px(200), self.px(32)),
                    "RECORD ROOM · R", ("screen", "records"))
        y += self.px(42)
        self.text(s, "Best with sound on — the run is scored to the track.",
                  self.f.small, MUTED, cx, y, "midtop")
        controls = [("← → or A / D", "Steer"), ("↓ or S", "Brake"),
                    ("J or Space", "Punch a rival"), ("M", "Sound on / off"),
                    ("F", "Graphics quality"), ("[  ]", "Brightness"),
                    ("C", "Reduced motion"), ("P", "Photo"), ("R", "Record room")]
        colw = (w - self.px(120)) // 3
        lh = self.f.small.get_height() + self.px(4)
        y0 = min(int(h * 0.84), h - lh * 3 - self.px(16))
        for i, (key, label) in enumerate(controls):
            col, row = i // 3, i % 3
            x = self.px(60) + col * colw
            self.text(s, key, self.f.key, SUN, x, y0 + row * lh)
            self.text(s, label, self.f.small, MUTED, x + int(colw * 0.44), y0 + row * lh)
        self._mute(s, g, w, with_difficulty=True)

    def _mute(self, s, g, w, with_difficulty=False):
        bw = self.px(132)
        bh = self.px(26)
        r = pygame.Rect(w - bw - self.px(14), self.px(12), bw, bh)
        self.button(s, r, "SOUND OFF" if g.audio.muted else "SOUND ON", ("mute", None),
                    font=self.f.tiny)
        if with_difficulty:
            d = pygame.Rect(r.x - bw - self.px(8), r.y, bw, bh)
            self.button(s, d, difficulty_name(g.difficulty).upper() + " · D",
                        ("difficulty", None), font=self.f.tiny)
            v = pygame.Rect(d.x - bw - self.px(8), r.y, bw, bh)
            self.button(s, v, camera_by_id(g.camera)["name"].upper() + " · V",
                        ("camera", None), font=self.f.tiny)
        pygame.draw.circle(s, HOT if g.audio.muted else MINT, (r.x + 12, r.centery),
                           max(3, int(4 * self._font_scale)))

    def mods(self, s, g, w, h):
        self.scrim(s, w, h)
        cx = w // 2
        self.text(s, "BEFORE YOU RIDE", self.f.tag, SUN, cx, int(h * 0.13), "midtop")
        self.text(s, "TAKE ONE", self.f.title, CREAM, cx, int(h * 0.16), "midtop")
        self.text(s, "Every card is a trade, not an upgrade.",
                  self.f.small, MUTED, cx, int(h * 0.26), "midtop")
        cards = g.mod_choices
        cw = min(self.px(230), (w - self.px(110)) // len(cards))
        total = cw * len(cards) + self.px(8) * (len(cards) - 1)
        x0 = cx - total // 2
        for i, m in enumerate(cards):
            r = pygame.Rect(x0 + i * (cw + self.px(8)), int(h * 0.33), cw,
                            self.px(16) + self.f.body.get_height()
                            + self.f.tiny.get_height() * 5)
            self.button(s, r, "", ("mod", m["id"]))
            accent = MUTED if m["id"] == "none" else SUN
            self.text(s, m["name"], self.f.body, accent, r.centerx, r.y + self.px(10), "midtop")
            lh = self.f.tiny.get_height() + 2
            for j, ln in enumerate(self.wrap(m["desc"], self.f.tiny, cw - self.px(22))[:5]):
                self.text(s, ln, self.f.tiny, MUTED, r.centerx,
                          r.y + self.px(12) + self.f.body.get_height() + j * lh, "midtop")
        self.button(s, pygame.Rect(cx - self.px(50), int(h * 0.72),
                                   self.px(100), self.px(30)), "BACK",
                    ("screen", "title"))

    def diff(self, s, g, w, h):
        self.scrim(s, w, h)
        cx = w // 2
        loc = LOCALES[daily_locale()]
        self.text(s, f"DAILY · {datetime.date.today().isoformat()} · {loc['name']}",
                  self.f.tag, SUN, cx, int(h * 0.18), "midtop")
        self.text(s, "SAME ROAD, TWO WAYS TO READ IT", self.f.title, CREAM, cx,
                  int(h * 0.22), "midtop")
        self.text(s, "Guided and Blind keep separate boards, so you are only measured",
                  self.f.small, MUTED, cx, int(h * 0.32), "midtop")
        self.text(s, "against riders who had the same information you did.",
                  self.f.small, MUTED, cx, int(h * 0.35), "midtop")
        for i, (did, name, desc, accent) in enumerate([
                ("easy", "GUIDED", "Road map and a corner call before every turn.", MINT),
                ("hard", "BLIND", "No map, no calls. Only what the road shows you.", HOT)]):
            cwid = self.px(300)
            r = pygame.Rect(cx - cwid - self.px(5) + i * (cwid + self.px(10)),
                            int(h * 0.44), cwid,
                            self.px(14) + self.f.h2.get_height() + self.f.tiny.get_height() * 3)
            self.button(s, r, "", ("diff", did))
            self.text(s, name, self.f.h2, accent, r.centerx, r.y + 12, "midtop")
            self.text(s, desc, self.f.tiny, MUTED, r.centerx, r.y + 48, "midtop")
            self.text(s, "PRESS " + ("E" if did == "easy" else "H"), self.f.tiny, MUTED,
                      r.centerx, r.y + 66, "midtop")
        self.button(s, pygame.Rect(cx - self.px(50), int(h * 0.66),
                                   self.px(100), self.px(30)), "BACK",
                    ("screen", "title"))

    def pause(self, s, g, w, h):
        self.scrim(s, w, h)
        cx = w // 2
        self.text(s, "PAUSED", self.f.tag, SUN, cx, int(h * 0.34), "midtop")
        self.text(s, "TAKE YOUR TIME", self.f.title, CREAM, cx, int(h * 0.37), "midtop")
        self.text(s, "Nothing is running down while this is open.", self.f.small, MUTED,
                  cx, int(h * 0.46), "midtop")
        bw, bh = self.px(150), self.px(34)
        self.button(s, pygame.Rect(cx - self.px(160), int(h * 0.53), bw, bh),
                    "RESUME", ("resume", None))
        self.button(s, pygame.Rect(cx + self.px(10), int(h * 0.53), bw, bh),
                    "END RIDE", ("quit", None))

    def results(self, s, g, w, h):
        res = g.results
        if res.get("story"):
            return self.story_results(s, g, w, h)
        self.scrim(s, w, h)
        cx = w // 2
        y = int(h * 0.06)
        if res["zen"]:
            self.text(s, "RIDE ENDED", self.f.tag, SUN, cx, y, "midtop")
            self.text(s, f"{res['dist_km']:.1f} km", self.f.big, MINT, cx, y + 18, "midtop")
            self.text(s, "No score in Zen. That is the point.", self.f.small, MUTED,
                      cx, y + 86, "midtop")
        else:
            if res["perfect"]:
                self.text(s, "PERFECT RUN", self.f.h2, MINT, cx, y, "midtop")
                self.text(s, f"No contact, no dirt, start to flag  ·  +{PTS['perfect']:,}",
                          self.f.tiny, MUTED, cx, y + 26, "midtop")
                y += 34
            elif res.get("tidy"):
                self.text(s, "CLEAN RUN", self.f.h2, MINT, cx, y, "midtop")
                self.text(s, f"{g.contacts} contact"
                             f"{'' if g.contacts == 1 else 's'}  ·  +{PTS['clean']:,}"
                             f"  ·  a perfect run is zero",
                          self.f.tiny, MUTED, cx, y + 26, "midtop")
                y += 34
            elif g.contacts <= 5:
                self.text(s, "SO CLOSE", self.f.h2, EMBER, cx, y, "midtop")
                self.text(s, f"Clean run missed by {g.contacts - 2} contact"
                             f"{'' if g.contacts - 2 == 1 else 's'}",
                          self.f.tiny, MUTED, cx, y + 26, "midtop")
                y += 34
            else:
                self.text(s, "TRACK FINISHED", self.f.tag, SUN, cx, y, "midtop")
                y += 8
            sy = y + self.px(14)
            self.text(s, f"{res['score']:,}", self.f.big, SUN, cx, sy, "midtop")
            sy += self.f.big.get_height()
            pb = res["pb"]
            self.text(s, "NEW PERSONAL BEST" if pb is None else f"PERSONAL BEST {pb:,}",
                      self.f.tiny, MINT if pb is None else MUTED, cx, sy, "midtop")
            sy += self.f.tiny.get_height() + self.px(12)

            stats = [("BEST COMBO", g.best_combo), ("HITS", g.hits),
                     ("KNOCKDOWNS", g.knockdowns), ("OVERTAKES", g.overtakes),
                     ("NEAR MISSES", g.near),
                     ("FINISHED", f"{res['pos']}/{res['of']}")]
            # The whole block below flows: ten riders no longer fit a layout
            # measured by hand against six.
            marg = self.px(80)
            # Leave the toast rail alone on a narrow window rather than let a
            # pop-up land on the finishing order; cap the width on a wide one,
            # because a table stretched over 1700 pixels stops reading as rows.
            room_w = w - marg * 2 - (self.toast_rail() if w < self.px(1180) else 0)
            tw = min(room_w, self.px(760))
            marg += (room_w - tw) // 2
            cols = len(stats) if tw > self.px(660) else 3
            sw = tw // cols
            tile_h = self.f.tiny.get_height() + self.f.body.get_height() + self.px(12)
            ty = sy
            for i, (lab, val) in enumerate(stats):
                r = pygame.Rect(marg + (i % cols) * sw,
                                ty + (i // cols) * (tile_h + self.px(5)),
                                sw - self.px(5), tile_h)
                self.panel(s, r, 150)
                self.text(s, lab, self.f.tiny, MUTED, r.x + self.px(8), r.y + self.px(5))
                self.text(s, str(val), self.f.body, SUN if i == 0 else CREAM,
                          r.x + self.px(8), r.y + self.px(5) + self.f.tiny.get_height())
            tile_rows = (len(stats) + cols - 1) // cols
            ty += tile_rows * (tile_h + self.px(5)) + self.px(12)

            n_rows = max(1, len(res["rows"]))
            room = int(h * 0.90) - self.px(18) - ty - self.f.tiny.get_height()
            rowh = max(self.f.small.get_height() + self.px(2),
                       min(self.px(22), room // (n_rows + 1)))
            gap_x = marg + int(tw * 0.60)
            int_x = marg + int(tw * 0.78)
            top_x = marg + int(tw * 0.93)
            for lab, lx, anchor in (("POS", marg + self.px(10), "topleft"),
                                    ("RIDER", marg + self.px(54), "topleft"),
                                    ("GAP", gap_x, "topright"),
                                    ("INT", int_x, "topright"),
                                    ("TOP", top_x, "topright")):
                self.text(s, lab, self.f.tiny, MUTED, lx, ty, anchor)
            ty += self.f.tiny.get_height() + self.px(3)
            for i, r in enumerate(res["rows"]):
                row = pygame.Rect(marg, ty, tw, rowh)
                if r["you"]:
                    pygame.draw.rect(s, (74, 56, 30), row, border_radius=3)
                elif r["purple"]:
                    pygame.draw.rect(s, (54, 32, 72), row, border_radius=3)
                self.text(s, str(i + 1), self.f.mono, CREAM, row.x + self.px(10),
                          ty + self.px(2))
                pygame.draw.circle(s, r["col"], (row.x + self.px(42), row.centery),
                                   max(3, self.px(4)))
                self.text(s, r["name"], self.f.small, CREAM, row.x + self.px(54),
                          ty + self.px(1))
                gap = "LEADER" if i == 0 else ("—" if r["gap"] is None else f"+{r['gap']:.3f}")
                self.text(s, gap, self.f.mono, SUN if i == 0 else CREAM,
                          gap_x, ty + self.px(2), "topright")
                itv = "" if i == 0 else ("—" if r["int"] is None else f"+{r['int']:.3f}")
                self.text(s, itv, self.f.mono, MUTED, int_x, ty + self.px(2), "topright")
                self.text(s, str(r["kmh"]), self.f.mono, MUTED, top_x, ty + self.px(2),
                          "topright")
                ty += rowh
            fast = next((r for r in res["rows"] if r["purple"]), None)
            if fast and fast["fkm"]:
                self.text(s, f"Fastest kilometre {fast['fkm']:.2f}s · "
                             f"{'you' if fast['you'] else fast['name'].lower()}",
                          self.f.tiny, (200, 139, 240), marg, ty + self.px(4))

        bw, bh = self.px(150), self.px(32)
        self.button(s, pygame.Rect(cx - self.px(160), int(h * 0.90), bw, bh),
                    "RIDE AGAIN", ("again", None))
        self.button(s, pygame.Rect(cx + self.px(10), int(h * 0.90), bw, bh),
                    "CHANGE MODE", ("screen", "title"))
        self.toasts(s, g, w)

    def story_results(self, s, g, w, h):
        res = g.results
        ch = res["chapter"]
        passed = res["passed"]
        self.scrim(s, w, h)
        cx = w // 2
        y = int(h * 0.10)
        self.text(s, ch["place"].upper(), self.f.tag, MUTED, cx, y, "midtop")
        y += self.f.tag.get_height() + self.px(2)
        self.text(s, "LEG CLEARED" if passed else "NOT THIS TIME",
                  self.f.h2, MINT if passed else EMBER, cx, y, "midtop")
        y += self.f.h2.get_height() + self.px(6)
        self.text(s, ch["title"], self.f.body, CREAM, cx, y, "midtop")
        y += self.f.body.get_height() + self.px(16)

        card = pygame.Rect(cx - self.px(230), y, self.px(460),
                           self.f.tiny.get_height() * 2 + self.f.small.get_height()
                           + self.px(22))
        self.panel(s, card, 200)
        pygame.draw.rect(s, MINT if passed else EMBER, card, 1, border_radius=5)
        ty = card.y + self.px(8)
        self.text(s, "THE GOAL", self.f.tag, MUTED, card.x + self.px(12), ty)
        ty += self.f.tag.get_height() + self.px(1)
        self.text(s, res["goal"], self.f.small, CREAM, card.x + self.px(12), ty)
        ty += self.f.small.get_height() + self.px(2)
        self.text(s, res["detail"], self.f.tiny, MINT if passed else EMBER,
                  card.x + self.px(12), ty)
        y = card.bottom + self.px(16)

        stats = [("SCORE", f"{res['score']:,}"),
                 ("DISTANCE", f"{res['stats']['dist'] / KM:.2f} km"),
                 ("KNOCKS TAKEN", str(res["contacts"])),
                 ("BEST COMBO", str(g.best_combo))]
        if res["rows"]:
            stats.insert(1, ("FINISHED", f"P{res['pos']}/{res['of']}"))
        tw = min(w - self.px(120), self.px(620))
        sw = tw // len(stats)
        tile_h = self.f.tiny.get_height() + self.f.body.get_height() + self.px(12)
        for i, (lab, val) in enumerate(stats):
            r = pygame.Rect(cx - tw // 2 + i * sw, y, sw - self.px(5), tile_h)
            self.panel(s, r, 150)
            self.text(s, lab, self.f.tiny, MUTED, r.x + self.px(8), r.y + self.px(5))
            self.text(s, val, self.f.body, SUN, r.x + self.px(8),
                      r.y + self.px(5) + self.f.tiny.get_height())
        y += tile_h + self.px(14)

        if res["perfect"]:
            self.text(s, f"PERFECT RUN  ·  +{PTS['perfect']:,}", self.f.small, MINT,
                      cx, y, "midtop")
            y += self.f.small.get_height() + self.px(4)
        elif res["tidy"]:
            self.text(s, f"CLEAN RUN  ·  +{PTS['clean']:,}", self.f.small, MINT,
                      cx, y, "midtop")
            y += self.f.small.get_height() + self.px(4)

        if not passed:
            self.text(s, "Nothing is lost. Turn around and take it again.",
                      self.f.tiny, MUTED, cx, y, "midtop")
            y += self.f.tiny.get_height() + self.px(4)

        bw, bh = self.px(180), self.px(34)
        by = max(y + self.px(16), min(int(h * 0.80), h - bh - self.px(30)))
        if passed:
            self.button(s, pygame.Rect(cx - bw - self.px(6), by, bw, bh),
                        "RIDE ON", ("storyoutro", None))
            self.button(s, pygame.Rect(cx + self.px(6), by, bw, bh),
                        "THE JOURNEY", ("screen", "journey"))
        else:
            self.button(s, pygame.Rect(cx - bw - self.px(6), by, bw, bh),
                        "RIDE IT AGAIN", ("storygo", None))
            self.button(s, pygame.Rect(cx + self.px(6), by, bw, bh),
                        "THE JOURNEY", ("screen", "journey"))
        self.toasts(s, g, w)

    def journey(self, s, g, w, h):
        """The five legs, in order, with the ones behind you marked."""
        self.scrim(s, w, h)
        cx = w // 2
        prog = story.progress(g.data)
        open_to = story.unlocked(g.data)
        self.text(s, "STORY", self.f.tag, (200, 139, 240), cx, int(h * 0.05), "midtop")
        self.text(s, "THE LONG WAY TO SUNRISE", self.f.title, CREAM, cx,
                  int(h * 0.08), "midtop")
        self.text(s, "Five legs, one night, one sunrise at the end of it.",
                  self.f.small, MUTED, cx, int(h * 0.145), "midtop")

        m = self.px(70)
        row_h = (self.f.body.get_height() + self.f.tiny.get_height() * 2
                 + self.px(16))
        y = int(h * 0.20)
        for i, ch in enumerate(story.CHAPTERS):
            ridden = ch["id"] in prog["done"]
            locked = i > open_to
            r = pygame.Rect(m, y + i * (row_h + self.px(7)), w - m * 2, row_h)
            self.panel(s, r, 210 if not locked else 110)
            if not locked:
                self.hot.append((r, ("story", i)))
                pygame.draw.rect(s, MINT if ridden else SUN, r, 1, border_radius=5)
            name_col = MUTED if locked else CREAM
            self.text(s, f"{i + 1}", self.f.h2, MUTED if locked else (200, 139, 240),
                      r.x + self.px(14), r.y + self.px(8))
            tx = r.x + self.px(48)
            self.text(s, ch["title"], self.f.body, name_col, tx, r.y + self.px(7))
            self.text(s, ch["place"] + "  ·  " + ch["goal"]["label"], self.f.tiny,
                      MUTED, tx, r.y + self.px(9) + self.f.body.get_height())
            best = prog["best"].get(ch["id"])
            if locked:
                tag, col = "LOCKED", MUTED
            elif ridden:
                tag, col = "RIDDEN", MINT
            else:
                tag, col = "NEXT", SUN
            self.text(s, tag, self.f.tiny, col, r.right - self.px(14), r.y + self.px(9),
                      "topright")
            if best:
                self.text(s, f"best {best['score']:,}", self.f.tiny, MUTED,
                          r.right - self.px(14),
                          r.y + self.px(11) + self.f.body.get_height(), "topright")
            if not locked and not ridden:
                self.text(s, "PRESS ENTER", self.f.tiny, MUTED,
                          r.right - self.px(14),
                          r.y + self.px(11) + self.f.body.get_height(), "topright")

        y = y + len(story.CHAPTERS) * (row_h + self.px(7)) + self.px(14)
        if story.finished(g.data):
            self.text(s, "You made it to the overlook. Ride any leg again whenever "
                         "you like.", self.f.small, MINT, cx, y, "midtop")
            y += self.f.small.get_height() + self.px(6)
        self.button(s, pygame.Rect(cx - self.px(50), min(y, h - self.px(44)),
                                   self.px(100), self.px(30)), "BACK",
                    ("screen", "title"), font=self.f.tiny)
        self._mute(s, g, w)

    def beat(self, s, g, w, h):
        """The words over a story beat.

        The scene itself is painted into the world surface by the caller, so
        that it goes through the same post-processing the road does.
        """
        b = g.beat
        if not b:
            return

        # a band behind the text, so the words hold on any sky
        band_h = int(h * 0.38)
        band = pygame.Surface((w, band_h), pygame.SRCALPHA)
        for i in range(band_h):
            band.fill((6, 3, 14, int(215 * (i / band_h) ** 0.7)),
                      pygame.Rect(0, i, w, 1))
        s.blit(band, (0, h - band_h))

        m = self.px(70)
        y = h - band_h + self.px(24)
        self.text(s, b["sub"].upper(), self.f.tag, (200, 139, 240), m, y)
        y += self.f.tag.get_height() + self.px(2)
        self.text(s, b["head"], self.f.h2, CREAM, m, y)
        y += self.f.h2.get_height() + self.px(8)

        # typewriter: characters arrive at a readable pace, and any key or
        # click fills the rest in — nobody should have to wait on prose
        budget = max(0, int((b["t"] - 0.6) / 0.026))
        lh = self.f.small.get_height() + self.px(4)
        for line in b["lines"]:
            if budget <= 0:
                break
            shown = line if budget >= len(line) else line[:budget]
            budget -= len(line)
            self.text(s, shown, self.f.small, CREAM, m, y)
            y += lh

        label = {"ride": "RIDE THIS LEG", "next": "NEXT CHAPTER",
                 "end": "BACK TO THE ROAD"}[b["next"]]
        act = {"ride": ("storygo", None), "next": ("storynext", None),
               "end": ("screen", "journey")}[b["next"]]
        br = pygame.Rect(0, 0, self.px(190), self.px(34))
        br.bottomright = (w - self.px(40), h - self.px(24))
        if g.beat_ready():
            self.button(s, br, label, act)
            self.text(s, "SPACE", self.f.tiny, MUTED, br.centerx,
                      br.y - self.f.tiny.get_height() - self.px(4), "midtop")
        else:
            self.text(s, "SPACE TO SKIP", self.f.tiny, MUTED, br.centerx, br.centery,
                      "center")
            self.hot.append((pygame.Rect(0, 0, w, h), ("beatskip", None)))

    def records(self, s, g, w, h):
        self.scrim(s, w, h)
        cx = w // 2
        self.text(s, "RECORD ROOM", self.f.tag, SUN, cx, int(h * 0.06), "midtop")
        for i, (tid, lab) in enumerate([("times", "TIMINGS & RECORDS"),
                                        ("ach", "ACHIEVEMENTS")]):
            self.button(s, pygame.Rect(cx - self.px(160) + i * self.px(165),
                                       int(h * 0.11), self.px(155), self.px(26)), lab,
                        ("rectab", tid), active=(g.rec_tab == tid), font=self.f.tiny)

        if g.rec_tab == "ach":
            won, total = progress(g.data)
            races = g.data["achievements"]["tally"].get("races", 0)
            self.text(s, f"{won} of {total} earned · {races} races finished",
                      self.f.mono, MUTED, cx, int(h * 0.17), "midtop")
            gw = (w - self.px(160)) // 3
            # Two lines for the description: several of them do not fit one.
            ah = (self.f.small.get_height() + self.f.tiny.get_height() * 2
                  + self.px(20))
            for i, (ident, name, desc, _t) in enumerate(ACHIEVEMENTS):
                col_i, row_i = i % 3, i // 3
                r = pygame.Rect(self.px(80) + col_i * gw,
                                int(h * 0.21) + row_i * (ah + self.px(6)), gw - self.px(6), ah)
                got = ident in g.data["achievements"]["won"]
                self.panel(s, r, 200 if got else 90)
                if got:
                    pygame.draw.rect(s, SUN, r, 1, border_radius=5)
                self.text(s, name, self.f.small, SUN if got else MUTED,
                          r.x + self.px(9), r.y + self.px(6))
                dy = r.y + self.px(8) + self.f.small.get_height()
                for line in self.wrap(desc, self.f.tiny, r.w - self.px(18))[:2]:
                    self.text(s, line, self.f.tiny, MUTED if got else (90, 80, 108),
                              r.x + self.px(9), dy)
                    dy += self.f.tiny.get_height()
        else:
            self.text(s, LOCALES[g.rec_road]["name"], self.f.h2, CREAM, cx, int(h * 0.16),
                      "midtop")
            bw = self.px(140)
            for i, lid in enumerate(LOCALE_IDS):
                self.button(s, pygame.Rect(cx - (bw * 2 + self.px(9)) + i * (bw + self.px(6)),
                                           int(h * 0.24), bw, self.px(24)),
                            LOCALES[lid]["name"], ("recroad", lid),
                            active=(lid == g.rec_road), font=self.f.tiny)
            for i, (mid, lab) in enumerate(REC_MODES):
                self.button(s, pygame.Rect(cx - self.px(230) + i * self.px(155),
                                           int(h * 0.30), self.px(150), self.px(24)), lab,
                            ("recmode", mid), active=(mid == g.rec_mode), font=self.f.tiny)

            parts = g.rec_mode.split(":")
            f = store.get_records(g.data, parts[0], g.rec_road,
                                  parts[1] if len(parts) > 1 else "hard")
            bp = f.get("best_pos") or 0
            self.text(s, f"Races {f.get('runs', 0)}   ·   Best finish "
                         f"{bp if bp and bp < 99 else '—'}   ·   Best combo "
                         f"{f.get('best_combo', 0)}",
                      self.f.mono, MUTED, cx, int(h * 0.36), "midtop")

            for ci, (title, rows, fmt) in enumerate([
                    ("TOP SCORES", f.get("scores", []),
                     lambda e: (f"{e['score']:,}", f"×{e['combo']} · P{e['pos']}")),
                    ("FASTEST KILOMETRE", f.get("splits", []),
                     lambda e: (f"{e['fkm']:.2f}s", f"{e.get('kmh', 0)} km/h · P{e['pos']}"))]):
                x = 80 + ci * ((w - 160) // 2 + 8)
                cw = (w - 176) // 2
                y = int(h * 0.42)
                self.text(s, title, self.f.tiny, MUTED, x, y)
                pygame.draw.line(s, LINE, (x, y + 14), (x + cw, y + 14))
                y += 20
                if not rows:
                    self.text(s, "Nothing recorded here yet.", self.f.small, MUTED, x, y + 4)
                for i, e in enumerate(rows):
                    row = pygame.Rect(x, y, cw, 19)
                    if i == 0:
                        pygame.draw.rect(s, (74, 56, 30), row, border_radius=3)
                    val, meta = fmt(e)
                    self.text(s, str(i + 1), self.f.tiny, MUTED, x + 6, y + 4)
                    self.text(s, val, self.f.mono, SUN, x + 26, y + 4)
                    self.text(s, meta, self.f.tiny, MUTED, x + cw - 96, y + 4)
                    when = datetime.datetime.fromtimestamp(e["ts"]).strftime("%d %b")
                    self.text(s, when, self.f.tiny, MUTED, x + cw - 6, y + 4, "topright")
                    y += 20

        self.button(s, pygame.Rect(cx - self.px(50), int(h * 0.90),
                                   self.px(100), self.px(30)), "BACK",
                    ("screen", "title"))
        self._mute(s, g, w)
