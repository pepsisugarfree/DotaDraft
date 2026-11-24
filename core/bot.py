import random

from core.draft import other

LEVELS = {"easy": 8, "normal": 3, "hard": 1}


class DraftBot:
    """Picks the heroes that raise its team's score the most.

    The bot chooses randomly among the best `top` heroes, so 'hard' always
    takes the best one and 'easy' makes mistakes.
    """

    def __init__(self, evaluator, pool, level="normal", rng=None):
        if level not in LEVELS:
            raise ValueError(f"Bot level is one of: {', '.join(LEVELS)}.")
        self.evaluator = evaluator
        self.pool = pool
        self.level = level
        self.rng = rng or random.Random()

    def suggestions(self, draft, team, count=5):
        """[(hero, gain)] - best picks for team right now."""
        ranked = []
        for hero in self.pool.all():
            if not draft.is_taken(hero.id):
                ranked.append((hero, self.evaluator.gain(draft, team, hero.id)))
        ranked.sort(key=lambda item: item[1], reverse=True)
        return ranked[:count]

    def choose(self, draft):
        team, action = draft.turn
        # a ban takes away the hero that would be the best pick for the enemy
        target = team if action == "pick" else other(team)
        best = self.suggestions(draft, target, LEVELS[self.level])
        hero, _ = self.rng.choice(best)
        return action, hero
