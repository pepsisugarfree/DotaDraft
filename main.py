"""Dota 2 draft simulator.

python main.py                     interactive mode
python main.py counters pudge      run one command and quit
options: --data=DIR (where saves and cache live), --no-color
"""

import shlex
import sys

from app import DEFAULT_DATA_DIR, App
from cli import TerminalConsole
from cli.errors import ExitRequested


def main(argv):
    data_dir = DEFAULT_DATA_DIR
    colors = True
    command = []
    for arg in argv:
        if arg.startswith("--data="):
            data_dir = arg.split("=", 1)[1]
        elif arg == "--no-color":
            colors = False
        else:
            command.append(arg)

    console = TerminalConsole()
    app = App(console, data_dir, colors and console.supports_color)
    if command:
        try:
            return app.run_once(shlex.join(command))
        except ExitRequested:
            return 0
    app.run()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
