"""Canvases that draw many heroes at once: the hero grid of the draft and lists of heroes.

One canvas with pictures is much faster than a hundred small widgets."""

import tkinter as tk
import tkinter.font as tkfont

from core import ATTRIBUTES
from gui.widgets import (ATTRIBUTE_COLORS, BAN_PICTURE, BOLD, CARD, CARD_HOVER, DEEP, FONT, GOLD, GRID_TILE,
                         LINE, MUTED, PANEL, SMALL_FONT, TEAM_COLORS, TEXT, TILE, disc, height_of, round_rect,
                         shade)

SMALL_BOLD = ("Segoe UI", 8, "bold")
TILE_GAP = 3
GROUP_GAP = 18
HEADER_HEIGHT = 30
ICON = 20


def draw_attribute(canvas, x, y, attribute, text, images, icon_path, font=BOLD, tags=()):
    """The icon of the attribute from the game and its name; a colored dot until the icon is downloaded."""
    icon = images.icon(icon_path(attribute), ICON, canvas.cget("background")) if icon_path(attribute) else None
    if icon is not None:
        canvas.create_image(x, y, image=icon, anchor="w", tags=tags)
    else:
        disc(canvas, x + 4, y - 6, 12, ATTRIBUTE_COLORS[attribute], tags=tags)
    canvas.create_text(x + ICON + 7, y, text=text, anchor="w", fill=TEXT, font=font, tags=tags)


