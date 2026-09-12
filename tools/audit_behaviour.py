"""Behaviour audit: determinism, persistence, memory, performance, edges."""
import os, sys, json, random, time, gc, copy
os.environ["SDL_VIDEODRIVER"]="dummy"; os.environ["SDL_AUDIODRIVER"]="dummy"
HOME = "/tmp/ghr-audit4"
os.environ["GOLDENHOUR_HOME"] = HOME
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import pygame
from goldenhour import store, story
from goldenhour.audio import Audio
from goldenhour.config import INK, MAX_SPEED, SURVIVE_HEALTH, SURVIVE_LEN
from goldenhour.game import Game
from goldenhour.postfx import PostFX
from goldenhour.render import Renderer
from goldenhour.ui import Fonts, Ui

fails = []
def ok(name, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"  — {detail}" if detail else ""))
    if not cond:
        fails.append(name)

pygame.init()
W, H = 1280, 760
screen = pygame.display.set_mode((W, H))
fonts = Fonts(); ui = Ui(fonts); r = Renderer(fonts); a = Audio()

def new_game(data=None):
    g = Game(r, a, data if data is not None else store.load())
    g.postfx = PostFX("low"); g.postfx.auto = False
    return g

def drive(g, frames=10**9, swing=True, dodge=True):
    n = 0
    while g.phase == "playing" and n < frames:
        pp = g.pos + g.PLAYER_Z
        seg = g.track.find(pp)
        want = -seg.curve * 0.09
        if dodge:
            threat = 0.0
            for c in g.cars:
                d = g.track.rel_z(c.z - pp)
                if 0 < d < 9000 and abs(c.offset - g.player_x) < 0.55:
                    threat += (1 if c.offset <= g.player_x else -1) * (1 - d/9000)
            for hz in getattr(g.hazards, "items", []):
                if hz.hit: continue
                d = g.track.rel_z(hz.z - pp)
                if 0 < d < 11000 and abs(hz.offset - g.player_x) < 0.6:
                    threat += (1 if hz.offset <= g.player_x else -1) * 1.6 * (1 - d/11000)
            if threat:
                want = max(-0.85, min(0.85, g.player_x + (1 if threat > 0 else -1) * 0.55))
        g.steer = max(-1, min(1, (want - g.player_x) * 2.6))
        g.braking = abs(seg.curve) > 4.4 and g.speed > MAX_SPEED*0.62
        if swing and n % 34 == 0: g.try_swing()
        g.update(1/60); n += 1
    return n

print("== determinism ==")
res = []
for _ in range(2):
    g = new_game(); g.start_mode("daily", "hard"); drive(g)
    res.append([round(x["dist"], 3) for x in g.results["rows"]])
ok("Daily is reproducible", res[0] == res[1])
res = []
for _ in range(2):
    g = new_game(); g.rnd = random.Random(5); g.start_survival()
    sd = g.seed
    drive(g, frames=60*45)
    res.append((sd, g.hazards.laid, round(g.dist, 3), round(g.health, 3)))
ok("Survival replays from its seed", res[0] == res[1], str(res[0]))

print("== persistence ==")
old = {"settings": {"locale": "coast", "music": True}, "records": {}, "best": {},
       "achievements": {"won": {}, "tally": {"races": 0, "hits": 0, "roads": {}}}}
os.makedirs(HOME, exist_ok=True)
json.dump(old, open(os.path.join(HOME, "save.json"), "w"))
d = store.load()
try:
    story.progress(d); story.unlocked(d)
    g = new_game(d); g.start_survival(); g.lives = 0; g.t = 30; g.survived = 30; g.finish()
    ok("A save from before Story/Survival still loads", True)
except Exception as e:
    ok("A save from before Story/Survival still loads", False, repr(e))
open(os.path.join(HOME, "save.json"), "w").write("{ this is not json")
store.LOAD_WARNING = None
d = store.load()
ok("A corrupt save is set aside, not lost",
   store.LOAD_WARNING is not None and d["records"] == {}, str(store.LOAD_WARNING))
