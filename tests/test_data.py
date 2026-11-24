import io
import urllib.error

import pytest

from data import CachedHeroSource, JsonFiles, JsonSaveStore, OpenDotaClient, PortraitCache, parse_heroes, parse_lanes
from data.opendota import WINDOW, add_matchup_rows, latest_patch
from tests.conftest import PICTURE, FakeImageClient, make_heroes

PATCH_START = 1_700_000_000
NEWEST_ID = 3 * WINDOW + 500

RAW_HEROES = [
    {"id": 1, "name": "npc_dota_hero_antimage", "localized_name": "Anti-Mage", "primary_attr": "agi",
     "attack_type": "Melee", "roles": ["Carry", "Escape", "Nuker"], "aliases": ["am"],
     "img": "/apps/dota2/images/dota_react/heroes/antimage.png?", "base_str": 21},
    {"id": 2, "name": "npc_dota_hero_axe", "localized_name": "Axe", "primary_attr": "str",
     "attack_type": "Melee", "roles": ["Initiator", "Durable"], "aliases": [], "img": ""},
]
RAW_LANES = {
    1: [{"hero_id": 1, "lane_role": 1, "time": 900, "games": "47", "wins": "29"},
        {"hero_id": 1, "lane_role": 1, "time": 1800, "games": "420", "wins": "203"}],
    2: [{"hero_id": 1, "lane_role": 2, "time": 1800, "games": "20", "wins": "9"}],
    3: [],
    4: [],
}
RAW_PATCHES = [{"name": "7.41", "date": "2026-03-24T00:50:59.580Z"},
               {"name": "7.42", "date": "2023-11-14T22:13:20Z"}]


class FakeClient:
    """Answers like OpenDota. Matches older than the patch start below id WINDOW."""

    def __init__(self):
        self.calls = []

    def get(self, path):
        self.calls.append(path)
        if path == "heroStats":
            return RAW_HEROES
        if path.startswith("scenarios/laneRoles"):
            return RAW_LANES[int(path[-1])]
        if path == "constants/patch":
            return RAW_PATCHES
        raise AssertionError(path)

    def query(self, sql):
        self.calls.append(sql[:30])
        if "max(match_id)" in sql:
            return [{"id": NEWEST_ID}]
        if sql.startswith("SELECT start_time"):
            low = int(sql.split("match_id > ")[1].split()[0])
            return [{"start_time": PATCH_START + 1 if low > WINDOW else PATCH_START - 1}]
        if "UNION ALL" in sql:
            # every window: Anti-Mage and Axe together 4 times, 3 wins
            return [{"a": 1, "b": 2, "games": 4, "wins": 3}]
        assert "avg_rank_tier >= 70" in sql
        # every window: Anti-Mage (radiant) beat Axe 6 times of 10
        return [{"a": 1, "b": 2, "games": 10, "wins": 6}, {"a": 0, "b": 2, "games": 5, "wins": 5}]


def test_parse_heroes():
    hero = parse_heroes(RAW_HEROES)[0]
    assert hero.key == "antimage"
    assert hero.aliases == ("am",) and not hasattr(hero, "roles")
    assert hero.image_url == "https://cdn.cloudflare.steamstatic.com/apps/dota2/images/dota_react/heroes/antimage.png"


def test_parse_lanes_adds_up_game_lengths():
    assert parse_lanes(RAW_LANES) == {1: {"safe": 467, "mid": 20, "off": 0, "jungle": 0}}


def test_latest_patch():
    assert latest_patch(RAW_PATCHES) == ("7.42", PATCH_START)


def test_matchup_rows_are_added_both_ways():
    table = {}
    add_matchup_rows(table, [{"a": 1, "b": 2, "games": 10, "wins": 6}])
    add_matchup_rows(table, [{"a": 2, "b": 1, "games": 4, "wins": 1}, {"a": 0, "b": 1, "games": 9, "wins": 9}])
    assert table == {(1, 2): [14, 9], (2, 1): [14, 5]}


def test_download_patch_stats(tmp_path):
    client = FakeClient()
    source = CachedHeroSource(client, JsonFiles(tmp_path))
    assert not source.has_patch_stats()
    with pytest.raises(LookupError, match="refresh"):
        source.matchups(1)

    progress = []
    patch, matches = source.download_patch_stats(lambda done, total: progress.append(done))
    windows = len(progress)
    assert patch == "7.42"
    assert windows == 3  # ids from WINDOW up to the newest one
    assert matches == windows * 10 // 25

    later = CachedHeroSource(client, JsonFiles(tmp_path))
    assert later.patch_info() == ("7.42", matches)
    assert later.matchups(1) == {2: (30, 18)}
    assert later.matchups(2) == {1: (30, 12)}
    assert later.allies(1) == {2: (12, 9)} and later.allies(2) == {1: (12, 9)}
    anti_mage = later.heroes()[0]
    assert (anti_mage.games, anti_mage.wins) == (6, 3)  # 30 // 5 and 18 // 5


