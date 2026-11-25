import tkinter as tk
from tkinter import ttk

from core import FORMATS, LEVELS, POSITIONS, TEAMS
from gui.hero_views import SMALL_BOLD, BanStrip, HeroGrid, HeroRows, PortraitSlot
from gui.view_models import (board_view, hero_card, hero_cards, hero_states, score_view, suggestion_lines,
                             timeline)
from gui.widgets import (BOARD_PICTURE, MINI_TILE, BOLD, CARD_PICTURE, DEEP, FONT, GOLD, HEADER, LINE, MONO, MUTED,
                         PANEL, SMALL_FONT, TEAM_COLORS, TEXT, TITLE, PillGroup, RoundButton, RoundFrame,
                         height_of, label, round_rect, shade)

SIDE_WIDTH = 290
CONSOLE_BACKGROUND = "#192030"


class Timeline(tk.Canvas):
    """The steps of each team in their order, a row for each team, like the top
    bar of the game. A done step shows the hero (gray for a ban), the current
    one has a gold frame, the next ones are empty boxes with P (pick) or B (ban)."""

    GAP = 3
    LABEL = 54
    HEIGHT = height_of(MINI_TILE)

    def __init__(self, parent, images):
        super().__init__(parent, background=parent.cget("background"), highlightthickness=0,
                         height=2 * self.HEIGHT + 4, width=10)
        self.images = images

    def show(self, dots):
        self.delete("all")
        if not dots:
            self.configure(width=10)
            return
        for row, team in enumerate(TEAMS):
            self.create_text(0, row * (self.HEIGHT + 4) + self.HEIGHT / 2, text=team.upper(), anchor="w",
                             fill=TEAM_COLORS[team], font=SMALL_BOLD)
        counts = {team: 0 for team in TEAMS}
        for dot in dots:
            x = self.LABEL + counts[dot.team] * (MINI_TILE + self.GAP)
            counts[dot.team] += 1
            y = 0 if dot.team == TEAMS[0] else self.HEIGHT + 4
            letter = "P" if dot.action == "pick" else "B"
            if dot.state == "done":
                picture = self.images.small(dot.portrait, MINI_TILE)
                if dot.action == "ban":
                    picture = self.images.gray(picture)
                self.create_image(x, y, image=picture, anchor="nw")
                if dot.action == "ban":
                    shade(self, x, y, MINI_TILE, self.HEIGHT, 0.35)
            elif dot.state == "now":
                self.create_rectangle(x + 1, y + 1, x + MINI_TILE - 1, y + self.HEIGHT - 1, fill=DEEP,
                                      outline=GOLD, width=2)
                self.create_text(x + MINI_TILE / 2, y + self.HEIGHT / 2, text=letter, fill=GOLD, font=SMALL_BOLD)
            else:
                self.create_rectangle(x, y, x + MINI_TILE - 1, y + self.HEIGHT - 1, fill=DEEP, outline=LINE)
                self.create_text(x + MINI_TILE / 2, y + self.HEIGHT / 2, text=letter, fill=LINE, font=SMALL_BOLD)
        self.configure(width=self.LABEL + max(counts.values()) * (MINI_TILE + self.GAP))


class TeamBoard(RoundFrame):
    """One team on the board: five positions with portraits and the bans under them."""

    def __init__(self, parent, team, images):
        super().__init__(parent, color=PANEL, padding=12)
        self.team = team
        top = tk.Frame(self.inner, background=PANEL)
        top.pack(fill="x")
        self.title = label(top, team.upper(), HEADER, TEAM_COLORS[team])
        self.title.pack(side="left")
        self.player = label(top, "", SMALL_FONT, MUTED)
        self.player.pack(side="left", padx=8, pady=(3, 0))
        self.turn = label(top, "", BOLD, GOLD)
        self.turn.pack(side="right")
        slots = tk.Frame(self.inner, background=PANEL)
        slots.pack(pady=(8, 4))
        self.slots = []
        for _ in POSITIONS:
            slot = PortraitSlot(slots, images, BOARD_PICTURE)
            slot.pack(side="left", padx=4)
            self.slots.append(slot)
        self.bans = BanStrip(self.inner, images, width=5 * (BOARD_PICTURE + 8))
        self.bans.pack(anchor="w", pady=(2, 0))

    def show(self, team_view, turn=None, bans=True):
        if bans and not self.bans.winfo_manager():
            self.bans.pack(anchor="w", pady=(2, 0))
        elif not bans:
            self.bans.pack_forget()  # All Pick has no bans
        if team_view is None:
            self.player.configure(text="")
            self.turn.configure(text="")
            for position, slot in zip(POSITIONS, self.slots):
                slot.show(None, self.team)
            self.bans.show([])
            return
        self.player.configure(text=team_view.player)
        current = turn is not None and turn[0] == self.team
        self.turn.configure(text=f"{turn[1].upper()} NOW" if current else "")
        first_empty = next((i for i, slot in enumerate(team_view.slots) if not slot.hero_id), None)
        for index, (slot_view, slot) in enumerate(zip(team_view.slots, self.slots)):
            slot.show(slot_view, self.team, current and turn[1] == "pick" and index == first_empty)
        self.bans.show(team_view.ban_lines)


