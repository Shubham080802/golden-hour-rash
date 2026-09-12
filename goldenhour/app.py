"""Golden Hour Rash — the application: window, event loop and frame.

Run it with ``golden-hour-rash``, ``python -m goldenhour``, or
``python main.py`` from a checkout.

Controls: arrows or A/D steer, down or S brakes, J or space swings,
Esc pauses or ends the ride, M mutes the music, R opens the record room.
"""
import pygame

from . import store
from .audio import Audio
from .config import FPS, INK, MAX_SPEED, WIN_H, WIN_W
from .game import Game
from .postfx import PostFX
from .render import Renderer
from .ui import Fonts, Ui


def dispatch(g, action):
    """One place where every button and key ends up."""
    if not action:
        return
    kind, val = action
    if kind == "locale":
        g.set_locale(val)
    elif kind == "mode":
        if val == "daily":
            g.audio.stop_music()
            g.screen = "diff"
        elif val == "run":
            g.open_mods()
        elif val == "story":
            g.open_journey()
        elif val == "survive":
            g.start_survival()
        else:
            g.start_mode(val)
    elif kind == "mod":
        from .modifiers import by_id
        g.start_mode("run", mod=by_id(val))
    elif kind == "diff":
        g.start_mode("daily", val)
    elif kind == "screen":
        g.audio.stop_music()
        if val == "title" and g.phase != "title":
            g.start_attract()
        else:
            g.screen = val
        if val == "records":
            g.rec_road = g.picked_locale
    elif kind == "camera":
        g.postfx.note("Camera: " + g.cycle_camera())
    elif kind == "difficulty":
        from .config import difficulty_name
        g.postfx.note("Field: " + difficulty_name(g.cycle_difficulty()))
    elif kind == "mute":
        g.audio.muted = not g.audio.muted
        g.data["settings"]["music"] = not g.audio.muted
        g.postfx.note("Sound off" if g.audio.muted else "Sound on")
        store.save(g.data)
    elif kind == "again":
        if g.mode == "survive":
            g.start_survival()
        elif g.mode == "story":
            g.start_story()
        else:
            g.start_mode(g.mode, g.diff)
    elif kind == "story":
        g.open_beat("intro", val)
    elif kind == "storygo":
        g.start_story()
    elif kind == "storyoutro":
        g.open_beat("outro")
    elif kind == "storynext":
        from .story import CHAPTERS
        g.open_beat("intro", min(g.story_i + 1, len(CHAPTERS) - 1))
    elif kind == "beatskip":
        if g.beat:
            g.beat["t"] = g.beat_len()
    elif kind == "resume":
        g.phase = "playing"
        g.screen = "race"
        g.audio.start_music(g.locale_data(), g.mode == "zen")
    elif kind == "quit":
        g.finish()
    elif kind == "rectab":
        g.rec_tab = val
    elif kind == "recroad":
        g.rec_road = val
    elif kind == "recmode":
        g.rec_mode = val


def photo(screen, g):
    """Photo mode: the frame as it stands, without the interface, written out
    beside the save file. Cheap to add and the nicest thing to share."""
    import datetime as _dt
    from pathlib import Path
    shots = Path(store.SAVE_DIR) / "photos"
    try:
        shots.mkdir(parents=True, exist_ok=True)
        name = shots / ("ghr-" + _dt.datetime.now().strftime("%Y%m%d-%H%M%S") + ".png")
        # drop the alpha channel: a display-format surface carries one, and
        # saving it straight out writes a fully transparent image
        pygame.image.save(screen.convert(24), str(name))
        return f"Photo saved to {name.parent.name}/{name.name}"
    except (OSError, pygame.error):
        return "Could not write the photo"


