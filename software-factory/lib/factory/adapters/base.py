import hashlib
import re

from ..errors import FactoryError

OPTIONAL = ("send_prompt", "focus", "state", "wait_idle", "notify", "rename", "focused", "read_screen")
HERDR_NAME_RE = re.compile(r"[a-z][a-z0-9_-]{0,31}")
HERDR_NAME_MAX = 32
HASH_CHARS = 4


def herdr_name(name):
    if HERDR_NAME_RE.fullmatch(name):
        return name
    text = re.sub(r"[^a-z0-9_-]+", "-", name.lower()).strip("-")
    if not text[:1].isalpha():
        text = f"t-{text}" if text else "t"
    if len(text) <= HERDR_NAME_MAX:
        return text
    digest = hashlib.sha1(name.encode()).hexdigest()[:HASH_CHARS]
    start = text[:HERDR_NAME_MAX - HASH_CHARS - 1].rstrip("-_")
    return f"{start}-{digest}"


class AdapterError(FactoryError):
    pass


class Adapter:
    name = ""

    def __init__(self, ctx):
        self.ctx = ctx

    def capabilities(self):
        return set()

    def check(self):
        raise NotImplementedError

    def start_session(self, name, cwd, prompt, claude_args):
        raise NotImplementedError

    def close(self, handle):
        raise NotImplementedError

    def unsupported(self, action):
        raise AdapterError(f"The {self.name} terminal adapter does not support {action}.")

    def send_prompt(self, handle, text):
        self.unsupported("send-prompt")

    def question_box(self, handle):
        return False

    def focus(self, handle):
        self.unsupported("focus")

    def read_screen(self, handle, lines):
        self.unsupported("read-screen")

    def rename(self, handle, name):
        self.unsupported("rename")

    def state(self, handle):
        self.unsupported("state")

    def wait_idle(self, handle, timeout_s):
        self.unsupported("wait-idle")

    def notify(self, text):
        self.unsupported("notify")

    def focused(self, handle):
        self.unsupported("focused")
