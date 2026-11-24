from pathlib import Path

from core import PortraitStore

PNG_START = b"\x89PNG"


class PortraitCache(PortraitStore):
    """Hero portraits from Valve's server, kept as files so each one is downloaded only once."""

    def __init__(self, client, root):
        self.client = client
        self.root = Path(root)

    def path(self, hero):
        return self.root / f"{hero.key}.png"

    def portrait(self, hero):
        path = self.path(hero)
        if path.exists():
            return path
        if not hero.image_url:
            return None
        data = self.client.download(hero.image_url)
        if not data.startswith(PNG_START):
            raise ConnectionError(f"the picture of {hero.name} is broken, try again later")
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(".tmp")
        temp.write_bytes(data)
        temp.replace(path)  # so a crash never leaves half a picture
        return path

    def missing(self, heroes):
        return [hero for hero in heroes if hero.image_url and not self.path(hero).exists()]

    def download_all(self, heroes, on_progress):
        """Downloads the portraits that are not in the folder yet, returns how many."""
        missing = self.missing(heroes)
        for done, hero in enumerate(missing, start=1):
            self.portrait(hero)
            on_progress(done, len(missing))
        return len(missing)

    def clear(self):
        if self.root.exists():
            for path in self.root.glob("*.png"):
                path.unlink()
