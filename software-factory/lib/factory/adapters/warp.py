"""Warp terminal adapter.

Warp has no way to drive a tab from outside on its Stable channel: `warpctrl` is off there, and even when on it cannot send
input or read a pane. So Claude runs in a detached tmux session that the factory owns, on its own tmux socket, and Warp only
shows it: a tab config (a Warp file that opens a tab running commands) attaches a Warp tab to that session. Everything the
factory needs (prompts, screen reads, attach, close) goes through tmux; working or idle comes from the factory's Claude hooks.
"""
import os
import shlex
import shutil
import subprocess
import sys
import time
from pathlib import Path

from .. import session_activity
from .base import Adapter, AdapterError, herdr_name

SOCKET = "captn"
TAB_CONFIG_PREFIX = "captn-"
TRUST_MARKERS = ("is this a project you created or one you trust", "yes, i trust this folder")
QUESTION_BOX_MARKERS = ("enter to select", "↑/↓ to navigate", "esc to cancel")
SCREEN_BOTTOM_LINES = 15
START_WAIT_SECONDS = 20
START_POLL_SECONDS = 0.5
PASTE_SETTLE_SECONDS = 0.3
WAIT_POLL_SECONDS = 1
WIDTH, HEIGHT = 200, 50
WARP_APP = "Warp"


def tab_config_dir():
    return Path(os.environ.get("FACTORY_WARP_TAB_CONFIGS") or Path.home() / ".warp" / "tab_configs")


def toml_string(text):
    return '"' + str(text).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"'


def shell_join(argv):
    """shlex.join for the user's shell, zsh included. shlex leaves a leading "=" bare, and zsh expands a bare "=word" to the
    path of the command `word`: the tmux target "=name" then fails with "zsh: name not found"."""
    return " ".join("'" + arg.replace("'", "'\\''") + "'" if arg.startswith("=") else shlex.quote(arg) for arg in argv)


def clean_env():
    """The environment for tmux. The factory often runs from a Claude session, and the tmux server keeps the environment it
    starts with: Claude's own variables would make every task's claude believe it runs nested in another one. TMUX would make
    tmux refuse to attach from inside another tmux."""
    return {k: v for k, v in os.environ.items() if k != "CLAUDECODE" and not k.startswith("CLAUDE_CODE_") and k != "TMUX"}


def session_id_of(claude_args):
    for flag in ("--session-id", "--resume"):
        if flag in claude_args:
            i = claude_args.index(flag)
            if i + 1 < len(claude_args):
                return claude_args[i + 1]
    return None


