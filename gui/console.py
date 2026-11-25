import queue

from cli import Console


class WindowConsole(Console):
    """A console for the CLI that lives in a window.

    Commands run in a background thread, and tkinter may only be touched from
    the main thread. So the console doesn't touch widgets at all: it puts
    messages into a queue, and the window takes them out every few milliseconds.
    """

    def __init__(self):
        self.messages = queue.Queue()

    def write(self, text, end="\n"):
        self.messages.put(("text", text + end))

    def read_line(self, prompt):
        """Asks the window to show a question and waits for the answer."""
        answer = queue.Queue(maxsize=1)
        self.messages.put(("ask", prompt, answer))
        line = answer.get()
        if line is None:  # the user closed the question
            raise EOFError
        return line

    def post(self, *message):
        self.messages.put(message)

    def take(self):
        """All messages that came since the last call."""
        result = []
        while True:
            try:
                result.append(self.messages.get_nowait())
            except queue.Empty:
                return result
