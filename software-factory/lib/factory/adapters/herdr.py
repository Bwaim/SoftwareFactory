import json
import os
import shutil
import subprocess

from .base import OPTIONAL, Adapter, AdapterError

TRUST_MARKERS = ("is this a project you created or one you trust", "yes, i trust this folder")
START_TIMEOUT_MS = 60000


def run(args, timeout=60, check=True):
    try:
        r = subprocess.run(["herdr", *args], capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise AdapterError(f"herdr {' '.join(args[:2])} timed out.")
    if check and r.returncode != 0:
        raise AdapterError(f"herdr {' '.join(args[:2])} failed: {(r.stderr or r.stdout).strip()}")
    return r


def parse(r):
    try:
        return json.loads(r.stdout) if r.stdout.strip() else {}
    except json.JSONDecodeError:
        return {}


def same_folder(a, b):
    return os.path.realpath(a) == os.path.realpath(b)


class HerdrAdapter(Adapter):
    name = "herdr"

    def capabilities(self):
        return set(OPTIONAL)

    def check(self):
        if os.environ.get("HERDR_ENV") != "1":
            return False, "This session does not run inside Herdr (HERDR_ENV is not 1). Start Claude in a Herdr pane, then start the factory again."
        if not shutil.which("herdr"):
            return False, "The `herdr` command is not installed. Install Herdr from https://herdr.dev."
        return True, "Herdr is available."

    def workspaces(self):
        return parse(run(["workspace", "list"])).get("result", {}).get("workspaces", [])

    def main_repo_workspace_ids(self, workspaces):
        ids = []
        for workspace in workspaces:
            info = workspace.get("worktree") or {}
            if info.get("checkout_path") and not info.get("is_linked_worktree") and same_folder(info["checkout_path"], self.ctx.main):
                ids.append(workspace["workspace_id"])
        return ids

    def open_worktree(self, name, cwd):
        before = {w["workspace_id"] for w in self.workspaces()}
        result = parse(run(["worktree", "open", "--cwd", str(self.ctx.main), "--path", str(cwd), "--label", name, "--no-focus"]))["result"]
        pane = result["root_pane"]
        handle = {"agent": name, "workspace": pane["workspace_id"]}
        created = [
            workspace_id
            for workspace_id in self.main_repo_workspace_ids(self.workspaces())
            if workspace_id not in before and workspace_id != pane["workspace_id"]
        ]
        if created:
            handle["extra_workspace"] = created[0]
        return handle, pane["pane_id"]

    def open_main_repo(self, name, cwd):
        existing = self.main_repo_workspace_ids(self.workspaces())
        if existing:
            result = parse(run(["tab", "create", "--workspace", existing[0], "--cwd", str(cwd), "--label", name, "--no-focus"]))["result"]
            return {"agent": name, "tab": result["tab"]["tab_id"]}, result["root_pane"]["pane_id"]
        result = parse(run(["workspace", "create", "--cwd", str(cwd), "--label", name, "--no-focus"]))["result"]
        pane = result["root_pane"]
        return {"agent": name, "workspace": pane["workspace_id"], "created_workspace": True}, pane["pane_id"]

    def open_location(self, name, cwd, in_worktree):
        if in_worktree:
            return self.open_worktree(name, cwd)
        return self.open_main_repo(name, cwd)

    def screen(self, name):
        r = run(["agent", "read", name, "--source", "recent-unwrapped", "--lines", "60"], check=False)
        return r.stdout

    def start_session(self, name, cwd, prompt, claude_args, in_worktree):
        handle, pane = self.open_location(name, cwd, in_worktree)
        try:
            run(["agent", "start", name, "--kind", "claude", "--pane", pane, "--timeout", str(START_TIMEOUT_MS), "--", *claude_args],
                timeout=START_TIMEOUT_MS // 1000 + 30)
            run(["agent", "prompt", name, prompt], timeout=60)
        except AdapterError as e:
            screen = self.screen(name).lower()
            self.close(handle)
            if any(marker in screen for marker in TRUST_MARKERS):
                raise AdapterError(
                    f"Claude asks to trust the folder {cwd}. "
                    "Open Claude once in the main repository and trust it, then launch again."
                )
            raise e
        return handle

    def stop_agent(self, handle):
        run(["agent", "send-keys", handle["agent"], "ctrl+c", "ctrl+c"], check=False)

    def close(self, handle):
        if not handle:
            return
        self.stop_agent(handle)
        if handle.get("workspace"):
            run(["workspace", "close", handle["workspace"]], check=False)
        elif handle.get("tab"):
            run(["tab", "close", handle["tab"]], check=False)
        if handle.get("extra_workspace"):
            run(["workspace", "close", handle["extra_workspace"]], check=False)

    def send_prompt(self, handle, text):
        run(["agent", "prompt", handle["agent"], text])

    def focus(self, handle):
        run(["agent", "focus", handle["agent"]])

    def state(self, handle):
        if not handle:
            return "gone"
        r = run(["agent", "get", handle["agent"]], check=False)
        if r.returncode != 0:
            return "gone"
        return parse(r).get("result", {}).get("agent", {}).get("agent_status") or "unknown"

    def wait_idle(self, handle, timeout_s):
        run(["agent", "wait", handle["agent"], "--timeout", str(int(timeout_s * 1000))], timeout=timeout_s + 30)

    def notify(self, text):
        run(["notification", "show", "Software factory", "--body", text, "--sound", "request"], check=False)


ADAPTER = HerdrAdapter
