import json
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime

from core import Hero

BASE_URL = "https://api.opendota.com/api/"
IMAGE_HOST = "https://cdn.cloudflare.steamstatic.com"
LANE_NAMES = {1: "safe", 2: "mid", 3: "off", 4: "jungle"}
WINDOW = 800_000  # match ids per explorer query; a bigger window hits the 15 s limit
DRAFT_MODES = (1, 2, 22)  # all pick, captains mode, ranked all pick - no turbo
MIN_RANK = 70  # average rank of the match: 70 is Divine 1, 80 is Immortal

class OpenDotaClient:
    def __init__(self, base_url=BASE_URL, timeout=60):
        self.base_url = base_url
        self.timeout = timeout

    def get(self, path):
        return json.loads(self.download(self.base_url + path))

    def download(self, url):
        """Raw bytes of any link: an answer of the API or a picture."""
        request = urllib.request.Request(url, headers={"User-Agent": "dota-draft"})
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return response.read()
        except urllib.error.HTTPError as error:
            if error.code == 429:
                raise ConnectionError("OpenDota says too many requests, wait a minute.")
            raise ConnectionError(f"OpenDota answered with error {error.code}.")
        except (urllib.error.URLError, TimeoutError) as error:
            raise ConnectionError(f"Can't reach OpenDota ({error}). Check the internet.")

    def query(self, sql):
        """Runs SQL on OpenDota's database (the 'explorer') and returns the rows."""
        answer = self.get("explorer?sql=" + urllib.parse.quote(sql))
        if answer.get("err"):
            raise ConnectionError(f"OpenDota explorer: {answer['err']}")
        return answer["rows"]


def parse_heroes(raw):
    """/heroStats has ~100 fields per hero, we keep only what the draft needs."""
    heroes = []
    for item in raw:
        heroes.append(Hero(
            id=item["id"],
            name=item["localized_name"],
            key=item["name"].replace("npc_dota_hero_", ""),
            attribute=item["primary_attr"],
            attack_type=item["attack_type"],
            aliases=tuple(item.get("aliases") or ()),
            image_url=IMAGE_HOST + item["img"].rstrip("?") if item.get("img") else "",
        ))
    return heroes


def parse_lanes(raw_by_lane):
    """{lane_role: rows of /scenarios/laneRoles} -> {hero_id: {"safe": games, ...}}

    The rows are split by game length, so games are added up.
    """
    lanes = {}
    for lane_role, rows in raw_by_lane.items():
        for row in rows:
            hero = lanes.setdefault(row["hero_id"], {name: 0 for name in LANE_NAMES.values()})
            hero[LANE_NAMES[lane_role]] += int(row["games"])
    return lanes


def latest_patch(raw):
    """/constants/patch -> (name, start as unix time)"""
    last = raw[-1]
    start = datetime.fromisoformat(last["date"].replace("Z", "+00:00"))
    return last["name"], int(start.timestamp())


def matches_sql(low_id, high_id, since):
    modes = ", ".join(str(mode) for mode in DRAFT_MODES)
    return (
        "WITH m AS (SELECT radiant_team r, dire_team d, radiant_win w FROM public_matches "
        f"WHERE match_id > {low_id} AND match_id <= {high_id} AND start_time >= {since} "
        f"AND game_mode IN ({modes}) AND avg_rank_tier >= {MIN_RANK} AND radiant_team[1] > 0) "
    )


def matchup_sql(low_id, high_id, since):
    """Every radiant hero against every dire hero in Divine+ matches of one id window."""
    return (matches_sql(low_id, high_id, since) +
            "SELECT a, b, count(*) games, sum(w::int) wins FROM m, unnest(r) a, unnest(d) b GROUP BY a, b")


def ally_sql(low_id, high_id, since):
    """Every two heroes of the same team: games together and wins together."""
    return (matches_sql(low_id, high_id, since) +
            "SELECT a, b, count(*) games, sum(win::int) wins FROM ("
            "SELECT a, b, w win FROM m, unnest(r) a, unnest(r) b WHERE a < b "
            "UNION ALL SELECT a, b, NOT w FROM m, unnest(d) a, unnest(d) b WHERE a < b) t GROUP BY a, b")


def add_matchup_rows(table, rows):
    """Adds explorer rows (radiant hero a, dire hero b, games, radiant wins) to
    table {(hero, enemy): [games, wins of hero]}, both ways round."""
    for row in rows:
        a, b = int(row["a"]), int(row["b"])
        if a <= 0 or b <= 0:
            continue  # OpenDota writes 0 when it doesn't know the hero
        games, wins = int(row["games"]), int(row["wins"])
        first = table.setdefault((a, b), [0, 0])
        first[0] += games
        first[1] += wins
        second = table.setdefault((b, a), [0, 0])
        second[0] += games
        second[1] += games - wins


def add_ally_rows(table, rows):
    """Adds explorer rows (hero a, hero b, games together, wins) to table {(hero, ally): [games, wins]}."""
    for row in rows:
        a, b = int(row["a"]), int(row["b"])
        if a <= 0 or b <= 0:
            continue
        games, wins = int(row["games"]), int(row["wins"])
        for pair in ((a, b), (b, a)):
            total = table.setdefault(pair, [0, 0])
            total[0] += games
            total[1] += wins
