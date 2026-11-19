import json
import os
import shutil
import subprocess

from .. import fsio
from .base import OPTIONAL, Adapter, AdapterError, herdr_name

TRUST_MARKERS = ("is this a project you created or one you trust", "yes, i trust this folder")
START_TIMEOUT_MS = 60000
QUESTION_BOX_MARKERS = ("enter to select", "↑/↓ to navigate", "esc to cancel")
SCREEN_BOTTOM_LINES = 15
GROUP_CLOSE_REQUIRED = "workspace_group_close_required"


def run(args, timeout=60, check=True):
    try:
        r = subprocess.run(["herdr", *args], capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise AdapterError(f"herdr {' '.join(args[:2])} timed out.")
    except OSError as e:
        raise AdapterError(f"herdr {' '.join(args[:2])} could not run: {e}")
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

    def tabs(self, workspace_id, own_tab=None):
        r = run(["tab", "list", "--workspace", workspace_id], check=False)
        if r.returncode != 0:
            return None
        tabs = parse(r).get("result", {}).get("tabs")
        if not isinstance(tabs, list) or not all(isinstance(t, dict) and "tab_id" in t for t in tabs):
            return None
        if own_tab is not None and own_tab not in {t["tab_id"] for t in tabs}:
            return None
        return tabs

    def main_repo_workspace_ids(self, workspaces):
        ids = []
        for workspace in workspaces:
            info = workspace.get("worktree") or {}
            if info.get("checkout_path") and not info.get("is_linked_worktree") and same_folder(info["checkout_path"], self.ctx.main):
                ids.append(workspace["workspace_id"])
        return ids

    def create_tab(self, handle, workspace_id, cwd):
        result = parse(run(["tab", "create", "--workspace", workspace_id, "--cwd", str(cwd), "--label", handle["agent"], "--no-focus"]))["result"]
        handle["tab"] = result["tab"]["tab_id"]
        return result["root_pane"]["pane_id"]

    def open_worktree(self, handle, cwd):
        result = parse(run(["worktree", "open", "--cwd", str(self.ctx.main), "--path", str(cwd), "--label", handle["agent"], "--no-focus"]))["result"]
        pane = result["root_pane"]
        if result.get("already_open"):
            return self.create_tab(handle, pane["workspace_id"], cwd)
        handle["workspace"] = pane["workspace_id"]
        handle["tab"] = pane["tab_id"]
        return pane["pane_id"]

    def find_extra_workspaces(self, before, handle):
        after = self.main_repo_workspace_ids(self.workspaces(check=False))
        return [w for w in after if w not in before and w != handle.get("workspace")]

    def shared_record(self):
        return self.ctx.fdir / "herdr-workspaces.json"

    def record_shared(self, ids):
        fsio.update_json(self.shared_record(), lambda record: record.extend(w for w in ids if w not in record), default_factory=list)

    def has_linked_workspaces(self, workspaces):
        for workspace in workspaces:
            info = workspace.get("worktree") or {}
            if info.get("is_linked_worktree") and info.get("repo_root") and same_folder(info["repo_root"], self.ctx.main):
                return True
        return False

    def screen(self, name):
        r = run(["agent", "read", name, "--source", "recent-unwrapped", "--lines", "60"], check=False)
        return r.stdout

    def start_session(self, name, cwd, prompt, claude_args):
        name = herdr_name(name)
        if self.find_agent(name) is not None:
            raise AdapterError(f"A Herdr agent named {name} already exists. Close it or launch with another --id.")
        before = set(self.main_repo_workspace_ids(self.workspaces()))
        handle = {"agent": name}
        agent_started = False
        try:
            pane = self.open_worktree(handle, cwd)
            if "workspace" in handle:
                extra = self.find_extra_workspaces(before, handle)
                if extra:
                    handle["extra_workspaces"] = extra
                    self.record_shared(extra)
            run(["agent", "start", name, "--kind", "claude", "--pane", pane, "--timeout", str(START_TIMEOUT_MS), "--", *claude_args],
                timeout=START_TIMEOUT_MS // 1000 + 30)
            agent_started = True
            run(["agent", "prompt", name, prompt], timeout=60)
        except Exception as e:
            screen = self.screen(name).lower()
            self.close_quietly(handle, agent_started)
            if any(marker in screen for marker in TRUST_MARKERS):
                raise AdapterError(
                    f"Claude asks to trust the folder {cwd}. "
                    "Open Claude once in the main repository and trust it, then launch again."
                )
            if isinstance(e, AdapterError):
                raise
            raise AdapterError(f"Herdr start failed: {e}")
        return handle

    def close_quietly(self, handle, agent_started):
        try:
            self.close(handle, stop=agent_started)
        except Exception:
            pass

    def find_agent(self, name):
        r = run(["agent", "get", name], check=False)
        if r.returncode != 0:
            return None
        return parse(r).get("result", {}).get("agent") or {}

    def owned_agent(self, handle):
        agent = self.find_agent(handle["agent"])
        if agent is None:
            return None
        same_tab = handle.get("tab") and agent.get("tab_id") == handle["tab"]
        same_workspace = handle.get("workspace") and agent.get("workspace_id") == handle["workspace"]
        return agent if same_tab or same_workspace else None

    def require_owned(self, handle):
        agent = self.owned_agent(handle)
        if agent is None:
            raise AdapterError(f"The Herdr agent {handle['agent']} is gone or does not belong to this task.")
        return agent

    def stop_agent(self, handle):
        if self.owned_agent(handle) is not None:
            run(["agent", "send-keys", handle["agent"], "ctrl+c", "ctrl+c"], check=False)

    def target_state(self, handle):
        workspace_id, tab_id = handle.get("workspace"), handle.get("tab")
        try:
            r = run(["workspace", "list"], check=False)
            if r.returncode != 0:
                return "unknown"
            ids = [w.get("workspace_id") for w in parse(r).get("result", {}).get("workspaces", [])]
            if workspace_id and workspace_id not in ids:
                return "gone"
            if not tab_id:
                return "present"
            for candidate in [workspace_id] if workspace_id else ids:
                r = run(["tab", "list", "--workspace", candidate], check=False)
                if r.returncode != 0:
                    return "unknown"
                if tab_id in {t.get("tab_id") for t in parse(r).get("result", {}).get("tabs", [])}:
                    return "present"
        except (AdapterError, AttributeError):
            return "unknown"
        return "gone"

    def close_own(self, handle):
        workspace_id, tab_id = handle.get("workspace"), handle.get("tab")
        command = None
        if workspace_id:
            tabs = self.tabs(workspace_id, tab_id)
            if tabs is not None and (len(tabs) <= 1 if tab_id is None else all(t["tab_id"] == tab_id for t in tabs)):
                command = ["workspace", "close", workspace_id]
        if command is None and tab_id:
            command = ["tab", "close", tab_id]
        if command is None:
            return
        r = run(command, check=False)
        if r.returncode != 0 and self.target_state(handle) != "gone":
            raise AdapterError(f"herdr {command[0]} close failed: {(r.stderr or r.stdout).strip()}")

    def close_extra(self, workspace_id):
        tabs = self.tabs(workspace_id)
        if tabs is not None and len(tabs) == 1 and tabs[0].get("agent_status", "unknown") == "unknown":
            r = run(["workspace", "close", workspace_id], check=False)
            if r.returncode == 0:
                return True, None
            output = (r.stderr or r.stdout).strip()
            if GROUP_CLOSE_REQUIRED in f"{r.stdout}{r.stderr}":
                return False, None
            return False, f"The workspace {workspace_id} was not closed: {output}"
        return False, None

    def close_recorded(self, record, old_ids):
        record.extend(w for w in old_ids if w not in record)
        if not record:
            return []
        r = run(["workspace", "list"], check=False)
        workspaces = parse(r).get("result", {}).get("workspaces") if r.returncode == 0 else None
        if not isinstance(workspaces, list):
            workspaces = None
        listed = None if workspaces is None else {w.get("workspace_id") for w in workspaces}
        linked = workspaces is not None and self.has_linked_workspaces(workspaces)
        problems, kept = [], []
        for workspace_id in record:
            if listed is not None and workspace_id not in listed:
                continue
            if linked:
                kept.append(workspace_id)
                continue
            done, problem = self.close_extra(workspace_id)
            if not done:
                kept.append(workspace_id)
            if problem:
                problems.append(problem)
        record[:] = kept
        return problems

    def close_shared(self, old_ids):
        path = self.shared_record()
        if not old_ids and not path.exists():
            return []
        return fsio.update_json(path, lambda record: self.close_recorded(record, old_ids), default_factory=list)

    def close(self, handle, stop=True):
        if not handle:
            return []
        if stop:
            self.stop_agent(handle)
        self.close_own(handle)
        return self.close_shared(handle.get("extra_workspaces", []))

    def send_prompt(self, handle, text):
        self.require_owned(handle)
        run(["agent", "prompt", handle["agent"], text])

    def question_box(self, handle):
        self.require_owned(handle)
        screen = run(["agent", "read", handle["agent"], "--source", "visible"]).stdout
        bottom = [line for line in screen.splitlines() if line.strip()][-SCREEN_BOTTOM_LINES:]
        text = "\n".join(bottom).lower()
        return any(marker in text for marker in QUESTION_BOX_MARKERS)

    def focus(self, handle):
        self.require_owned(handle)
        run(["agent", "focus", handle["agent"]])

    def read_screen(self, handle, lines):
        self.require_owned(handle)
        return run(["agent", "read", handle["agent"], "--source", "recent-unwrapped", "--lines", str(lines), "--format", "ansi"]).stdout

    def send_text(self, handle, text):
        agent = self.require_owned(handle)
        run(["pane", "send-text", agent["pane_id"], text])

    def send_keys(self, handle, keys):
        self.require_owned(handle)
        run(["agent", "send-keys", handle["agent"], *keys])

    def rename(self, handle, name):
        self.require_owned(handle)
        run(["agent", "rename", handle["agent"], name])
        handle = {**handle, "agent": name}
        problems = []
        for kind in ("tab", "workspace"):
            if handle.get(kind):
                try:
                    run([kind, "rename", handle[kind], name])
                except AdapterError as e:
                    problems.append(str(e))
        return handle, problems

    def state(self, handle):
        if not handle:
            return "gone"
        agent = self.owned_agent(handle)
        if agent is None:
            return "gone"
        return agent.get("agent_status") or "unknown"

    def wait_idle(self, handle, timeout_s):
        self.require_owned(handle)
        run(["agent", "wait", handle["agent"], "--timeout", str(int(timeout_s * 1000))], timeout=timeout_s + 30)

    def focused(self, handle):
        return bool(self.require_owned(handle).get("focused"))

    def notify(self, text):
        run(["notification", "show", "Software factory", "--body", text, "--sound", "request"], check=False)


ADAPTER = HerdrAdapter
