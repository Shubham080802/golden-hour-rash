# Golden Hour Rash

A stress-relief motorcycle combat racer. Road Rash's catharsis with Road Rash's
punishment deleted.

```bash
pip install -r requirements.txt
python main.py
```

```
← →  or A/D   steer          (or a gamepad's left stick)
↓    or S     brake          (or B / left trigger)
J or Space    swing          (or A / X)
Esc           pause / end ride
M             sound on / off (music and effects)
F             graphics quality
C             reduced motion on / off
P             photo mode — writes a PNG with no interface
V             camera view
D             difficulty (title screen)
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

Daily takes its road from the date, so the board stays comparable. Everything
that moves a racer draws from a stream seeded by the track, so the same seed
really is the same race — verified by running one twice with identical inputs
and diffing the finishing distances. **Guided**
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

## Cameras

**V** cycles the view at any time, mid-race included.

| | |
|---|---|
| **Chase** | Behind and above. The whole machine, the most road. |
| **Close** | Dropped in and tucked up behind the rider's shoulders. |
| **Rider** | From the saddle: screen, bar ends, mirrors and gloves, nothing else. |

The camera is a camera. `forward` slides the eye along the line between the
chase position and the bike, `height` scales the eye height, and neither is
allowed anywhere near the simulation — collisions and rival distances are
always measured from the bike. Racing an identical seed through all three
views returns the same finishing position, score, hit count and distance to
the unit.

## Difficulty

**D** on the title screen cycles the field. It lifts the rivals' cornering
skill, nerve and appetite for a fight together, so a harder race is a field of
better riders rather than a field with more horsepower — and a landed punch
sets a better rider back less, otherwise the race is decided by the first two
hits.

Measured over twenty races per level, every level racing the same roads and
seeds:

| | win | podium | mean finish |
|---|---|---|---|
| **Steady** | 50% | 80% | 1.9 |
| **Racer** (default) | 35% | 75% | 2.4 |
| **Ruthless** | 25% | 60% | 3.0 |

Those are a bot's numbers, and it reads corners with no reaction time while
never dodging traffic — treat them as the shape of the ladder, not as your
own odds.

Daily always runs at **Racer** whatever your setting is. A shared board cannot
mean anything if the field is softer for some players than others.

## The pack

Nine named riders and you — a field of ten, each colour-matched to their dot on
the standings. The base colours are the Okabe-Ito set, which stays
distinguishable under the common forms of colour blindness; the four added for
the larger field were picked to stay separable alongside it.

| | Reads ahead | Pushes | Corners | Wants a fight |
|---|---|---|---|---|
| **SABLE** | furthest | hard | cleanest | some |
| **MARLA** | furthest | hard | very clean | some |
| **HOYT** | far | little | clean | rarely |
| **PIKE** | mid | hard | ok | nearly always |
| **KADE** | mid | hard | ok | always |
| **JUNO** | mid | some | ok | sometimes |
| **TORO** | short | hard | ok | often |
| **VEX** | short | hardest | badly | often |
| **DIZZY** | shortest | some | badly | some |

**SABLE** and **MARLA** are the two you will struggle with: they read the road
furthest ahead and hold a line you cannot match on pace alone. The five in the
middle are pitched at your level — you will beat them on a good lap and lose to
them on a scruffy one. **VEX** and **DIZZY** have the fastest hands and the
worst heads; they will be alongside you early and in the dirt by the flag.

The grid is ordered by pace, quickest furthest up the road, so the riders get
harder in the order you reach them.

Everyone fights everyone. A rival in reach of another rival will swing at them
rather than wait for you, and take the same stagger, speed loss and lost ground
you do — softened, because the pack roughing each other up is texture, not a
second way for you to win. Over a race you will see places change ahead of you
that you had nothing to do with.

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
| Clean run — two contacts or fewer | 800 |
| **Perfect run** — none at all | **2,500** |

A pip in the HUD tracks contact live, so the run always has something to
protect. **Clean run** is the reachable tier; **perfect** asks for a whole
race with no traffic contact, no rival landing one on you and no excursion
off the road, and is meant to be rare. Brushing the shoulder through an apex
does not count — only being off the road for a fifth of a second does.

Fifteen **achievements** persist and appear in the record room.

A **rear view** above the road shows who is behind you and on which shoulder —
the standings tell you a rival is close, this tells you which side to expect
them. A ring around a marker means they are coming for the place back.

## Run modifiers

Before a **Run** you are offered three cards and take one. Every card is a
trade rather than an upgrade, so the choice is a choice:

| | |
|---|---|
| **Glass Cannon** | Double points. The combo decays twice as fast. |
| **Rush Hour** | Twice the traffic. Near misses pay triple. |
| **Grudge Match** | Every rival rides angry all race. Hits pay double. |
| **Tailwind** | Twelve percent more top speed. Corners punish twice as hard. |
| **Featherweight** | Traffic barely slows you. No perfect-run bonus. |
| **Unbroken** | The combo never times out. Any contact wipes it to zero. |
| **Breakaway** | Start mid-pack instead of last. Rivals are five percent quicker. |
| **Straight Up** | No modifier. The road as it comes. |

Daily never offers them — that board has to stay comparable.

## Photo mode and comfort

**P** writes the current frame, without any interface, to
`~/.golden-hour-rash/photos/`. **C** turns off camera bounce and speed blur for
anyone who would rather not have them. A gamepad rumbles on landed hits and
collisions.

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

## Graphics pipeline

The world is drawn into an offscreen surface, filtered, then resolved into the
window. The interface is drawn afterwards at native size so text stays sharp.

- **Supersampling** — draw big, resolve small. The cheapest real anti-aliasing
  there is, and it removes the jagged diagonals a road is made of.
- **Bloom** — bright-pass, blur, add back. Every expensive step happens on a
  surface a sixth of the size; going down and coming back up use nearest
  neighbour, because a blurred image has no detail left to protect. Only the
  blur itself is smooth.
- **Speed blur** — successive zooms blended over the frame, ramped by how fast
  you are going, so it costs nothing when you are slow.
- **Airborne atmosphere** — dust, spray and mist streaming radially out of the
  vanishing point, per road. One list of floats, and it sells motion better
  than anything else at the price.

`F` cycles **low / high / ultra**. The setting persists, and if frames start
running long the game eases itself down a level rather than stuttering.

Measured in software rendering at 1000×640: low **330 fps**, high **99 fps**,
ultra **73 fps**. Hardware surfaces will do better.

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
- **Input** — keyboard or gamepad; an analogue stick gives finer steering than
  a key ever can.

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
