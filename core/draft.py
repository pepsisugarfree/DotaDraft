from dataclasses import dataclass

from core.positions import POSITIONS
from core.rendering import Renderable

RADIANT = "radiant"
DIRE = "dire"
TEAMS = (RADIANT, DIRE)


def other(team):
    return DIRE if team == RADIANT else RADIANT


@dataclass(frozen=True)
class DraftFormat:
    key: str
    title: str
    order: tuple  # ("first" or "second", "pick" or "ban") for every step


def _steps(text):
    # "F-ban S-pick ..." is easier to check by eye than a long tuple
    names = {"F": "first", "S": "second"}
    return tuple((names[part[0]], part[2:]) for part in text.split())


CAPTAINS_MODE = DraftFormat("cm", "Captains Mode", _steps(
    "F-ban F-ban S-ban S-ban F-ban S-ban S-ban "
    "F-pick S-pick "
    "F-ban F-ban S-ban "
    "S-pick F-pick F-pick S-pick S-pick F-pick "
    "F-ban S-ban S-ban F-ban "
    "F-pick S-pick"
))
ALL_PICK = DraftFormat("ap", "All Pick", _steps(
    "F-pick S-pick S-pick F-pick F-pick S-pick S-pick F-pick F-pick S-pick"
))
FORMATS = {CAPTAINS_MODE.key: CAPTAINS_MODE, ALL_PICK.key: ALL_PICK}


@dataclass(frozen=True)
class Step:
    team: str
    action: str
    hero_id: int
    position: int = None


class Draft(Renderable):
    def __init__(self, draft_format, first=RADIANT):
        if first not in TEAMS:
            raise ValueError("The first team is 'radiant' or 'dire'.")
        self.format = draft_format
        self.first = first
        self.steps = []

    @property
    def turn(self):
        """(team, action) of the next step, or None when the draft is over."""
        if self.is_finished:
            return None
        side, action = self.format.order[len(self.steps)]
        team = self.first if side == "first" else other(self.first)
        return team, action

    @property
    def is_finished(self):
        return len(self.steps) >= len(self.format.order)

    def picks(self, team):
        return [s.hero_id for s in self.steps if s.team == team and s.action == "pick"]

    def bans(self, team=None):
        return [s.hero_id for s in self.steps if s.action == "ban" and team in (None, s.team)]

    def fixed_positions(self, team):
        return {s.hero_id: s.position for s in self.steps
                if s.team == team and s.action == "pick" and s.position}

    def is_taken(self, hero_id):
        return any(step.hero_id == hero_id for step in self.steps)

    def make(self, action, hero_id, position=None):
        if self.is_finished:
            raise ValueError("The draft is over. Start a new one with 'new'.")
        team, expected = self.turn
        if action != expected:
            raise ValueError(f"Now {team.title()} has to {expected}, not {action}.")
        if self.is_taken(hero_id):
            raise ValueError("This hero is already picked or banned.")
        if position is not None:
            if action != "pick" or position not in POSITIONS:
                raise ValueError("A position is a number from 1 to 5 and only for picks.")
            if position in self.fixed_positions(team).values():
                raise ValueError(f"{team.title()} already has a hero on position {position}.")
        step = Step(team, action, hero_id, position)
        self.steps.append(step)
        return step

    def undo(self):
        if not self.steps:
            raise ValueError("Nothing to undo.")
        return self.steps.pop()

    def to_dict(self):
        return {
            "format": self.format.key,
            "first": self.first,
            "steps": [[s.team, s.action, s.hero_id, s.position] for s in self.steps],
        }

    @classmethod
    def from_dict(cls, data):
        draft = cls(FORMATS[data["format"]], data["first"])
        for team, action, hero_id, position in data["steps"]:
            draft.steps.append(Step(team, action, hero_id, position))
        return draft
