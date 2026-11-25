"""Three groups of commands: information, draft actions and app infrastructure."""

from cli.command import Command, CommandStrategy
from cli.errors import CommandError, ExitRequested
from cli.graphics import Table
from cli.renderers import percent
from core import ATTRIBUTES, DIRE, FORMATS, LEVELS, PLAYERS, POSITIONS, RADIANT, TEAMS, roles, traits

def positive_number(text, default=None):
    if text is None or text is True:
        return default
    if not str(text).isdigit() or int(text) < 1:
        raise CommandError(f"'{text}' is not a positive number.")
    return int(text)


def hero_names(pool, hero_ids):
    return ", ".join(pool.get(hero_id).name for hero_id in hero_ids)


def role_names(hero):
    return ", ".join(POSITIONS[position] for position in roles(hero))


class InfoCommands(CommandStrategy):
    title = "Info"

    def __init__(self, cli, game, portraits=None):
        self.game = game
        self.pool = game.pool
        self.portraits = portraits
        super().__init__(cli)

    def register_commands(self):
        self.register_command(Command("heroes", "heroes [--pos=P] [--attr=A]", "all heroes, can filter", self.heroes))
        self.register_command(Command("hero", "hero <name>", "positions, traits, winrate, portrait", self.hero, 1))
        self.register_command(Command("counters", "counters <hero>", "counters, whom it counters, best allies",
                                      self.counters, 1))
        self.register_command(Command("meta", "meta [count]", "heroes with the best winrate", self.meta))
        self.register_command(Command("board", "board", "current draft", self.board))
        self.register_command(Command("history", "history", "all steps of the draft", self.history))
        self.register_command(Command("score", "score", "who is winning the draft and why", self.score))
        self.register_command(Command("results", "results", "results of finished drafts", self.results))

    def heroes(self, args):
        attribute = args.option("attr")
        if attribute and attribute not in ATTRIBUTES:
            raise CommandError(f"Attribute is one of: {', '.join(ATTRIBUTES)}.")
        try:
            heroes = self.pool.filter(args.option("pos"), attribute)
        except ValueError as error:
            raise CommandError(str(error))
        if not heroes:
            self.cli.info("No heroes like that.")
            return
        table = Table(["Hero", "Attr", "Attack", "Roles", "Traits"])
        for hero in heroes:
            table.add_row(hero.name, self.cli.style.attribute(hero.attribute), hero.attack_type,
                          role_names(hero), ", ".join(traits(hero)))
        self.cli.print(table.render(self.cli.style))
        self.cli.info(f"{len(heroes)} heroes")

    def hero(self, args):
        hero = self.pool.find(" ".join(args.positional))
        self.cli.display(hero)
        self.cli.print()
        if self.portraits is None:
            self.cli.print(f"Portrait: {hero.image_url or '-'}")
            return
        try:
            path = self.portraits.portrait(hero)
        except ConnectionError as error:
            self.cli.print(f"Portrait: {hero.image_url} (not downloaded: {error})")
            return
        self.cli.print(f"Portrait: {path or '-'}")

    def counters(self, args):
        hero = self.pool.find(" ".join(args.positional))
        matchups = self.game.evaluator.matchups
        for title, column, rows in (
            (f"Good against {hero.name}", "Advantage", matchups.counters_of(hero.id)),
            (f"{hero.name} is good against", "Advantage", matchups.good_against(hero.id)),
            (f"{hero.name} works well with", "Synergy", matchups.best_allies(hero.id)),
        ):
            table = Table(["Hero", column], right_aligned=[1])
            for other_id, value in rows:
                table.add_row(self.pool.get(other_id).name, f"{value * 100:+.1f}%")
            self.cli.print(self.cli.style.bold(title))
            self.cli.print(table.render(self.cli.style))
            self.cli.print()

    def meta(self, args):
        count = positive_number(args.get(0), 10)
        heroes = sorted(self.pool.all(), key=lambda hero: hero.winrate, reverse=True)[:count]
        table = Table(["Hero", "Winrate", "Games", "Roles"], right_aligned=[1, 2])
        for hero in heroes:
            table.add_row(hero.name, percent(hero.winrate), f"{hero.games:,}", role_names(hero))
        self.cli.print(table.render(self.cli.style))

    def board(self, args):
        self.cli.display(self.game.current())
        self.cli.print(next_turn_text(self.cli.style, self.game))

    def history(self, args):
        draft = self.game.current()
        if not draft.steps:
            self.cli.info("No steps yet.")
        for number, step in enumerate(draft.steps, start=1):
            self.cli.print(f"{number:>2}. {step_text(self.cli.style, self.pool, step)}")

    def score(self, args):
        draft = self.game.current()
        if not draft.picks(RADIANT) and not draft.picks(DIRE):
            raise CommandError("Nobody has picked yet.")
        self.cli.display(self.game.evaluate())

    def results(self, args):
        results = self.game.results()
        if not results:
            self.cli.info("No finished drafts yet.")
            return
        table = Table(["Date", "Mode", "Radiant", "Dire", "Radiant chance"], right_aligned=[4])
        for result in results:
            table.add_row(result["date"], result["format"], hero_names(self.pool, result["radiant"]),
                          hero_names(self.pool, result["dire"]), percent(result["radiant_chance"]))
        self.cli.print(table.render(self.cli.style))


