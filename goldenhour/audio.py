"""Procedural audio.

There are no sound files. Every tone is a waveform synthesised into a numpy
buffer and handed to pygame.mixer; every drum is shaped noise. Buffers are
cached at unit gain and their level is set per play, so the same note fired a
hundred times costs one allocation.

The browser build scheduled notes against the Web Audio clock with a
lookahead. Here the sequencer advances off the frame clock instead, which is
simpler and, at a sixteenth every ~120 ms, close enough not to hear.
"""
import math

import numpy as np
import pygame

RATE = 44100

KICKS = {"four": (0, 8, 11), "drive": (0, 6, 8, 14), "shuffle": (0, 8), "soft": (0, 8)}


def _env(n, decay=6.0):
    """Exponential decay envelope."""
    return np.exp(-np.linspace(0.0, decay, n))


def _wave(kind, freq, n, f_end=None):
    t = np.arange(n, dtype=np.float32) / RATE
    if f_end and f_end != freq:
        # exponential glide, used for the kick
        k = np.exp(np.linspace(math.log(freq), math.log(max(1.0, f_end)), n))
        phase = np.cumsum(k) * (2 * math.pi / RATE)
    else:
        phase = 2 * math.pi * freq * t
    if kind == "sine":
        return np.sin(phase)
    if kind == "square":
        return np.sign(np.sin(phase))
    if kind == "saw":
        return 2.0 * ((phase / (2 * math.pi)) % 1.0) - 1.0
    # triangle
    return 2.0 * np.abs(2.0 * ((phase / (2 * math.pi)) % 1.0) - 1.0) - 1.0