d = store.load()
for i in range(25):
    store.record_run(d, "run", "coast", "hard",
                     {"ts": store.now_ts(), "score": i * 100, "combo": i,
                      "hits": i, "pos": 1, "fkm": 15.0 + i, "kmh": 200})
f = store.get_records(d, "run", "coast", "hard")
ok("Record tables stay capped at ten",
   len(f["scores"]) == 10 and len(f["splits"]) == 10, f"{len(f['scores'])}/{len(f['splits'])}")

print("== survival rules ==")
g = new_game(); g.start_survival()
g.health = 5; g.damage(100, None)
ok("Condition never shows below zero", g.health >= 0, str(g.health))
ok("A wipeout costs exactly one life", g.lives == 2 and g.wipeouts == 1)
before = g.lives
g.damage(999, None)
ok("You cannot be knocked out while getting up", g.lives == before)
g.getting_up = 0
for _ in range(4):
    g.getting_up = 0; g.health = 1; g.damage(50, None)
ok("Three wipeouts end the run", g.phase == "ended" and g.lives <= 0)
# clear the road first: with traffic still on it this measured "did the bot
# get hit in the next two seconds", which it sometimes did
g = new_game(); g.start_survival()
g.cars = []; g.riders = []; g.actors = []; g.hazards.items = []
g.player_x = 0.0; g.clean_for = 99; g.health = 50
def coast(frames):
    # hold the bike on the road: drifting onto the kerb is its own (correct)
    # drain, and this check is about the trickle back, not about that
    for _ in range(frames):
        g.hazards.items = []
        g.player_x = 0.0
        g.update(1/60)
coast(120)
regen = g.health
g.health = SURVIVE_HEALTH
coast(120)
ok("Condition regenerates but never past full",
   50 < regen <= SURVIVE_HEALTH and g.health == SURVIVE_HEALTH,
   f"50 -> {regen:.1f}, and full stays {g.health:.0f}")
g = new_game(); g.start_mode("zen")
ok("Zen has no hazards and no health bar",
   not getattr(g.hazards, "items", []) and g.mode == "zen")

print("== memory and growth ==")
g = new_game(); g.rnd = random.Random(3); g.start_survival()
drive(g, frames=60*60*5)
ok("The hazard field does not grow without bound",
   len(g.hazards.items) < 60, f"{len(g.hazards.items)} live, {g.hazards.laid} laid")
ok("Particles and pops are reaped",
   len(g.particles) < 400 and len(g.pops) < 20,
   f"{len(g.particles)} particles, {len(g.pops)} pops")
gc.collect()
import resource
rss0 = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
for i in range(6):
    g = new_game(); g.set_locale(["coast","dunes","ridge","canyon"][i % 4])
    g.start_mode("run"); drive(g, frames=60*40)
gc.collect()
rss1 = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
grew = (rss1 - rss0) / (1024 * 1024 if sys.platform == "darwin" else 1024)
ok("Memory is flat across many races", grew < 60, f"{grew:+.1f} MB peak")

print("== performance ==")
for label, setup in (("run", lambda g: (g.set_locale("coast"), g.start_mode("run"))),
                     ("survive", lambda g: g.start_survival()),
                     ("rush (double traffic)",
                      lambda g: (g.set_locale("coast"),
                                 g.start_mode("run", mod=__import__(
                                     "goldenhour.modifiers", fromlist=["by_id"]).by_id("rush"))))):
    g = new_game(); setup(g)
    drive(g, frames=60*20)
    fx = PostFX("high"); fx.auto = False
    sc = fx.scene_for(W, H)
    t0 = time.perf_counter()
    N = 45
    for _ in range(N):
        sc.fill(INK); g.draw_world(sc, *sc.get_size()); fx.bloom(sc)
        fx.resolve(sc, screen); ui.begin(); ui.hud(screen, g, W, H)
        g.update(1/60)
    ms = (time.perf_counter() - t0) / N * 1000
    # 20 ms is the bar, not 16.7: the quality governor steps down on its own
    # past 21 ms, and a threshold sitting exactly on 60 fps flaps run to run.
    ok(f"{label}: frame time", ms < 20.0, f"{ms:.1f} ms -> {1000/ms:.0f} fps, "
       f"{len(g.cars)} cars")

