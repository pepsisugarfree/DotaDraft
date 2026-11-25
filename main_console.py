"""Entry point of DotaDraft-console.exe: the same program, but it starts in the terminal."""

import sys

from main import main

if __name__ == "__main__":
    sys.exit(main(["--console", *sys.argv[1:]]))