def step_text(style, pool, step):
    verb = "picks" if step.action == "pick" else "bans"
    text = f"{style.team(step.team)} {verb} {style.bold(pool.get(step.hero_id).name)}"
    if step.position:
        text += f" (pos {step.position})"
    return text


def next_turn_text(style, game):
    draft = game.current()
    if draft.is_finished:
        return style.bold("The draft is over.")
    team, action = draft.turn
    who = "you" if game.players[team] == "human" else "bot"
    hint = f" - type '{action} <hero>'" if who == "you" else " - type 'auto' to let it move"
    if game.competitive and who == "you":
        hint += ", no hints in a competitive draft"
    return f"Next: {style.team(team)} {action}s ({who}){hint}"


class DraftCommands(CommandStrategy):
    title = "Draft"

    def __init__(self, cli, game):
        self.game = game
        self.pool = game.pool
        super().__init__(cli)

    def register_commands(self):
        self.register_command(Command(
            "new", "new [options]",
            "start a draft, without options it asks questions", self.new))
        self.register_command(Command("pick", "pick <hero> [--pos=1-5]", "pick a hero for your team", self.pick, 1))
        self.register_command(Command("ban", "ban <hero>", "ban a hero", self.ban, 1))
        self.register_command(Command("suggest", "suggest [count]", "best heroes for this step", self.suggest))
        self.register_command(Command("auto", "auto", "let the bot make your step", self.auto))
        self.register_command(Command("undo", "undo", "take back your last step", self.undo))

    def new(self, args):
        if args.options:
            settings = {
                "format_key": args.option("mode", "cm"),
                "radiant": args.option("radiant", "human"),
                "dire": args.option("dire", "bot"),
                "first": args.option("first", RADIANT),
                "level": args.option("bot", "normal"),
                "competitive": bool(args.option("competitive", False)),
            }
        else:
            settings = self._ask_settings()
        draft = self.game.new(**settings)
        players = ", ".join(f"{self.cli.style.team(t)}: {self.game.players[t]}" for t in TEAMS)
        self.cli.success(f"New {draft.format.title} draft. {players}.")
        if self.game.competitive:
            self.cli.info("Competitive draft: suggest and auto are off, think by yourself.")
        self._after_move()

    def pick(self, args):
        position = positive_number(args.option("pos"))
        self._move("pick", " ".join(args.positional), position)

    def ban(self, args):
        self._move("ban", " ".join(args.positional))

    def suggest(self, args):
        count = positive_number(args.get(0), 5)
        self.game.check_hints()
        team, action = self.game.current().turn
        self.cli.info(f"Best heroes to {action} for {team.title()} now:")
        table = Table(["Hero", "Gain", "Roles"], right_aligned=[1])
        for hero, gain in self.game.suggestions(count):
            table.add_row(hero.name, f"{gain:+.1f}", role_names(hero))
        self.cli.print(table.render(self.cli.style))

    def auto(self, args):
        if self.game.current().is_finished:
            raise CommandError("The draft is over.")
        self.cli.print(step_text(self.cli.style, self.pool, self.game.bot_move()))
        self._after_move()

    def undo(self, args):
        for step in self.game.undo():
            self.cli.info(f"Took back: {step_text(self.cli.style, self.pool, step)}")
        self.cli.display(self.game.current())
        self.cli.print(next_turn_text(self.cli.style, self.game))

    def _move(self, action, hero_text, position=None):
        hero = self.pool.find(hero_text)
        step = self.game.human_move(action, hero, position)
        self.cli.print(step_text(self.cli.style, self.pool, step))
        self._after_move()

    def _after_move(self):
        for step in self.game.play_bots():
            self.cli.print(step_text(self.cli.style, self.pool, step))
        draft = self.game.current()
        self.cli.print()
        self.cli.display(draft)
        if draft.is_finished:
            evaluation = self.game.evaluate()
            self.cli.print()
            self.cli.display(evaluation)
            winner = evaluation.winner
            loser = DIRE if winner == RADIANT else RADIANT
            if evaluation.is_even:
                self.cli.success("The drafts are even, it's up to the players.")
            else:
                self.cli.success(f"{winner.title()} outdrafted {loser.title()}!")
        else:
            self.cli.print(next_turn_text(self.cli.style, self.game))

    def _ask_settings(self):
        settings = {
            "format_key": self._choose("Mode (cm = Captains Mode, ap = All Pick)", list(FORMATS), "cm"),
            "radiant": self._choose("Radiant is played by", list(PLAYERS), "human"),
            "dire": self._choose("Dire is played by", list(PLAYERS), "bot"),
            "first": self._choose("First pick", list(TEAMS), RADIANT),
            "level": "normal",
        }
        if "bot" in (settings["radiant"], settings["dire"]):
            settings["level"] = self._choose("Bot level", list(LEVELS), "normal")
        settings["competitive"] = self._choose("Competitive, no hints", ["no", "yes"], "no") == "yes"
        return settings

    def _choose(self, question, options, default):
        while True:
            answer = self.cli.ask(f"{question} [{'/'.join(options)}, empty = {default}]: ").lower()
            if not answer:
                return default
            if answer in options:
                return answer
            self.cli.error(f"Write one of: {', '.join(options)}.")


