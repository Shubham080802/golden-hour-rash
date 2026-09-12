import os, sys, time
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
print("boot OK | audio:", a.ok)

def draw(name):
    ui.begin()
    screen.fill(INK)
    if name == "beat" and g.beat:
        g.cinema.paint(screen, WIN_W, WIN_H, g.beat["spec"], g.beat["t"])
    else:
        g.draw_world(screen, WIN_W, WIN_H)
    getattr(ui, name)(screen, g, WIN_W, WIN_H)

# --- every screen renders ---
for scr, fn in [("title","title"), ("diff","diff"), ("records","records")]:
    g.screen = scr
    draw(fn)
    print("screen", scr, "OK")
g.rec_tab = "ach"; draw("records"); g.rec_tab = "times"
print("screen records/achievements OK")
g.open_mods(); draw("mods"); print("screen mods OK")

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
    while g.phase == "playing" and n < 60*60*5:
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

# --- every modifier, end to end ---
from goldenhour.modifiers import MODIFIERS, NONE
for m in MODIFIERS + [NONE]:
    g.set_locale("coast"); g.start_mode("run", mod=m)
    n = 0
    while g.phase == "playing" and n < 60*60*5:
        seg = g.track.find(g.pos + g.PLAYER_Z)
        g.steer = max(-1, min(1, (-seg.curve*0.09 - g.player_x)*2.6))
        if n % 34 == 0: g.try_swing()
        g.update(1/60); n += 1
    print(f"  mod {m['id']:9s} P{g.results['pos']}/{g.results['of']} "
          f"score={g.results['score']:>7,} cars={len(g.cars)} "
          f"perfect={g.results['perfect']}")

# --- zen + daily ---
g.start_mode("zen")
for _ in range(60): g.update(1/60)
g.finish(); draw("results"); print("zen OK, dist", round(g.results["dist_km"],2), "km")
g.start_mode("daily", "easy")
for _ in range(120): g.update(1/60)
ui.begin(); ui.hud(screen, g, WIN_W, WIN_H)
print("daily guided OK (map + callout drawn)")

# --- story mode: every leg, both beats, and the goals it judges them by ---
from goldenhour import story
g.open_journey(); draw("journey"); print("screen journey OK")
for i, ch in enumerate(story.CHAPTERS):
    g.open_beat("intro", i)
    for _ in range(int(60 * 1.5)): g.update(1/60)
    draw("beat")                                   # mid-typewriter
    g.beat["t"] = g.beat_len() + 1
    draw("beat")                                   # settled, with its button
    g.start_story(i)
    n = 0
    while g.phase == "playing" and n < 60*60*5:
        seg = g.track.find(g.pos + g.PLAYER_Z)
        # This rider dodges. The legs are asserted clearable below, and a
        # rider who drives through every car in the road is not the standard
        # they should be held to.
        want = -seg.curve * 0.09
        pp = g.pos + g.PLAYER_Z
        threat = 0.0
        for c in g.cars:
            d = g.track.rel_z(c.z - pp)
            if 0 < d < 9000 and abs(c.offset - g.player_x) < 0.55:
                threat += (1 if c.offset <= g.player_x else -1) * (1 - d/9000)
        if threat:
            want = max(-0.75, min(0.75, g.player_x + (1 if threat > 0 else -1) * 0.55))
        g.steer = max(-1, min(1, (want - g.player_x)*2.6))
        g.braking = abs(seg.curve) > 4.2 and g.speed > 12000*0.62
        if n % 34 == 0: g.try_swing()
        if n % 300 == 0: ui.begin(); ui.hud(screen, g, WIN_W, WIN_H)
        g.update(1/60); n += 1
    res = g.results
    draw("results")
    g.open_beat("outro", i)
    for _ in range(30): g.update(1/60)
    draw("beat")
    print(f"  leg {i+1} {ch['id']:11s} {'PASS' if res['passed'] else 'FAIL'}"
          f"  {res['detail']:<28} score={res['score']:>7,}"
          f"  riders={len(g.riders)} cars={len(g.cars)}")
    # A leg the self-test's own rider cannot clear is a leg out of tune, and
    # this rider does not even dodge.
    assert res["passed"], f"leg {ch['id']} is not clearable: {res['detail']}"
st = store.load().get("story", {})
print("story progress:", st.get("done"))
assert len(st.get("done", [])) == len(story.CHAPTERS), "a leg failed to record"
assert all(ch["id"] in st.get("best", {}) for ch in story.CHAPTERS), "a best went missing"

# --- persistence ---
d2 = store.load()
print("records saved:", sorted(d2["records"].keys()))
print("achievements:", sorted(d2["achievements"]["won"].keys()))
pygame.quit()
print("ALL OK")
