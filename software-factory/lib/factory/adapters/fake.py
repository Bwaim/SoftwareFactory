from .. import fsio
from .base import OPTIONAL, Adapter, AdapterError


class FakeAdapter(Adapter):
    name = "fake"

    def cfg(self):
        return fsio.read_json(self.ctx.fdir / "fake_adapter_config.json", {}) or {}

    def record(self, op, **fields):
        fsio.update_json(
            self.ctx.fdir / "fake_adapter_calls.json",
            lambda d: d.setdefault("calls", []).append({"op": op, **fields}),
        )

    def capabilities(self):
        return set(self.cfg().get("capabilities", OPTIONAL))

    def check(self):
        cfg = self.cfg()
        if cfg.get("check_raises"):
            raise RuntimeError(cfg["check_raises"])
        return bool(cfg.get("check_ok", True)), cfg.get("check_message", "Fake terminal is available.")

    def start_session(self, name, cwd, prompt, claude_args, in_worktree):
        self.record("start_session", name=name, cwd=str(cwd), prompt=prompt, args=list(claude_args), in_worktree=in_worktree)
        if self.cfg().get("fail_start"):
            raise AdapterError("The fake adapter failed to start the session.")
        return {"agent": name, "fake": True}

    def close(self, handle):
        self.record("close", handle=handle)

    def require(self, action):
        if action not in self.capabilities():
            self.unsupported(action.replace("_", "-"))

    def send_prompt(self, handle, text):
        self.require("send_prompt")
        self.record("send_prompt", handle=handle, text=text)

    def focus(self, handle):
        self.require("focus")
        self.record("focus", handle=handle)

    def state(self, handle):
        self.require("state")
        cfg = self.cfg()
        return cfg.get("states", {}).get(handle.get("agent"), cfg.get("state", "idle"))

    def wait_idle(self, handle, timeout_s):
        self.require("wait_idle")
        self.record("wait_idle", handle=handle)

    def notify(self, text):
        self.require("notify")
        self.record("notify", text=text)


ADAPTER = FakeAdapter
