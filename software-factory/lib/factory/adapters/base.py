from ..errors import FactoryError

OPTIONAL = ("send_prompt", "focus", "state", "wait_idle", "notify")


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

    def start_session(self, name, cwd, prompt, claude_args, in_worktree):
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

    def state(self, handle):
        self.unsupported("state")

    def wait_idle(self, handle, timeout_s):
        self.unsupported("wait-idle")

    def notify(self, text):
        self.unsupported("notify")
