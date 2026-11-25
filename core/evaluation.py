import math
from dataclasses import dataclass

from core.draft import DIRE, RADIANT, other
from core.hero_notes import traits
from core.positions import assign_positions, playable
from core.rendering import Renderable

# Points are made so that 1 point of difference is about 1% of win chance.
POINTS_PER_LOG_ODDS = 25
EVEN_DRAFT = 0.02
STRENGTH_WEIGHT = 0.5  # half of a hero's winrate is the hero, half is who likes to play it
POSITION_PENALTY = 10  # a position nobody in the team can play costs 10 points

# Cores decide more fights than supports, so their matchups weigh more.
# The weights add up to 5, so 25 pairs still weigh 25 in total.
POSITION_WEIGHTS = {1: 1.25, 2: 1.25, 3: 1.0, 4: 0.75, 5: 0.75}
LANE_OF = {1: "safe", 5: "safe", 2: "mid", 3: "off", 4: "off"}
FACING = {("safe", "off"), ("off", "safe"), ("mid", "mid")}
LANE_WEIGHT = 1.5  # heroes that stand against each other on a lane for 10 minutes

# (problem, penalty, check) - checked when the team has all 5 heroes
COMPOSITION_RULES = [
    ("no initiator", 4, lambda heroes: not has_trait(heroes, "initiator")),
    ("no frontline", 3, lambda heroes: not has_trait(heroes, "frontline")),
    ("all melee", 3, lambda heroes: all(hero.attack_type == "Melee" for hero in heroes)),
    ("all ranged", 3, lambda heroes: all(hero.attack_type == "Ranged" for hero in heroes)),
]


def has_trait(heroes, trait):
    return any(trait in traits(hero) for hero in heroes)


@dataclass(frozen=True)
class TeamScore:
    counters: float
    synergy: float
    strength: float
    positions: float
    composition: float
    roles: dict  # {hero_id: position}
    problems: tuple = ()  # what the composition misses, e.g. "no initiator"

    @property
    def total(self):
        return self.counters + self.synergy + self.strength + self.positions + self.composition


@dataclass(frozen=True)
class DraftEvaluation(Renderable):
    radiant: TeamScore
    dire: TeamScore
    key_matchups: tuple  # (hero_id, enemy_id, advantage), the biggest ones
    key_synergies: tuple = ()  # (team, hero_id, ally_id, synergy)

    @property
    def radiant_chance(self):
        difference = self.radiant.total - self.dire.total
        return 1 / (1 + math.exp(-difference / POINTS_PER_LOG_ODDS))

    @property
    def winner(self):
        return RADIANT if self.radiant_chance >= 0.5 else DIRE

    @property
    def is_even(self):
        """48-52% is a draw: then it's up to the players."""
        return abs(self.radiant_chance - 0.5) < EVEN_DRAFT

    def score(self, team):
        return self.radiant if team == RADIANT else self.dire


class Evaluator:
    """Gives points to a draft. All the math is in DESIGN.md, part 5."""

    def __init__(self, pool, matchups):
        self.pool = pool
        self.matchups = matchups

    def pair_weight(self, position, enemy_position):
        weight = POSITION_WEIGHTS[position] * POSITION_WEIGHTS[enemy_position]
        if (LANE_OF[position], LANE_OF[enemy_position]) in FACING:
            weight *= LANE_WEIGHT
        return weight

    def team_score(self, own_ids, enemy_ids, own_fixed=None, enemy_fixed=None):
        own = [self.pool.get(hero_id) for hero_id in own_ids]
        roles = assign_positions(own, own_fixed)
        enemy_roles = assign_positions([self.pool.get(hero_id) for hero_id in enemy_ids], enemy_fixed)

        # a counter pick helps one team as much as it hurts the other,
        # so each team gets half and the gap between them is the whole effect
        counters = 0.0
        for hero_id in own_ids:
            for enemy_id in enemy_ids:
                weight = self.pair_weight(roles[hero_id], enemy_roles[enemy_id])
                counters += weight * self.matchups.advantage(hero_id, enemy_id) * 100 / 2

        synergy = 0.0
        for i, hero_id in enumerate(own_ids):
            for ally_id in own_ids[i + 1:]:
                synergy += self.matchups.synergy(hero_id, ally_id) * 100

        strength = POINTS_PER_LOG_ODDS * STRENGTH_WEIGHT * sum(
            self.matchups.strength(hero_id) for hero_id in own_ids)

        # squared, so a support standing in as carry (0.4 -> 0.16) is really bad
        positions = -POSITION_PENALTY * sum(
            1 - playable(self.pool.get(hero_id), position) ** 2 for hero_id, position in roles.items())

        composition, problems = 0.0, []
        if len(own) == 5:
            for problem, penalty, check in COMPOSITION_RULES:
                if check(own):
                    composition -= penalty
                    problems.append(problem)

        return TeamScore(counters, synergy, strength, positions, composition, roles, tuple(problems))

    def evaluate(self, draft):
        radiant = draft.picks(RADIANT)
        dire = draft.picks(DIRE)
        self.matchups.load(radiant + dire)
        radiant_score = self.team_score(radiant, dire, draft.fixed_positions(RADIANT), draft.fixed_positions(DIRE))
        dire_score = self.team_score(dire, radiant, draft.fixed_positions(DIRE), draft.fixed_positions(RADIANT))

        pairs = []
        for hero_id in radiant:
            for enemy_id in dire:
                pairs.append((hero_id, enemy_id, self.matchups.advantage(hero_id, enemy_id)))
        # the pairs that changed the score the most, not just the biggest numbers
        pairs.sort(key=lambda pair: abs(pair[2]) * self.pair_weight(
            radiant_score.roles[pair[0]], dire_score.roles[pair[1]]), reverse=True)

        synergies = []
        for team, heroes in ((RADIANT, radiant), (DIRE, dire)):
            for i, hero_id in enumerate(heroes):
                for ally_id in heroes[i + 1:]:
                    synergies.append((team, hero_id, ally_id, self.matchups.synergy(hero_id, ally_id)))
        synergies.sort(key=lambda item: abs(item[3]), reverse=True)

        return DraftEvaluation(radiant_score, dire_score, tuple(pairs[:3]), tuple(synergies[:3]))

    def gain(self, draft, team, hero_id):
        """How much better team's score gets compared to the enemy if it picks hero_id."""
        self.matchups.load(draft.picks(RADIANT) + draft.picks(DIRE))
        own = draft.picks(team) + [hero_id]
        enemy = draft.picks(other(team))
        own_fixed, enemy_fixed = draft.fixed_positions(team), draft.fixed_positions(other(team))
        mine = self.team_score(own, enemy, own_fixed, enemy_fixed)
        theirs = self.team_score(enemy, own, enemy_fixed, own_fixed)
        return mine.total - theirs.total