class ChanceMeter(tk.Canvas):
    """Between the teams: 'VS' during the draft, the win chances when it is over."""

    def __init__(self, parent):
        super().__init__(parent, background=parent.cget("background"), highlightthickness=0, width=150,
                         height=150)

    def show(self, chance, verdict=""):
        self.delete("all")
        if chance is None:
            self.create_text(75, 75, text="VS", fill=LINE, font=("Segoe UI", 26, "bold"))
            return
        self.create_text(75, 34, text=f"{chance * 100:.0f}%", fill=TEAM_COLORS["radiant"], font=TITLE)
        self.create_text(75, 58, text="win chance", fill=MUTED, font=SMALL_FONT)
        self.create_text(75, 82, text=f"{(1 - chance) * 100:.0f}%", fill=TEAM_COLORS["dire"], font=TITLE)
        left = round(130 * chance)
        round_rect(self, 10, 108, 140, 120, 6, fill=TEAM_COLORS["dire"], outline="")
        if left > 0:
            round_rect(self, 10, 108, 10 + left, 120, 6, fill=TEAM_COLORS["radiant"], outline="")


class SidePanel(tk.Frame):
    """On the right: the chosen hero with the pick/ban button and suggestions,
    or the result when the draft is over."""

    def __init__(self, parent, page):
        super().__init__(parent, background=DEEP, width=SIDE_WIDTH)
        self.page = page
        window = page.window
        self.hero_card = RoundFrame(self, color=PANEL, padding=14)
        self.hero_card.pack(fill="x")
        inner = self.hero_card.inner
        top = tk.Frame(inner, background=PANEL)
        top.pack(fill="x")
        self.picture = tk.Canvas(top, width=CARD_PICTURE, height=72, background=PANEL, highlightthickness=0,
                                 cursor="hand2")
        self.picture.pack(side="left")
        self.picture.bind("<Button-1>", lambda e: self.page.open_selected())
        text = tk.Frame(top, background=PANEL)
        text.pack(side="left", fill="x", padx=(10, 0))
        self.name = label(text, "", HEADER, anchor="w")
        self.name.pack(anchor="w")
        self.info = label(text, "", SMALL_FONT, MUTED, justify="left", anchor="w")
        self.info.pack(anchor="w")
        self.position_line = tk.Frame(inner, background=PANEL)
        label(self.position_line, "Position", SMALL_FONT, MUTED).pack(anchor="w", pady=(10, 2))
        self.position = PillGroup(self.position_line, [("auto", "Auto")] + [(str(p), str(p)) for p in POSITIONS],
                                  "auto", height=28)
        self.position.pack(anchor="w")
        self.position_line.pack(anchor="w")
        self.action = RoundButton(inner, "Choose a hero", self.page.make_step, kind="gold",
                                  width=SIDE_WIDTH - 28, height=42, font=HEADER)
        self.action.pack(pady=(12, 0))

        self.list_card = RoundFrame(self, color=PANEL, padding=14)
        self.list_card.pack(fill="x", pady=(10, 0))
        self.list_title = label(self.list_card.inner, "Suggested now", BOLD)
        self.list_title.pack(anchor="w", pady=(0, 8))
        self.suggestions = HeroRows(self.list_card.inner, window.images, page.select, width=SIDE_WIDTH - 28)
        self.suggestions.pack()

        self.result_card = RoundFrame(self, color=PANEL, padding=14)
        self.result = tk.Frame(self.result_card.inner, background=PANEL)
        self.result.pack(fill="both")

    def show_hero(self, card, page_state):
        """page_state: (text of the button or None if the step can't be made, show the position choice)."""
        self.picture.delete("all")
        images = self.page.window.images
        if card is None:
            self.picture.create_image(0, 0, image=images.blank(CARD_PICTURE), anchor="nw")
            self.name.configure(text="No hero chosen")
            self.info.configure(text="Click a hero in the grid,\nor one of the suggestions")
        else:
            self.picture.create_image(0, 0, image=images.get(card.portrait, CARD_PICTURE), anchor="nw")
            self.name.configure(text=card.name)
            self.info.configure(text=f"{card.roles}\n{card.details}\n{card.winrate}")
        text, positions = page_state
        if positions and not self.position_line.winfo_manager():
            self.position_line.pack(anchor="w", before=self.action)
        elif not positions:
            self.position_line.pack_forget()
        self.action.configure_button(text=text or "Can't do it now", enabled=bool(text) and not self.page.window.busy)

    def show_suggestions(self, title, lines, shown=True):
        """shown=False in a competitive draft: the players think by themselves."""
        if self.result_card.winfo_manager():
            self.result_card.pack_forget()
            self.hero_card.pack(fill="x")
        if shown and not self.list_card.winfo_manager():
            self.list_card.pack(fill="x", pady=(10, 0))
        elif not shown:
            self.list_card.pack_forget()
        if self.suggestions.lines is not lines:  # a click on a hero doesn't change the list
            self.list_title.configure(text=title)
            self.suggestions.show(lines)

    def show_result(self, score):
        self.hero_card.pack_forget()
        self.list_card.pack_forget()
        self.result_card.pack(fill="x")
        for widget in self.result.winfo_children():
            widget.destroy()
        label(self.result, "Result", HEADER).pack(anchor="w")
        label(self.result, score.verdict, BOLD, GOLD, wraplength=SIDE_WIDTH - 30, justify="left").pack(
            anchor="w", pady=(2, 10))
        table = tk.Frame(self.result, background=PANEL)
        table.pack(fill="x")
        label(table, "", SMALL_FONT).grid(row=0, column=0)
        label(table, "Radiant", BOLD, TEAM_COLORS["radiant"]).grid(row=0, column=1, sticky="e", padx=6)
        label(table, "Dire", BOLD, TEAM_COLORS["dire"]).grid(row=0, column=2, sticky="e")
        for row, (title, radiant, dire) in enumerate(score.rows, start=1):
            font = BOLD if title == "Total" else FONT
            label(table, title, font, TEXT if title == "Total" else MUTED).grid(row=row, column=0, sticky="w")
            label(table, f"{radiant:+.1f}", font).grid(row=row, column=1, sticky="e", padx=6)
            label(table, f"{dire:+.1f}", font).grid(row=row, column=2, sticky="e")
        table.columnconfigure(0, weight=1)
        for note in score.notes:
            label(self.result, note, SMALL_FONT, MUTED, wraplength=SIDE_WIDTH - 30, justify="left").pack(
                anchor="w", pady=(6, 0))
        RoundButton(self.result, "New draft", self.page.window.show_new_draft, kind="gold",
                    width=SIDE_WIDTH - 28, height=40, font=HEADER).pack(pady=(14, 0))


