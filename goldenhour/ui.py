"""HUD and screens.

The browser build layered DOM elements over the canvas. Here everything is
drawn, and buttons are immediate-mode: each frame registers its rectangles and
a click is resolved against them.
"""
import datetime
import math

import pygame

from .achievements import ACHIEVEMENTS, progress
from .config import (CREAM, EMBER, HOT, INK, LINE, MINT, MUTED, PTS, SONG_LEN,
                     SUN, U_PER_M, clamp, lerp)
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
        s.blit(self._gradient(w, 74, False), (0, 0))
        s.blit(self._gradient(w, 190, True), (0, h - 190))

        self.text(s, "SPEED", self.f.tag, MUTED, 16, 12)
        self.text(s, str(round(g.speed / U_PER_M * 3.6)), self.f.num, CREAM, 16, 24)
        self.text(s, "km/h", self.f.tiny, MUTED, 64, 36)

        self.text(s, "SCORE", self.f.tag, MUTED, w - 16, 12, "topright")
        self.text(s, "—" if zen else f"{int(g.score):,}", self.f.num, SUN, w - 16, 24, "topright")

        bar = pygame.Rect(w // 2 - 150, 30, 300, 5)
        self.text(s, "NOW PLAYING", self.f.tag, MUTED, bar.centerx, 12, "midtop")
        pygame.draw.rect(s, (46, 35, 66), bar, border_radius=3)
        pct = ((g.t * 3) % 100) / 100 if zen else clamp(g.t / SONG_LEN, 0, 1)
        pygame.draw.rect(s, SUN, pygame.Rect(bar.x, bar.y, int(bar.w * pct), bar.h),
                         border_radius=3)
        name = "Long Way Home (Pad)" if zen else LOCALES[g.locale]["track"]
        self.text(s, name, self.f.tiny, MUTED, bar.x, bar.bottom + 5)
        self.text(s, f"{int(g.t // 60)}:{int(g.t % 60):02d}", self.f.tiny, MUTED,
                  bar.right, bar.bottom + 5, "topright")

        if not zen:
            self._mirror(s, g, w, h)
            self._standings(s, g, w, h)
            self._combo(s, g, w, h)
            self._clean_pip(s, g, h)
            if g.guide:
                self._guide_map(s, g, w, h)
                self._callout(s, g, w, h)

        self._keys(s, w, h, [("← →", "Steer"), ("↓", "Brake"),
                             ("J / Space", "Punch"), ("Esc", "Pause")])

        if g.mod["id"] != "none" and not zen:
            chip = self.f.tiny.render(g.mod["name"].upper(), True, SUN)
            box = chip.get_rect(topleft=(16, 60))
            pygame.draw.rect(s, SUN, box.inflate(14, 10), 1, border_radius=3)
            s.blit(chip, box)

        self._pops(s, g, w, h)
        self.toasts(s, g, w)

    def _mirror(self, s, g, w, h):
        """Who is behind, and on which side.

        Not a true mirror — that would want a second render pass. It is a read
        of the road behind you, which is the part you actually need: the
        standings tell you a rival is close, this tells you which shoulder to
        expect them over.
        """
        rect = pygame.Rect(w // 2 - 118, 58, 236, 48)
        self.panel(s, rect, 170)
        pygame.draw.polygon(s, (32, 22, 52), [
            (rect.centerx - 78, rect.bottom - 3), (rect.centerx + 78, rect.bottom - 3),
            (rect.centerx + 30, rect.y + 11), (rect.centerx - 30, rect.y + 11)])

        player_pos = g.pos + g.PLAYER_Z
        closest = None
        for r in g.riders:
            d = g.track.rel_z(r.z - player_pos)
            if not (-9000 < d < -120):
                continue
            t = clamp((-d) / 9000.0, 0, 1)         # 0 right behind, 1 far back
            y = rect.bottom - 6 - t * (rect.height - 20)
            half = lerp(74, 28, t)
            x = rect.centerx + (r.offset - g.player_x) * half * 0.9
            sz = max(2, int(lerp(8, 3, t)))
            pygame.draw.circle(s, r.bike, (int(x), int(y)), sz)
            if r.fight > 0:                         # coming for the place back
                pygame.draw.circle(s, SUN, (int(x), int(y)), sz + 3, 1)
            if closest is None or t < closest:
                closest = t
        label = "CLEAR BEHIND" if closest is None else (
            "CLOSING" if closest < 0.25 else "BEHIND")
        col = MUTED if closest is None else (HOT if closest < 0.25 else CREAM)
        self.text(s, label, self.f.tiny, col, rect.centerx, rect.y + 1, "midtop")

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
        self.text(s, str(g.combo), self.f.big, col, 16, h - 84)
        self.text(s, f"×{g.mult()}", self.f.body, CREAM if g.combo else MUTED, 78, h - 50)
        rail = pygame.Rect(16, h - 36, 190, 4)
        pygame.draw.rect(s, (46, 35, 66), rail, border_radius=2)
        pygame.draw.rect(s, HOT, pygame.Rect(rail.x, rail.y,
                                             int(rail.w * clamp(g.combo_t / 4.2, 0, 1)), rail.h),
                         border_radius=2)

    def _clean_pip(self, s, g, h):
        label = "CLEAN RUN" if g.clean else "CONTACT MADE"
        col = MINT if g.clean else MUTED
        img = self.f.tiny.render(label, True, col)
        r = img.get_rect(topleft=(16, h - 112))
        pygame.draw.rect(s, col, r.inflate(14, 10), 1, border_radius=3)
        s.blit(img, r)

    def _standings(self, s, g, w, h):
        rows = g.pack_order()
        mine = next(i for i, r in enumerate(rows) if r["you"])
        x, y = 16, int(h * 0.24)
        self.text(s, "PACK", self.f.tag, MUTED, x, y)
        self.text(s, f"P{mine + 1}/{len(rows)}", self.f.mono, SUN, x + 150, y, "topright")
        y += 15
        for i, r in enumerate(rows):
            rect = pygame.Rect(x, y, 150, 17)
            if r["you"]:
                pygame.draw.rect(s, (74, 56, 30), rect, border_radius=3)
            elif r["trouble"]:
                pygame.draw.rect(s, (74, 26, 42), rect, border_radius=3)
            elif r["hunting"]:
                pygame.draw.rect(s, (70, 54, 22), rect, border_radius=3)
            else:
                pygame.draw.rect(s, (24, 15, 42), rect, border_radius=3)
            self.text(s, str(i + 1), self.f.tiny, MUTED, x + 5, y + 4)
            pygame.draw.circle(s, r["col"], (x + 22, y + 8), 4)
            self.text(s, r["name"], self.f.tiny, CREAM if r["you"] else MUTED, x + 32, y + 4)
            gap = round((r["dist"] - g.dist) / U_PER_M)
            self.text(s, "—" if r["you"] else f"{gap:+d}m", self.f.tiny, MUTED,
                      x + 145, y + 4, "topright")
            y += 18

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

    def toasts(self, s, g, w):
        for i, t in enumerate(g.toasts):
            rect = pygame.Rect(w - 250, 80 + i * 58, 234, 50)
            self.panel(s, rect, 225)
            pygame.draw.rect(s, SUN, pygame.Rect(rect.x, rect.y, 3, rect.h))
            self.text(s, "ACHIEVEMENT", self.f.tiny, SUN, rect.x + 12, rect.y + 7)
            self.text(s, t["name"], self.f.body, CREAM, rect.x + 12, rect.y + 19)
            self.text(s, t["desc"], self.f.tiny, MUTED, rect.x + 12, rect.y + 36)

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
        self.text(s, "VERTICAL SLICE · 100 SECONDS", self.f.tag, SUN, cx, int(h * 0.10), "midtop")
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
        modes = [("run", "RUN", "One song, one road, one score.", EMBER),
                 ("zen", "ZEN", "No rivals, no timer, no score.", MINT),
                 ("daily", "DAILY", "Today's road, shared board.", SUN)]
        mw = (w - m * 2 - gap * 2) // 3
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
        self._mute(s, g, w)

    def _mute(self, s, g, w):
        bw = int(132 * self._font_scale)
        r = pygame.Rect(w - bw - 14, 12, bw, int(26 * self._font_scale))
        self.button(s, r, "SOUND OFF" if g.audio.muted else "SOUND ON", ("mute", None),
                    font=self.f.tiny)
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
        self.button(s, pygame.Rect(cx - 50, int(h * 0.72), 100, 30), "BACK",
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
        self.button(s, pygame.Rect(cx - 50, int(h * 0.66), 100, 30), "BACK",
                    ("screen", "title"))

    def pause(self, s, g, w, h):
        self.scrim(s, w, h)
        cx = w // 2
        self.text(s, "PAUSED", self.f.tag, SUN, cx, int(h * 0.34), "midtop")
        self.text(s, "TAKE YOUR TIME", self.f.title, CREAM, cx, int(h * 0.37), "midtop")
        self.text(s, "Nothing is running down while this is open.", self.f.small, MUTED,
                  cx, int(h * 0.46), "midtop")
        self.button(s, pygame.Rect(cx - 160, int(h * 0.53), 150, 34), "RESUME", ("resume", None))
        self.button(s, pygame.Rect(cx + 10, int(h * 0.53), 150, 34), "END RIDE", ("quit", None))

    def results(self, s, g, w, h):
        res = g.results
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
            self.text(s, f"{res['score']:,}", self.f.big, SUN, cx, y + 14, "midtop")
            pb = res["pb"]
            self.text(s, "NEW PERSONAL BEST" if pb is None else f"PERSONAL BEST {pb:,}",
                      self.f.tiny, MINT if pb is None else MUTED, cx, y + 74, "midtop")

            stats = [("BEST COMBO", g.best_combo), ("HITS", g.hits),
                     ("KNOCKDOWNS", g.knockdowns), ("OVERTAKES", g.overtakes),
                     ("NEAR MISSES", g.near),
                     ("FINISHED", f"{res['pos']}/{res['of']}")]
            sw = (w - 160) // len(stats)
            for i, (lab, val) in enumerate(stats):
                r = pygame.Rect(80 + i * sw, y + 96, sw - 4, 40)
                self.panel(s, r, 150)
                self.text(s, lab, self.f.tiny, MUTED, r.x + 8, r.y + 6)
                self.text(s, str(val), self.f.body, SUN if i == 0 else CREAM, r.x + 8, r.y + 20)

            ty = y + 146
            cols = [("POS", 90), ("RIDER", 130), ("GAP", 420), ("INT", 520), ("TOP", 610)]
            for lab, cxp in cols:
                self.text(s, lab, self.f.tiny, MUTED, 80 + cxp - 80, ty)
            ty += 14
            for i, r in enumerate(res["rows"]):
                row = pygame.Rect(80, ty, w - 160, 19)
                if r["you"]:
                    pygame.draw.rect(s, (74, 56, 30), row, border_radius=3)
                elif r["purple"]:
                    pygame.draw.rect(s, (54, 32, 72), row, border_radius=3)
                self.text(s, str(i + 1), self.f.mono, CREAM, row.x + 10, ty + 4)
                pygame.draw.circle(s, r["col"], (row.x + 42, ty + 9), 4)
                self.text(s, r["name"], self.f.small, CREAM, row.x + 54, ty + 3)
                gap = "LEADER" if i == 0 else ("—" if r["gap"] is None else f"+{r['gap']:.3f}")
                self.text(s, gap, self.f.mono, SUN if i == 0 else CREAM, row.x + 400, ty + 4,
                          "topright")
                itv = "" if i == 0 else ("—" if r["int"] is None else f"+{r['int']:.3f}")
                self.text(s, itv, self.f.mono, MUTED, row.x + 500, ty + 4, "topright")
                self.text(s, str(r["kmh"]), self.f.mono, MUTED, row.x + 580, ty + 4, "topright")
                ty += 20
            fast = next((r for r in res["rows"] if r["purple"]), None)
            if fast and fast["fkm"]:
                self.text(s, f"Fastest kilometre {fast['fkm']:.2f}s · "
                             f"{'you' if fast['you'] else fast['name'].lower()}",
                          self.f.tiny, (200, 139, 240), 80, ty + 6)

        self.button(s, pygame.Rect(cx - 160, int(h * 0.90), 150, 32), "RIDE AGAIN",
                    ("again", None))
        self.button(s, pygame.Rect(cx + 10, int(h * 0.90), 150, 32), "CHANGE MODE",
                    ("screen", "title"))
        self.toasts(s, g, w)

    def records(self, s, g, w, h):
        self.scrim(s, w, h)
        cx = w // 2
        self.text(s, "RECORD ROOM", self.f.tag, SUN, cx, int(h * 0.06), "midtop")
        for i, (tid, lab) in enumerate([("times", "TIMINGS & RECORDS"),
                                        ("ach", "ACHIEVEMENTS")]):
            self.button(s, pygame.Rect(cx - 160 + i * 165, int(h * 0.11), 155, 26), lab,
                        ("rectab", tid), active=(g.rec_tab == tid), font=self.f.tiny)

        if g.rec_tab == "ach":
            won, total = progress(g.data)
            races = g.data["achievements"]["tally"].get("races", 0)
            self.text(s, f"{won} of {total} earned · {races} races finished",
                      self.f.mono, MUTED, cx, int(h * 0.17), "midtop")
            gw = (w - 160) // 3
            for i, (ident, name, desc, _t) in enumerate(ACHIEVEMENTS):
                col_i, row_i = i % 3, i // 3
                r = pygame.Rect(80 + col_i * gw, int(h * 0.21) + row_i * 52, gw - 6, 46)
                got = ident in g.data["achievements"]["won"]
                self.panel(s, r, 200 if got else 90)
                if got:
                    pygame.draw.rect(s, SUN, r, 1, border_radius=5)
                self.text(s, name, self.f.small, SUN if got else MUTED, r.x + 9, r.y + 7)
                self.text(s, desc, self.f.tiny, MUTED if got else (90, 80, 108),
                          r.x + 9, r.y + 26)
        else:
            self.text(s, LOCALES[g.rec_road]["name"], self.f.h2, CREAM, cx, int(h * 0.16),
                      "midtop")
            bw = 140
            for i, lid in enumerate(LOCALE_IDS):
                self.button(s, pygame.Rect(cx - (bw * 2 + 9) + i * (bw + 6), int(h * 0.24),
                                           bw, 24),
                            LOCALES[lid]["name"], ("recroad", lid),
                            active=(lid == g.rec_road), font=self.f.tiny)
            for i, (mid, lab) in enumerate(REC_MODES):
                self.button(s, pygame.Rect(cx - 230 + i * 155, int(h * 0.30), 150, 24), lab,
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

        self.button(s, pygame.Rect(cx - 50, int(h * 0.90), 100, 30), "BACK",
                    ("screen", "title"))
        self._mute(s, g, w)
