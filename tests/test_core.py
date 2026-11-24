import random

import pytest

from core import (ALL_PICK, CAPTAINS_MODE, DIRE, RADIANT, Draft, DraftGame, Evaluator,
                  HeroPool, Matchups, SaveStore, assign_positions, fitness, roles, traits)
from core.positions import parse_position
from tests.conftest import FakeSource


class MemoryStore(SaveStore):
    def __init__(self):
        self.data = {}

    def save(self, name, data):
        self.data[name] = data

    def load(self, name):
        return self.data.get(name)

    def names(self):
        return sorted(self.data)


@pytest.fixture
def pool():
    return HeroPool(FakeSource())


def make_game(level="hard"):
    source = FakeSource()
    pool = HeroPool(source)
    game = DraftGame(pool, Matchups(source, pool), MemoryStore(), random.Random(3))
    return game, source


@pytest.mark.parametrize(("text", "name"), [
    ("Axe", "Axe"), ("am", "Anti-Mage"), ("antimage", "Anti-Mage"), ("cm", "Crystal Maiden"),
    ("jugg", "Juggernaut"), ("WITCH doctor", "Witch Doctor"), ("phantom", "Phantom Assassin"),
])
def test_find_hero(pool, text, name):
    assert pool.find(text).name == name


def test_find_hero_errors(pool):
    with pytest.raises(ValueError, match="Shadow Fiend, Shadow Shaman"):
        pool.find("shadow")
    with pytest.raises(LookupError):
        pool.find("roshan")


def test_matchups_are_smoothed_and_symmetric():
    source = FakeSource()
    matchups = Matchups(source, HeroPool(source))
    assert matchups.advantage(1, 2) == pytest.approx(-matchups.advantage(2, 1))
    # 1 vs 2: 37 wins of 100, plus 800 imaginary games with the expected result
    expected = matchups.expected(1, 2)
    assert matchups.winrate(1, 2) == pytest.approx((37 + 800 * expected) / 900)
    assert matchups.advantage(1, 2) == pytest.approx(matchups.winrate(1, 2) - expected)
    assert matchups.advantage(1, 999) == pytest.approx(0)


def test_strong_hero_is_not_a_counter_to_everyone():
    class StrongHero(FakeSource):
        def heroes(self, refresh=False):
            heroes = super().heroes()
            for hero in heroes:
                hero.games, hero.wins = 1000, 600 if hero.id == 1 else 500
            return heroes

        def matchups(self, hero_id):
            # hero 1 wins 60% against everyone - exactly what its winrate says
            if hero_id == 1:
                return {enemy: (1000, 600) for enemy in range(2, 27)}
            return {1: (1000, 400)}

    source = StrongHero()
    matchups = Matchups(source, HeroPool(source))
    assert matchups.strength(1) > 0
    assert matchups.advantage(1, 2) == pytest.approx(0, abs=0.001)


def test_positions(pool):
    heroes = [pool.find(name) for name in ("am", "sf", "axe", "lion", "cm")]
    lineup = {pool.get(hero_id).name: position for hero_id, position in assign_positions(heroes).items()}
    assert lineup["Axe"] == 3
    assert lineup["Anti-Mage"] in (1, 2) and lineup["Shadow Fiend"] in (1, 2)
    assert {lineup["Lion"], lineup["Crystal Maiden"]} == {4, 5}
    assert roles(pool.find("axe"))[0] == 3
    assert roles(pool.find("sven"))[0] == 1
    assert roles(pool.find("sf"))[0] == 2
    assert roles(pool.find("cm"))[0] == 5
    assert roles(pool.find("earthshaker"))[0] == 4
    assert fitness(pool.find("zeus"), 5) == 1  # no lane data: every position is possible

    fixed = assign_positions(heroes, {pool.find("cm").id: 4})
    assert fixed[pool.find("cm").id] == 4


def test_lanes_decide_where_a_core_or_support_stands(pool):
    # like Wraith King: half safe lane, half off lane, a core
    ursa = pool.find("ursa")
    ursa.lanes = {"safe": 500, "mid": 20, "off": 480, "jungle": 0}
    assert roles(ursa) == [1, 3]
    # the same lanes for a support
    lion = pool.find("lion")
    lion.lanes = {"safe": 500, "mid": 20, "off": 480, "jungle": 0}
    assert set(roles(lion)) == {4, 5}


def test_captains_mode_order():
    order = CAPTAINS_MODE.order
    assert len(order) == 24
    assert sum(1 for side, action in order if action == "ban") == 14
    assert order.count(("first", "pick")) == order.count(("second", "pick")) == 5
    assert order.count(("first", "ban")) == order.count(("second", "ban")) == 7
    assert [action for _, action in ALL_PICK.order] == ["pick"] * 10


