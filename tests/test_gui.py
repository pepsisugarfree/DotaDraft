import random
import threading
import time

import pytest

from app import App
from gui.console import WindowConsole
from gui.view_models import (board_view, hero_card, hero_cards, hero_page, hero_sections, hero_states,
                             score_view, suggestion_lines, timeline)
from tests.conftest import FakeSource


@pytest.fixture
def app(tmp_path):
    return App(WindowConsole(), tmp_path, colors=False, source=FakeSource(), rng=random.Random(1))


def test_hero_cards_and_filters(app):
    pool = app.game.pool
    cards = hero_cards(pool)
    assert len(cards) == 26 and cards[0].name == "Anti-Mage"
    assert cards[0].attribute == "agi" and cards[0].details == "Melee" and cards[0].roles.startswith("Carry")
    assert cards[0].portrait is None
    assert [card.name for card in hero_cards(pool, text="shadow")] == ["Shadow Fiend", "Shadow Shaman"]
    supports = hero_cards(pool, position="5", attribute="int")
    assert "Crystal Maiden" in [card.name for card in supports]
    assert all(card.attribute == "int" for card in supports)
    assert hero_card(pool.find("axe")).details == "Melee, initiator, frontline"


def test_cards_are_split_by_attribute_like_in_the_game(app):
    sections = hero_sections(hero_cards(app.game.pool))
    assert [name for attribute, name, cards in sections] == ["Strength", "Agility", "Intelligence", "Universal"]
    strength = sections[0][2]
    assert "Axe" in [card.name for card in strength] and all(card.attribute == "str" for card in strength)
    assert sum(len(cards) for attribute, name, cards in sections) == 26


def test_card_shows_downloaded_portrait(app, tmp_path):
    class Portraits:
        def cached(self, hero):
            return tmp_path / f"{hero.key}.png"

    card = hero_card(app.game.pool.find("axe"), Portraits())
    assert card.portrait == tmp_path / "axe.png"
    assert card.winrate.endswith("1,000 games")


def test_hero_page(app):
    page = hero_page(app.game, app.game.pool.find("axe"))
    assert page.name == "Axe" and page.about == "Strength, Melee" and page.traits == "initiator, frontline"
    assert page.positions[2][0] == "3 Offlane" and abs(sum(share for title, share in page.positions) - 1) < 1e-9
    assert [title for title, lines in page.lists] == ["Good against Axe", "Good against", "Works well with"]
    counters = page.lists[0][1]
    assert len(counters) == 5 and not counters[0].good and counters[0].value.startswith("+")


def test_hero_page_without_stats(app):
    def no_stats(hero_id):
        raise LookupError("No match statistics yet, type 'refresh' to download them.")

    app.game.evaluator.matchups.counters_of = no_stats
    page = hero_page(app.game, app.game.pool.find("axe"))
    assert page.lists == [] and "refresh" in page.note


def test_board_view(app):
    game = app.game
    assert board_view(game) is None
    game.new("ap", "human", "human")
    game.human_move("pick", game.pool.find("axe"), 3)
    view = board_view(game)
    assert view.title == "All Pick, step 1/10"
    assert view.turn == "Dire picks (you)" and view.turn_team == "dire"
    radiant = view.teams[0]
    assert radiant.player == "human" and radiant.slots[2].name == "Axe" and radiant.slots[0].name == "-"
    for name in ("cm", "sven", "lion", "sf", "jugg", "tide", "wd", "pa", "invoker"):
        game.human_move("pick", game.pool.find(name))
    view = board_view(game)
    assert view.turn == "The draft is over"
    assert 0 < view.radiant_chance < 1 and view.verdict


def test_timeline_and_taken_heroes(app):
    game = app.game
    assert hero_states(None) == {}
    game.new("cm", "human", "human")
    axe = game.pool.find("axe")
    game.human_move("ban", axe)
    dots = timeline(game.draft)
    assert len(dots) == 24
    assert (dots[0].team, dots[0].action, dots[0].state) == ("radiant", "ban", "done")
    assert dots[1].state == "now" and dots[2].state == "later"
    assert timeline(game.draft, game.pool)[0].hero == "Axe"
    assert hero_states(game.draft) == {axe.id: ("ban", "radiant")}