class Console(RoundFrame):
    """The game text and a command line. The buttons do the same, but every
    command still works here, and the questions of a command are answered here."""

    def __init__(self, parent, page):
        super().__init__(parent, color=PANEL, padding=10, fill=True)
        self.page = page
        self.question = None
        self.history = []
        self.history_index = 0
        box = tk.Frame(self.inner, background=CONSOLE_BACKGROUND)
        box.pack(fill="both", expand=True)
        self.text = tk.Text(box, font=MONO, wrap="none", state="disabled", padx=10, pady=6, borderwidth=0,
                            height=5, background=CONSOLE_BACKGROUND, foreground="#d5dce6",
                            insertbackground=TEXT, selectbackground="#3b4a66", highlightthickness=0)
        self.text.tag_configure("command", foreground=GOLD)
        self.text.tag_configure("error", foreground="#ff7b72")
        scrollbar = ttk.Scrollbar(box, orient="vertical", command=self.text.yview)
        self.text.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.text.pack(fill="both", expand=True)
        line = tk.Frame(self.inner, background=PANEL)
        line.pack(fill="x", pady=(8, 0))
        label(line, ">", BOLD, GOLD).pack(side="left", padx=(2, 6))
        self.entry = ttk.Entry(line, font=MONO)
        self.entry.pack(side="left", fill="x", expand=True)
        self.entry.bind("<Return>", lambda e: self.send())
        self.entry.bind("<Escape>", lambda e: self.answer(None))
        self.entry.bind("<Up>", lambda e: self.browse_history(-1))
        self.entry.bind("<Down>", lambda e: self.browse_history(1))
        self.run = RoundButton(line, "Run", self.send, height=30)
        self.run.pack(side="left", padx=(8, 0))

    def write(self, text):
        self.text.configure(state="normal")
        if text.startswith("\r"):  # a progress bar draws itself again on the same line
            self.text.delete("end-1c linestart", "end-1c")
            text = text[1:]
        tag = "error" if text.startswith("Error:") else "command" if text.startswith("> ") else ""
        self.text.insert("end", text, tag)
        self.text.see("end")
        self.text.configure(state="disabled")

    def ask(self, prompt, answer_box):
        """A command asks a question: the next line typed here is the answer."""
        self.write(prompt)
        self.question = answer_box
        self.run.configure_button(enabled=True)
        self.entry.focus_set()

    def answer(self, line):
        if self.question is None:
            return
        box, self.question = self.question, None
        self.write((line or "") + "\n")
        box.put(line)  # None means 'cancel'

    def send(self):
        line = self.entry.get().strip()
        self.entry.delete(0, "end")
        if self.question is not None:
            self.answer(line)
            return
        if not line:
            return
        self.history.append(line)
        self.history_index = len(self.history)
        self.page.window.run_command(line)

    def browse_history(self, step):
        if not self.history:
            return
        self.history_index = min(max(self.history_index + step, 0), len(self.history))
        line = self.history[self.history_index] if self.history_index < len(self.history) else ""
        self.entry.delete(0, "end")
        self.entry.insert(0, line)


