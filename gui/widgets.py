"""Colors, fonts and widgets with round corners.

tkinter has no round corners, so the buttons, panels and pictures here are
drawn on a Canvas. Tk draws curves without smoothing, so the corners are
small half see-through PNG pictures made here, and the rest is rectangles.
"""

import base64
import struct
import tkinter as tk
import tkinter.font as tkfont
import zlib
from fractions import Fraction
from pathlib import Path
from tkinter import ttk

FONT = ("Segoe UI", 10)
SMALL_FONT = ("Segoe UI", 9)
BOLD = ("Segoe UI", 10, "bold")
HEADER = ("Segoe UI", 12, "bold")
TITLE = ("Segoe UI", 17, "bold")
MONO = ("Consolas", 10)

MIDNIGHT = "#2f3a4f"  # rgb(47, 58, 79), the main color
DEEP = "#242d3f"  # behind the panels
PANEL = "#38445c"
CARD = "#435069"
CARD_HOVER = "#516081"
FIELD = "#1d2535"
LINE = "#56647f"
TEXT = "#eef2f8"
MUTED = "#a3afc3"
GOLD = "#e0b354"
GOLD_HOVER = "#efc670"
DARK_TEXT = "#1d2433"
TEAM_COLORS = {"radiant": "#6ccf6c", "dire": "#ef6155"}
ATTRIBUTE_COLORS = {"str": "#ec5a43", "agi": "#4fcf78", "int": "#4cbcec", "all": "#cc9fe6"}

PORTRAIT = 256  # width of a portrait on Valve's server (a few are 128)
CARD_PICTURE = 128
BOARD_PICTURE = 86  # 256 shrunk 3 times, rounded up like tkinter does
TILE = 64
GRID_TILE = 64  # pictures of the hero grid
MINI_TILE = 32  # pictures in the line of steps
BAN_PICTURE = 43
RADIUS = 10


def height_of(width):
    return (width * 9 + 15) // 16


def apply_theme(root):
    """ttk widgets that stay (text fields, lists, scroll bars) in the same colors.
    'clam' is the only built-in theme that lets you change colors."""
    root.configure(background=DEEP)
    style = ttk.Style(root)
    style.theme_use("clam")
    style.configure(".", background=DEEP, foreground=TEXT, fieldbackground=FIELD, bordercolor=LINE,
                    lightcolor=FIELD, darkcolor=FIELD, troughcolor=DEEP, font=FONT,
                    selectbackground=CARD_HOVER, selectforeground=TEXT, insertcolor=TEXT)
    style.configure("TEntry", fieldbackground=FIELD, foreground=TEXT, borderwidth=0, padding=6)
    style.map("TEntry", bordercolor=[("focus", GOLD)], lightcolor=[("focus", GOLD)])
    style.configure("TCombobox", fieldbackground=FIELD, background=CARD, foreground=TEXT, arrowcolor=TEXT,
                    borderwidth=0, padding=5)
    style.map("TCombobox", fieldbackground=[("readonly", FIELD)], foreground=[("readonly", TEXT)])
    root.option_add("*TCombobox*Listbox.background", FIELD)
    root.option_add("*TCombobox*Listbox.foreground", TEXT)
    root.option_add("*TCombobox*Listbox.selectBackground", CARD_HOVER)
    style.configure("Vertical.TScrollbar", background=CARD, troughcolor=PANEL, arrowcolor=MUTED,
                    borderwidth=0, gripcount=0)
    style.map("Vertical.TScrollbar", background=[("active", CARD_HOVER)])


SAMPLES = 4  # 4 x 4 points in every pixel of a corner give a smooth edge


def png_image(width, height, color, alphas):
    """A picture of one color where every pixel has its own transparency (0..1).
    put() of Tk 8.6 can't do that, but Tk reads it from a PNG file."""
    red, green, blue = (int(color[i:i + 2], 16) for i in (1, 3, 5))
    rows = b""
    for y in range(height):
        rows += b"\x00" + b"".join(bytes((red, green, blue, round(alphas[y][x] * 255))) for x in range(width))

    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))

    data = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b""))
    return tk.PhotoImage(data=base64.b64encode(data))


def coverage(radius, inset=0):
    """How much of every pixel of a top left corner is inside the circle, 0..1.
    With inset it is the smaller circle of the inner side of an outline."""
    small = radius - inset
    rows = []
    for y in range(radius):
        row = []
        for x in range(radius):
            inside = 0
            for sy in range(SAMPLES):
                for sx in range(SAMPLES):
                    dx = radius - x - (sx + 0.5) / SAMPLES
                    dy = radius - y - (sy + 0.5) / SAMPLES
                    if dx * dx + dy * dy <= small * small:
                        inside += 1
            row.append(inside / SAMPLES ** 2)
        rows.append(row)
    return rows


