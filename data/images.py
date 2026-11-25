import threading
from pathlib import Path

from core import PortraitStore

PNG_START = b"\x89PNG"
ICON_URL = "https://cdn.cloudflare.steamstatic.com/apps/dota2/images/dota_react/icons/hero_{}.png"
ICON_NAMES = {"str": "strength", "agi": "agility", "int": "intelligence", "all": "universal"}


class PortraitCache(PortraitStore):
    """Hero portraits from Valve's server, kept as files so each one is downloaded only once."""

    def __init__(self, client, root):
        self.client = client
        self.root = Path(root)

    def path(self, hero):
        return self.root / f"{hero.key}.png"

    def cached(self, hero):
        path = self.path(hero)
        return path if path.exists() else None

    def portrait(self, hero):
        path = self.path(hero)
        if path.exists():
            return path
        if not hero.image_url:
            return None
        self._download(hero.image_url, path, f"the picture of {hero.name}")
        return path

    def icon_path(self, attribute):
        return self.root / "icons" / f"{ICON_NAMES[attribute]}.png"

    def icon(self, attribute):
        """The attribute icon of the game (strength, agility...), downloaded once."""
        path = self.icon_path(attribute)
        if not path.exists():
            self._download(ICON_URL.format(ICON_NAMES[attribute]), path, f"the {ICON_NAMES[attribute]} icon")
        return path

    def cached_icon(self, attribute):
        path = self.icon_path(attribute)
        return path if path.exists() else None

    def _download(self, url, path, what):
        data = self.client.download(url)
        if not data.startswith(PNG_START):
            raise ConnectionError(f"{what} is broken, try again later")
        path.parent.mkdir(parents=True, exist_ok=True)
        # the window downloads pictures in the background, so two threads may write one file
        temp = path.with_name(f"{path.stem}.{threading.get_ident()}.tmp")
        temp.write_bytes(data)
        temp.replace(path)  # so a crash never leaves half a picture

    def missing(self, heroes):
        return [hero for hero in heroes if hero.image_url and not self.path(hero).exists()]

    def missing_icons(self):
        return [attribute for attribute in ICON_NAMES if not self.icon_path(attribute).exists()]

    def download_all(self, heroes, on_progress):
        """Downloads the portraits and icons that are not in the folder yet, returns how many portraits."""
        missing = self.missing(heroes)
        icons = self.missing_icons()
        total = len(missing) + len(icons)
        for done, attribute in enumerate(icons, start=1):
            self.icon(attribute)
            on_progress(done, total)
        for done, hero in enumerate(missing, start=len(icons) + 1):
            self.portrait(hero)
            on_progress(done, total)
        return len(missing)

    def clear(self):
        """Removes the portraits, the icons and the small tiles the window made from them."""
        for folder in (self.root, self.root / "icons", self.root / "tiles"):
            if folder.exists():
                for path in folder.glob("*.png"):
                    path.unlink()
