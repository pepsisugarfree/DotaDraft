import tkinter as tk
from tkinter import ttk

from core import POSITIONS
from gui.hero_views import HeroRows, draw_attribute
from gui.view_models import hero_cards, hero_page, hero_sections
from gui.widgets import (ATTRIBUTE_COLORS, BOLD, CARD, CARD_HOVER, CARD_PICTURE, DEEP, FIELD, FONT, GOLD, HEADER,
                         MUTED, PANEL, SMALL_FONT, TEXT, TITLE, PillGroup, RoundButton, RoundFrame, height_of, label,
                         round_rect, wheel_scroll)

CARD_WIDTH = 300
CARD_HEIGHT = 92
CARD_GAP = 12


class HeroesPage(tk.Frame):
    """The catalog: hero cards split by attribute like in the game, with a search and a position filter."""

    def __init__(self, parent, window):
        super().__init__(parent, background=DEEP)
        self.window = window
        self.cards = []
        self.hover = None
        self.backs = {}
        self.card_width = CARD_WIDTH

        bar = tk.Frame(self, background=DEEP)
        bar.pack(fill="x", padx=16, pady=(12, 10))
        label(bar, "Heroes", TITLE).pack(side="left")
        self.count = label(bar, "", FONT, MUTED)
        self.count.pack(side="left", padx=12, pady=(6, 0))
        self.position = PillGroup(bar, [("any", "Any")] + [(str(p), title) for p, title in POSITIONS.items()],
                                  "any", lambda value: self.draw(), height=30)
        self.position.pack(side="right")
        self.search = tk.StringVar()
        self.search.trace_add("write", lambda *args: self.draw())
        ttk.Entry(bar, textvariable=self.search, width=24).pack(side="right", padx=12)
        label(bar, "Find", SMALL_FONT, MUTED).pack(side="right")

        holder = RoundFrame(self, color=PANEL, padding=10, fill=True)
        holder.pack(fill="both", expand=True, padx=16, pady=(0, 12))
        self.canvas = tk.Canvas(holder.inner, background=PANEL, highlightthickness=0)
        scrollbar = ttk.Scrollbar(holder.inner, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.canvas.bind("<Configure>", lambda e: self.draw())
        self.canvas.bind("<Motion>", self._moved)
        self.canvas.bind("<Leave>", lambda e: self._set_hover(None))
        self.canvas.bind("<Button-1>", self._clicked)
        wheel_scroll(self.canvas)

    def load(self):
        app = self.window.app
        self.cards = hero_cards(app.game.pool, app.portraits)
        self.draw()

    def draw(self):
        canvas = self.canvas
        canvas.delete("all")
        self.backs = {}
        if not self.cards:
            return
        position = self.position.get()
        query = self.search.get().strip().lower()
        allowed = {card.hero_id for card in hero_cards(self.window.app.game.pool,
                                                        position=None if position == "any" else position)}
        shown = [card for card in self.cards if card.hero_id in allowed and query in card.name.lower()]
        self.count.configure(text=f"{len(shown)} heroes")
        columns = max(1, (canvas.winfo_width() + CARD_GAP) // (CARD_WIDTH + CARD_GAP))
        self.card_width = max(CARD_WIDTH, (canvas.winfo_width() + CARD_GAP) // columns - CARD_GAP)
        y = 4
        for attribute, name, cards in hero_sections(shown):
            if not cards:
                continue
            draw_attribute(canvas, 2, y + 11, attribute, f"{name.upper()}   {len(cards)}", self.window.images,
                           self.window.icon_path, HEADER)
            y += 32
            for index, card in enumerate(cards):
                x = (index % columns) * (self.card_width + CARD_GAP)
                top = y + (index // columns) * (CARD_HEIGHT + CARD_GAP)
                self._card(card, x, top)
            y += ((len(cards) - 1) // columns + 1) * (CARD_HEIGHT + CARD_GAP) + 10
        canvas.configure(scrollregion=(0, 0, canvas.winfo_width(), y))

    def _card(self, card, x, y):
        canvas = self.canvas
        tag = f"hero{card.hero_id}"
        canvas.delete(tag)
        self.backs[card.hero_id] = (card, x, y)
        color = CARD_HOVER if card.hero_id == self.hover else CARD
        round_rect(canvas, x, y, x + self.card_width, y + CARD_HEIGHT, 8, fill=color, tags=(tag,))
        picture_y = y + (CARD_HEIGHT - height_of(CARD_PICTURE)) // 2
        canvas.create_image(x + 10, picture_y, image=self.window.images.get(card.portrait, CARD_PICTURE),
                            anchor="nw", tags=(tag,))
        left = x + CARD_PICTURE + 22
        canvas.create_text(left, y + 18, text=card.name, anchor="w", fill=TEXT, font=BOLD, tags=(tag,))
        canvas.create_text(left, y + 39, text=card.roles, anchor="w", fill=GOLD, font=SMALL_FONT, tags=(tag,))
        canvas.create_text(left, y + 57, text=card.details, anchor="w", fill=MUTED, font=SMALL_FONT, tags=(tag,))
        canvas.create_text(left, y + 74, text=card.winrate, anchor="w", fill=MUTED, font=SMALL_FONT, tags=(tag,))

    def hero_at(self, event):
        x, y = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
        for hero_id, (card, left, top) in self.backs.items():
            if left <= x < left + self.card_width and top <= y < top + CARD_HEIGHT:
                return hero_id
        return None

    def _moved(self, event):
        self._set_hover(self.hero_at(event))

    def _set_hover(self, hero_id):
        if hero_id == self.hover:
            return
        old, self.hover = self.hover, hero_id
        for changed in (old, hero_id):
            if changed in self.backs:
                self._card(*self.backs[changed])  # only these two cards are drawn again
        self.canvas.configure(cursor="hand2" if hero_id else "")

    def _clicked(self, event):
        hero_id = self.hero_at(event)
        if hero_id is not None:
            self.window.open_hero(hero_id)


class HeroPage(tk.Frame):
    """One hero: big portrait, info, positions and the three hero lists."""

    def __init__(self, parent, window):
        super().__init__(parent, background=DEEP)
        self.window = window
        self.hero = None

    def show(self, hero):
        self.hero = hero
        app = self.window.app
        page = hero_page(app.game, hero, app.portraits)
        images = self.window.images
        for widget in self.winfo_children():
            widget.destroy()

        top = tk.Frame(self, background=DEEP)
        top.pack(fill="x", padx=16, pady=(14, 0))
        card = RoundFrame(top, color=PANEL, padding=16)
        card.pack(side="left")
        picture = tk.Canvas(card.inner, width=256, height=144, background=PANEL, highlightthickness=0)
        picture.create_image(0, 0, image=images.get(page.portrait), anchor="nw")
        picture.pack(side="left")
        info = tk.Frame(card.inner, background=PANEL)
        info.pack(side="left", fill="y", padx=(18, 0))
        label(info, page.name, TITLE).pack(anchor="w")
        label(info, page.about, BOLD, ATTRIBUTE_COLORS.get(page.attribute, TEXT)).pack(anchor="w")
        for title, value in (("Roles", page.roles), ("Traits", page.traits), ("Winrate", page.winrate),
                             ("Lanes", page.lanes)):
            line = tk.Frame(info, background=PANEL)
            line.pack(anchor="w", pady=1)
            label(line, title, SMALL_FONT, MUTED, width=8, anchor="w").pack(side="left")
            label(line, value, SMALL_FONT).pack(side="left")
        buttons = tk.Frame(info, background=PANEL)
        buttons.pack(anchor="w", pady=(10, 0))
        RoundButton(buttons, "Choose in draft", self.choose, kind="gold").pack(side="left")
        RoundButton(buttons, "Back", self.window.show_heroes, kind="ghost").pack(side="left", padx=(8, 0))

        positions = RoundFrame(top, color=PANEL, padding=16)
        positions.pack(side="left", padx=(12, 0), anchor="n")
        label(positions.inner, "Positions", BOLD).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 6))
        for row, (title, share) in enumerate(page.positions, start=1):
            label(positions.inner, title, SMALL_FONT, MUTED, width=10, anchor="w").grid(row=row, column=0, sticky="w")
            bar = tk.Canvas(positions.inner, width=160, height=12, background=PANEL, highlightthickness=0)
            round_rect(bar, 0, 0, 160, 12, 6, fill=FIELD, outline="")
            if share > 0.02:
                round_rect(bar, 0, 0, max(12, round(160 * share)), 12, 6, fill=GOLD, outline="")
            bar.grid(row=row, column=1, padx=8, pady=3)
            label(positions.inner, f"{share * 100:.0f}%", SMALL_FONT, width=4, anchor="e").grid(row=row, column=2)

        if page.note:
            label(self, page.note, FONT, MUTED).pack(anchor="w", padx=16, pady=16)
            return
        lists = tk.Frame(self, background=DEEP)
        lists.pack(fill="x", padx=16, pady=12)
        for column, (title, lines) in enumerate(page.lists):
            lists.columnconfigure(column, weight=1, uniform="list")
            box = RoundFrame(lists, color=PANEL, padding=14, fill=True)
            box.grid(row=0, column=column, sticky="nsew", padx=(0 if column == 0 else 12, 0))
            label(box.inner, title, BOLD).pack(anchor="w", pady=(0, 8))
            rows = HeroRows(box.inner, images, self.window.open_hero)
            rows.pack(fill="x")
            rows.show(lines)

    def choose(self):
        """Back to the draft with this hero chosen; the step is made there with one click."""
        self.window.show_draft()
        self.window.draft_page.select(self.hero.id)


class SavesPage(tk.Frame):
    """Saved drafts: load one or save the current draft under a name."""

    def __init__(self, parent, window):
        super().__init__(parent, background=DEEP)
        self.window = window
        card = RoundFrame(self, color=PANEL, padding=24, radius=20)
        card.place(relx=0.5, rely=0.42, anchor="center")
        inner = card.inner
        label(inner, "Saves", TITLE).pack(anchor="w")
        label(inner, "The last draft is saved on exit as 'autosave'.", FONT, MUTED).pack(anchor="w", pady=(2, 14))
        self.list = tk.Listbox(inner, width=36, height=12, font=("Segoe UI", 11), activestyle="none", borderwidth=0,
                               highlightthickness=0, background=FIELD, foreground=TEXT, selectbackground=GOLD,
                               selectforeground="#1d2433")
        self.list.pack(fill="x")
        self.list.bind("<Double-Button-1>", lambda e: self.load_selected())
        self.list.bind("<<ListboxSelect>>", lambda e: self._selected())
        self.load_button = RoundButton(inner, "Load", self.load_selected, kind="gold", width=320, height=38)
        self.load_button.pack(pady=(12, 18))
        label(inner, "Save the current draft as", SMALL_FONT, MUTED).pack(anchor="w")
        line = tk.Frame(inner, background=PANEL)
        line.pack(fill="x", pady=(4, 0))
        self.name = ttk.Entry(line, font=("Segoe UI", 11))
        self.name.pack(side="left", fill="x", expand=True)
        self.name.bind("<Return>", lambda e: self.save())
        self.save_button = RoundButton(line, "Save", self.save)
        self.save_button.pack(side="left", padx=(8, 0))

    def refresh(self):
        self.list.delete(0, "end")
        for name in self.window.app.game.save_names():
            self.list.insert("end", name)

    def selected(self):
        selection = self.list.curselection()
        return self.list.get(selection[0]) if selection else None

    def _selected(self):
        name = self.selected()
        if name:
            self.name.delete(0, "end")
            self.name.insert(0, name)

    def load_selected(self):
        name = self.selected()
        if name and not self.window.busy:
            self.window.show_draft()
            self.window.run_command(f'load "{name}"')

    def save(self):
        name = self.name.get().strip()
        if name and not self.window.busy:
            self.window.run_command(f'save "{name}"')

    def set_busy(self, busy):
        for button in (self.load_button, self.save_button):
            button.configure_button(enabled=not busy)
