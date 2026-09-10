# Golden Hour Rash

A playable prototype of a stress-relief motorcycle combat racer. Road Rash's catharsis
with Road Rash's punishment deleted.

Open `index.html` in a browser. No build step, no dependencies, no assets.

```
← →     steer
↓       brake
J/Space swing
Esc     pause / end ride
```

Turn sound on — the run is scored to a procedurally generated track and the road
pulses on the kick.

---

## The design thesis

Road Rash was not a stress-relief game. It was punishing — you fell off, jogged back
to your bike, watched the pack vanish, lost the race. The catharsis was in the
*hitting*; the stress was in the *losing*.

The whole product is one inversion: **keep the violence, delete the punishment.**

- **You cannot lose a run.** A wipeout costs speed and your combo, never the run.
  Instant remount, no "run back to your bike", no getting busted.
- **The clock is a progress bar, not a countdown.** Same information, opposite
  feeling: one says "time is running out", the other says "the song is playing".
- **The pack rubber-bands back to you**, so there is always someone in reach to hit.
- Every cost in the game is charged to your *score*, never to your position or your
  ability to keep riding.

## Modes

| Mode | What's at stake |
|---|---|
| **Run** | One song, one road, one score. Nothing else. |
| **Zen** | No rivals, no timer, no score, no meter. Just the road and a slow pad. |
| **Daily** | Everyone gets the same seeded road, traffic and location. Shared board. |

### Competition without the stress

Daily is the only competitive mode, and it is deliberately **asynchronous**: you
chase a number, never another person in real time, never on a clock. Unlimited
attempts, and a posted score only ever moves up — a worse run cannot cost you your
place.

It splits into **Guided** (road map on the right, rally-style corner calls before
every turn) and **Blind** (nothing but the road). These keep **separate boards**, so
difficulty is a choice rather than a handicap, and Guided works as the on-ramp where
you learn today's seed before riding it blind for the higher board.

## Roads

Each locale owns its palette, sky, road surface, scenery *and* terrain profile, so
the roads differ in shape, not just colour.

| Road | Terrain | Surface |
|---|---|---|
| **Golden Coast** | Rolling hills, long sweepers | Marked asphalt, guardrails |
| **Salt & Sand** | Flat and fast, long straights | Bare sand — no markings, no rails |
| **Ridge Pass** | One sustained climb and descent per lap, hairpins | Cold wet asphalt |
| **Dry Canyon** | Fast straights, wide sweepers | Dusty asphalt, no rails |

Ridge Pass replaces random hills with a sine over the whole track, which is what
makes it read as a mountain pass rather than as bumpy ground.

## The pack

Five named riders with distinct personalities — colour-matched to their dot on the
standings so you learn to recognise them on the road.

| | Reads ahead | Pushes | Corners | Wants a fight |
|---|---|---|---|---|
| **MARLA** | furthest | hard | cleanest | some |
| **HOYT** | far | little | clean | rarely |
| **VEX** | short | hardest | badly | often |
| **DIZZY** | shortest | some | badly | some |
| **KADE** | mid | hard | ok | always |

They are not on rails. Each rider only reads the road as far ahead as their own
look-ahead distance, fights the same centrifugal force you do, hits the same traffic,
and pays the same price for running wide. **Mistakes are emergent, not scripted**:
carry more speed into a corner than your skill supports and the corner throws you off
the outside.

Standings rank on **total ground covered**, which on a looping endless road is the
only definition that stays honest — and it means a rival's gap number is exactly the
distance you can see between you.

## Technical notes

Single file, ~2500 lines, zero dependencies.

- **Rendering** — segment-based pseudo-3D road projection (the *Lou's Pseudo 3D Games
  Guide* / Jake Gordon technique), Canvas 2D. Every sprite is drawn from primitives;
  there are no image assets.
- **Depth fog** — baked into the road's own colours via a per-palette lookup table
  across 22 depth bands, so the road recedes *because it is far away* rather than
  being hidden behind a curtain drawn in front of it.
- **Audio** — fully procedural WebAudio. Kick, snare, hat, bass, arp and pad
  scheduled on a 16th-note lookahead clock. No audio files. BPM is per-locale.
- **Tracks** — seeded generation (mulberry32). The Daily seed is derived from the
  date, so every player gets a byte-identical road.
- **Fonts** — Anton (display), IBM Plex Sans Condensed (UI), IBM Plex Mono (data),
  loaded from Google Fonts. Everything else ships in the file.

### Daily leaderboard

The board uses the Claude Artifacts `db` runtime capability when the page is served
inside a claude.ai artifact. Anywhere else — including this repository — that call
resolves to `null` and the board falls back to per-device `localStorage`. This is
handled gracefully; the footer says which mode it is in.

For a real deployment this is the one piece that needs a backend: a keyed
`{date, difficulty, handle} → score` store with a top-N query. Nothing else in the
game needs a server.

## Known gaps

This is a vertical slice built to answer one question — *is the loop fun?* — and it
deliberately stops there.

- **Combat is the thinnest part** and it is what the whole product rests on. A swing
  is a proximity check with hit-stop. It lands, but the rivals have no memory: nobody
  holds a grudge after you hit them. That is the next thing to build.
- **No real 3D.** This is a 1990 technique dressed as well as it can be dressed.
  Actual realism needs WebGL, real geometry, lighting and — the real cost — an
  artist. Do not spend that until the loop is proven.
- No bike progression, no damage model, no unlocks, no persistence beyond a local
  personal best.
- Touch controls exist but are minimal; this genre wants a gamepad or a keyboard.

## Intended platform

PC/Steam first, premium (~$10), no ads, no live-ops. Browser demo for reach.
Mobile only later — touch controls fight this genre.
