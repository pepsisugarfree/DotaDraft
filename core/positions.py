from itertools import permutations

from core.hero_notes import support_share

POSITIONS = {1: "Carry", 2: "Mid", 3: "Offlane", 4: "Pos 4", 5: "Pos 5"}
POSITION_NAMES = {"carry": 1, "mid": 2, "offlane": 3, "off": 3}
MIN_LANE_GAMES = 100
SUPPORT_SWAP = 0.8  # a pos 4 can play pos 5 and back almost as well
PLAYABLE = 0.55  # a position with 55% of the best one's score is played without problems
ROLE_SHARE = 0.2  # a role is a position the hero has in at least 20% of games


def lane_shares(hero):
    """Part of games on safe, mid and off lane. None if there is too little data."""
    lanes = hero.lanes or {}
    total = lanes.get("safe", 0) + lanes.get("mid", 0) + lanes.get("off", 0)
    if total < MIN_LANE_GAMES:
        return None
    return lanes.get("safe", 0) / total, lanes.get("mid", 0) / total, lanes.get("off", 0) / total


def raw_position_scores(hero):
    """{position: score}. Safe lane is pos 1 + pos 5, off lane is pos 3 + pos 4,
    mid is pos 2 (sometimes a roaming 4). Support share splits each lane."""
    shares = lane_shares(hero)
    if shares is None:
        return {position: 1.0 for position in POSITIONS}  # no lane data: can be anything

    safe, mid, off = shares
    support = support_share(hero)
    return {
        1: safe * (1 - support),
        2: mid * (1 - support / 2),
        3: off * (1 - support),
        4: off * support + mid * support / 2,
        5: safe * support,
    }


def position_scores(hero):
    """Like raw_position_scores, but supports can swap 4 and 5."""
    scores = raw_position_scores(hero)
    soft, hard = scores[4], scores[5]
    scores[4] = max(soft, SUPPORT_SWAP * hard)
    scores[5] = max(hard, SUPPORT_SWAP * soft)
    return scores


def fitness(hero, position):
    """0..1, how well the hero plays the position compared with its best one."""
    scores = position_scores(hero)
    return scores[position] / max(scores.values())


def playable(hero, position):
    """0..1 like fitness, but every position close to the best one counts as 1."""
    return min(fitness(hero, position) / PLAYABLE, 1.0)


def position_shares(hero):
    """{position: part of games}, a guess that adds up to 1."""
    scores = raw_position_scores(hero)
    total = sum(scores.values())
    return {position: score / total for position, score in scores.items()}


def roles(hero):
    """Positions the hero is played on, the most common first."""
    shares = position_shares(hero)
    ranked = sorted(POSITIONS, key=lambda position: shares[position], reverse=True)
    return [ranked[0]] + [position for position in ranked[1:] if shares[position] >= ROLE_SHARE]


def parse_position(text):
    """'1'..'5', 'carry', 'mid', 'offlane', 'pos4' -> position number."""
    text = str(text).lower().replace("pos", "").replace(" ", "")
    if text in POSITION_NAMES:
        return POSITION_NAMES[text]
    if text.isdigit() and int(text) in POSITIONS:
        return int(text)
    raise ValueError("Position is 1-5, carry, mid or offlane.")


def assign_positions(heroes, fixed=None):
    """Gives every hero a position so the total score is the biggest.

    fixed = {hero_id: position} for heroes the player put on a position himself.
    Returns {hero_id: position}. 5 heroes at most, so trying all variants is fast.
    """
    fixed = dict(fixed or {})
    free_heroes = [hero for hero in heroes if hero.id not in fixed]
    free_positions = [p for p in POSITIONS if p not in fixed.values()]
    scores = {hero.id: position_scores(hero) for hero in free_heroes}

    best, best_score = {}, -1.0
    for chosen in permutations(free_positions, len(free_heroes)):
        score = sum(scores[hero.id][position] for hero, position in zip(free_heroes, chosen))
        if score > best_score:
            best, best_score = dict(zip((h.id for h in free_heroes), chosen)), score
    return {**fixed, **best}
