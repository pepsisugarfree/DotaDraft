from abc import ABC, abstractmethod
from datetime import datetime

from core.bot import DraftBot
from core.draft import DIRE, FORMATS, RADIANT, Draft, other
from core.evaluation import Evaluator

PLAYERS = ("human", "bot")
AUTOSAVE = "autosave"
RESULTS = "_results"


class SaveStore(ABC):
    @abstractmethod
    def save(self, name, data):
        pass

    @abstractmethod
    def load(self, name):
        pass

    @abstractmethod
    def names(self):
        pass


class DraftGame:
    """One draft at a time: whose turn it is, bot moves, results and saves."""

    def __init__(self, pool, matchups, store, rng=None):
        self.pool = pool
        self.store = store
        self.rng = rng
        self.evaluator = Evaluator(pool, matchups)
        self.draft = None
        self.players = {RADIANT: "human", DIRE: "bot"}
        self.bot = DraftBot(self.evaluator, pool, "normal", rng)
        self._result_written = False

    def new(self, format_key="cm", radiant="human", dire="bot", first=RADIANT, level="normal"):
        if format_key not in FORMATS:
            raise ValueError(f"Format is one of: {', '.join(FORMATS)}.")
        for player in (radiant, dire):
            if player not in PLAYERS:
                raise ValueError("A team is played by 'human' or 'bot'.")
        self.bot = DraftBot(self.evaluator, self.pool, level, self.rng)
        self.draft = Draft(FORMATS[format_key], first)
        self.players = {RADIANT: radiant, DIRE: dire}
        self._result_written = False
        return self.draft

    def current(self):
        if self.draft is None:
            raise ValueError("No draft yet. Start one with 'new'.")
        return self.draft

    @property
    def is_bot_turn(self):
        draft = self.current()
        return not draft.is_finished and self.players[draft.turn[0]] == "bot"

    def human_move(self, action, hero, position=None):
        if self.is_bot_turn:
            raise ValueError("Now it's the bot's turn.")
        step = self.current().make(action, hero.id, position)
        self._write_result_if_over()
        return step

    def bot_move(self):
        """The bot makes the current step (also used as a hint for a human: 'auto')."""
        action, hero = self.bot.choose(self.current())
        step = self.draft.make(action, hero.id)
        self._write_result_if_over()
        return step

    def play_bots(self):
        steps = []
        while self.is_bot_turn:
            steps.append(self.bot_move())
        return steps

    def undo(self):
        """Takes back the last human step and the bot steps after it."""
        draft = self.current()
        if self._result_written:
            results = self.results()
            results.pop()
            self.store.save(RESULTS, results)
            self._result_written = False
        undone = [draft.undo()]
        while draft.steps and self.players[undone[-1].team] == "bot" and "human" in self.players.values():
            undone.append(draft.undo())
        return undone

    def evaluate(self):
        return self.evaluator.evaluate(self.current())

    def suggestions(self, count=5):
        draft = self.current()
        if draft.is_finished:
            raise ValueError("The draft is over.")
        team, action = draft.turn
        target = team if action == "pick" else other(team)
        return self.bot.suggestions(draft, target, count)

    def results(self):
        return self.store.load(RESULTS) or []

    def _write_result_if_over(self):
        if not self.draft.is_finished or self._result_written:
            return
        evaluation = self.evaluate()
        results = self.results()
        results.append({
            "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "format": self.draft.format.key,
            "radiant": self.draft.picks(RADIANT),
            "dire": self.draft.picks(DIRE),
            "radiant_chance": round(evaluation.radiant_chance, 3),
        })
        self.store.save(RESULTS, results)
        self._result_written = True

    def save(self, name=AUTOSAVE):
        if not name or name.startswith("_"):
            raise ValueError("Bad save name.")
        self.store.save(name, {
            "draft": self.current().to_dict(),
            "players": self.players,
            "level": self.bot.level,
            "result_written": self._result_written,
        })

    def load(self, name=AUTOSAVE):
        data = self.store.load(name)
        if data is None or name.startswith("_"):
            raise LookupError(f"No save '{name}'.")
        self.draft = Draft.from_dict(data["draft"])
        self.players = data["players"]
        self.bot = DraftBot(self.evaluator, self.pool, data["level"], self.rng)
        self._result_written = data["result_written"]
        return self.draft

    def save_names(self):
        return [name for name in self.store.names() if not name.startswith("_")]
