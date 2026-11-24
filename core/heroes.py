import math
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from core.positions import parse_position, roles
from core.rendering import Renderable

ATTRIBUTES = {"str": "Strength", "agi": "Agility", "int": "Intelligence", "all": "Universal"}


@dataclass(eq=False)
class Hero(Renderable):
    id: int
    name: str
    key: str
    attribute: str
    attack_type: str
    aliases: tuple = ()
    image_url: str = ""
    games: int = 0  # Divine+ public games in the current patch
    wins: int = 0
    lanes: dict = field(default_factory=dict)  # {"safe": games, "mid": ..., "off": ..., "jungle": ...}

    @property
    def winrate(self):
        if not self.games:
            return 0.5
        return self.wins / self.games

    def to_dict(self):
        data = dict(self.__dict__)
        data["aliases"] = list(self.aliases)
        data["lanes"] = dict(self.lanes)
        return data

    @classmethod
    def from_dict(cls, data):
        # fields from older versions of the file are skipped
        known = {key: value for key, value in data.items() if key in cls.__dataclass_fields__}
        known["aliases"] = tuple(known.get("aliases", ()))
        return cls(**known)


class HeroSource(ABC):
    """Where heroes and matchups come from. The data layer implements it."""

    @abstractmethod
    def heroes(self, refresh=False):
        pass

    @abstractmethod
    def matchups(self, hero_id):
        """{enemy_id: (games, wins of hero_id)}"""

    @abstractmethod
    def allies(self, hero_id):
        """{ally_id: (games together, wins together)}"""


def simplify(text):
    return re.sub(r"[^a-z0-9]", "", text.lower())


def initials(name):
    words = re.split(r"[\s\-]+", name)
    return "".join(word[0] for word in words if word).lower()


class HeroPool:
    def __init__(self, source):
        self.source = source
        self._heroes = None

    def all(self):
        if self._heroes is None:
            self._heroes = {hero.id: hero for hero in self.source.heroes()}
        return sorted(self._heroes.values(), key=lambda hero: hero.name)

    def refresh(self):
        self._heroes = {hero.id: hero for hero in self.source.heroes(refresh=True)}
        return len(self._heroes)

    def get(self, hero_id):
        self.all()
        return self._heroes[hero_id]

    def find(self, text):
        """Finds a hero by name, part of the name, alias ('am', 'sf') or initials."""
        wanted = simplify(text)
        if not wanted:
            raise ValueError("Write a hero name.")
        heroes = self.all()

        exact = [h for h in heroes
                 if wanted in (simplify(h.name), simplify(h.key), initials(h.name))
                 or wanted in [simplify(a) for a in h.aliases]]
        if len(exact) == 1:
            return exact[0]

        starts = [h for h in heroes if simplify(h.name).startswith(wanted)]
        if len(starts) == 1:
            return starts[0]

        inside = [h for h in heroes if wanted in simplify(h.name)]
        if len(inside) == 1:
            return inside[0]

        options = exact or starts or inside
        if options:
            names = ", ".join(h.name for h in options[:6])
            raise ValueError(f"'{text}' can be: {names}. Write more of the name.")
        raise LookupError(f"No hero '{text}'.")

    def filter(self, position=None, attribute=None):
        position = parse_position(position) if position else None
        result = []
        for hero in self.all():
            if position and position not in roles(hero):
                continue
            if attribute and hero.attribute != attribute.lower():
                continue
            result.append(hero)
        return result


