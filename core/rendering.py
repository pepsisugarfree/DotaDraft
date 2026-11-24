from abc import ABC, abstractmethod


class Renderer(ABC):
    """Turns a core object into text. The presentation layer implements it."""

    @abstractmethod
    def render(self, item):
        pass


class Renderable:
    """A core object that is shown by a renderer set from outside."""

    _renderer = None

    @classmethod
    def use_renderer(cls, renderer):
        cls._renderer = renderer

    def render(self, renderer=None):
        renderer = renderer or type(self)._renderer
        if renderer is None:
            return str(self)
        return renderer.render(self)
