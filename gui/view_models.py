"""What the window shows, made from the core objects. There is no tkinter here,
so it is easy to test and the widgets only copy these fields to the screen."""

from dataclasses import dataclass, field

from core import ATTRIBUTES, DIRE, POSITIONS, RADIANT, TEAMS, assign_positions, position_shares, roles, traits
from core.hero_notes import support_share
from core.positions import lane_shares


@dataclass
class HeroCard:
    hero_id: int
    name: str
    attribute: str
    details: str  # "Melee, initiator"
    roles: str
    winrate: str
    portrait: object = None  # local file or None


@dataclass
class HeroLine:
    """One row in the lists of the hero page: a hero and a number."""
    hero_id: int
    name: str
    value: str
    good: bool
    portrait: object = None


@dataclass
class HeroPage:
    hero_id: int
    name: str
    attribute: str
    about: str  # "Strength, Melee"
    roles: str
    traits: str
    winrate: str
    lanes: str
    positions: list  # (title, share)
    lists: list = field(default_factory=list)  # (title, [HeroLine])
    note: str = ""
    portrait: object = None


@dataclass
class Slot:
    position: int
    title: str
    hero_id: int = None
    name: str = "-"
    portrait: object = None


@dataclass
class TeamView:
    team: str
    player: str  # human or bot
    slots: list
    bans: str
    ban_lines: list = field(default_factory=list)  # HeroLine of each banned hero


@dataclass
class StepDot:
    """One step in the line of all steps of the draft."""
    team: str
    action: str
    state: str  # done, now or later
    hero: str = ""
    portrait: object = None


@dataclass
class ScoreView:
    rows: list  # (title, radiant points, dire points)
    radiant_chance: float
    verdict: str
    notes: list  # lines about problems, key matchups and synergies


@dataclass
class BoardView:
    title: str
    turn: str
    turn_team: str  # whose step it is, for the color
    teams: list
    radiant_chance: float = None  # only when the draft is over
    verdict: str = ""


def local_portrait(portraits, hero):
    return portraits.cached(hero) if portraits is not None else None


def role_names(hero):
    return ", ".join(POSITIONS[position] for position in roles(hero))


def winrate_text(hero):
    if not hero.games:
        return "no games yet"
    return f"{hero.winrate * 100:.1f}% in {hero.games:,} games"


def hero_card(hero, portraits=None):
    return HeroCard(
        hero_id=hero.id,
        name=hero.name,
        attribute=hero.attribute,
        details=", ".join([hero.attack_type] + traits(hero)),
        roles=role_names(hero),
        winrate=winrate_text(hero),
        portrait=local_portrait(portraits, hero),
    )


def hero_cards(pool, portraits=None, position=None, attribute=None, text=""):
    """Cards for the heroes that pass the filters, sorted by name."""
    text = text.strip().lower()
    cards = []
    for hero in pool.filter(position, attribute):
        if text and text not in hero.name.lower():
            continue
        cards.append(hero_card(hero, portraits))
    return cards


def hero_sections(cards):
    """Cards split by attribute like in the game: strength, agility, intelligence, universal."""
    return [(attribute, name, [card for card in cards if card.attribute == attribute])
            for attribute, name in ATTRIBUTES.items()]


def hero_page(game, hero, portraits=None):
    shares = lane_shares(hero)
    if shares:
        safe, mid, off = shares
        lanes = (f"safe {safe * 100:.0f}%, mid {mid * 100:.0f}%, off {off * 100:.0f}%, "
                 f"support ~{support_share(hero) * 100:.0f}%")
    else:
        lanes = "not enough games yet"
    page = HeroPage(
        hero_id=hero.id,
        name=hero.name,
        attribute=hero.attribute,
        about=f"{ATTRIBUTES.get(hero.attribute, hero.attribute)}, {hero.attack_type}",
        roles=role_names(hero),
        traits=", ".join(traits(hero)) or "-",
        winrate=winrate_text(hero),
        lanes=lanes,
        positions=[(f"{position} {POSITIONS[position]}", share)
                   for position, share in position_shares(hero).items()],
        portrait=local_portrait(portraits, hero),
    )

    matchups = game.evaluator.matchups
    try:
        tables = [
            ("Good against " + hero.name, matchups.counters_of(hero.id), False),
            ("Good against", matchups.good_against(hero.id), True),
            ("Works well with", matchups.best_allies(hero.id), True),
        ]
    except LookupError as error:  # no match statistics yet
        page.note = str(error)
        return page
    for title, rows, good in tables:
        lines = []
        for other_id, value in rows:
            other = game.pool.get(other_id)
            lines.append(HeroLine(other.id, other.name, f"{value * 100:+.1f}%", good,
                                  local_portrait(portraits, other)))
        page.lists.append((title, lines))
    return page