class DraftPage(tk.Frame):
    """The main page: the step line and buttons, both teams, the hero grid,
    the side panel and the console under them."""

    def __init__(self, parent, window):
        super().__init__(parent, background=DEEP)
        self.window = window
        self.selected = None
        self.cards = []
        self.suggested = ("Suggested now", [])  # counted once a step, not on every click

        header = tk.Frame(self, background=DEEP)
        header.pack(fill="x", padx=16, pady=(10, 8))
        titles = tk.Frame(header, background=DEEP)
        titles.pack(side="left")
        self.title = label(titles, "No draft yet", TITLE)
        self.title.pack(anchor="w")
        self.step = label(titles, "", FONT, MUTED)
        self.step.pack(anchor="w")
        self.timeline = Timeline(header, window.images)
        self.timeline.pack(side="left", padx=(28, 0))
        self.buttons = []
        for text, command, kind in (("Console", self.toggle_console, "ghost"),
                                    ("Undo", lambda: window.run_command("undo"), "normal"),
                                    ("Bot step", lambda: window.run_command("auto"), "normal"),
                                    ("New draft", window.show_new_draft, "gold")):
            button = RoundButton(header, text, command, kind=kind)
            button.pack(side="right", padx=(8, 0))
            if text != "Console":
                self.buttons.append(button)
            if text == "Bot step":
                self.bot_step = button

        board = tk.Frame(self, background=DEEP)
        board.pack(fill="x", padx=16)
        self.teams = [TeamBoard(board, team, window.images) for team in TEAMS]
        self.teams[0].pack(side="left")
        self.meter = ChanceMeter(board)
        self.meter.pack(side="left", expand=True)
        self.teams[1].pack(side="left")

        self.console = Console(self, self)
        self.console_shown = True
        self.console.pack(side="bottom", fill="x", padx=16, pady=(0, 12))

        body = tk.Frame(self, background=DEEP)
        body.pack(fill="both", expand=True, padx=16, pady=8)
        self.side = SidePanel(body, self)
        self.side.pack(side="right", fill="y", padx=(10, 0))
        grid_card = RoundFrame(body, color=PANEL, padding=14, fill=True)
        grid_card.pack(side="left", fill="both", expand=True)
        search_line = tk.Frame(grid_card.inner, background=PANEL)
        search_line.pack(fill="x", pady=(0, 10))
        label(search_line, "Find", SMALL_FONT, MUTED).pack(side="left")
        self.search = tk.StringVar()
        self.search.trace_add("write", lambda *args: self.refresh_grid())
        ttk.Entry(search_line, textvariable=self.search, width=22).pack(side="left", padx=(8, 12))
        self.hint = label(search_line, "Click a hero to choose, double click to make the step", SMALL_FONT, MUTED)
        self.hint.pack(side="left")
        self.hero_grid = HeroGrid(grid_card.inner, window.images, window.icon_path, self.select, self.double_click)
        self.hero_grid.pack(fill="x", anchor="n")

    def load(self):
        app = self.window.app
        self.cards = hero_cards(app.game.pool, app.portraits)
        self.refresh()

    def toggle_console(self):
        self.console_shown = not self.console_shown
        if self.console_shown:
            self.console.pack(side="bottom", fill="x", padx=16, pady=(0, 12))
        else:
            self.console.pack_forget()

    def show_console(self):
        if not self.console_shown:
            self.toggle_console()

    def write(self, text):
        self.console.write(text)

    def select(self, hero_id):
        self.selected = hero_id
        self.hero_grid.select(hero_id)
        self.refresh_side()

    def double_click(self, hero_id):
        self.select(hero_id)
        self.make_step()

    def open_selected(self):
        if self.selected is not None:
            self.window.open_hero(self.selected)

    def current_step(self):
        """(team, action) if a human can make a step now, else None."""
        game = self.window.app.game
        if game.draft is None or game.draft.is_finished or game.is_bot_turn:
            return None
        return game.draft.turn

    def make_step(self):
        step = self.current_step()
        if step is None or self.selected is None or self.window.busy:
            return
        hero = self.window.app.game.pool.get(self.selected)
        if self.window.app.game.draft.is_taken(hero.id):
            return
        line = f'{step[1]} "{hero.name}"'
        position = self.side.position.get()
        if step[1] == "pick" and position != "auto":
            line += f" --pos={position}"
        self.selected = None
        self.hero_grid.select(None)
        self.side.position.set("auto", notify=False)
        self.window.run_command(line)

    def refresh_grid(self):
        draft = self.window.app.game.draft
        self.hero_grid.show(self.cards, hero_states(draft), self.search.get())
        self.hero_grid.select(self.selected)

    def refresh(self):
        app = self.window.app
        game = app.game
        if self.cards:
            self.cards = hero_cards(game.pool, app.portraits)  # portraits may have come since
        view = board_view(game, app.portraits)
        if view is None:
            self.title.configure(text="No draft yet")
            self.step.configure(text="press New draft to start")
            self.timeline.show([])
            for board in self.teams:
                board.show(None)
            self.meter.show(None)
        else:
            self.title.configure(text=view.turn if view.radiant_chance is None else "Draft is over",
                                 foreground=TEAM_COLORS.get(view.turn_team, TEXT))
            self.step.configure(text=view.title)
            self.timeline.show(timeline(game.draft, game.pool, app.portraits))
            turn = None if game.draft.is_finished else game.draft.turn
            bans = any(action == "ban" for side, action in game.draft.format.order)
            for board, team_view in zip(self.teams, view.teams):
                board.show(team_view, turn, bans)
            self.meter.show(view.radiant_chance)
        if game.draft is not None and game.draft.is_finished:
            self.selected = None  # nothing to choose any more
        if self.cards:
            self.refresh_grid()
        self.suggested = self.suggestions()
        self.refresh_side()

    def suggestions(self):
        app = self.window.app
        step = self.current_step()
        if step is None or self.window.busy or app.game.competitive:
            return "Suggested now", []
        try:
            return f"Best to {step[1]} now", suggestion_lines(app.game, app.portraits, 4)
        except (ValueError, LookupError):
            return f"Best to {step[1]} now", []

    def refresh_side(self):
        app = self.window.app
        game = app.game
        if game.draft is not None and game.draft.is_finished:
            self.side.show_result(score_view(game))
            return
        card = None
        if self.selected is not None:
            card = hero_card(game.pool.get(self.selected), app.portraits)
        step = self.current_step()
        if game.draft is None:
            state = (None, False)
        elif step is None:
            state = ("Bot is thinking..." if game.is_bot_turn else None, False)
        elif card is None:
            state = (None, step[1] == "pick")
        elif game.draft.is_taken(card.hero_id):
            state = ("Already taken", False)
        else:
            state = (f"{step[1].upper()}  {card.name}", step[1] == "pick")
        self.side.show_hero(card, state)
        if state[0] in ("Already taken", "Bot is thinking..."):
            self.side.action.configure_button(enabled=False)
        self.side.show_suggestions(*self.suggested, shown=not game.competitive)
        # the bot doesn't make steps for the players in a competitive draft
        self.bot_step.configure_button(enabled=not self.window.busy and not (game.competitive and step is not None))

    def set_busy(self, busy):
        for button in self.buttons:
            button.configure_button(enabled=not busy)
        if self.console.question is None:
            self.console.run.configure_button(enabled=not busy)
        if not busy:
            return
        self.side.action.configure_button(enabled=False)


