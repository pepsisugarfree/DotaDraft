import threading
import tkinter as tk

from app import App
from cli.errors import ExitRequested
from cli.facade import USER_ERRORS
from gui.console import WindowConsole
from gui.draft_page import DraftPage, NewDraftPage
from gui.pages import HeroesPage, HeroPage, SavesPage
from gui.widgets import DEEP, GOLD, MIDNIGHT, MUTED, SMALL_FONT, TITLE, Images, RoundButton, apply_theme, label

POLL_MS = 40


class MainWindow(tk.Tk):
    """A bar with the pages on top and one page under it: the draft, the new
    draft settings, the hero cards, one hero or the saves. No pop-up windows.

    The window only shows things. Everything the user does becomes a console
    command ('pick "Axe"', 'load "my draft"') and goes to the same CLI as in
    the terminal, in a background thread so the window doesn't freeze while
    the stats or the pictures are downloading.
    """

    def __init__(self, app):
        super().__init__()
        self.app = app
        self.console = app.cli.console
        self.images = Images()
        self.busy = False
        self.ready = False
        self.closed = False

        self.title("Dota 2 Draft Simulator")
        self.geometry("1500x960")
        self.minsize(1400, 900)
        try:
            self.state("zoomed")  # the whole screen on Windows
        except tk.TclError:
            pass
        apply_theme(self)

        bar = tk.Frame(self, background=MIDNIGHT)
        bar.pack(fill="x")
        label(bar, "DOTA 2 DRAFT", TITLE, GOLD).pack(side="left", padx=(18, 24), pady=10)
        self.nav = {}
        for key, text in (("draft", "Draft"), ("heroes", "Heroes"), ("hero", "Hero"), ("saves", "Saves")):
            button = RoundButton(bar, text, lambda key=key: self.show(key), kind="ghost", height=32)
            button.pack(side="left", padx=(0, 6))
            self.nav[key] = button
        self.nav["hero"].pack_forget()
        self.status = label(bar, "", SMALL_FONT, MUTED)
        self.status.pack(side="right", padx=18)

        pages = tk.Frame(self, background=DEEP)
        pages.pack(fill="both", expand=True)
        pages.rowconfigure(0, weight=1)
        pages.columnconfigure(0, weight=1)
        self.draft_page = DraftPage(pages, self)
        self.new_draft_page = NewDraftPage(pages, self)
        self.heroes_page = HeroesPage(pages, self)
        self.hero_page = HeroPage(pages, self)
        self.saves_page = SavesPage(pages, self)
        self.pages = {"draft": self.draft_page, "new": self.new_draft_page, "heroes": self.heroes_page,
                      "hero": self.hero_page, "saves": self.saves_page}
        for page in self.pages.values():
            page.grid(row=0, column=0, sticky="nsew")
        self.current = None
        self.show("draft")

        self.protocol("WM_DELETE_WINDOW", self.close)
        self.draft_page.refresh()
        self.after(POLL_MS, self.poll)
        self.in_background(app.start, "ready")

    def show(self, key):
        self.current = key
        self.pages[key].tkraise()
        highlighted = "draft" if key == "new" else key
        for name, button in self.nav.items():
            button.configure_button(kind="gold" if name == highlighted else "ghost")
        if key == "saves":
            self.saves_page.refresh()

    def in_background(self, work, done_message):
        self.busy = True
        self.set_busy(True)
        self.status.configure(text="Working...")

        def run():
            try:
                work()
            except ExitRequested:
                self.console.post("exit")
            except EOFError:
                self.app.cli.info("Cancelled.")
            except USER_ERRORS as error:
                self.app.cli.error(str(error))
            except Exception as error:
                self.app.cli.error(f"Something went wrong ({type(error).__name__}: {error}).")
            self.console.post(done_message)

        threading.Thread(target=run, daemon=True).start()

    def set_busy(self, busy):
        self.draft_page.set_busy(busy)
        self.saves_page.set_busy(busy)
        self.new_draft_page.start_button.configure_button(enabled=not busy)

    def run_command(self, line):
        if self.busy:
            return
        self.draft_page.write(f"> {line}\n")
        self.in_background(lambda: self.app.cli.exec_command(line), "done")

    def poll(self):
        """Takes what the background thread said and shows it."""
        try:
            self.show_messages()
        finally:
            # even after a bug in the window the messages must keep coming
            if not self.closed:
                self.after(POLL_MS, self.poll)

    def show_messages(self):
        for message in self.console.take():
            kind = message[0]
            if kind == "text":
                self.draft_page.write(message[1])
            elif kind == "ask":
                self.show("draft")
                self.draft_page.show_console()
                self.draft_page.console.ask(message[1], message[2])
            elif kind in ("done", "ready"):
                self.finished(kind)
            elif kind == "portraits":
                self.status.configure(text=f"Downloading portraits {message[1]}/{message[2]}...")
            elif kind == "portraits done":
                self.status.configure(text=message[1])
                self.draft_page.load()
                self.heroes_page.load()
            elif kind == "exit":
                self.close()
                return

    def finished(self, kind):
        self.busy = False
        self.set_busy(False)
        self.status.configure(text="")
        if kind == "ready":
            self.ready = True
            self.draft_page.write("Pick heroes in the grid or type commands here, 'help' lists all of them.\n")
            try:
                self.draft_page.load()
                self.heroes_page.load()
            except USER_ERRORS as error:
                self.draft_page.write(f"Error: couldn't load the heroes: {error}\n")
            self.download_portraits()
            if self.app.game.draft is None and self.current == "draft":
                self.show("new")  # nothing to continue: start with the settings of a new draft
        self.draft_page.refresh()
        self.saves_page.refresh()

    def download_portraits(self):
        """Pictures that are not in the folder yet are downloaded while the user plays."""
        portraits = self.app.portraits
        if portraits is None:
            return
        try:
            heroes = self.app.game.pool.all()
        except USER_ERRORS:
            return
        if not portraits.missing(heroes) and not portraits.missing_icons():
            return

        def run():
            try:
                count = portraits.download_all(heroes, lambda done, total: self.console.post("portraits", done, total))
                self.console.post("portraits done", f"{count} portraits downloaded.")
            except ConnectionError as error:
                self.console.post("portraits done", f"Couldn't download the portraits: {error}")

        threading.Thread(target=run, daemon=True).start()

    def open_hero(self, hero_id):
        hero = self.app.game.pool.get(hero_id)
        self.hero_page.show(hero)
        self.nav["hero"].configure_button(text=hero.name)
        self.nav["hero"].configure(width=self.nav["hero"].font.measure(hero.name) + 32)
        self.nav["hero"].pack(side="left", padx=(0, 6), before=self.nav["saves"])
        self.show("hero")

    def icon_path(self, attribute):
        """The downloaded icon of an attribute or None."""
        return self.app.portraits.cached_icon(attribute) if self.app.portraits is not None else None

    def show_draft(self):
        self.show("draft")

    def show_new_draft(self):
        self.show("new")

    def show_heroes(self):
        self.show("heroes")

    def close(self):
        if self.closed:
            return
        self.closed = True
        self.draft_page.console.answer(None)  # a command waiting for an answer must not hang
        try:
            self.app.autosave()
        except USER_ERRORS:
            pass
        self.destroy()


def run_gui(data_dir):
    app = App(WindowConsole(), data_dir, colors=False)
    MainWindow(app).mainloop()