class WarpAdapter(Adapter):
    name = "warp"
    front_app = WARP_APP

    def capabilities(self):
        # No "focused": tmux knows whether a Warp tab is attached, not whether that tab is in front.
        return {"send_prompt", "focus", "state", "wait_idle", "notify", "rename", "attach"}

    def tmux_path(self):
        return shutil.which("tmux")

    def tmux(self, *args, timeout=30, check=True, input=None):
        exe = self.tmux_path()
        if not exe:
            raise AdapterError("The `tmux` command is not installed. Install it with `brew install tmux`.")
        try:
            r = subprocess.run([exe, "-L", SOCKET, *args], capture_output=True, text=True, timeout=timeout, input=input, env=clean_env())
        except subprocess.TimeoutExpired:
            raise AdapterError(f"tmux {args[0]} timed out.")
        except OSError as e:
            raise AdapterError(f"tmux {args[0]} could not run: {e}")
        if check and r.returncode != 0:
            raise AdapterError(f"tmux {args[0]} failed: {(r.stderr or r.stdout).strip()}")
        return r

    def check(self):
        if sys.platform != "darwin":
            return False, "The Warp adapter works on macOS only."
        if not self.tmux_path():
            return False, "The `tmux` command is not installed. Install it with `brew install tmux`."
        if subprocess.run(["open", "-Ra", WARP_APP], capture_output=True).returncode != 0:
            return False, "Warp is not installed. Install it from https://www.warp.dev."
        return True, "Warp and tmux are available."

    # The leading "=" makes tmux match the session name exactly, not as a prefix.
    def target(self, handle):
        return f"={handle['agent']}"

    def exists(self, handle):
        return self.tmux("has-session", "-t", self.target(handle), check=False).returncode == 0

    def require_owned(self, handle):
        if not handle or not self.exists(handle):
            raise AdapterError(f"The tmux session {handle and handle.get('agent')} is gone.")

    def screen(self, handle, lines=None):
        args = ["capture-pane", "-p", "-t", self.target(handle)]
        if lines:
            args += ["-S", f"-{lines}"]
        r = self.tmux(*args, check=False)
        return r.stdout if r.returncode == 0 else ""

    def start_session(self, name, cwd, prompt, claude_args):
        name = herdr_name(name)
        handle = {"agent": name, "session_id": session_id_of(claude_args)}
        if self.exists(handle):
            raise AdapterError(f"A tmux session named {name} already exists. Close it or launch with another --id.")
        # The first prompt goes on the command line, after `--` because --add-dir takes several folders.
        # Claude submits it once it is ready, so there is nothing to time.
        self.tmux("new-session", "-d", "-s", name, "-c", str(cwd), "-x", str(WIDTH), "-y", str(HEIGHT),
                  "-e", "TERM=xterm-256color", "claude", *claude_args, "--", prompt)
        try:
            self.wait_started(handle, cwd)
        except Exception:
            self.close(handle, stop=False)
            raise
        handle["tab_config"] = self.write_tab_config(handle, cwd)
        self.open_tab(handle)
        return handle

    def wait_started(self, handle, cwd):
        """Fail fast when Claude stops at the trust question or exits; otherwise return once the first prompt is in."""
        deadline = time.monotonic() + START_WAIT_SECONDS
        while time.monotonic() < deadline:
            if not self.exists(handle):
                raise AdapterError("Claude exited right after it started. Run it once by hand in the worktree to see why.")
            text = self.screen(handle).lower()
            if any(marker in text for marker in TRUST_MARKERS):
                raise AdapterError(
                    f"Claude asks to trust the folder {cwd}. "
                    "Open Claude once in the main repository and trust it, then launch again."
                )
            if session_activity.read(self.ctx, handle.get("session_id")):
                return
            time.sleep(START_POLL_SECONDS)

    def attach_argv(self, handle):
        return ["env", "-u", "TMUX", self.tmux_path() or "tmux", "-L", SOCKET, "attach-session", "-t", self.target(handle)]

    def write_tab_config(self, handle, cwd):
        name = TAB_CONFIG_PREFIX + handle["agent"]
        folder = tab_config_dir()
        folder.mkdir(parents=True, exist_ok=True)
        # exec: when the tmux session ends, the shell ends too, so Warp closes the tab instead of leaving an empty shell.
        command = "exec " + shell_join(self.attach_argv(handle))
        text = (
            f"name = {toml_string(name)}\n"
            f"title = {toml_string(handle['agent'])}\n\n"
            "[[panes]]\n"
            'id = "main"\n'
            'type = "terminal"\n'
            f"directory = {toml_string(cwd)}\n"
            f"commands = [{toml_string(command)}]\n"
        )
        (folder / f"{name}.toml").write_text(text)
        return name

    def open_tab(self, handle):
        if not handle.get("tab_config"):
            return
        r = subprocess.run(["open", f"warp://tab_config/{handle['tab_config']}"], capture_output=True, text=True)
        if r.returncode != 0:
            raise AdapterError(f"Warp did not open the tab: {(r.stderr or r.stdout).strip()}")

    def attached(self, handle):
        r = self.tmux("list-clients", "-t", self.target(handle), check=False)
        return r.returncode == 0 and bool(r.stdout.strip())

    def remove_tab_config(self, handle):
        if handle.get("tab_config"):
            (tab_config_dir() / f"{handle['tab_config']}.toml").unlink(missing_ok=True)

    def close(self, handle, stop=True):
        if not handle:
            return []
        if self.exists(handle):
            if stop:
                self.tmux("send-keys", "-t", self.target(handle), "C-c", "C-c", check=False)
            r = self.tmux("kill-session", "-t", self.target(handle), check=False)
            if r.returncode != 0 and self.exists(handle):
                raise AdapterError(f"tmux kill-session failed: {(r.stderr or r.stdout).strip()}")
        self.remove_tab_config(handle)
        session_activity.forget(self.ctx, handle.get("session_id"))
        return []

    def send_prompt(self, handle, text):
        self.require_owned(handle)
        # A bracketed paste keeps line breaks inside the prompt; typing them would submit each line on its own.
        self.tmux("load-buffer", "-b", "captn-prompt", "-", input=text)
        self.tmux("paste-buffer", "-p", "-d", "-b", "captn-prompt", "-t", self.target(handle))
        time.sleep(PASTE_SETTLE_SECONDS)
        self.tmux("send-keys", "-t", self.target(handle), "Enter")

    def question_box(self, handle):
        self.require_owned(handle)
        bottom = [line for line in self.screen(handle).splitlines() if line.strip()][-SCREEN_BOTTOM_LINES:]
        text = "\n".join(bottom).lower()
        return any(marker in text for marker in QUESTION_BOX_MARKERS)

    def focus(self, handle):
        """Bring Warp to the front. Without an attached Warp tab (closed by the user), open a new one first."""
        self.require_owned(handle)
        if not self.attached(handle) and handle.get("tab_config"):
            if not (tab_config_dir() / f"{handle['tab_config']}.toml").exists():
                self.write_tab_config(handle, self.pane_folder(handle))
            self.open_tab(handle)
            return
        r = subprocess.run(["open", "-a", WARP_APP], capture_output=True, text=True)
        if r.returncode != 0:
            raise AdapterError(f"Warp could not be brought to the front: {(r.stderr or r.stdout).strip()}")

    def pane_folder(self, handle):
        r = self.tmux("display-message", "-p", "-t", self.target(handle), "#{pane_current_path}", check=False)
        return r.stdout.strip() or str(Path.home())

    def attach_command(self, handle):
        self.require_owned(handle)
        return self.attach_argv(handle)

    def rename(self, handle, name):
        self.require_owned(handle)
        self.tmux("rename-session", "-t", self.target(handle), name)
        # The tab config keeps its first name: an open Warp tab cannot be renamed from outside.
        return {**handle, "agent": name}, []

    def state(self, handle):
        if not handle or not self.exists(handle):
            return "gone"
        return session_activity.read(self.ctx, handle.get("session_id")) or "unknown"

    def wait_idle(self, handle, timeout_s):
        deadline = time.monotonic() + timeout_s
        while True:
            current = self.state(handle)
            if current == "gone":
                raise AdapterError(f"The tmux session {handle['agent']} is gone.")
            if current == "idle":
                return
            if time.monotonic() >= deadline:
                raise AdapterError(f"The session {handle['agent']} did not become idle in {int(timeout_s)} seconds.")
            time.sleep(WAIT_POLL_SECONDS)

    def notify(self, text):
        script = 'on run argv\ndisplay notification (item 1 of argv) with title "CAPTN Factory" sound name "Glass"\nend run'
        subprocess.run(["osascript", "-e", script, text], capture_output=True)


ADAPTER = WarpAdapter