def download_patch_stats(cli, source):
    cli.info("Downloading Divine+ matches of the current patch from OpenDota, it takes about half a minute...")
    try:
        patch, matches = source.download_patch_stats(cli.progress)
    except ConnectionError:
        cli.print()  # the error goes under the progress bar, not after it
        raise
    cli.success(f"Patch {patch}: {matches:,} Divine+ matches.")


class SystemCommands(CommandStrategy):
    title = "System"

    def __init__(self, cli, game, source, portraits=None):
        self.game = game
        self.source = source
        self.portraits = portraits
        super().__init__(cli)

    def register_commands(self):
        self.register_command(Command("refresh", "refresh", "download fresh stats of the current patch", self.refresh))
        self.register_command(Command("portraits", "portraits [--again]", "download pictures of all heroes",
                                      self.download_portraits))
        self.register_command(Command("save", "save [name]", "save the draft", self.save))
        self.register_command(Command("load", "load [name]", "load a draft (default: last one)", self.load))
        self.register_command(Command("saves", "saves", "list of saves", self.saves))
        self.register_command(Command("help", "help", "this list", self.help))
        self.register_command(Command("exit", "exit", "save and quit", self.exit))

    def refresh(self, args):
        if hasattr(self.source, "download_patch_stats"):
            download_patch_stats(self.cli, self.source)
        count = self.game.pool.refresh()
        self.game.evaluator.matchups.clear()
        self.cli.success(f"Stats of {count} heroes are up to date.")

    def download_portraits(self, args):
        if self.portraits is None:
            raise CommandError("Portraits are not available here.")
        if args.option("again"):
            self.portraits.clear()
        heroes = self.game.pool.all()
        if not self.portraits.missing(heroes) and not self.portraits.missing_icons():
            self.cli.info(f"All portraits are already in {self.portraits.root}")
            return
        self.cli.info("Downloading hero portraits...")
        try:
            count = self.portraits.download_all(heroes, self.cli.progress)
        except ConnectionError:
            self.cli.print()
            raise
        self.cli.success(f"{count} portraits saved to {self.portraits.root}")

    def save(self, args):
        name = args.get(0, "autosave")
        self.game.save(name)
        self.cli.success(f"Saved as '{name}'.")

    def load(self, args):
        name = args.get(0, "autosave")
        self.game.load(name)
        self.cli.success(f"Loaded '{name}'.")
        self.cli.display(self.game.current())
        self.cli.print(next_turn_text(self.cli.style, self.game))

    def saves(self, args):
        names = self.game.save_names()
        if names:
            self.cli.print(", ".join(names))
        else:
            self.cli.info("No saves yet.")

    def help(self, args):
        for strategy in self.cli.strategies:
            self.cli.print(self.cli.style.bold(strategy.title))
            for command in strategy.commands:
                self.cli.print(f"  {command.usage:<32}{command.summary}")
        self.cli.print()
        self.cli.info("new options: --mode=cm|ap --radiant=human|bot --dire=human|bot "
                      "--first=radiant|dire --bot=easy|normal|hard --competitive")

    def exit(self, args):
        raise ExitRequested
