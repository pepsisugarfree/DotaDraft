Dota 2 draft simulator. Two teams take turns banning and picking heroes (Captains Mode or All Pick), each team is played by you or a bot. When the draft is over, the app counts counter picks, synergy, hero strength, positions and team composition and says who outdrafted whom.

Hero stats, matchups and synergy are counted from Divine+ public matches of the current patch on [OpenDota](https://www.opendota.com) (~30 seconds on the first start) and cached locally. Only Python 3.10+ is needed, no extra packages (pytest for the tests).

## Commands

| | |
|---|---|
| `new [options]` | new draft, without options it asks questions |
| `pick <hero> [--pos=1-5]`, `ban <hero>` | your step |
| `suggest`, `auto`, `undo` | hint, let the bot move, take back |
| `board`, `history`, `score`, `results` | draft state and results |
| `heroes`, `hero <name>`, `counters <hero>`, `meta` | hero info |
| `save [name]`, `load [name]`, `saves` | saves (the last draft is saved on exit) |
| `refresh`, `help`, `exit` | system |

Heroes can be written short: `am`, `sf`, `cm`, `jugg`.

## Structure

- `core/` - heroes, matchups, hand-written hero notes, positions, draft rules, scoring, bot
- `data/` - OpenDota client, JSON parsing, cache and saves
- `cli/` - console interface: parser, command strategies, renderers, tables
- `tests/` - tests

How it all works and all the math are in [DESIGN.md](DESIGN.md).
