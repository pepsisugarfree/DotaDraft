import shlex
from dataclasses import dataclass, field

from cli.errors import CommandError


@dataclass
class Args:
    name: str
    positional: list = field(default_factory=list)
    options: dict = field(default_factory=dict)

    def get(self, index, default=None):
        if index < len(self.positional):
            return self.positional[index]
        return default

    def option(self, name, default=None):
        return self.options.get(name, default)


class ArgParser:
    """Splits 'add pikachu "mr-mime" --force' into a command name, arguments and options.

    Options look like --flag or --key=value.
    """

    def parse_args(self, line):
        try:
            tokens = shlex.split(line)
        except ValueError as error:
            raise CommandError(f"Can't read the command: {error}.")
        if not tokens:
            return None

        args = Args(tokens[0].lower())
        for token in tokens[1:]:
            if token.startswith("--") and len(token) > 2:
                key, _, value = token[2:].partition("=")
                args.options[key] = value if value else True
            else:
                args.positional.append(token)
        return args