def cached(canvas, key, make):
    """Pictures made once for the window (they belong to its Tk)."""
    root = canvas.winfo_toplevel()
    if not hasattr(root, "picture_cache"):
        root.picture_cache = {}
    if key not in root.picture_cache:
        root.picture_cache[key] = make()
    return root.picture_cache[key]


def corners(canvas, radius, color, kind="fill", width=0):
    """Four corner pictures: 'fill' is a quarter of a circle, 'ring' only its edge of the given width."""
    def make():
        outer = coverage(radius)
        if kind == "ring":
            inner = coverage(radius, width)
            alphas = [[a - b for a, b in zip(row, inner_row)] for row, inner_row in zip(outer, inner)]
        else:
            alphas = outer
        flipped = [row[::-1] for row in alphas]
        return [png_image(radius, radius, color, a) for a in (alphas, flipped, alphas[::-1], flipped[::-1])]
    return cached(canvas, (radius, color, kind, width), make)


def place_corners(canvas, x1, y1, x2, y2, radius, images, tags):
    for image, x, y in zip(images, (x1, x2 - radius, x1, x2 - radius), (y1, y1, y2 - radius, y2 - radius)):
        canvas.create_image(x, y, image=image, anchor="nw", tags=tags)


def _body(canvas, x1, y1, x2, y2, radius, color, tags):
    if radius <= 0:
        canvas.create_rectangle(x1, y1, x2, y2, fill=color, outline="", tags=tags)
        return
    canvas.create_rectangle(x1 + radius, y1, x2 - radius, y2, fill=color, outline="", tags=tags)
    canvas.create_rectangle(x1, y1 + radius, x2, y2 - radius, fill=color, outline="", tags=tags)
    place_corners(canvas, x1, y1, x2, y2, radius, corners(canvas, radius, color), tags)