class Matchups:
    """How heroes do against each other, from match statistics.

    A strong hero (Riki has 57% in the patch) wins against almost everyone,
    that is its strength and not a counter pick. So the advantage of a pair is
    how much better it does than expected from the winrates of the two heroes.

    The same goes for two heroes in one team (synergy).

    A pair has a few hundred Divine+ games, and on that many games luck alone
    moves the winrate by ~3%, more than a real counter pick does (~1.7%).
    So imaginary games with the expected result are added: a pair needs a lot
    of games to move far from the expectation. The numbers are measured on the
    data, see DESIGN.md 5.1.
    """

    PRIOR_GAMES = 800
    ALLY_PRIOR_GAMES = 2000

    def __init__(self, source, pool):
        self.source = source
        self.pool = pool
        self._loaded = {}
        self._allies = {}

    def clear(self):
        self._loaded = {}
        self._allies = {}

    def table(self, hero_id):
        if hero_id not in self._loaded:
            self._loaded[hero_id] = self.source.matchups(hero_id)
        return self._loaded[hero_id]

    def ally_table(self, hero_id):
        if hero_id not in self._allies:
            self._allies[hero_id] = self.source.allies(hero_id)
        return self._allies[hero_id]

    def load(self, hero_ids):
        """Loads tables of picked heroes, then pairs with them need no more requests."""
        for hero_id in hero_ids:
            self.table(hero_id)
            self.ally_table(hero_id)

    def strength(self, hero_id):
        """Winrate of the hero in log-odds: 50% -> 0, 57% -> +0.28, 45% -> -0.2."""
        try:
            winrate = min(max(self.pool.get(hero_id).winrate, 0.01), 0.99)
        except KeyError:
            return 0.0  # a hero the hero list doesn't know yet
        return math.log(winrate / (1 - winrate))

    def expected(self, hero_id, enemy_id):
        """Chance to win the pair if only the strength of the two heroes mattered."""
        return 1 / (1 + math.exp(self.strength(enemy_id) - self.strength(hero_id)))

    def winrate(self, hero_id, enemy_id):
        """Chance that hero_id wins against enemy_id (0..1)."""
        if hero_id not in self._loaded and enemy_id in self._loaded:
            games, enemy_wins = self.table(enemy_id).get(hero_id, (0, 0))
            wins = games - enemy_wins
        else:
            games, wins = self.table(hero_id).get(enemy_id, (0, 0))
        prior = self.expected(hero_id, enemy_id)
        return (wins + self.PRIOR_GAMES * prior) / (games + self.PRIOR_GAMES)

    def advantage(self, hero_id, enemy_id):
        """Winrate over the expected one, e.g. 0.03 means +3%. advantage(a, b) == -advantage(b, a)."""
        return self.winrate(hero_id, enemy_id) - self.expected(hero_id, enemy_id)

    def synergy(self, hero_id, ally_id):
        """How much more two heroes win together than expected from their strength."""
        expected = 1 / (1 + math.exp(-self.strength(hero_id) - self.strength(ally_id)))
        if hero_id not in self._allies and ally_id in self._allies:
            games, wins = self.ally_table(ally_id).get(hero_id, (0, 0))
        else:
            games, wins = self.ally_table(hero_id).get(ally_id, (0, 0))
        winrate = (wins + self.ALLY_PRIOR_GAMES * expected) / (games + self.ALLY_PRIOR_GAMES)
        return winrate - expected

    def best_allies(self, hero_id, count=5):
        allies = self.ally_table(hero_id).keys()
        ranked = sorted(allies, key=lambda ally: self.synergy(hero_id, ally), reverse=True)
        return [(ally, self.synergy(hero_id, ally)) for ally in ranked[:count]]

    def counters_of(self, hero_id, count=5):
        """Heroes that are good against hero_id, best first."""
        enemies = self.table(hero_id).keys()
        ranked = sorted(enemies, key=lambda enemy: self.advantage(enemy, hero_id), reverse=True)
        return [(enemy, self.advantage(enemy, hero_id)) for enemy in ranked[:count]]

    def good_against(self, hero_id, count=5):
        enemies = self.table(hero_id).keys()
        ranked = sorted(enemies, key=lambda enemy: self.advantage(hero_id, enemy), reverse=True)
        return [(enemy, self.advantage(hero_id, enemy)) for enemy in ranked[:count]]
