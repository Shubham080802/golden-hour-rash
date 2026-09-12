"""Post-processing.

The world is drawn into an offscreen surface, optionally larger than the
window, then filtered and resolved down. The interface is drawn afterwards at
native resolution so text stays crisp.

Three effects, all built from `pygame.transform` rather than per-pixel numpy —
scaling is C-speed, and a down-up scale pair is a perfectly good blur:

* supersampling      — draw big, resolve small; the cheapest real anti-aliasing
* bloom              — subtract a threshold, blur what is left, add it back
* speed blur         — successive zooms blended in, ramped by how fast you are

Quality is a runtime setting and falls back on its own if frames get long, so a
slow machine degrades instead of stuttering.
"""
import pygame

LEVELS = ("ultra", "high", "low")
_SS = {"ultra": 1.6, "high": 1.25, "low": 1.0}


class PostFX:
    THRESHOLD = 165      # only genuinely bright pixels are allowed to glow

    def __init__(self, quality="high"):
        self.quality = quality if quality in LEVELS else "high"
        self.auto = True
        self._scene = None
        self._size = None
        self._frame_ms = 16.0
        self._slow_for = 0.0
        self.last_note = ""
        self._note_t = 0.0

    # ---- scene surface ---------------------------------------------------
    def scene_for(self, w, h):
        ss = _SS[self.quality]
        size = (max(1, int(w * ss)), max(1, int(h * ss)))
        if self._size != size:
            self._scene = pygame.Surface(size).convert()
            self._size = size
        return self._scene

    def cycle(self):
        self.quality = LEVELS[(LEVELS.index(self.quality) + 1) % len(LEVELS)]
        self.auto = False            # an explicit choice outranks the governor
        self.note(f"Graphics: {self.quality}")
        return self.quality

    def note(self, text):
        self.last_note = text
        self._note_t = 2.0

    def tick(self, dt, frame_ms):
        """Watch the frame clock and step down a level if we cannot hold 60."""
        self._note_t = max(0.0, self._note_t - dt)
        self._frame_ms += (frame_ms - self._frame_ms) * 0.05
        if not self.auto:
            return
        if self._frame_ms > 21.0 and self.quality != "low":
            self._slow_for += dt
            if self._slow_for > 2.0:
                self._slow_for = 0.0
                self.quality = LEVELS[LEVELS.index(self.quality) + 1]
                self.note(f"Graphics eased to {self.quality} to hold the frame rate")
        else:
            self._slow_for = 0.0

    @property
    def note_alpha(self):
        return min(1.0, self._note_t / 0.6) if self._note_t > 0 else 0.0

    # ---- effects ---------------------------------------------------------
    def bloom(self, scene, strength=1.0):
        """Bright-pass, blur, add back.

        Every expensive step happens on a surface a sixth of the size. Going
        down uses nearest-neighbour (cheap, and about to be blurred anyway);
        only the blur itself is smooth, and coming back up is nearest too
        because a blurred image has no detail left to protect.
        """
        if self.quality == "low" or strength <= 0:
            return
        w, h = scene.get_size()
        sw, sh = max(4, w // 6), max(4, h // 6)
        small = pygame.transform.scale(scene, (sw, sh))
        t = self.THRESHOLD
        small.fill((t, t, t), special_flags=pygame.BLEND_RGB_SUB)
        small = pygame.transform.smoothscale(small, (max(2, sw // 3), max(2, sh // 3)))
        small = pygame.transform.smoothscale(small, (sw, sh))
        glow = pygame.transform.scale(small, (w, h))
        if strength < 1.0:
            glow.set_alpha(int(255 * strength))
        scene.blit(glow, (0, 0), special_flags=pygame.BLEND_RGB_ADD)

    def speed_blur(self, scene, amount):
        """Successive zooms blended over the frame — cheap radial blur that
        costs nothing when you are slow, which is when you would notice it."""
        if self.quality == "low" or amount <= 0.02:
            return
        w, h = scene.get_size()
        for scale, alpha in ((1.010, 82), (1.022, 54)):
            zw, zh = int(w * scale), int(h * scale)
            z = pygame.transform.scale(scene, (zw, zh))   # nearest: it is a blur
            z.set_alpha(int(alpha * amount))
            scene.blit(z, (-(zw - w) // 2, -(zh - h) // 2))

    def resolve(self, scene, screen):
        """Down-sample the supersampled scene into the window."""
        if scene.get_size() == screen.get_size():
            screen.blit(scene, (0, 0))
        else:
            pygame.transform.smoothscale(scene, screen.get_size(), screen)