def round_rect(canvas, x1, y1, x2, y2, radius=RADIUS, fill="", outline="", width=1, tags=()):
    """A rectangle with round corners. Tk draws every curve with steps, so the
    corners are small pictures with smooth edges and the rest is rectangles."""
    x1, y1, x2, y2 = round(x1), round(y1), round(x2), round(y2)
    r = int(max(0, min(radius, (x2 - x1) // 2, (y2 - y1) // 2)))
    if outline == fill:
        outline = ""
    if outline and fill:
        _body(canvas, x1, y1, x2, y2, r, outline, tags)
        _body(canvas, x1 + width, y1 + width, x2 - width, y2 - width, r - width, fill, tags)
    elif fill:
        _body(canvas, x1, y1, x2, y2, r, fill, tags)
    elif outline:
        for box in ((x1 + r, y1, x2 - r, y1 + width), (x1 + r, y2 - width, x2 - r, y2),
                    (x1, y1 + r, x1 + width, y2 - r), (x2 - width, y1 + r, x2, y2 - r)):
            canvas.create_rectangle(*box, fill=outline, outline="", tags=tags)
        place_corners(canvas, x1, y1, x2, y2, r, corners(canvas, r, outline, "ring", width), tags)


def disc(canvas, x, y, size, color, tags=()):
    """A circle with smooth edges (size is even)."""
    def make():
        quarter = coverage(size // 2)
        right = [row[::-1] for row in quarter]
        top = [left + other for left, other in zip(quarter, right)]
        return png_image(size, size, color, top + top[::-1])
    canvas.create_image(round(x), round(y), image=cached(canvas, ("disc", size, color), make), anchor="nw",
                        tags=tags)


def shade(canvas, x, y, width, height, strength, tags=()):
    """A dark see-through layer over a picture: the hero is taken or doesn't fit the search."""
    image = cached(canvas, ("shade", width, height, strength),
                   lambda: png_image(width, height, DEEP, [[strength] * width] * height))
    canvas.create_image(round(x), round(y), image=image, anchor="nw", tags=tags)


def pixels(image, background=None):
    """Colors of all pixels as rows of (r, g, b). See-through pixels are mixed with the background."""
    options = ("-background", background) if background else ()
    rows = []
    for row in image.tk.splitlist(image.tk.call(image, "data", *options)):
        colors = row.split() if isinstance(row, str) else row
        rows.append([(int(str(c)[1:3], 16), int(str(c)[3:5], 16), int(str(c)[5:7], 16)) for c in colors])
    return rows


def area_weights(source, target):
    """For each new pixel: which old pixels it covers and how much of each."""
    scale = source / target
    result = []
    for i in range(target):
        start, end = i * scale, (i + 1) * scale
        taps = []
        j = int(start)
        while j < end and j < source:
            part = min(end, j + 1) - max(start, j)
            if part > 0:
                taps.append((j, part / scale))
            j += 1
        result.append(taps)
    return result


def resized(image, width, height, background=None):
    """A smaller copy where every pixel is the average of the pixels under it.
    zoom/subsample of tkinter just drop pixels, which makes the edges torn."""
    rows = pixels(image, background)
    across = area_weights(len(rows[0]), width)
    down = area_weights(len(rows), height)
    narrow = [[[sum(row[j][c] * w for j, w in taps) for c in range(3)] for taps in across] for row in rows]
    lines = []
    for taps in down:
        colors = []
        for x in range(width):
            color = [0.0, 0.0, 0.0]
            for j, w in taps:
                pixel = narrow[j][x]
                for c in range(3):
                    color[c] += pixel[c] * w
            colors.append("#%02x%02x%02x" % tuple(min(255, round(value)) for value in color))
        lines.append("{" + " ".join(colors) + "}")
    result = tk.PhotoImage(width=width, height=height)
    result.put(" ".join(lines))
    return result


class Images:
    """Loads every picture once, at the size it is needed.
    tkinter shows nothing if no one keeps the image object."""

    def __init__(self):
        self._loaded = {}
        self._blank = {}

    def get(self, path, width=PORTRAIT):
        if path is None:
            return self.blank(width)
        key = (str(path), width)
        if key not in self._loaded:
            try:
                self._loaded[key] = scaled(tk.PhotoImage(file=str(path)), width)
            except tk.TclError:  # a broken file: show an empty place instead
                self._loaded[key] = None
        return self._loaded[key] or self.blank(width)

    def gray(self, image):
        """A copy of a picture without colors, for banned heroes."""
        key = ("gray", str(image))
        if key not in self._loaded:
            copy = image.copy()
            copy.configure(palette="64")  # one number means 64 shades of gray
            self._loaded[key] = copy
        return self._loaded[key]

    def small(self, path, width):
        """A small portrait shrunk smoothly, for the hero grid and the line of steps.

        Smooth shrinking is slow in Python (~10 ms a hero), so the result is
        saved to images/tiles/ and the next start only loads the file."""
        key = ("small", str(path), width)
        if key in self._loaded:
            return self._loaded[key]
        height = height_of(width)
        if path is None:
            image = tk.PhotoImage(width=width, height=height)
            image.put(FIELD, to=(0, 0, width, height))
            self._loaded[key] = image
            return image
        path = Path(path)
        saved = path.parent / "tiles" / f"{path.stem}_{width}.png"
        try:
            if saved.exists() and saved.stat().st_mtime >= path.stat().st_mtime:
                self._loaded[key] = tk.PhotoImage(file=str(saved))
                return self._loaded[key]
        except (OSError, tk.TclError):
            pass
        source = self.get(path, PORTRAIT // 2)  # 128 x 72, an empty one if the file is broken
        image = resized(source, width, height)
        try:
            saved.parent.mkdir(exist_ok=True)
            image.write(str(saved), format="png")
        except (OSError, tk.TclError):
            pass  # no place to save it: it is made again next time
        self._loaded[key] = image
        return image

    def icon(self, path, size, background):
        """A small icon with smooth edges on the given background, or None if there is no file."""
        key = ("icon", str(path), size, background)
        if key not in self._loaded:
            try:
                self._loaded[key] = resized(tk.PhotoImage(file=str(path)), size, size, background)
            except tk.TclError:
                self._loaded[key] = None
        return self._loaded[key]

    def blank(self, width=PORTRAIT):
        """An empty picture of the portrait size, so the layout doesn't jump."""
        if width not in self._blank:
            image = tk.PhotoImage(width=width, height=height_of(width))
            image.put(FIELD, to=(0, 0, width, height_of(width)))
            self._blank[width] = image
        return self._blank[width]


def scaled(image, width):
    """tkinter can only zoom and shrink by whole numbers, so 256 -> 86 is 'shrink 3'
    and 128 -> 86 is 'zoom 2, shrink 3'."""
    ratio = Fraction(width, image.width()).limit_denominator(6)
    if ratio.numerator > 1:
        image = image.zoom(ratio.numerator)
    if ratio.denominator > 1:
        image = image.subsample(ratio.denominator)
    return image


BUTTON_KINDS = {
    # kind: (background, under the mouse, text)
    "normal": (CARD, CARD_HOVER, TEXT),
    "gold": (GOLD, GOLD_HOVER, DARK_TEXT),
    "radiant": (TEAM_COLORS["radiant"], "#86dc86", DARK_TEXT),
    "dire": (TEAM_COLORS["dire"], "#f57d73", DARK_TEXT),
    "ghost": (PANEL, CARD, MUTED),
}


class RoundButton(tk.Canvas):
    """A button with round corners. kind is one of BUTTON_KINDS."""

    def __init__(self, parent, text, command=None, kind="normal", width=None, height=34, font=BOLD,
                 background=None, radius=None):
        self.font = tkfont.Font(font=font)
        width = width or self.font.measure(text) + 32
        background = background or parent.cget("background")
        super().__init__(parent, width=width, height=height, background=background, highlightthickness=0,
                         cursor="hand2")
        self.text = text
        self.command = command
        self.kind = kind
        self.radius = radius if radius is not None else height // 2
        self.enabled = True
        self.hover = False
        self.bind("<Configure>", lambda e: self.draw())
        self.bind("<Enter>", lambda e: self._set_hover(True))
        self.bind("<Leave>", lambda e: self._set_hover(False))
        self.bind("<Button-1>", lambda e: self.click())
        self.draw()

    def draw(self):
        self.delete("all")
        width, height = int(self.cget("width")), int(self.cget("height"))
        if self.winfo_width() > 1:
            width, height = self.winfo_width(), self.winfo_height()
        fill, hover, color = BUTTON_KINDS[self.kind]
        if not self.enabled:
            fill, color = PANEL, "#6f7b92"
        elif self.hover:
            fill = hover
        round_rect(self, 0, 0, width, height, self.radius, fill=fill, outline=fill)
        self.create_text(width / 2, height / 2, text=self.text, fill=color, font=self.font)

    def configure_button(self, text=None, kind=None, enabled=None, command=None):
        if text is not None:
            self.text = text
        if kind is not None:
            self.kind = kind
        if enabled is not None:
            self.enabled = enabled
            self.configure(cursor="hand2" if enabled else "arrow")
        if command is not None:
            self.command = command
        self.draw()

    def _set_hover(self, hover):
        self.hover = hover
        self.draw()

    def click(self):
        if self.enabled and self.command:
            self.command()


class RoundFrame(tk.Frame):
    """A panel with round corners; put widgets into self.inner.

    A canvas behind the inner frame draws the round rectangle, so the panel
    is as big as its inside, or as big as it is told with pack/grid fill."""

    def __init__(self, parent, color=PANEL, padding=14, radius=RADIUS, fill=False, background=None):
        background = background or parent.cget("background")
        super().__init__(parent, background=background)
        self.color = color
        self.radius = radius
        self.back = tk.Canvas(self, background=background, highlightthickness=0)
        self.back.place(x=0, y=0, relwidth=1, relheight=1)
        self.inner = tk.Frame(self, background=color)
        self.inner.pack(fill="both", expand=fill, padx=padding, pady=padding)
        self.bind("<Configure>", self._resized)

    def _resized(self, event):
        self.back.delete("all")
        round_rect(self.back, 0, 0, event.width, event.height, self.radius, fill=self.color, outline=self.color)


class PillGroup(tk.Frame):
    """A row of round buttons where one is chosen, like radio buttons."""

    def __init__(self, parent, options, value, on_change=None, background=None, height=32):
        background = background or parent.cget("background")
        super().__init__(parent, background=background)
        self.value = value
        self.on_change = on_change
        self.buttons = {}
        for key, text in options:
            button = RoundButton(self, text, lambda key=key: self.set(key), height=height, background=background)
            button.pack(side="left", padx=(0, 6))
            self.buttons[key] = button
        self.set(value, notify=False)

    def set(self, value, notify=True):
        self.value = value
        for key, button in self.buttons.items():
            button.configure_button(kind="gold" if key == value else "normal")
        if notify and self.on_change:
            self.on_change(value)

    def get(self):
        return self.value


def label(parent, text="", font=FONT, color=TEXT, **options):
    """A plain label on the parent's background."""
    return tk.Label(parent, text=text, font=font, foreground=color, background=parent.cget("background"),
                    **options)


def wheel_scroll(canvas):
    """The mouse wheel scrolls the canvas when the mouse is over it."""
    def scroll(event):
        widget = canvas.winfo_containing(event.x_root, event.y_root)
        if widget is None or not str(widget).startswith(str(canvas)):
            return
        top, bottom = canvas.yview()
        if top > 0 or bottom < 1:
            canvas.yview_scroll(-event.delta // 120, "units")

    canvas.bind_all("<MouseWheel>", scroll, add="+")
