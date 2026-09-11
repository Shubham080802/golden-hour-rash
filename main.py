#!/usr/bin/env python3
"""Golden Hour Rash — a stress-relief motorcycle combat racer.

    python main.py

Controls: arrows or A/D steer, down or S brakes, J or space swings,
Esc pauses or ends the ride, M mutes the music, R opens the record room.
"""
import sys

import pygame

from goldenhour import store
from goldenhour.audio import Audio
from goldenhour.config import FPS, INK, WIN_H, WIN_W
from goldenhour.game import Game
from goldenhour.locales import LOCALE_IDS
from goldenhour.render import Renderer
from goldenhour.ui import Fonts, Ui


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
        else:
            g.start_mode(val)
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
    elif kind == "mute":
        g.audio.muted = not g.audio.muted
        g.data["settings"]["music"] = not g.audio.muted
        store.save(g.data)
    elif kind == "again":
        g.start_mode(g.mode, g.diff)
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


def keydown(g, key):
    if key == pygame.K_m:
        dispatch(g, ("mute", None))
        return
    if g.phase == "title":
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


def read_steering(g):
    k = pygame.key.get_pressed()
    left = k[pygame.K_LEFT] or k[pygame.K_a]
    right = k[pygame.K_RIGHT] or k[pygame.K_d]
    g.steer = (-1 if left else 0) + (1 if right else 0)
    g.braking = bool(k[pygame.K_DOWN] or k[pygame.K_s])
    g.throttle = 0.0 if g.braking else 1.0


def main():
    pygame.init()
    screen = pygame.display.set_mode((WIN_W, WIN_H), pygame.RESIZABLE)
    pygame.display.set_caption("Golden Hour Rash")
    clock = pygame.time.Clock()

    fonts = Fonts()
    ui = Ui(fonts)
    renderer = Renderer(fonts)
    audio = Audio()
    data = store.load()
    game = Game(renderer, audio, data)
    game.locale_data = lambda: __import__(
        "goldenhour.locales", fromlist=["LOCALES"]).LOCALES[game.locale]

    running = True
    while running:
        dt = min(0.05, clock.tick(FPS) / 1000.0)
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                running = False
            elif ev.type == pygame.VIDEORESIZE:
                screen = pygame.display.set_mode(ev.size, pygame.RESIZABLE)
            elif ev.type == pygame.KEYDOWN:
                keydown(game, ev.key)
            elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                dispatch(game, ui.click(ev.pos))

        if game.phase == "playing":
            read_steering(game)
        game.update(dt)

        w, h = screen.get_size()
        screen.fill(INK)
        game.draw_world(screen, w, h)
        screen.blit(renderer.vignette(w, h), (0, 0))
        if game.flash > 0.01:
            fl = pygame.Surface((w, h), pygame.SRCALPHA)
            fl.fill((*game.flash_col, int(70 * game.flash)))
            screen.blit(fl, (0, 0))

        ui.begin()
        if game.screen == "race":
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

        pygame.display.flip()

    store.save(data)
    pygame.quit()
    return 0


if __name__ == "__main__":
    sys.exit(main())
