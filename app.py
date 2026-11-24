from pathlib import Path

from cli import CLI, Style
from cli.facade import USER_ERRORS
from cli.renderers import DraftRenderer, EvaluationRenderer, HeroRenderer
from cli.strategies import DraftCommands, InfoCommands, SystemCommands, download_patch_stats
from core import AUTOSAVE, Draft, DraftEvaluation, DraftGame, Hero, HeroPool, Matchups
from data import CachedHeroSource, JsonFiles, JsonSaveStore, OpenDotaClient, PortraitCache

DEFAULT_DATA_DIR = Path.home() / ".dotadraft"


class App:
    """Puts the layers together: data -> core -> console interface."""

    def __init__(self, console, data_dir=DEFAULT_DATA_DIR, colors=True, source=None, rng=None, portraits=None):
        data_dir = Path(data_dir)
        if source is None:
            client = OpenDotaClient()
            source = CachedHeroSource(client, JsonFiles(data_dir / "cache"))
            portraits = PortraitCache(client, data_dir / "images")
        self.source = source
        pool = HeroPool(source)
        store = JsonSaveStore(JsonFiles(data_dir / "saves"))
        self.game = DraftGame(pool, Matchups(source, pool), store, rng)

        style = Style(colors)
        Hero.use_renderer(HeroRenderer(style))
        Draft.use_renderer(DraftRenderer(style, pool))
        DraftEvaluation.use_renderer(EvaluationRenderer(style, pool))

        self.cli = CLI(console, style)
        self.cli.prompt = self.prompt
        self.cli.use_strategy(InfoCommands(self.cli, self.game, portraits))
        self.cli.use_strategy(DraftCommands(self.cli, self.game))
        self.cli.use_strategy(SystemCommands(self.cli, self.game, source, portraits))

    def prompt(self):
        draft = self.game.draft
        if draft is None:
            return "draft> "
        if draft.is_finished:
            return "draft [over]> "
        team, action = draft.turn
        return f"draft [{team} {action}]> "

    def start(self):
        source = self.source
        if hasattr(source, "has_patch_stats"):
            try:
                if not source.has_patch_stats():
                    download_patch_stats(self.cli, source)
                patch, matches = source.patch_info()
                self.cli.info(f"Stats of patch {patch}, {matches:,} Divine+ matches.")
            except USER_ERRORS as error:
                self.cli.error(f"Couldn't download the stats: {error}. Try 'refresh' later.")

        if AUTOSAVE not in self.game.save_names():
            return
        try:
            self.game.load(AUTOSAVE)
            if not self.game.draft.is_finished:
                self.cli.info("Continuing the last draft, type 'board' to see it.")
        except USER_ERRORS as error:
            self.cli.error(f"Couldn't load the last draft: {error}")

    def autosave(self):
        if self.game.draft is not None:
            self.game.save(AUTOSAVE)

    def run(self):
        self.start()
        self.cli.info("Dota 2 draft simulator. Type 'new' to start a draft or 'help' for all commands.")
        self.cli.run()
        self.autosave()
        self.cli.info("Bye!")

    def run_once(self, line):
        """Runs one command given in the program arguments."""
        self.start()
        try:
            self.cli.exec_command(line)
        except USER_ERRORS as error:
            self.cli.error(str(error))
            return 1
        self.autosave()
        return 0