def keydown(g, key):
    if key == pygame.K_v:
        g.postfx.note("Camera: " + g.cycle_camera())
        return
    if key == pygame.K_p:
        g.photo = True                      # captured after the world is drawn
        return
    if key == pygame.K_c:
        g.reduced = not g.reduced
        g.data["settings"]["reduced_motion"] = g.reduced
        store.save(g.data)
        g.postfx.note("Reduced motion: " + ("on" if g.reduced else "off"))
        return
    if key in (pygame.K_LEFTBRACKET, pygame.K_RIGHTBRACKET):
        step = -1 if key == pygame.K_LEFTBRACKET else 1
        g.postfx.step_brightness(step)
        g.data["settings"]["brightness"] = g.postfx.brightness
        store.save(g.data)
        return
    if key == pygame.K_f:
        g.postfx.cycle()
        g.data["settings"]["quality"] = g.postfx.quality
        store.save(g.data)
        return
    if key == pygame.K_m:
        dispatch(g, ("mute", None))
        return
    if g.phase == "title":
        if g.screen == "beat":
            if key == pygame.K_ESCAPE:
                g.open_journey()
            elif key in (pygame.K_SPACE, pygame.K_RETURN, pygame.K_KP_ENTER):
                if not g.beat_ready():
                    g.beat["t"] = g.beat_len()       # first press fills the text
                elif g.beat["next"] == "ride":
                    g.start_story()
                elif g.beat["next"] == "next":
                    dispatch(g, ("storynext", None))
                else:
                    g.open_journey()
            return
        if g.screen == "journey":
            from . import story as _story
            if key == pygame.K_ESCAPE:
                g.screen = "title"
            elif key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                g.open_beat("intro", min(g.story_i, _story.unlocked(g.data)))
            elif pygame.K_1 <= key <= pygame.K_9:
                want = key - pygame.K_1
                if want <= _story.unlocked(g.data) and want < len(_story.CHAPTERS):
                    g.open_beat("intro", want)
            return
        if g.screen == "records":
            if key in (pygame.K_ESCAPE, pygame.K_r):
                g.screen = "title"
            return
        if g.screen == "diff":
            if key == pygame.K_e:
                g.start_mode("daily", "easy")
            elif key == pygame.K_h:
                g.start_mode("daily", "hard")
            elif key == pygame.K_ESCAPE:
                g.screen = "title"
            return
        if key == pygame.K_d:
            dispatch(g, ("difficulty", None))
            return
        if key == pygame.K_r:
            g.rec_road = g.picked_locale
            g.screen = "records"
        elif key == pygame.K_1:
            g.start_mode("run")
        elif key == pygame.K_2:
            g.start_mode("zen")
        elif key == pygame.K_3:
            g.audio.stop_music()
            g.screen = "diff"
        elif key == pygame.K_4:
            g.open_journey()
        elif key == pygame.K_5:
            g.start_survival()
        return

    if key == pygame.K_ESCAPE:
        if g.phase == "playing":
            if g.mode == "zen":
                g.finish()
            else:
                g.phase = "paused"
                g.screen = "pause"
                g.audio.stop_music()
        elif g.phase == "paused":
            dispatch(g, ("resume", None))
        return

    if g.phase == "playing" and key in (pygame.K_j, pygame.K_SPACE):
        g.try_swing()


DEADZONE = 0.18


def read_steering(g, pads):
    k = pygame.key.get_pressed()
    left = k[pygame.K_LEFT] or k[pygame.K_a]
    right = k[pygame.K_RIGHT] or k[pygame.K_d]
    steer = (-1.0 if left else 0.0) + (1.0 if right else 0.0)
    brake = bool(k[pygame.K_DOWN] or k[pygame.K_s])

    # a pad, if one is plugged in — analogue steering beats digital here
    for pad in pads:
        try:
            ax = pad.get_axis(0)
            if abs(ax) > DEADZONE:
                steer = max(-1.0, min(1.0, (ax - DEADZONE * (1 if ax > 0 else -1))
                                      / (1 - DEADZONE)))
            if pad.get_numbuttons() > 1 and pad.get_button(1):
                brake = True
            if pad.get_numaxes() > 4 and pad.get_axis(4) > 0.1:
                brake = True
        except pygame.error:
            continue

    g.steer = steer
    g.braking = brake
    g.throttle = 0.0 if brake else 1.0


