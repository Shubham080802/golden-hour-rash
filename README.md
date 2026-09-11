# Golden Hour Rash

A stress-relief motorcycle combat racer. Road Rash's catharsis with Road Rash's
punishment deleted.

```bash
pip install -r requirements.txt
python main.py
```

```
← →  or A/D   steer
↓    or S     brake
J or Space    swing
Esc           pause / end ride
M             music on / off
R             record room (title screen)
1 / 2 / 3     Run / Zen / Daily
```

---

## The design thesis

Road Rash was not a stress-relief game. It was punishing — you fell off, jogged
back to your bike, watched the pack vanish, lost the race. The catharsis was in
the *hitting*; the stress was in the *losing*.

The whole product is one inversion: **keep the violence, delete the punishment.**

- **You cannot lose a run.** A wipeout costs speed and your combo, never the
  run. Instant remount, no jogging back, no getting busted.
- **The clock is a progress bar, not a countdown.** Same information, opposite
  feeling: one says "time is running out", the other says "the song is playing".
- **The pack rubber-bands back to you**, so there is always someone in reach.
- Every cost is charged to your *score*, never to your ability to keep riding.

## Modes

| Mode | What's at stake |
|---|---|
| **Run** | One song, one road, one score. Nothing else. |
| **Zen** | No rivals, no timer, no score. Just the road and a slow pad. |
| **Daily** | The same seeded road for everyone, split Guided / Blind. |

Daily takes its road from the date, so the board stays comparable. **Guided**
gives a road map and rally-style corner calls; **Blind** gives you nothing.
They keep separate records, so difficulty is a choice rather than a handicap.

## Roads

Each locale owns its palette, road surface, scenery, terrain profile and music.

| Road | Terrain | Surface | Music |
|---|---|---|---|
| **Golden Coast** | Rolling hills, long sweepers | Marked asphalt, guardrails | A minor, four on the floor, 126 bpm |
| **Salt & Sand** | Flat and fast | Bare sand, no markings or rails | D major, half-time, 116 bpm |
| **Ridge Pass** | One sustained climb and descent per lap, hairpins | Cold wet asphalt | E phrygian, 132 bpm |
| **Dry Canyon** | Fast straights, wide sweepers | Dusty asphalt, no rails | A blues, swung sixteenth, 128 bpm |

Zen keeps the road's key so it still sounds like that place, but drops the kit
for root, fifth and a long pad at 76 bpm.

## The pack

Five named riders, colour-matched to their dot on the standings.

| | Reads ahead | Pushes | Corners | Wants a fight |
|---|---|---|---|---|
| **MARLA** | furthest | hard | cleanest | some |
| **HOYT** | far | little | clean | rarely |
| **VEX** | short | hardest | badly | often |
| **DIZZY** | shortest | some | badly | some |
| **KADE** | mid | hard | ok | always |

They are not on rails. Each only reads the road as far ahead as their own
look-ahead, fights the same centrifugal force you do, hits the same traffic and
pays the same price for running wide. **Mistakes are emergent, not scripted**:
carry more speed into a corner than your skill supports and the corner throws
you off the outside. Pass one and they get a fightback timer — more nerve, more
corner risk, and far more willingness to come looking for you.

## Scoring

| Event | Points |
|---|---|
| Near miss | 70 |
| Airtime off a crest | 60 |
| Clean corner held at speed | 90 |
| Hit a rival | 130 |
| Overtake | 180 |
| Knockdown — a hit that puts them in the dirt | 260 |
| **Perfect run** | **2,500** |

A **perfect run** is a whole race with no traffic contact, no rival landing one
on you and no wheel off the road. A pip in the HUD tracks it live.

Fifteen **achievements** persist and appear in the record room.

## Classification and records

A run ends when the song ends, not at a finish line, so a "gap" needs a
definition. Every racer records a distance/time trace, and the gap to the leader
is **the time at which the leader was at your final distance** — exactly what a
timing screen reports at a real finish. Results show position, gap, interval to
the rider ahead, top speed, and the run's **fastest kilometre**.

The **record room** (press R) keeps a top ten by score and a top ten by fastest
kilometre for every road and format — two capped lists, because ranking by score
alone would bound the split table to whatever those ten runs happened to do.

Everything is saved to `~/.golden-hour-rash/save.json`.

## Layout

```
main.py                 entry point
goldenhour/
  config.py             constants, colour helpers, the scoring table
  locales.py            the four roads: palette, terrain, scenery, music
  track.py              seeded generation (mulberry32), segments
  racers.py             traffic, rival AI, timing-trace maths
  render.py             pseudo-3D projection and all drawing
  ui.py                 HUD and screens
  audio.py              procedural synthesis and the sequencer
  store.py              JSON persistence
  achievements.py       definitions and checking
  game.py               state, physics, world render pass
tools/smoke.py          headless self-test — renders every screen and races
web/index.html          the original browser build, kept for reference
```

Run the self-test without a display:

```bash
python tools/smoke.py
```

## Technical notes

- **Rendering** — segment-based pseudo-3D road projection, the technique OutRun
  and Road Rash used. No real geometry anywhere. Depth fog is baked into the
  road's own colours via a per-locale lookup table across 22 depth bands.
- **Audio** — no sound files. Every tone is a waveform synthesised into a numpy
  buffer; every drum is shaped noise. Buffers are cached at unit gain and their
  level set per play.
- **Tracks** — seeded generation, so a given seed always produces the same road.
- **Assets** — none. Every bike, rider, car, palm, pine, cactus and mesa is
  drawn from primitives at runtime.

Dependencies: `pygame` and `numpy`.

### Differences from the browser build

The browser original is kept in `web/`. Porting changed four things:

- Canvas has gradients; pygame does not. The sky is pre-rendered to a cached
  surface and vehicle shading is approximated with flat bands.
- Canvas fades distant sprites with alpha; here they are mixed toward the
  horizon colour, which costs nothing and reads the same.
- Web Audio scheduled notes against its own clock with a lookahead; the
  sequencer here advances off the frame clock.
- The shared Daily leaderboard needed a server the browser build got for free.
  Offline, Daily records are local like the rest.

## Known gaps

This is a vertical slice built to answer one question — *is the loop fun?*

- **Combat is the thinnest part** and the whole product rests on it. A swing is
  a proximity check with hit-stop. Rivals have no memory: nobody holds a grudge
  after you hit them.
- **No real 3D.** Getting to genuinely realistic graphics means a 3D engine and,
  the real cost, an artist. Do not spend that until the loop is proven.
- No bike progression, damage model or unlocks.
- Fonts fall back to whatever the system has (Impact, Menlo and friends) rather
  than shipping their own.
