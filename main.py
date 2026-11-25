"""Dota 2 draft simulator.

python main.py                     the window
python main.py --console           interactive mode in the terminal
python main.py counters pudge      run one command in the terminal and quit
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
    terminal = False
    command = []
    for arg in argv:
        if arg.startswith("--data="):
            data_dir = arg.split("=", 1)[1]
        elif arg == "--no-color":
            colors = False
        elif arg == "--console":
            terminal = True
        else:
            command.append(arg)

    if not terminal and not command:
        from gui import run_gui  # tkinter is loaded only for the window

        run_gui(data_dir)
        return 0

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