def test_suggestions_and_score(app):
    game = app.game
    game.new("ap", "human", "human")
    lines = suggestion_lines(game, count=3)
    assert len(lines) == 3 and all(line.value[0] in "+-" for line in lines)
    for name in ("axe", "cm", "sven", "lion", "sf", "jugg", "tide", "wd", "pa", "invoker"):
        game.human_move("pick", game.pool.find(name))
    score = score_view(game)
    assert [row[0] for row in score.rows][-1] == "Total" and len(score.rows) == 6
    assert 0 < score.radiant_chance < 1 and score.verdict and score.notes


def test_smooth_corners():
    from gui.widgets import coverage
    corner = coverage(6)
    assert corner[0][0] == 0 and corner[5][5] == 1  # outside and inside the circle
    assert 0 < corner[0][4] < 1  # a pixel on the edge is partly covered, that is the smoothing
    ring = coverage(6, 2)
    assert ring[5][5] == 1 and ring[0][0] == 0


def test_console_messages():
    console = WindowConsole()
    console.write("hello")
    console.post("done")
    assert console.take() == [("text", "hello\n"), ("done",)]
    assert console.take() == []


def test_console_question_is_answered_by_the_window():
    console = WindowConsole()
    answers = []
    thread = threading.Thread(target=lambda: answers.append(console.read_line("Mode? ")))
    thread.start()
    while True:
        messages = console.take()
        if messages:
            break
        time.sleep(0.01)
    kind, prompt, box = messages[0]
    assert (kind, prompt) == ("ask", "Mode? ")
    box.put("ap")
    thread.join(2)
    assert answers == ["ap"]


def test_closed_question_is_end_of_input():
    console = WindowConsole()
    errors = []

    def ask():
        try:
            console.read_line("Mode? ")
        except EOFError:
            errors.append("eof")

    thread = threading.Thread(target=ask)
    thread.start()
    while not (messages := console.take()):
        time.sleep(0.01)
    messages[0][2].put(None)
    thread.join(2)
    assert errors == ["eof"]


