import os, sys, time, traceback
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
os.environ["GOLDENHOUR_HOME"] = "/tmp/ghr-test-save"
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pygame
from goldenhour import store
from goldenhour.audio import Audio
from goldenhour.config import WIN_W, WIN_H, INK
from goldenhour.game import Game
from goldenhour.render import Renderer
from goldenhour.ui import Fonts, Ui

pygame.init()
screen = pygame.display.set_mode((WIN_W, WIN_H))
fonts = Fonts()
ui = Ui(fonts)
r, a = Renderer(fonts), Audio()
data = store.load()
g = Game(r, a, data)
g.locale_data = lambda: __import__("goldenhour.locales", fromlist=["LOCALES"]).LOCALES[g.locale]
print("boot OK | audio:", a.ok)

def draw(name):
    ui.begin()
    screen.fill(INK)
    g.draw_world(screen, WIN_W, WIN_H)
    getattr(ui, name)(screen, g, WIN_W, WIN_H)

# --- every screen renders ---
for scr, fn in [("title","title"), ("diff","diff"), ("records","records")]:
    g.screen = scr
    draw(fn)
    print("screen", scr, "OK")
g.rec_tab = "ach"; draw("records"); g.rec_tab = "times"
print("screen records/achievements OK")

# --- benchmark the world pass ---
g.start_mode("run")
t0 = time.time(); N = 120
for _ in range(N):
    g.update(1/60)
    screen.fill(INK); g.draw_world(screen, WIN_W, WIN_H)
    ui.begin(); ui.hud(screen, g, WIN_W, WIN_H)
ms = (time.time()-t0)/N*1000
print(f"frame: {ms:.1f} ms  -> {1000/ms:.0f} fps headless")

# --- a full race on every road ---
for loc in ["coast","dunes","ridge","canyon"]:
    g.set_locale(loc); g.start_mode("run")
    n = 0
    while g.phase == "playing" and n < 60*60*3:
        seg = g.track.find(g.pos + g.PLAYER_Z)
        g.steer = max(-1, min(1, (-seg.curve*0.09 - g.player_x)*2.6))
        g.braking = abs(seg.curve) > 4.2 and g.speed > 12000*0.62
        if n % 34 == 0: g.try_swing()
        g.update(1/60); n += 1
    res = g.results
    rows = res["rows"]
    print(f"{loc:7s} P{res['pos']}/{res['of']} score={res['score']:>6,} "
          f"clean={g.clean} hits={g.hits} pass={g.overtakes} "
          f"gaps={[None if x['gap'] is None else round(x['gap'],2) for x in rows[1:4]]}")
    draw("results")

# --- zen + daily ---
g.start_mode("zen")
for _ in range(60): g.update(1/60)
g.finish(); draw("results"); print("zen OK, dist", round(g.results["dist_km"],2), "km")
g.start_mode("daily", "easy")
for _ in range(120): g.update(1/60)
ui.begin(); ui.hud(screen, g, WIN_W, WIN_H)
print("daily guided OK (map + callout drawn)")

# --- persistence ---
d2 = store.load()
print("records saved:", sorted(d2["records"].keys()))
print("achievements:", sorted(d2["achievements"]["won"].keys()))
pygame.quit()
print("ALL OK")