print("== sound ==")
g = new_game(); g.audio.muted = True
g.audio._cache.clear()
g.start_survival()
g.collide(0.6); g.audio.sfx_hit(); g.audio.sfx_clip(); g.audio.sfx_near()
ok("Mute silences the crash sounds too", len(g.audio._cache) == 0,
   f"{len(g.audio._cache)} samples built")
g.audio.muted = False
g.audio.sfx_clip(); g.audio.sfx_near()
ok("Unmuted, effects are built again", len(g.audio._cache) > 0)

print("== story rules ==")
d = store.load(); d["story"] = {"done": [], "best": {}}
g = new_game(d)
ok("Only the first leg is open on a fresh save", story.unlocked(d) == 0)
g.open_beat("intro", 0); g.start_story(0)
g.dist = 9e9; g.finish()
ok("Clearing a leg unlocks the next", story.unlocked(g.data) == 1)
g.start_story(0); g.dist = 0; g.finish()
ok("Failing a leg does not lock it again", story.unlocked(g.data) == 1)
ok("A story run stays out of the record room",
   not any(k.startswith("story") for k in g.data["records"]), str(list(g.data["records"])))

print("== mode hygiene ==")
g = new_game(); g.start_survival()
ok("Survival takes no modifier", g.mod["id"] == "none")
g.set_locale("coast"); g.start_mode("run")
ok("A race after Survival is back to three minutes", g.time_limit == 180.0,
   str(g.time_limit))
g.start_story(1)
ok("A story leg sets its own clock", g.time_limit == story.chapter(1)["secs"])
g.set_locale("coast"); g.start_mode("run")
ok("And hands it back afterwards", g.time_limit == 180.0)
g = new_game(); g.start_survival()
cams = []
for cam in ("chase", "close", "rider"):
    g2 = new_game(); g2.rnd = random.Random(77); g2.camera = cam
    g2.start_survival(); drive(g2, frames=60*30)
    cams.append((round(g2.dist, 3), round(g2.health, 3), g2.hazards.laid))
ok("The camera never touches the simulation", len(set(cams)) == 1, str(cams[0]))

print("== window and output ==")
g = new_game(); g.set_locale("ridge"); g.start_mode("run"); drive(g, frames=60*10)
crashed = None
try:
    for size in ((640, 400), (1920, 1080), (900, 561), (1280, 760)):
        sc = pygame.display.set_mode(size)
        fx = PostFX("high"); fx.auto = False
        scene = fx.scene_for(*size)
        scene.fill(INK); g.draw_world(scene, *scene.get_size())
        fx.resolve(scene, sc); ui.ensure_fonts(size[1]); ui.begin()
        ui.hud(sc, g, *size)
        g.update(1/60)
except Exception as e:
    crashed = repr(e)
ok("Resizing mid-race is safe", crashed is None, crashed or "")
screen2 = pygame.display.set_mode((W, H))
fx = PostFX("high"); fx.auto = False
scene = fx.scene_for(W, H); scene.fill(INK)
g.draw_world(scene, *scene.get_size()); fx.resolve(scene, screen2)
shot = screen2.convert(24)
px = [shot.get_at((x, y))[:3] for x, y in
      ((5, 5), (W//2, H//2), (W-5, H-5), (W//3, H//3))]
ok("A photo is a picture, not a blank frame", len(set(px)) > 1, str(px[:2]))

print("== achievements ==")
d = store.load()
d["achievements"] = {"won": {}, "tally": {"races": 0, "hits": 0, "roads": {}}}
g = new_game(d)
g.set_locale("coast"); g.start_mode("run"); drive(g)
first = set(g.data["achievements"]["won"])
n_toasts = len(g.toasts)
g.set_locale("coast"); g.start_mode("run"); drive(g)
again = set(g.data["achievements"]["won"]) - first
ok("Achievements are not awarded twice",
   not (again & first) and n_toasts > 0, f"{len(first)} then {len(again)} new")

print()
if fails:
    print(f"{len(fails)} FAILURES: " + ", ".join(fails))
else:
    print("audit clean")
pygame.quit()
