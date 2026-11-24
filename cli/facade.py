from cli.errors import CommandError, ExitRequested
from cli.graphics import progress_bar
from cli.parser import ArgParser

USER_ERRORS = (CommandError, ValueError, LookupError, ConnectionError, OSError)


class CLI:
    """The only thing the outside code talks to: runs commands and shows results."""

    def __init__(self, console, style, parser=None):
        self.console = console
        self.style = style
        self.parser = parser or ArgParser()
        self.prompt = lambda: "> "
        self._strategies = []
        self._owners = {}

    def use_strategy(self, strategy):
        for selector in strategy.get_command_selectors():
            if selector in self._owners:
                raise ValueError(f"Command '{selector}' is registered twice.")
            self._owners[selector] = strategy
        self._strategies.append(strategy)

    @property
    def strategies(self):
        return list(self._strategies)

    def exec_command(self, line):
        args = self.parser.parse_args(line)
        if args is None:
            return
        strategy = self._owners.get(args.name)
        if strategy is None:
            raise CommandError(f"Unknown command '{args.name}'. Type 'help' to see all commands.")
        strategy.exec_command(args.name, args)

    def run(self):
        while True:
            try:
                line = self.console.read_line(self.prompt())
                self.exec_command(line)
            except (EOFError, KeyboardInterrupt):
                # input ended or Ctrl+C, maybe in the middle of a dialog
                self.console.write("")
                return
            except ExitRequested:
                return
            except USER_ERRORS as error:
                self.error(str(error))
            except Exception as error:
                # a bug should not close the whole program
                self.error(f"Something went wrong ({type(error).__name__}: {error}).")

    def display(self, item):
        self.console.write(item.render())

    def print(self, text=""):
        self.console.write(text)

    def ask(self, question):
        return self.console.read_line(self.style.cyan(question)).strip()

    def info(self, text):
        self.console.write(self.style.dim(text))

    def success(self, text):
        self.console.write(self.style.green(text))

    def error(self, text):
        self.console.write(self.style.red(f"Error: {text}"))

    def progress(self, done, total):
        end = "\n" if done == total else ""
        self.console.write("\r" + progress_bar(done, total), end=end)
