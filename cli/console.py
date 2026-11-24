import os
import sys
from abc import ABC, abstractmethod


class Console(ABC):
    """Everything the CLI needs from a terminal, so tests can replace it."""

    supports_color = False

    @abstractmethod
    def read_line(self, prompt):
        pass

    @abstractmethod
    def write(self, text, end="\n"):
        pass


class TerminalConsole(Console):
    def __init__(self):
        self.supports_color = sys.stdout.isatty() and self._enable_ansi()

    def read_line(self, prompt):
        return input(prompt)

    def write(self, text, end="\n"):
        print(text, end=end, flush=True)

    @staticmethod
    def _enable_ansi():
        if os.name != "nt":
            return True
        try:
            import ctypes

            kernel32 = ctypes.windll.kernel32
            handle = kernel32.GetStdHandle(-11)  # stdout
            mode = ctypes.c_ulong()
            if not kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
                return False
            # 0x0004 = ENABLE_VIRTUAL_TERMINAL_PROCESSING, lets Windows understand ANSI codes
            return bool(kernel32.SetConsoleMode(handle, mode.value | 0x0004))
        except (AttributeError, OSError):
            return False


class MemoryConsole(Console):
    """Takes input from a list and keeps the output; used in tests."""

    def __init__(self, lines=()):
        self.lines = list(lines)
        self.chunks = []

    def read_line(self, prompt):
        self.chunks.append(prompt)
        if not self.lines:
            raise EOFError
        line = self.lines.pop(0)
        self.chunks.append(line + "\n")
        return line

    def write(self, text, end="\n"):
        self.chunks.append(text + end)

    @property
    def text(self):
        return "".join(self.chunks)