def test_heroes_are_cached(tmp_path):
    client = FakeClient()
    CachedHeroSource(client, JsonFiles(tmp_path)).heroes()
    heroes = CachedHeroSource(client, JsonFiles(tmp_path)).heroes()
    assert heroes[0].lanes["safe"] == 467
    assert client.calls == ["heroStats"] + [f"scenarios/laneRoles?lane_role={n}" for n in (1, 2, 3, 4)]


def test_save_store(tmp_path):
    store = JsonSaveStore(JsonFiles(tmp_path))
    assert store.load("a") is None and store.names() == []
    store.save("a", {"x": 1})
    assert JsonSaveStore(JsonFiles(tmp_path)).load("a") == {"x": 1}
    assert store.names() == ["a"]


def test_api_errors(monkeypatch):
    def too_many(request, timeout):
        raise urllib.error.HTTPError(request.full_url, 429, "Too Many", {}, io.BytesIO())

    monkeypatch.setattr("urllib.request.urlopen", too_many)
    with pytest.raises(ConnectionError, match="wait a minute"):
        OpenDotaClient().get("heroStats")

    def offline(request, timeout):
        raise urllib.error.URLError("no network")

    monkeypatch.setattr("urllib.request.urlopen", offline)
    with pytest.raises(ConnectionError, match="internet"):
        OpenDotaClient().get("heroStats")


def test_explorer_error_is_reported(monkeypatch):
    monkeypatch.setattr(OpenDotaClient, "get", lambda self, path: {"err": "Query read timeout"})
    with pytest.raises(ConnectionError, match="timeout"):
        OpenDotaClient().query("SELECT 1")


def test_old_cache_files_are_downloaded_again(tmp_path):
    files = JsonFiles(tmp_path)
    # what the first version of the app wrote: a plain list with pro stats, no version
    files.write("heroes", [{"id": 1, "name": "Anti-Mage", "key": "antimage", "attribute": "agi",
                            "attack_type": "Melee", "roles": [], "aliases": [], "pro_picks": 5}])
    files.write("patch", {"patch": "7.41", "matches": 1, "pairs": [[0, 1, 5, 5]]})
    client = FakeClient()
    source = CachedHeroSource(client, files)
    assert not source.has_patch_stats()
    assert source.heroes()[1].name == "Axe"
    assert "heroStats" in client.calls


def test_hero_ignores_unknown_fields():
    from core import Hero
    hero = Hero.from_dict({"id": 1, "name": "Axe", "key": "axe", "attribute": "str",
                           "attack_type": "Melee", "roles": ["Durable"], "pro_bans": 3})
    assert hero.aliases == () and not hasattr(hero, "roles")


def test_portrait_is_downloaded_once(tmp_path):
    client = FakeImageClient()
    hero = make_heroes()[0]
    path = PortraitCache(client, tmp_path).portrait(hero)
    assert path == tmp_path / "anti-mage.png" and path.read_bytes() == PICTURE
    assert PortraitCache(client, tmp_path).portrait(hero) == path
    assert client.downloads == ["https://img/1.png"]


def test_hero_without_image_has_no_portrait(tmp_path):
    hero = make_heroes()[0]
    hero.image_url = ""
    assert PortraitCache(FakeImageClient(), tmp_path).portrait(hero) is None


def test_broken_portrait_is_not_saved(tmp_path):
    hero = make_heroes()[0]
    cache = PortraitCache(FakeImageClient(broken=[hero.image_url]), tmp_path)
    with pytest.raises(ConnectionError, match="broken"):
        cache.portrait(hero)
    assert list(tmp_path.iterdir()) == []


def test_download_all_portraits(tmp_path):
    client = FakeImageClient()
    heroes = make_heroes()
    cache = PortraitCache(client, tmp_path)
    cache.portrait(heroes[0])
    progress = []
    assert cache.download_all(heroes, lambda done, total: progress.append((done, total))) == len(heroes) - 1
    assert progress[-1] == (len(heroes) - 1, len(heroes) - 1)
    assert cache.missing(heroes) == []
    cache.clear()
    assert cache.missing(heroes) == heroes


def test_client_downloads_bytes(monkeypatch):
    class Answer(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    monkeypatch.setattr("urllib.request.urlopen", lambda request, timeout: Answer(b'{"a": 1}'))
    client = OpenDotaClient()
    assert client.download("https://img/1.png") == b'{"a": 1}'
    assert client.get("heroStats") == {"a": 1}