class NewDraftPage(tk.Frame):
    """The same choices as 'new' asks in the console, as round buttons on one card."""

    def __init__(self, parent, window):
        super().__init__(parent, background=DEEP)
        self.window = window
        card = RoundFrame(self, color=PANEL, padding=28, radius=20)
        card.place(relx=0.5, rely=0.42, anchor="center")
        inner = card.inner
        label(inner, "New draft", TITLE).grid(row=0, column=0, columnspan=2, sticky="w")
        label(inner, "Choose the mode and who plays each side.", FONT, MUTED).grid(
            row=1, column=0, columnspan=2, sticky="w", pady=(2, 18))
        choices = [
            ("mode", "Mode", [(key, f.title) for key, f in FORMATS.items()], "cm"),
            ("radiant", "Radiant", [("human", "Human"), ("bot", "Bot")], "human"),
            ("dire", "Dire", [("human", "Human"), ("bot", "Bot")], "bot"),
            ("first", "First pick", [(team, team.title()) for team in TEAMS], "radiant"),
            ("bot", "Bot level", [(level, level.title()) for level in LEVELS], "normal"),
            ("competitive", "Competitive", [("no", "No, with hints"), ("yes", "Yes, no hints")], "no"),
        ]
        self.groups = {}
        self.titles = {}
        for row, (key, title, options, default) in enumerate(choices, start=2):
            self.titles[key] = label(inner, title, BOLD, MUTED)
            self.titles[key].grid(row=row, column=0, sticky="w", pady=7, padx=(0, 30))
            group = PillGroup(inner, options, default, on_change=lambda value: self.show_bot_level())
            group.grid(row=row, column=1, sticky="w", pady=7)
            self.groups[key] = group
        buttons = tk.Frame(inner, background=PANEL)
        buttons.grid(row=len(choices) + 2, column=0, columnspan=2, sticky="e", pady=(22, 0))
        RoundButton(buttons, "Cancel", window.show_draft, kind="ghost", height=40).pack(side="left", padx=(0, 8))
        self.start_button = RoundButton(buttons, "Start the draft", self.start, kind="gold", height=40,
                                        font=HEADER)
        self.start_button.pack(side="left")
        self.show_bot_level()

    def has_bot(self):
        return "bot" in (self.groups["radiant"].get(), self.groups["dire"].get())

    def show_bot_level(self):
        """The bot level only matters when a bot plays."""
        for widget in (self.titles["bot"], self.groups["bot"]):
            if self.has_bot():
                widget.grid()
            else:
                widget.grid_remove()

    def start(self):
        if self.window.busy:
            return
        options = " ".join(f"--{key}={group.get()}" for key, group in self.groups.items()
                           if key not in ("bot", "competitive") or key == "bot" and self.has_bot())
        if self.groups["competitive"].get() == "yes":
            options += " --competitive"
        self.window.show_draft()
        self.window.run_command(f"new {options}")
