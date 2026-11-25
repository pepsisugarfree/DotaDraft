Dota 2 draft simulator with a window (`python main.py`) and a console (`python main.py --console`). Two teams take turns banning and picking heroes (Captains Mode or All Pick), each team is played by you or a bot. When the draft is over, the app counts counter picks, synergy, hero strength, positions and team composition and says who outdrafted whom.

Hero stats, matchups and synergy are counted from Divine+ public matches of the current patch on [OpenDota](https://www.opendota.com) (~30 seconds on the first start) and cached locally, together with hero portraits. From source only Python 3.10+ is needed, no extra packages (pytest for the tests, PyInstaller for the build).

## Commands

| | |
|---|---|
| `new [options]` | new draft, without options it asks questions |
| `pick <hero> [--pos=1-5]`, `ban <hero>` | your step |
| `suggest`, `auto`, `undo` | hint, let the bot move, take back |
| `new --competitive` | a draft without hints: no `suggest` and `auto`, players think by themselves |
| `board`, `history`, `score`, `results` | draft state and results |
| `heroes`, `hero <name>`, `counters <hero>`, `meta` | hero info |
| `save [name]`, `load [name]`, `saves` | saves (the last draft is saved on exit if a step was made) |
| `portraits` | download pictures of all heroes |
| `refresh`, `help`, `exit` | system |

Heroes can be written short: `am`, `sf`, `cm`, `jugg`.

## Windows build

Ready programs need no Python: `DotaDraft-windows.zip` has `DotaDraft.exe` (the window) and `DotaDraft-console.exe` (the console, takes the same commands and options, e.g. `DotaDraft-console.exe counters pudge`). Each exe is one file, unpack anywhere and start. Saves, cache and portraits are kept in `%USERPROFILE%\.dotadraft`, the internet is needed on the first start to download the stats.

To build them yourself (Windows, Python 3.10+):

```
python -m pip install pyinstaller
python build.py
```

The exe files and the zip appear in `dist/`. `python build.py --debug` makes a debug build instead: a folder `dist/DotaDraft-debug/` with the exe and its libraries, and the window keeps a console where errors are printed.

## Structure

- `core/` - heroes, matchups, hand-written hero notes, positions, draft rules, scoring, bot
- `data/` - OpenDota client, JSON parsing, cache, portraits and saves
- `cli/` - console interface: parser, command strategies, renderers, tables
- `gui/` - window on tkinter: hero grid by attribute with Pick / Ban buttons, the board with portraits, hero cards, saves and the console
- `main.py` - start of the app, `main_console.py` - start of the console exe
- `build.py` - builds the exe files with PyInstaller
- `tests/` - tests

How it all works and all the math are in [DESIGN.md](DESIGN.md).
