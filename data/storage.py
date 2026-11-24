import json
from pathlib import Path

from core import Hero, HeroSource, SaveStore
from data.opendota import (LANE_NAMES, WINDOW, add_ally_rows, add_matchup_rows, ally_sql, latest_patch,
                           matchup_sql, parse_heroes, parse_lanes)

CACHE_VERSION = 6  # change it when the format of the cache files changes


class JsonFiles:
    """Reads and writes small JSON files inside one folder."""

    def __init__(self, root):
        self.root = Path(root)

    def path(self, name):
        return self.root / f"{name}.json"

    def read(self, name):
        path = self.path(name)
        if not path.exists():
            return None
        with open(path, encoding="utf-8") as file:
            return json.load(file)

    def write(self, name, data):
        path = self.path(name)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(".tmp")
        with open(temp, "w", encoding="utf-8") as file:
            json.dump(data, file)
        temp.replace(path)  # so a crash never leaves half a file

    def names(self):
        if not self.root.exists():
            return []
        return sorted(path.stem for path in self.root.glob("*.json"))


class CachedHeroSource(HeroSource):
    """Heroes, matchups and synergy of the current patch, downloaded once and kept in files.

    - heroes.json: names, attributes, images (/heroStats) and lane games (/scenarios/laneRoles)
    - patch.json:  every hero against and together with every hero in Divine+ public
                   matches since the patch came out
    """

    def __init__(self, client, files):
        self.client = client
        self.files = files
        self._patch = None

    def heroes(self, refresh=False):
        cached = None if refresh else self.files.read("heroes")
        if not isinstance(cached, dict) or cached.get("version") != CACHE_VERSION:
            cached = None  # a file from an older version of the app, download again
        if cached is None:
            heroes = parse_heroes(self.client.get("heroStats"))
            raw_lanes = {}
            for lane_role in LANE_NAMES:
                raw_lanes[lane_role] = self.client.get(f"scenarios/laneRoles?lane_role={lane_role}")
            lanes = parse_lanes(raw_lanes)
            for hero in heroes:
                hero.lanes = lanes.get(hero.id, {})
            self.files.write("heroes", {"version": CACHE_VERSION,
                                        "heroes": [hero.to_dict() for hero in heroes]})
        else:
            heroes = [Hero.from_dict(item) for item in cached["heroes"]]

        if not self.has_patch_stats():
            return heroes

        # winrate of the patch: every game of a hero is counted once for each of the 5 enemies
        totals = {}
        for (hero_id, _), (games, wins) in self._pairs().items():
            total = totals.setdefault(hero_id, [0, 0])
            total[0] += games
            total[1] += wins
        for hero in heroes:
            games, wins = totals.get(hero.id, (0, 0))
            hero.games, hero.wins = games // 5, wins // 5
        return heroes

    def matchups(self, hero_id):
        return self._rows("table", "pairs", hero_id)

    def allies(self, hero_id):
        return self._rows("ally_table", "allies", hero_id)

    def patch_info(self):
        """(patch name, number of matches) or None if nothing is downloaded yet."""
        data = self._load_patch()
        if data is None:
            return None
        return data["patch"], data["matches"]

    def has_patch_stats(self):
        return self._load_patch() is not None

    def download_patch_stats(self, on_progress):
        """Goes back from the newest public match, one id window at a time,
        until the matches are older than the patch."""
        patch, since = latest_patch(self.client.get("constants/patch"))
        newest = int(self.client.query("SELECT max(match_id) AS id FROM public_matches")[0]["id"])

        # how far back to go: find the first match of the patch
        oldest = newest
        while oldest > 0:
            rows = self.client.query(
                f"SELECT start_time FROM public_matches WHERE match_id > {oldest - WINDOW} "
                "ORDER BY match_id LIMIT 1")
            oldest -= WINDOW
            if not rows or int(rows[0]["start_time"]) < since:
                break

        windows = list(range(oldest, newest, WINDOW))
        table, allies = {}, {}
        for done, low in enumerate(windows, start=1):
            add_matchup_rows(table, self.client.query(matchup_sql(low, low + WINDOW, since)))
            add_ally_rows(allies, self.client.query(ally_sql(low, low + WINDOW, since)))
            on_progress(done, len(windows))

        matches = sum(games for (a, b), (games, _) in table.items() if a < b) // 25
        self.files.write("patch", {
            "version": CACHE_VERSION,
            "patch": patch,
            "since": since,
            "matches": matches,
            "pairs": [[a, b, games, wins] for (a, b), (games, wins) in table.items()],
            "allies": [[a, b, games, wins] for (a, b), (games, wins) in allies.items()],
        })
        self._patch = None
        return patch, matches

    def _load_patch(self):
        if self._patch is None:
            data = self.files.read("patch")
            if isinstance(data, dict) and data.get("version") == CACHE_VERSION:
                self._patch = data
        return self._patch

    def _pairs(self, table="table", rows="pairs"):
        data = self._load_patch()
        if data is None:
            raise LookupError("No match statistics yet, type 'refresh' to download them.")
        if table not in data:
            data[table] = {(a, b): (games, wins) for a, b, games, wins in data[rows]}
        return data[table]

    def _rows(self, table, rows, hero_id):
        return {other: value for (hero, other), value in self._pairs(table, rows).items() if hero == hero_id}


class JsonSaveStore(SaveStore):
    def __init__(self, files):
        self.files = files

    def save(self, name, data):
        self.files.write(name, data)

    def load(self, name):
        return self.files.read(name)

    def names(self):
        return self.files.names()
