import random

import pytest

from app import App
from cli import MemoryConsole
from core import Hero, HeroSource

HERO_LIST = [
    (1, "Anti-Mage", "agi", "Melee", "am"),
    (2, "Axe", "str", "Melee", ""),
    (3, "Crystal Maiden", "int", "Ranged", ""),
    (4, "Invoker", "all", "Ranged", ""),
    (5, "Lion", "int", "Ranged", ""),
    (6, "Pudge", "str", "Melee", ""),
    (7, "Shadow Fiend", "agi", "Ranged", "sf"),
    (8, "Shadow Shaman", "int", "Ranged", ""),
    (9, "Sven", "str", "Melee", ""),
    (10, "Tidehunter", "str", "Melee", ""),
    (11, "Witch Doctor", "int", "Ranged", "wd"),
    (12, "Juggernaut", "agi", "Melee", ""),
    (13, "Dazzle", "all", "Ranged", ""),
    (14, "Mars", "str", "Melee", ""),
    (15, "Phantom Assassin", "agi", "Melee", "pa"),
    (16, "Earthshaker", "str", "Melee", ""),
    (17, "Bane", "all", "Ranged", ""),
    (18, "Lina", "int", "Ranged", ""),
    (19, "Viper", "agi", "Ranged", ""),
    (20, "Slardar", "str", "Melee", ""),
    (21, "Rubick", "int", "Ranged", ""),
    (22, "Ursa", "agi", "Melee", ""),
    (23, "Zeus", "int", "Ranged", ""),
    (24, "Omniknight", "str", "Melee", ""),
    (25, "Templar Assassin", "agi", "Ranged", ""),
    (26, "Necrophos", "int", "Ranged", ""),
]


# games on safe, mid and off lane, like OpenDota gives them; Zeus has none on purpose
LANES = {
    1: (940, 40, 20), 2: (30, 30, 940), 3: (790, 50, 160), 4: (100, 850, 50), 5: (450, 130, 420),
    6: (280, 190, 530), 7: (380, 590, 30), 8: (500, 60, 440), 9: (970, 20, 10), 10: (40, 30, 930),
    11: (520, 40, 440), 12: (970, 20, 10), 13: (600, 50, 350), 14: (20, 70, 910), 15: (940, 40, 20),
    16: (100, 100, 800), 17: (480, 60, 460), 18: (300, 600, 100), 19: (200, 600, 200),
    20: (30, 40, 930), 21: (400, 150, 450), 22: (900, 50, 50), 24: (500, 50, 450),
    25: (100, 880, 20), 26: (200, 500, 300),
}


def make_heroes():
    heroes = []
    for hero_id, name, attribute, attack, alias in HERO_LIST:
        safe, mid, off = LANES.get(hero_id, (0, 0, 0))
        heroes.append(Hero(hero_id, name, name.lower().replace(" ", "_"), attribute, attack,
                           (alias,) if alias else (), f"https://img/{hero_id}.png",
                           1000, 500 + (hero_id * 13) % 61 - 30,
                           lanes={"safe": safe, "mid": mid, "off": off, "jungle": 0}))
    return heroes


def wins_against(hero_id, enemy_id):
    """Made-up but consistent: wins of a against b + wins of b against a = 100."""
    if hero_id < enemy_id:
        return 50 + (hero_id * enemy_id) % 31 - 15
    return 100 - wins_against(enemy_id, hero_id)


class FakeSource(HeroSource):
    """Works without internet and remembers which matchups were asked."""

    def __init__(self):
        self.requested = []

    def heroes(self, refresh=False):
        return make_heroes()

    def matchups(self, hero_id):
        self.requested.append(hero_id)
        return {enemy: (100, wins_against(hero_id, enemy))
                for enemy, *_ in HERO_LIST if enemy != hero_id}

    def allies(self, hero_id):
        # the same for both heroes of a pair, like real games together
        return {ally: (80, 40 + (hero_id + ally) % 11 - 5)
                for ally, *_ in HERO_LIST if ally != hero_id}


@pytest.fixture
def run_app(tmp_path):
    """Runs the app on the given input lines and returns the console."""

    def run(*lines):
        console = MemoryConsole(lines)
        App(console, tmp_path, colors=False, source=FakeSource(), rng=random.Random(1)).run()
        return console

    return run