def test_window(app, tmp_path):
    tk = pytest.importorskip("tkinter")
    from gui.window import MainWindow

    try:
        window = MainWindow(app)
    except tk.TclError:
        pytest.skip("no screen for windows here")
    window.withdraw()

    def wait(until=lambda: not window.busy and window.ready):
        end = time.time() + 10
        while time.time() < end and not until() and not window.closed:
            window.update()
            time.sleep(0.01)
        if not window.closed:
            window.update()

    wait()
    assert window.current == "new"  # no autosave yet, so the window opens on the New draft page
    heroes = window.heroes_page
    window.show("heroes")
    assert window.current == "heroes" and len(heroes.cards) == 26
    heroes.search.set("shadow")
    assert heroes.count.cget("text") == "2 heroes"
    heroes.search.set("")
    heroes.position.set("5")
    assert heroes.count.cget("text") != "26 heroes"

    # the hero page is a page of the window, not a new window
    axe = app.game.pool.find("axe")
    window.open_hero(axe.id)
    assert window.current == "hero" and window.nav["hero"].text == "Axe"
    assert window.hero_page.hero.name == "Axe"

    # 'New draft' opens its page, 'Start' runs the command and goes back to the draft
    window.show_new_draft()
    assert window.current == "new"
    new_page = window.new_draft_page
    # the bot level is shown only when a bot plays
    new_page.groups["dire"].set("human")
    assert not new_page.groups["bot"].winfo_manager()
    new_page.groups["dire"].set("bot")
    assert new_page.groups["bot"].winfo_manager() == "grid"
    new_page.groups["mode"].set("ap")
    window.new_draft_page.start()
    wait()
    page = window.draft_page
    assert window.current == "draft"
    assert not page.teams[0].bans.winfo_manager()  # All Pick has no bans
    text = page.console.text.get("1.0", "end")
    assert "> new --mode=ap --radiant=human --dire=bot" in text

    # a click on a hero and the big button make the step
    maiden = app.game.pool.find("crystal maiden")
    page.select(maiden.id)
    assert page.side.action.text == "PICK  Crystal Maiden" and page.side.action.enabled
    page.side.position.set("5")
    page.side.action.click()
    wait()
    assert "Radiant picks Crystal Maiden (pos 5)" in page.console.text.get("1.0", "end")
    assert page.selected is None and app.game.draft.is_taken(maiden.id)
    assert page.teams[0].slots[4] is not None
    # the bot answered, now it's our step again and a taken hero can't be picked
    page.select(maiden.id)
    assert page.side.action.text == "Already taken" and not page.side.action.enabled
    page.double_click(axe.id)
    wait()
    assert app.game.draft.is_taken(axe.id)

    # questions of a command are answered in the console line
    window.run_command("new")
    wait(lambda: page.console.question is not None)
    for answer in ("ap", "", "bot", "", "", ""):
        page.console.entry.insert(0, answer)
        page.console.send()
        wait(lambda: page.console.question is not None or not window.busy)
    wait()
    assert "New All Pick draft. Radiant: human, Dire: bot." in page.console.text.get("1.0", "end")
    window.run_command("new")
    wait(lambda: page.console.question is not None)
    page.console.answer(None)
    wait()
    assert page.console.text.get("1.0", "end").rstrip().endswith("Cancelled.")

    # the console hides, but a question shows it again
    page.toggle_console()
    assert not page.console_shown
    page.show_console()
    assert page.console_shown

    window.show("saves")
    window.saves_page.name.insert(0, "first")
    window.saves_page.save()
    wait()
    window.saves_page.refresh()
    assert "first" in window.saves_page.list.get(0, "end")
    window.run_command("pick roshan")
    wait()
    assert page.console.text.tag_ranges("error")

    # Captains Mode shows the bans; the mouse over a hero frames only that tile
    window.run_command("new --mode=cm --radiant=human --dire=human")
    wait()
    assert page.teams[0].bans.winfo_manager() == "pack"
    grid = page.hero_grid
    card, x, y, state, hidden = grid.places[axe.id]
    assert grid.hero_at(x + 5, y + 5) == axe.id and grid.hero_at(-10, -10) is None
    grid._set_hover(axe.id)
    assert grid.hover == axe.id and grid.find_withtag(f"hero{axe.id}")

    # a competitive draft has no suggestions and no bot step for the players
    window.show_new_draft()
    new_page.groups["competitive"].set("yes")
    new_page.start()
    wait()
    assert app.game.competitive and "--competitive" in page.console.text.get("1.0", "end")
    assert not page.side.list_card.winfo_manager() and not page.bot_step.enabled
    assert "competitive" in page.step.cget("text")
    page.select(axe.id)
    assert page.side.action.enabled  # picking is still a click
    new_page.groups["competitive"].set("no")

    # a finished draft shows the result instead of the hero card
    window.run_command("new --mode=ap --radiant=bot --dire=bot")
    wait()
    for _ in range(10):
        window.run_command("auto")
        wait()
    assert app.game.draft.is_finished
    assert page.side.result_card.winfo_manager() == "pack" and not page.side.hero_card.winfo_manager()

    # Drow Ranger's picture on Valve's server is 128 wide, the others 256: both end up the same size
    from gui.widgets import Images
    for width in (128, 256):
        tk.PhotoImage(master=window, width=width, height=width * 9 // 16).write(str(tmp_path / f"{width}.png"),
                                                                                 format="png")
    images = Images()
    assert [images.get(tmp_path / f"{width}.png", 86).width() for width in (128, 256)] == [86, 86]
    assert images.get(tmp_path / "128.png").width() == 256

    # smooth small pictures for the grid: the same size for both, saved next to the portrait and loaded next time
    tiles = [images.small(tmp_path / f"{width}.png", 64) for width in (128, 256)]
    assert [(tile.width(), tile.height()) for tile in tiles] == [(64, 36), (64, 36)]
    assert (tmp_path / "tiles" / "256_64.png").exists()
    assert Images().small(tmp_path / "256.png", 64).height() == 36
    assert images.gray(tiles[0]).width() == 64 and images.small(None, 32).height() == 18

    # shrinking averages the pixels: black and white stripes become gray, not black or white
    from gui.widgets import resized
    stripes = tk.PhotoImage(master=window, width=4, height=2)
    stripes.put("{#000000 #ffffff #000000 #ffffff} {#000000 #ffffff #000000 #ffffff}")
    assert resized(stripes, 2, 1).get(0, 0) == (128, 128, 128)

    window.run_command("exit")
    wait()
    assert window.closed
    assert "autosave" in app.game.save_names()

    # with an autosave the window opens on the draft
    from gui.window import MainWindow as Again
    again = Again(App(WindowConsole(), tmp_path, colors=False, source=FakeSource(), rng=random.Random(1)))
    again.withdraw()
    end = time.time() + 10
    while time.time() < end and not again.ready:
        again.update()
        time.sleep(0.01)
    assert again.current == "draft" and again.app.game.draft is not None
    again.close()
