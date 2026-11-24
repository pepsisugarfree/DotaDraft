import random

import pytest

from app import App
from cli import CLI, ArgParser, Command, CommandError, CommandStrategy, MemoryConsole, Style
from cli.graphics import ANSI_CODE, Table
from data import PortraitCache
from tests.conftest import FakeImageClient, FakeSource


class EchoCommands(CommandStrategy):
    title = "Echo"

    def register_commands(self):
        self.register_command(Command("echo", "echo <text>", "repeat", self.echo, 1))

    def echo(self, args):
        self.cli.print(" ".join(args.positional))


def make_cli(*lines):
    console = MemoryConsole(lines)
    cli = CLI(console, Style(False))
    cli.use_strategy(EchoCommands(cli))
    return cli, console


def test_parser():
    args = ArgParser().parse_args('pick "anti mage" --pos=1 --force')
    assert args.name == "pick"
    assert args.positional == ["anti mage"]
    assert args.options == {"pos": "1", "force": True}
    assert ArgParser().parse_args("  ") is None
    with pytest.raises(CommandError):
        ArgParser().parse_args('pick "pudge')


def test_cli_runs_strategy_commands():
    cli, console = make_cli("echo hi there", "nope", "echo")
    cli.run()
    assert "hi there\n" in console.text
    assert "Error: Unknown command 'nope'" in console.text
    assert "Error: Usage: echo <text>" in console.text


def test_a_bug_in_a_command_does_not_close_the_program():
    console = MemoryConsole(["boom", "echo still here"])
    cli = CLI(console, Style(False))

    class Broken(EchoCommands):
        def register_commands(self):
            super().register_commands()
            self.register_command(Command("boom", "boom", "crash", lambda args: 1 / 0))

    cli.use_strategy(Broken(cli))
    cli.run()
    assert "Error: Something went wrong (ZeroDivisionError" in console.text
    assert "still here" in console.text


def test_same_command_twice_is_rejected():
    cli, _ = make_cli()
    with pytest.raises(ValueError):
        cli.use_strategy(EchoCommands(cli))


def test_table_ignores_color_codes():
    table = Table(["A", "B"])
    table.add_row(Style(True).red("x"), "1")
    table.add_row("yy", "2")
    lines = [ANSI_CODE.sub("", line) for line in table.render(Style(False)).split("\n")]
    assert lines[2] == "x   1"
    assert lines[3] == "yy  2"


def test_hero_info_commands(run_app):
    text = run_app("hero am", "counters axe", "meta 3", "heroes --pos=5 --attr=int", "heroes --pos=support").text
    assert "Anti-Mage  (Agility, Melee)" in text
    assert "Portrait: https://img/1.png" in text
    assert "Good against Axe" in text and "Axe is good against" in text
    assert "Crystal Maiden" in text and "Lion" in text and "Anti-Mage  " in text
    assert "heroes" in text
    assert "Traits: " in text and "Roles: Carry" in text
    assert "Error: Position is 1-5" in text


def test_draft_with_dialog_against_bot(run_app):
    text = run_app("new", "ap", "", "", "dire", "hard",
                   "pick axe", "suggest 3", "pick sf --pos=2", "history").text
    assert "New All Pick draft. Radiant: human, Dire: bot." in text
    assert "Dire picks" in text
    assert "Radiant picks Axe" in text
    assert "Radiant picks Shadow Fiend (pos 2)" in text
    assert "Best heroes to pick for Radiant now:" in text
    assert " 1. Dire picks" in text


def test_wrong_moves_show_errors(run_app):
    text = run_app("pick axe", "new --mode=cm", "pick axe", "ban roshan", "ban shadow").text
    assert "Error: No draft yet" in text
    assert "Error: Now Radiant has to ban, not pick." in text
    assert "Error: No hero 'roshan'." in text
    assert "Error: 'shadow' can be:" in text


def test_full_draft_ends_with_result(run_app):
    text = run_app("new --radiant=bot --dire=bot --mode=cm", "score", "results").text
    assert "step 24/24" in text
    assert "Win chance: Radiant" in text
    assert "outdrafted" in text or "drafts are even" in text
    assert "Key matchups:" in text
    assert "Radiant chance" in text


def test_auto_and_undo(run_app):
    text = run_app("new --mode=ap", "auto", "undo", "board").text
    assert "Took back" in text
    assert "step 0/10" in text


def test_draft_continues_after_restart(run_app):
    run_app("new --mode=ap --dire=human", "pick axe")
    text = run_app("board", "pick lion").text
    assert "Continuing the last draft" in text
    assert "Dire picks Lion" in text


def test_named_saves(run_app):
    text = run_app("new --mode=ap --dire=human", "pick pudge", "save mine", "pick axe",
                   "load mine", "saves").text
    assert "Saved as 'mine'." in text
    assert "step 1/10" in text.split("Loaded 'mine'.")[1]
    assert "saves\nmine\n" in text


def test_help_lists_commands(run_app):
    text = run_app("help").text
    for name in ("heroes", "counters", "new", "pick", "ban", "suggest", "undo", "save", "load", "exit"):
        assert f"\n  {name}" in text


def test_input_ending_in_dialog_does_not_crash(run_app):
    assert run_app("new", "ap").text.endswith("Bye!\n")


def test_run_once(tmp_path):
    console = MemoryConsole()
    app = App(console, tmp_path, colors=False, source=FakeSource(), rng=random.Random(1))
    assert app.run_once("hero pudge") == 0
    assert app.run_once("hero roshan") == 1
    assert "Error: No hero 'roshan'." in console.text


def test_portraits(tmp_path):
    client = FakeImageClient(broken=["https://img/2.png"])
    console = MemoryConsole(["hero am", "hero axe", "portraits", "portraits"])
    App(console, tmp_path, colors=False, source=FakeSource(),
        portraits=PortraitCache(client, tmp_path / "images")).run()
    text = console.text
    assert f"Portrait: {tmp_path / 'images' / 'anti-mage.png'}" in text
    assert "Portrait: https://img/2.png (not downloaded: the picture of Axe is broken" in text
    assert "Error: the picture of Axe is broken" in text

    client.broken = []
    console = MemoryConsole(["portraits", "portraits", "portraits --again"])
    App(console, tmp_path, colors=False, source=FakeSource(),
        portraits=PortraitCache(client, tmp_path / "images")).run()
    text = console.text
    assert "portraits saved to" in text and "All portraits are already in" in text
    assert text.count("portraits saved to") == 2