def main():
    pygame.init()
    screen = pygame.display.set_mode((WIN_W, WIN_H), pygame.RESIZABLE)
    pygame.display.set_caption("Golden Hour Rash")
    clock = pygame.time.Clock()

    pygame.joystick.init()
    pads = []
    for i in range(pygame.joystick.get_count()):
        try:
            pad = pygame.joystick.Joystick(i)
            pad.init()
            pads.append(pad)
        except pygame.error:
            pass

    fonts = Fonts()
    ui = Ui(fonts)
    renderer = Renderer(fonts)
    audio = Audio()
    data = store.load()
    game = Game(renderer, audio, data)
    game.postfx = PostFX(data["settings"].get("quality", "high"))
    if store.LOAD_WARNING:
        game.postfx.note(store.LOAD_WARNING)
    game.reduced = data["settings"].get("reduced_motion", False)
    game.postfx.brightness = data["settings"].get("brightness", 1.0)

    running = True
    while running:
        dt = min(0.05, clock.tick(FPS) / 1000.0)
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                running = False
            elif ev.type == pygame.VIDEORESIZE:
                # take the size the window manager actually gives back, not
                # the one we asked for — they differ on macOS
                pygame.display.set_mode(ev.size, pygame.RESIZABLE)
                screen = pygame.display.get_surface()
            elif ev.type == pygame.KEYDOWN:
                keydown(game, ev.key)
            elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                dispatch(game, ui.click(ev.pos))
            elif ev.type == pygame.JOYBUTTONDOWN:
                if ev.button in (4, 5):                  # shoulders — camera
                    game.postfx.note("Camera: " + game.cycle_camera())
                elif ev.button in (0, 2):                # A / X — swing
                    if game.phase == "playing":
                        game.try_swing()
                    elif game.phase == "title":
                        game.start_mode("run")
                elif ev.button in (6, 7, 9):             # start / menu
                    keydown(game, pygame.K_ESCAPE)
            elif ev.type == pygame.JOYDEVICEADDED:
                try:
                    pad = pygame.joystick.Joystick(ev.device_index)
                    pad.init()
                    pads.append(pad)
                except pygame.error:
                    pass

        if game.phase == "playing":
            read_steering(game, pads)
        shake_before = game.shake
        game.update(dt)
        # a landed hit or a collision should be felt, not just seen
        if game.shake > shake_before + 0.25:
            for pad in pads:
                try:
                    pad.rumble(min(1.0, game.shake), min(1.0, game.shake * 0.6), 160)
                except (AttributeError, pygame.error):
                    pass

        # re-read the surface every frame: a resize can hand us a new one,
        # and a window taller than what we last drew would otherwise keep a
        # stale, unpainted strip along the bottom
        screen = pygame.display.get_surface() or screen
        w, h = screen.get_size()
        screen.fill(INK)
        fx = game.postfx
        fx.tick(dt, clock.get_time())

        # the world is drawn big and filtered, then resolved into the window;
        # the interface goes on afterwards at native size so text stays sharp
        scene = fx.scene_for(w, h)
        scene.fill(INK)
        if game.screen == "beat" and game.beat:
            # A story beat paints its own world. Sending it through the same
            # pipeline as the road means it gets the supersampling and the
            # bloom too, which is most of why the sunrise glows.
            game.cinema.reduced = game.reduced
            game.cinema.paint(scene, *scene.get_size(), game.beat["spec"],
                              game.beat["t"])
        else:
            game.draw_world(scene, *scene.get_size())
        fx.bloom(scene)
        if game.phase == "playing" and not game.reduced:
            fx.speed_blur(scene, max(0.0, game.speed / MAX_SPEED - 0.45) / 0.55)
        # Vignette and flash go onto the SCENE, not the window. The scene
        # carries a zero alpha channel, resolve copies that into the display
        # surface, and a per-pixel-alpha blit onto a zero-alpha destination
        # blends wrong — it floods the frame with the overlay's own colour.
        sw, sh = scene.get_size()
        scene.blit(renderer.vignette(sw, sh), (0, 0))
        if game.flash > 0.01:
            fl = renderer.flash_layer(sw, sh)
            fl.fill((*game.flash_col, int(70 * game.flash)))
            scene.blit(fl, (0, 0))

        fx.resolve(scene, screen, game.shake_offset(w, h))
        fx.apply_brightness(screen)

        if game.photo:
            game.photo = False
            game.postfx.note(photo(screen, game))

        ui.ensure_fonts(h)
        ui.begin()
        if game.screen == "mods":
            ui.mods(screen, game, w, h)
        elif game.screen == "race":
            ui.hud(screen, game, w, h)
        elif game.screen == "title":
            ui.title(screen, game, w, h)
        elif game.screen == "diff":
            ui.diff(screen, game, w, h)
        elif game.screen == "records":
            ui.records(screen, game, w, h)
        elif game.screen == "pause":
            ui.pause(screen, game, w, h)
        elif game.screen == "results":
            ui.results(screen, game, w, h)
        elif game.screen == "journey":
            ui.journey(screen, game, w, h)
        elif game.screen == "beat":
            ui.beat(screen, game, w, h)

        if fx.note_alpha > 0:
            ui.fx_note(screen, fx, w, h)

        pygame.display.flip()

    store.save(data)
    pygame.quit()
    return 0
