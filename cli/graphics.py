"""Console-only pieces: colors, tables and bars."""

import re

ANSI_CODE = re.compile(r"\x1b\[[0-9;]*m")

ATTRIBUTE_COLORS = {"str": "91", "agi": "92", "int": "94", "all": "93"}


def visible_len(text):
    return len(ANSI_CODE.sub("", text))


class Style:
    def __init__(self, enabled=True):
        self.enabled = enabled

    def paint(self, text, code):
        if not self.enabled:
            return text
        return f"\x1b[{code}m{text}\x1b[0m"

    def bold(self, text):
        return self.paint(text, "1")

    def dim(self, text):
        return self.paint(text, "2")

    def red(self, text):
        return self.paint(text, "91")

    def green(self, text):
        return self.paint(text, "92")

    def cyan(self, text):
        return self.paint(text, "96")

    def team(self, team, text=None):
        text = text or team.title()
        return self.green(text) if team == "radiant" else self.red(text)

    def attribute(self, attribute, text=None):
        return self.paint(text or attribute, ATTRIBUTE_COLORS.get(attribute, "0"))


class Table:
    def __init__(self, headers, right_aligned=()):
        self.headers = list(headers)
        self.rows = []
        self.right_aligned = set(right_aligned)

    def add_row(self, *cells):
        self.rows.append([str(cell) for cell in cells])

    def render(self, style):
        widths = [visible_len(h) for h in self.headers]
        for row in self.rows:
            for i, cell in enumerate(row):
                widths[i] = max(widths[i], visible_len(cell))

        lines = [style.bold(self._line(self.headers, widths)), "-" * (sum(widths) + 2 * (len(widths) - 1))]
        for row in self.rows:
            lines.append(self._line(row, widths))
        return "\n".join(lines)

    def _line(self, cells, widths):
        parts = []
        for i, cell in enumerate(cells):
            padding = " " * (widths[i] - visible_len(cell))
            parts.append(padding + cell if i in self.right_aligned else cell + padding)
        return "  ".join(parts).rstrip()


def bar(value, maximum, width=20):
    filled = round(width * min(value, maximum) / maximum)
    return "#" * filled + "." * (width - filled)


def progress_bar(done, total, width=30):
    return f"[{bar(done, max(total, 1), width)}] {done}/{total}"
