"""Run modifiers.

Before a Run you are offered three of these and take one. Every card is a
trade rather than an upgrade, so the choice is a choice: the thing that pays
double also takes something away.

Daily never offers them — that board has to stay comparable.
"""
import random

MODIFIERS = [
    {"id": "glass", "name": "Glass Cannon",
     "desc": "Double points. The combo decays twice as fast.",
     "score": 2.0, "combo_t": 0.5},
    {"id": "rush", "name": "Rush Hour",
     "desc": "Twice the traffic. Near misses pay triple.",
     "traffic": 2.0, "near": 3.0},
    {"id": "grudge", "name": "Grudge Match",
     "desc": "Every rival rides angry all race. Hits pay double.",
     "always_fight": True, "hit": 2.0},
    {"id": "tailwind", "name": "Tailwind",
     "desc": "Twelve percent more top speed. Corners punish twice as hard.",
     "speed": 1.12, "scrub": 2.0},
    {"id": "feather", "name": "Featherweight",
     "desc": "Traffic barely slows you. No perfect-run bonus.",
     "collide": 0.25, "no_perfect": True},
    {"id": "unbroken", "name": "Unbroken",
     "desc": "The combo never times out. Any contact wipes it to zero.",
     "combo_t": 40.0, "contact_wipes": True},
    {"id": "loner", "name": "Breakaway",
     "desc": "Start mid-pack instead of last. Rivals are five percent quicker.",
     "head_start": True, "rival_pace": 1.05},
]

NONE = {"id": "none", "name": "Straight Up", "desc": "No modifier. The road as it comes."}


def offer(rng=None, count=3):
    """Three cards plus the option to take none."""
    rng = rng or random
    return rng.sample(MODIFIERS, min(count, len(MODIFIERS))) + [NONE]


def by_id(ident):
    if ident == "none" or ident is None:
        return NONE
    for m in MODIFIERS:
        if m["id"] == ident:
            return m
    return NONE
