from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Callable

from cli.errors import CommandError
from cli.parser import Args


@dataclass
class Command:
    name: str
    usage: str
    summary: str
    action: Callable[[Args], None]
    min_args: int = 0

    def execute(self, args):
        if len(args.positional) < self.min_args:
            raise CommandError(f"Usage: {self.usage}")
        self.action(args)


class CommandStrategy(ABC):
    """A group of related commands that can be plugged into the CLI."""

    title = ""

    def __init__(self, cli):
        self.cli = cli
        self._commands = {}
        self.register_commands()

    @abstractmethod
    def register_commands(self):
        pass

    def register_command(self, command):
        self._commands[command.name] = command

    def get_command_selectors(self):
        return list(self._commands)

    @property
    def commands(self):
        return list(self._commands.values())

    def exec_command(self, name, args):
        self._commands[name].execute(args)
