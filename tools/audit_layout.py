"""Layout audit: draw every screen at several sizes and catch text that
runs off the window or lands on other text."""
import os, sys
os.environ["SDL_VIDEODRIVER"]="dummy"; os.environ["SDL_AUDIODRIVER"]="dummy"
os.environ["GOLDENHOUR_HOME"]="/tmp/ghr-audit3"
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import pygame
from goldenhour import store
from goldenhour.audio import Audio
from goldenhour.config import INK
from goldenhour.game import Game
from goldenhour.hazards import Hazard
from goldenhour.postfx import PostFX
from goldenhour.render import Renderer
from goldenhour.ui import Fonts, Ui

pygame.init()
drawn = []
_orig_text = Ui.text
def spy(self, s, txt, font, col, x, y, anchor="topleft"):
    r = _orig_text(self, s, txt, font, col, x, y, anchor)
    try:
        img = font.render(str(txt), True, col)
        rect = img.get_rect(**{anchor if anchor != "topleft" else "topleft": (x, y)})
        if str(txt).strip():
            drawn.append((rect, str(txt)))
    except Exception:
        pass
    return r
Ui.text = spy

SIZES = [(820, 520), (1000, 640), (1280, 760), (1600, 1000), (1920, 1080)]
problems = []

def check(label, w, h):
    # off the window
    for rect, txt in drawn:
        if rect.x < -2 or rect.y < -2 or rect.right > w + 2 or rect.bottom > h + 2:
            problems.append(f"{label} @{w}x{h}: OFF-WINDOW {txt!r} at {tuple(rect)}")
    # text on text
    for i in range(len(drawn)):
        ri, ti = drawn[i]
        for j in range(i + 1, len(drawn)):
            rj, tj = drawn[j]
            if not ri.colliderect(rj):
                continue
            clip = ri.clip(rj)
            area = clip.w * clip.h
            small = min(ri.w * ri.h, rj.w * rj.h) or 1
            if area / small > 0.30:
                problems.append(
                    f"{label} @{w}x{h}: OVERLAP {ti!r} x {tj!r} "
                    f"({area/small:.0%} of the smaller)")
    drawn.clear()

for size in SIZES:
    w, h = size
    screen = pygame.display.set_mode(size)
    fonts = Fonts(); ui = Ui(fonts); r = Renderer(fonts); a = Audio()
    data = store.load()
    g = Game(r, a, data); g.postfx = PostFX("low"); g.postfx.auto = False
    for _ in range(60): g.update(1/60)

    def frame(label, fn, world=True):
        screen.fill(INK)
        if world:
            g.draw_world(screen, w, h)
        ui.ensure_fonts(h); ui.begin(); fn()
        check(label, w, h)

    frame("title", lambda: ui.title(screen, g, w, h))
    g.open_mods(); frame("mods", lambda: ui.mods(screen, g, w, h))
    frame("diff", lambda: ui.diff(screen, g, w, h))
    g.rec_tab = "times"
    for mode in ("run", "daily:easy", "survive"):
        g.rec_mode = mode
        frame(f"records[{mode}]", lambda: ui.records(screen, g, w, h))
    g.rec_tab = "ach"; frame("achievements", lambda: ui.records(screen, g, w, h))
    g.rec_tab = "times"; g.rec_mode = "run"
    g.open_journey(); frame("journey", lambda: ui.journey(screen, g, w, h))
    for i in (0, 4):
        for which in ("intro", "outro"):
            g.open_beat(which, i)
            g.beat["t"] = g.beat_len() + 1
            frame(f"beat[{i}:{which}]", lambda: ui.beat(screen, g, w, h), world=False)

    # in-race HUDs
    g.set_locale("coast"); g.start_mode("run")
    for n in range(60 * 30):
        seg = g.track.find(g.pos + g.PLAYER_Z)
        g.steer = max(-1, min(1, (-seg.curve*0.09 - g.player_x)*2.6))
        if n % 40 == 0: g.try_swing()
        g.update(1/60)
    frame("hud[run]", lambda: ui.hud(screen, g, w, h))
    g.phase = "paused"; frame("pause", lambda: ui.pause(screen, g, w, h))
    g.phase = "playing"; g.finish(); frame("results[run]", lambda: ui.results(screen, g, w, h))

    g.start_mode("zen")
    for _ in range(60 * 10): g.update(1/60)
    frame("hud[zen]", lambda: ui.hud(screen, g, w, h))
    g.finish(); frame("results[zen]", lambda: ui.results(screen, g, w, h))

    g.start_mode("daily", "easy")
    for _ in range(60 * 20): g.update(1/60)
    frame("hud[daily-guided]", lambda: ui.hud(screen, g, w, h))

    g.start_story(2)
    for _ in range(60 * 20): g.update(1/60)
    frame("hud[story]", lambda: ui.hud(screen, g, w, h))
    g.dist = 9e9; g.finish(); frame("results[story-pass]", lambda: ui.results(screen, g, w, h))
    g.start_story(2); g.dist = 0; g.finish()
    frame("results[story-fail]", lambda: ui.results(screen, g, w, h))

    g.start_survival()
    for _ in range(60 * 20): g.update(1/60)
    pp = g.pos + g.PLAYER_Z
    g.hazards.items.append(Hazard("skip", (pp + 4000) % g.track.length, 0.1, 0.5))
    g.health = 38.0; g.lives = 2
    frame("hud[survive]", lambda: ui.hud(screen, g, w, h))
    g.getting_up = 1.0; frame("hud[survive-down]", lambda: ui.hud(screen, g, w, h))
    g.getting_up = 0.0
    g.t = g.time_limit; g.finish()
    frame("results[survive-out]", lambda: ui.results(screen, g, w, h))
    g.start_survival(); g.lives = 0; g.t = 91.0; g.survived = 91.0; g.finish()
    frame("results[survive-stopped]", lambda: ui.results(screen, g, w, h))

print(f"checked {len(SIZES)} sizes")
if problems:
    seen = set()
    for p in problems:
        key = p.split(": ", 1)[1][:70]
        if key in seen: continue
        seen.add(key)
        print("  " + p)
    print(f"TOTAL {len(problems)} findings, {len(seen)} distinct")
else:
    print("no layout problems found")
pygame.quit()