class Audio:
    """Owns the mixer, the sample cache and the sequencer."""

    def __init__(self):
        self.ok = False
        self.muted = False
        self.music_on = False
        self.bpm = 126
        self.step = 0
        self.acc = 0.0
        self.locale = None
        self.beat = 0.0
        self._cache = {}
        self._fade = 1.0
        self._fading = 0.0
        try:
            pygame.mixer.pre_init(RATE, -16, 2, 512)
            pygame.mixer.init()
            pygame.mixer.set_num_channels(48)
            self.ok = True
        except pygame.error:
            self.ok = False  # dummy audio driver, or no device — game still runs

    # ---- sample construction ------------------------------------------
    def _sound(self, key, build):
        """Build and cache one sample.

        Returns None if the mixer has gone away underneath us — a device can
        disappear mid-session (headphones unplugged, output switched), and
        the game carrying on in silence beats it dying in a crash handler.
        """
        snd = self._cache.get(key)
        if snd is None:
            try:
                mono = build().astype(np.float32)
                peak = float(np.max(np.abs(mono))) or 1.0
                mono = (mono / peak * 0.85 * 32767).astype(np.int16)
                stereo = np.repeat(mono[:, None], 2, axis=1)
                snd = pygame.sndarray.make_sound(np.ascontiguousarray(stereo))
            except (pygame.error, ValueError):
                self.ok = False
                return None
            self._cache[key] = snd
        return snd

    def _play(self, snd, vol):
        if snd is None:
            return
        try:
            ch = pygame.mixer.find_channel(True)
            if ch:
                ch.set_volume(min(1.0, vol))
                ch.play(snd)
        except pygame.error:
            self.ok = False

    def tone(self, kind, freq, dur, gain, f_end=None, music=True):
        if not self.ok or gain <= 0:
            return
        if self.muted:
            return
        vol = gain * (self._fade if music else 1.0)
        if vol <= 0.001:
            return
        n = max(64, int(dur * RATE))
        key = ("t", kind, round(freq, 2), round(dur, 3), round(f_end or 0, 2))
        snd = self._sound(key, lambda: _wave(kind, freq, n, f_end) * _env(n))
        self._play(snd, vol)

    def noise(self, dur, gain, tilt=1.0, music=True):
        """`tilt` above 1 brightens (hats), below 1 dulls (snare, thuds)."""
        if not self.ok or gain <= 0:
            return
        if self.muted:
            return
        vol = gain * (self._fade if music else 1.0)
        if vol <= 0.001:
            return
        n = max(64, int(dur * RATE))
        key = ("n", round(dur, 3), round(tilt, 2))

        def build():
            rng = np.random.default_rng(1234)
            x = rng.standard_normal(n)
            if tilt < 1.0:  # dull it with a moving average
                k = max(2, int(8 / max(0.05, tilt)))
                x = np.convolve(x, np.ones(k) / k, mode="same")
            elif tilt > 1.0:  # brighten by differencing
                x = np.diff(np.concatenate([[0.0], x]))
            return x * _env(n, 9.0)

        snd = self._sound(key, build)
        self._play(snd, vol)

    # ---- music ---------------------------------------------------------
    def start_music(self, locale, zen):
        self.locale = locale
        self.bpm = 76 if zen else locale["bpm"]
        self.zen = zen
        self.step = 0
        self.acc = 0.0
        self.music_on = True
        self._fade = 0.0
        self._fading = 1.0

    def stop_music(self):
        """Silence the sequencer at once; only the level fade is gradual.

        The browser build left the sequencer running through the fade, which
        let a finished race keep playing over the menus. Stopping here means
        stopped.
        """
        self.music_on = False
        self._fading = -1.0

    def update(self, dt):
        if self._fading > 0:
            self._fade = min(1.0, self._fade + dt * 1.6)
        elif self._fading < 0:
            self._fade = max(0.0, self._fade - dt * 2.5)
        self.beat = max(0.0, self.beat - dt * 5)
        if not self.music_on or not self.ok:
            return
        step16 = (60.0 / self.bpm) / 4
        self.acc += dt
        guard = 0
        while self.acc >= step16 and guard < 8:
            self.acc -= step16
            self._play_step(self.step, step16)
            self.step += 1
            guard += 1

    def _play_step(self, i, step16):
        m = self.locale["music"]
        s = i % 16
        bar = (i // 16) % 4
        root = m["roots"][bar]
        scale = m["scale"]

        if self.zen:
            # Zen keeps the road's key so it still sounds like this place,
            # but drops the kit: root, fifth and a long pad.
            if s == 0:
                self.tone("sine", root * 0.5, 3.6, 0.17)
                self.tone("tri", root * 2, 3.4, 0.05)
                self.tone("tri", root * 3.01, 3.0, 0.032)
                self.beat = 1.0
            elif s == 8:
                self.tone("sine", root * 0.5, 0.6, 0.11, f_end=root * 0.375)
            elif s in (4, 12):
                n = scale[(i // 4) % len(scale)]
                self.tone("sine", n, 1.8, 0.045)
            return

        d = m["drive"]

        if s in KICKS[m["drums"]]:
            self.tone("sine", 128, 0.24, 0.34 + d * 0.32, f_end=42)
            if s in (0, 8):
                self.beat = 1.0

        if m["drums"] == "soft":
            if s == 12:
                self.noise(0.16, 0.09, 0.6)
        elif s in (4, 12):
            self.noise(0.13, 0.10 + d * 0.10, 0.8)

        if m["drums"] == "drive":
            self.noise(0.028, 0.030 + d * 0.022, 2.0)
        elif m["drums"] == "soft":
            if s % 4 == 2:
                self.noise(0.045, 0.028, 1.6)
        elif s % 2 == 0:
            self.noise(0.035, 0.045, 1.8)

        if s % 2 == 0:
            octv = 2 if (d > 0.6 and s in (6, 14)) else 1
            self.tone(m["bass"], root * octv,
                      0.26 if m["drums"] == "soft" else 0.15, 0.14 + d * 0.09)

        play_lead = (s % 4 == 1) if m["drums"] == "soft" else (s % 2 == 1 and (bar != 1 or s > 7))
        if play_lead:
            n = scale[m["lead"][i % 16] % len(scale)] * (1.5 if bar == 2 else 1)
            self.tone(m["leadw"], n, 0.22 if m["drums"] == "soft" else 0.11,
                      0.028 + d * 0.035)

        if s == 0:
            self.tone(m["pad"], root * 2, 2.2 if m["drums"] == "soft" else 1.5,
                      0.030 + d * 0.022)

    # ---- effects --------------------------------------------------------
    # Mute silences these too. Keeping crash and punch sounds alive through a
    # mute was a nice idea on paper and wrong in practice: pressing mute and
    # still hearing the game reads as a bug, not a feature.
    def sfx_hit(self):
        self.noise(0.16, 0.50, 0.5, music=False)
        self.tone("square", 180, 0.14, 0.30, f_end=60, music=False)

    def sfx_whiff(self):
        self.noise(0.14, 0.09, 2.2, music=False)

    def sfx_near(self):
        self.noise(0.30, 0.11, 1.4, music=False)

    def sfx_bump(self):
        self.noise(0.22, 0.32, 0.5, music=False)
        self.tone("sine", 90, 0.20, 0.22, f_end=40, music=False)

    def sfx_clip(self):
        self.noise(0.26, 0.40, 0.4, music=False)
        self.tone("saw", 150, 0.26, 0.24, f_end=55, music=False)

    def sfx_air(self):
        self.tone("sine", 500, 0.20, 0.10, f_end=900, music=False)
