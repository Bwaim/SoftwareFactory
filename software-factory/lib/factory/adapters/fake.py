import subprocess

from .. import fsio
from .base import OPTIONAL, Adapter, AdapterError, herdr_name


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

    def start_session(self, name, cwd, prompt, claude_args):
        real = herdr_name(name)
        self.record("start_session", name=name, herdr_name=real, cwd=str(cwd), prompt=prompt, args=list(claude_args))
        if self.cfg().get("fail_start"):
            raise AdapterError("The fake adapter failed to start the session.")
        return {"agent": real, "fake": True}

    def close(self, handle):
        cfg = self.cfg()
        on_close = cfg.get("on_close")
        if on_close:
            for argv in on_close["commands"]:
                subprocess.run(argv, cwd=on_close["cwd"], check=True, capture_output=True)
        self.record("close", handle=handle)
        if cfg.get("fail_close"):
            raise AdapterError("The fake adapter failed to close the terminal.")
        return []

    def require(self, action):
        if action not in self.capabilities():
            self.unsupported(action.replace("_", "-"))

    def send_prompt(self, handle, text):
        self.require("send_prompt")
        if self.cfg().get("send_prompt_fails"):
            raise AdapterError("The fake adapter failed to send the prompt.")
        self.record("send_prompt", handle=handle, text=text)

    def question_box(self, handle):
        return bool(self.cfg().get("question_box"))

    def focus(self, handle):
        self.require("focus")
        self.record("focus", handle=handle)

    def attach_command(self, handle):
        self.require("attach")
        self.record("attach_command", handle=handle)
        return list(self.cfg().get("attach_command", ["cat"]))


    def rename(self, handle, name):
        self.require("rename")
        self.record("rename", handle=handle, name=name)
        cfg = self.cfg()
        if cfg.get("fail_rename"):
            raise AdapterError("The fake adapter failed to rename.")
        return {**handle, "agent": name}, list(cfg.get("rename_problems", []))

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

    def focused(self, handle):
        self.require("focused")
        return bool(self.cfg().get("focused", False))


ADAPTER = FakeAdapter
