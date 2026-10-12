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

    def workspaces(self, check=True):
        return parse(run(["workspace", "list"], check=check)).get("result", {}).get("workspaces", [])

    def tabs(self, workspace_id):
        r = run(["tab", "list", "--workspace", workspace_id], check=False)
        if r.returncode != 0:
            return None
        return parse(r).get("result", {}).get("tabs", [])

    def main_repo_workspace_ids(self, workspaces):
        ids = []
        for workspace in workspaces:
            info = workspace.get("worktree") or {}
            if info.get("checkout_path") and not info.get("is_linked_worktree") and same_folder(info["checkout_path"], self.ctx.main):
                ids.append(workspace["workspace_id"])
        return ids

    def create_tab(self, name, workspace_id, cwd):
        result = parse(run(["tab", "create", "--workspace", workspace_id, "--cwd", str(cwd), "--label", name, "--no-focus"]))["result"]
        return {"agent": name, "tab": result["tab"]["tab_id"]}, result["root_pane"]["pane_id"]

    def open_worktree(self, name, cwd):
        result = parse(run(["worktree", "open", "--cwd", str(self.ctx.main), "--path", str(cwd), "--label", name, "--no-focus"]))["result"]
        pane = result["root_pane"]
        if result.get("already_open"):
            return self.create_tab(name, pane["workspace_id"], cwd)
        handle = {"agent": name, "workspace": pane["workspace_id"], "tab": pane["tab_id"]}
        return handle, pane["pane_id"]

    def find_extra_workspaces(self, before, handle):
        after = self.main_repo_workspace_ids(self.workspaces(check=False))
        return [w for w in after if w not in before and w != handle.get("workspace")]

    def open_main_repo(self, name, cwd):
        existing = self.main_repo_workspace_ids(self.workspaces())
        if existing:
            return self.create_tab(name, existing[0], cwd)
        result = parse(run(["workspace", "create", "--cwd", str(cwd), "--label", name, "--no-focus"]))["result"]
        pane = result["root_pane"]
        handle = {"agent": name, "workspace": pane["workspace_id"], "tab": pane["tab_id"], "created_workspace": True}
        return handle, pane["pane_id"]

    def screen(self, name):
        r = run(["agent", "read", name, "--source", "recent-unwrapped", "--lines", "60"], check=False)
        return r.stdout

    def start_session(self, name, cwd, prompt, claude_args, in_worktree):
        before = set(self.main_repo_workspace_ids(self.workspaces())) if in_worktree else set()
        handle, pane = self.open_worktree(name, cwd) if in_worktree else self.open_main_repo(name, cwd)
        try:
            if in_worktree and "workspace" in handle:
                extra = self.find_extra_workspaces(before, handle)
                if extra:
                    handle["extra_workspaces"] = extra
            run(["agent", "start", name, "--kind", "claude", "--pane", pane, "--timeout", str(START_TIMEOUT_MS), "--", *claude_args],
                timeout=START_TIMEOUT_MS // 1000 + 30)
            run(["agent", "prompt", name, prompt], timeout=60)
        except Exception as e:
            screen = self.screen(name).lower()
            self.close(handle)
            if any(marker in screen for marker in TRUST_MARKERS):
                raise AdapterError(
                    f"Claude asks to trust the folder {cwd}. "
                    "Open Claude once in the main repository and trust it, then launch again."
                )
            if isinstance(e, AdapterError):
                raise
            raise AdapterError(f"Herdr start failed: {e}")
        return handle

    def stop_agent(self, handle):
        run(["agent", "send-keys", handle["agent"], "ctrl+c", "ctrl+c"], check=False)

    def close_own(self, handle):
        workspace_id, tab_id = handle.get("workspace"), handle.get("tab")
        if workspace_id:
            tabs = self.tabs(workspace_id)
            others = [t for t in tabs if t["tab_id"] != tab_id] if tabs is not None else [None]
            if not others:
                run(["workspace", "close", workspace_id], check=False)
                return
        if tab_id:
            run(["tab", "close", tab_id], check=False)

    def close_extra(self, workspace_id):
        tabs = self.tabs(workspace_id)
        if tabs is not None and len(tabs) == 1 and tabs[0].get("agent_status", "unknown") == "unknown":
            run(["workspace", "close", workspace_id], check=False)

    def close(self, handle):
        if not handle:
            return
        self.stop_agent(handle)
        self.close_own(handle)
        for workspace_id in handle.get("extra_workspaces", []):
            self.close_extra(workspace_id)

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