class HeroGrid(tk.Canvas):
    """All heroes as small pictures in four groups by attribute, like the draft screen of the game.

    A click selects a hero, a double click makes the current step with it.
    Picked heroes are dark with a bar in the team color, banned ones gray and dark.
    The number of columns follows the width of the canvas."""

    def __init__(self, parent, images, icon_path, on_select, on_double):
        super().__init__(parent, background=PANEL, highlightthickness=0)
        self.images = images
        self.icon_path = icon_path
        self.on_select = on_select
        self.on_double = on_double
        self.cards = []
        self.states = {}
        self.query = ""
        self.columns = 0
        self.places = {}  # hero_id: (card, x, y, state, hidden)
        self.selected = None
        self.hover = None
        self.bind("<Button-1>", lambda e: self._clicked(e, self.on_select))
        self.bind("<Double-Button-1>", lambda e: self._clicked(e, self.on_double))
        self.bind("<Motion>", self._moved)
        self.bind("<Leave>", lambda e: self._set_hover(None))
        self.bind("<Configure>", self._resized)

    def columns_for(self, width):
        group = (width - 3 * GROUP_GAP) / 4
        return max(3, min(8, int((group + TILE_GAP) // (GRID_TILE + TILE_GAP))))

    def _resized(self, event):
        if self.columns_for(event.width) != self.columns:
            self.show(self.cards, self.states, self.query)

    def show(self, cards, states, query=""):
        """cards: HeroCard list; states: {hero_id: (action, team)}; query: dims heroes that don't match."""
        self.cards, self.states, self.query = cards, states, query
        self.delete("all")
        self.places = {}
        width = self.winfo_width() if self.winfo_width() > 1 else int(self.cget("width"))
        self.columns = self.columns_for(width)
        tile_height = height_of(GRID_TILE)
        group_width = self.columns * (GRID_TILE + TILE_GAP) - TILE_GAP
        start = max(0, (width - 4 * group_width - 3 * GROUP_GAP) // 2)
        query = query.strip().lower()
        tallest = 0
        for index, (attribute, name) in enumerate(ATTRIBUTES.items()):
            left = start + index * (group_width + GROUP_GAP)
            group = [card for card in cards if card.attribute == attribute]
            draw_attribute(self, left, 13, attribute, name.upper(), self.images, self.icon_path)
            for number, card in enumerate(group):
                x = left + (number % self.columns) * (GRID_TILE + TILE_GAP)
                y = HEADER_HEIGHT + (number // self.columns) * (tile_height + TILE_GAP)
                hidden = bool(query) and query not in card.name.lower()
                self.places[card.hero_id] = (card, x, y, states.get(card.hero_id), hidden)
                self._tile(card.hero_id)
                tallest = max(tallest, y + tile_height)
        self.configure(height=tallest + 4)

    def _tile(self, hero_id):
        """Draws one hero again; on hover only the tiles that changed are drawn."""
        if hero_id not in self.places:
            return
        card, x, y, state, hidden = self.places[hero_id]
        tag = f"hero{hero_id}"
        self.delete(tag)
        height = height_of(GRID_TILE)
        action = state[0] if state else None
        picture = self.images.small(card.portrait, GRID_TILE)
        if action == "ban":
            picture = self.images.gray(picture)
        self.create_image(x, y, image=picture, anchor="nw", tags=(tag,))
        if state is not None:
            shade(self, x, y, GRID_TILE, height, 0.5 if action == "ban" else 0.55, tags=(tag,))
            if action == "pick":
                self.create_rectangle(x, y + height - 4, x + GRID_TILE, y + height, fill=TEAM_COLORS[state[1]],
                                      outline="", tags=(tag,))
        elif hidden:
            shade(self, x, y, GRID_TILE, height, 0.7, tags=(tag,))
        if hero_id == self.selected or hero_id == self.hover:
            color = GOLD if hero_id == self.selected else TEXT
            width = 2 if hero_id == self.selected else 1
            # inside the picture, so the frame never covers the neighbours
            self.create_rectangle(x + width / 2, y + width / 2, x + GRID_TILE - width / 2, y + height - width / 2,
                                  outline=color, width=width, tags=(tag,))

    def select(self, hero_id):
        old, self.selected = self.selected, hero_id
        self._tile(old)
        self._tile(hero_id)

    def hero_at(self, x, y):
        """Found by the position and not by the canvas item: the items under the
        mouse are drawn again on hover."""
        height = height_of(GRID_TILE)
        for hero_id, (card, left, top, state, hidden) in self.places.items():
            if left <= x < left + GRID_TILE and top <= y < top + height:
                return hero_id
        return None

    def _clicked(self, event, action):
        hero_id = self.hero_at(event.x, event.y)
        if hero_id is not None:
            action(hero_id)

    def _moved(self, event):
        self._set_hover(self.hero_at(event.x, event.y))

    def _set_hover(self, hero_id):
        if hero_id != self.hover:
            old, self.hover = self.hover, hero_id
            self.configure(cursor="hand2" if hero_id else "")
            self._tile(old)
            self._tile(hero_id)


class HeroRows(tk.Canvas):
    """A list of heroes, one row each: small picture, name and a number on the right."""

    ROW = 42

    def __init__(self, parent, images, on_click, width=280, color=CARD, background=None):
        background = background or parent.cget("background")
        super().__init__(parent, background=background, highlightthickness=0, width=width, height=10)
        self.images = images
        self.on_click = on_click
        self.color = color
        self.lines = []
        self.bind("<Button-1>", self._clicked)
        self.bind("<Motion>", self._moved)
        self.bind("<Leave>", lambda e: self._highlight(None))
        self.bind("<Configure>", lambda e: self._draw())
        self.hover = None

    def show(self, lines):
        self.lines = lines
        self.configure(height=max(1, len(lines) * self.ROW - 4))
        self._draw()

    def _draw(self):
        self.delete("all")
        width = max(self.winfo_width(), int(self.cget("width")) if self.winfo_width() <= 1 else 0)
        picture_height = height_of(TILE)
        for index, line in enumerate(self.lines):
            top = index * self.ROW
            color = CARD_HOVER if index == self.hover else self.color
            round_rect(self, 0, top, width, top + self.ROW - 4, 6, fill=color)
            self.create_image(0, top + (self.ROW - 4 - picture_height) // 2, image=self.images.get(line.portrait, TILE),
                              anchor="nw")
            self.create_text(TILE + 12, top + (self.ROW - 4) / 2, text=line.name, anchor="w", fill=TEXT, font=FONT)
            if line.value:
                value_color = TEAM_COLORS["radiant"] if line.good else TEAM_COLORS["dire"]
                self.create_text(width - 12, top + (self.ROW - 4) / 2, text=line.value, anchor="e",
                                 fill=value_color, font=BOLD)

    def index_at(self, y):
        index = int(y) // self.ROW
        return index if 0 <= index < len(self.lines) and y % self.ROW < self.ROW - 4 else None

    def _clicked(self, event):
        index = self.index_at(event.y)
        if index is not None:
            self.on_click(self.lines[index].hero_id)

    def _moved(self, event):
        self._highlight(self.index_at(event.y))

    def _highlight(self, index):
        if index != self.hover:
            self.hover = index
            self.configure(cursor="hand2" if index is not None else "")
            self._draw()


class BanStrip(tk.Canvas):
    """Small gray pictures of the banned heroes."""

    def __init__(self, parent, images, width=480, background=None):
        background = background or parent.cget("background")
        super().__init__(parent, background=background, highlightthickness=0, width=width, height=26)
        self.images = images

    def show(self, lines, slots=7):
        self.delete("all")
        height = height_of(BAN_PICTURE)
        self.create_text(0, height / 2, text="BANS", anchor="w", fill=MUTED, font=SMALL_FONT)
        for index in range(slots):
            x = 42 + index * (BAN_PICTURE + 5)
            if index < len(lines):
                picture = self.images.gray(self.images.get(lines[index].portrait, BAN_PICTURE))
                self.create_image(x, 0, image=picture, anchor="nw")
                shade(self, x, 0, BAN_PICTURE, height, 0.25)
            else:
                self.create_rectangle(x, 0, x + BAN_PICTURE - 1, height - 1, fill=DEEP, outline=LINE)


class PortraitSlot(tk.Canvas):
    """One position of a team on the board: picture, position and name."""

    def __init__(self, parent, images, picture_width, background=None):
        background = background or parent.cget("background")
        self.picture_width = picture_width
        self.picture_height = height_of(picture_width)
        super().__init__(parent, background=background, highlightthickness=0, width=picture_width,
                         height=self.picture_height + 40)
        self.images = images

    def show(self, slot, team, current=False):
        self.delete("all")
        width, height = self.picture_width, self.picture_height
        if slot is not None and slot.hero_id:
            self.create_image(0, 0, image=self.images.get(slot.portrait, width), anchor="nw")
            self.create_rectangle(0, height - 4, width, height, fill=TEAM_COLORS[team], outline="")
        elif current:
            self.create_rectangle(1, 1, width - 1, height - 1, fill=DEEP, outline=GOLD, width=2)
        else:
            self.create_rectangle(0, 0, width - 1, height - 1, fill=DEEP, outline=LINE)
        if slot is not None:
            self.create_text(width / 2, height + 11, text=f"{slot.position} {slot.title}", fill=MUTED,
                             font=SMALL_FONT)
            name = slot.name if slot.hero_id else ""
            font = BOLD if tkfont.Font(font=BOLD).measure(name) <= width else SMALL_BOLD
            self.create_text(width / 2, height + 28, text=name, fill=TEXT, font=font)