def test_draft_rules():
    draft = Draft(ALL_PICK, first=DIRE)
    assert draft.turn == (DIRE, "pick")
    with pytest.raises(ValueError, match="has to pick"):
        draft.make("ban", 1)
    draft.make("pick", 1, position=1)
    with pytest.raises(ValueError, match="already picked"):
        draft.make("pick", 1)
    draft.make("pick", 2, position=3)
    with pytest.raises(ValueError, match="position"):
        draft.make("pick", 3, position=9)
    assert draft.picks(DIRE) == [1] and draft.picks(RADIANT) == [2]
    assert draft.undo().hero_id == 2

    copy = Draft.from_dict(draft.to_dict())
    assert copy.steps == draft.steps and copy.turn == draft.turn


def test_evaluation():
    source = FakeSource()
    pool = HeroPool(source)
    evaluator = Evaluator(pool, Matchups(source, pool))
    draft = Draft(ALL_PICK)
    for hero_id in (1, 2, 3, 4, 5, 6, 7, 8, 9, 10):
        draft.make("pick", hero_id)
    result = evaluator.evaluate(draft)
    assert result.radiant.counters == pytest.approx(-result.dire.counters)
    assert 0 < result.radiant_chance < 1
    assert len(result.key_matchups) == 3
    assert sorted(result.radiant.roles.values()) == [1, 2, 3, 4, 5]


def test_composition_problems():
    source = FakeSource()
    pool = HeroPool(source)
    evaluator = Evaluator(pool, Matchups(source, pool))
    melee = evaluator.team_score([1, 2, 6, 9, 10], [])
    assert melee.problems == ("all melee",)
    # Anti-Mage, Juggernaut, PA, Templar Assassin, Shadow Fiend: nobody starts fights or tanks
    carries = evaluator.team_score([1, 12, 15, 25, 7], [])
    assert carries.problems == ("no initiator", "no frontline")
    assert carries.composition == -4 - 3
    assert evaluator.team_score([1, 12], []).composition == 0  # checked only for 5 heroes


def test_traits(pool):
    assert traits(pool.find("axe")) == ["initiator", "frontline"]
    assert traits(pool.find("juggernaut")) == []
    assert roles(pool.find("juggernaut")) == [1]


def test_parse_position():
    assert parse_position("carry") == 1 and parse_position("pos4") == 4 and parse_position("3") == 3
    with pytest.raises(ValueError):
        parse_position("support")


def test_core_matchups_weigh_more_than_support_ones():
    source = FakeSource()
    pool = HeroPool(source)
    evaluator = Evaluator(pool, Matchups(source, pool))
    assert evaluator.pair_weight(1, 1) > evaluator.pair_weight(5, 5)
    assert evaluator.pair_weight(1, 3) > evaluator.pair_weight(1, 1)  # carry and offlaner meet on a lane
    assert evaluator.pair_weight(2, 2) > evaluator.pair_weight(2, 1)


def test_evaluation_shows_synergies():
    source = FakeSource()
    pool = HeroPool(source)
    evaluator = Evaluator(pool, Matchups(source, pool))
    draft = Draft(ALL_PICK)
    for hero_id in (1, 2, 3, 4, 5, 6, 7, 8, 9, 10):
        draft.make("pick", hero_id)
    synergies = evaluator.evaluate(draft).key_synergies
    assert len(synergies) == 3
    team, hero_id, ally_id, value = synergies[0]
    assert set(draft.picks(team)) >= {hero_id, ally_id}
    assert abs(value) >= abs(synergies[-1][3])


def test_synergy_is_the_same_both_ways():
    source = FakeSource()
    matchups = Matchups(source, HeroPool(source))
    assert matchups.synergy(3, 5) == pytest.approx(matchups.synergy(5, 3))
    assert len(matchups.best_allies(3, 4)) == 4


def test_bot_asks_only_matchups_of_picked_heroes():
    game, source = make_game()
    game.new("cm", radiant="bot", dire="bot", level="hard")
    game.play_bots()
    picked = set(game.draft.picks(RADIANT) + game.draft.picks(DIRE))
    assert game.draft.is_finished
    assert set(source.requested) <= picked


def test_hard_bot_takes_the_best_suggestion():
    game, _ = make_game()
    game.new("ap", radiant="human", dire="bot", level="hard")
    game.human_move("pick", game.pool.find("axe"))
    best = game.bot.suggestions(Draft.from_dict(game.draft.to_dict()), DIRE, 1)[0][0]
    step = game.bot_move()
    assert step.hero_id == best.id


def test_human_against_bot_and_undo():
    game, _ = make_game()
    game.new("ap", radiant="human", dire="bot")
    game.human_move("pick", game.pool.find("axe"))
    game.play_bots()
    assert len(game.draft.steps) == 3
    with pytest.raises(ValueError):
        game.human_move("ban", game.pool.find("lion"))
    undone = game.undo()
    assert len(undone) == 3 and not game.draft.steps


def test_result_is_written_once_and_save_load():
    game, _ = make_game()
    game.new("ap", radiant="bot", dire="bot")
    game.play_bots()
    assert len(game.results()) == 1
    game.save("final")
    picks = game.draft.picks(RADIANT)

    game.new("cm")
    game.load("final")
    assert game.draft.picks(RADIANT) == picks
    assert game.save_names() == ["final"]
    game.undo()
    assert game.results() == []
    with pytest.raises(LookupError):
        game.load("nope")