def board_view(game, portraits=None):
    draft = game.draft
    if draft is None:
        return None
    pool = game.pool

    teams = []
    for team in TEAMS:
        heroes = [pool.get(hero_id) for hero_id in draft.picks(team)]
        lineup = assign_positions(heroes, draft.fixed_positions(team))
        by_position = {position: pool.get(hero_id) for hero_id, position in lineup.items()}
        slots = []
        for position, title in POSITIONS.items():
            hero = by_position.get(position)
            if hero is None:
                slots.append(Slot(position, title))
            else:
                slots.append(Slot(position, title, hero.id, hero.name, local_portrait(portraits, hero)))
        banned = [pool.get(hero_id) for hero_id in draft.bans(team)]
        ban_lines = [HeroLine(hero.id, hero.name, "", False, local_portrait(portraits, hero)) for hero in banned]
        bans = ", ".join(hero.name for hero in banned)
        teams.append(TeamView(team, game.players[team], slots, bans or "-", ban_lines))

    mode = draft.format.title + (", competitive" if game.competitive else "")
    title = f"{mode}, step {len(draft.steps)}/{len(draft.format.order)}"
    if not draft.is_finished:
        team, action = draft.turn
        who = "bot" if game.is_bot_turn else "you"
        return BoardView(title, f"{team.title()} {action}s ({who})", team, teams)

    evaluation = game.evaluate()
    return BoardView(title, "The draft is over", "", teams, evaluation.radiant_chance, verdict_text(evaluation))


def verdict_text(evaluation):
    if evaluation.is_even:
        return "The drafts are even, it's up to the players."
    winner = evaluation.winner
    loser = DIRE if winner == RADIANT else RADIANT
    return f"{winner.title()} outdrafted {loser.title()}!"


def timeline(draft, pool=None, portraits=None):
    """All steps of the draft: which are done (with the hero), which one is now."""
    dots = []
    for index, (side, action) in enumerate(draft.format.order):
        team = draft.first if side == "first" else (DIRE if draft.first == RADIANT else RADIANT)
        if index < len(draft.steps):
            step = draft.steps[index]
            if pool is None:
                dots.append(StepDot(team, action, "done", str(step.hero_id)))
            else:
                hero = pool.get(step.hero_id)
                dots.append(StepDot(team, action, "done", hero.name, local_portrait(portraits, hero)))
        else:
            dots.append(StepDot(team, action, "now" if index == len(draft.steps) else "later"))
    return dots


def hero_states(draft):
    """{hero_id: (action, team)} for every hero that is already picked or banned."""
    if draft is None:
        return {}
    return {step.hero_id: (step.action, step.team) for step in draft.steps}


def suggestion_lines(game, portraits=None, count=5):
    """Best heroes for the current step, like 'suggest' in the console."""
    return [HeroLine(hero.id, hero.name, f"{gain:+.1f}", gain >= 0, local_portrait(portraits, hero))
            for hero, gain in game.suggestions(count)]


def score_view(game):
    evaluation = game.evaluate()
    radiant, dire = evaluation.radiant, evaluation.dire
    rows = [("Counter picks", radiant.counters, dire.counters), ("Synergy", radiant.synergy, dire.synergy),
            ("Hero strength", radiant.strength, dire.strength), ("Positions", radiant.positions, dire.positions),
            ("Composition", radiant.composition, dire.composition), ("Total", radiant.total, dire.total)]
    pool = game.pool
    notes = []
    for team, score in ((RADIANT, radiant), (DIRE, dire)):
        if score.problems:
            notes.append(f"{team.title()} lacks: {', '.join(score.problems)}")
    for hero_id, enemy_id, advantage in evaluation.key_matchups:
        hero, enemy = pool.get(hero_id).name, pool.get(enemy_id).name
        if advantage < 0:
            hero, enemy, advantage = enemy, hero, -advantage
        notes.append(f"{hero} is good against {enemy} ({advantage * 100:+.1f}%)")
    for team, hero_id, ally_id, synergy in evaluation.key_synergies:
        how = "work well together" if synergy >= 0 else "work badly together"
        notes.append(f"{pool.get(hero_id).name} and {pool.get(ally_id).name} {how} ({synergy * 100:+.1f}%)")
    return ScoreView(rows, evaluation.radiant_chance, verdict_text(evaluation), notes)
