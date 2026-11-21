import json
import os
import re
import secrets
import signal
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from pathlib import Path

from . import cli, fsio, repo, workspaces
from .errors import FactoryError

API_URL = "https://api.github.com/repos/Bwaim/SoftwareFactory/releases/latest"
RELEASES = "https://github.com/Bwaim/SoftwareFactory/releases/download"
CHECK_SECONDS = 24 * 3600
HOLD_SECONDS = 60
INSTALL_TIMEOUT_SECONDS = 900
RUNNING_STATUSES = ("active", "awaiting_approval", "waiting_external")
VERSION_RE = re.compile(r"v?(\d+)\.(\d+)\.(\d+)")


def root():
    return Path(os.environ.get("FACTORY_UPDATE_ROOT") or repo.PLUGIN_ROOT)


def script_install():
    return (root() / ".installed-by-script").exists()


def parse(text):
    m = VERSION_RE.fullmatch(text) if isinstance(text, str) else None
    return tuple(int(n) for n in m.groups()) if m else None


def newer(latest, installed):
    a, b = parse(latest), parse(installed)
    return a is not None and b is not None and a > b


def log(text):
    print(text, file=sys.stderr, flush=True)


def fetch_latest(url=None, timeout=10):
    url = url or os.environ.get("FACTORY_UPDATE_URL") or API_URL
    request = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json", "User-Agent": "captn-factory"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            tag = json.load(response)["tag_name"]
    except Exception as e:
        log(f"Update check failed: {e}")
        return None
    if parse(tag) is None:
        log(f"Update check failed: unexpected tag {tag!r}")
        return None
    return tag.removeprefix("v")


def dismissed_path():
    return workspaces.home() / "update-dismissed"


def dismissed():
    return fsio.read_text(dismissed_path()).strip() or None


def dismiss(version):
    fsio.atomic_write_text(dismissed_path(), version + "\n")


class Checker:
    def __init__(self):
        self.latest = None
        self.checked_at = None

    def check_once(self):
        found = fetch_latest()
        self.checked_at = time.time()
        if found and newer(found, cli.VERSION):
            self.latest = found

    def run(self):
        while True:
            self.check_once()
            time.sleep(CHECK_SECONDS)

    def start(self):
        if os.environ.get("FACTORY_NO_UPDATE_CHECK") or not script_install():
            return
        threading.Thread(target=self.run, daemon=True).start()


def install_url(version):
    return os.environ.get("FACTORY_UPDATE_INSTALL_URL") or f"{RELEASES}/v{version}/install.sh"


def install_env(version):
    env = dict(os.environ)
    env["FACTORY_INSTALL_TTY"] = str(Path(tempfile.mkdtemp()) / "tty")
    env["FACTORY_INSTALL_DOWNLOAD_BASE"] = f"{RELEASES}/v{version}"
    env["FACTORY_INSTALL_DIR"] = str(root())
    terminal = workspaces.home() / "terminal"
    if terminal.exists():
        env["FACTORY_INSTALL_TERMINAL"] = terminal.read_text().strip()
    return env


def run_install(version):
    with tempfile.TemporaryDirectory() as tmp:
        script = Path(tmp) / "install.sh"
        try:
            with urllib.request.urlopen(install_url(version), timeout=60) as response:
                script.write_bytes(response.read())
        except Exception as e:
            return 1, f"Download of install.sh failed: {e}"
        proc = subprocess.Popen(
            ["sh", str(script)], cwd=tmp, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, text=True, env=install_env(version), start_new_session=True,
        )
        try:
            output, _ = proc.communicate(timeout=INSTALL_TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except OSError:
                pass
            output, _ = proc.communicate()
            note = f"The install timed out after {INSTALL_TIMEOUT_SECONDS:g} s."
            return 1, f"{output or ''}\n{note}".strip()
        return proc.returncode, output


def installed_version():
    return fsio.read_text(root() / "VERSION").strip() or None


def spawn_new():
    from . import server as server_mod
    return server_mod.spawn_server([str(root() / "bin" / "factory"), "serve"])


def not_started(output):
    from . import server as server_mod
    error = f"The update is installed, but the new server did not start. See {server_mod.log_path()}."
    return "failed", {"status": "error", "error": error, "output": output}


class Updater:
    def __init__(self, server, checker, start=spawn_new):
        self.server = server
        self.checker = checker
        self.start = start
        self.lock = threading.Lock()
        self.job_id = None
        self.state = None

    def run(self, ws):
        with self.lock:
            if self.state is not None:
                return self.job_id
            latest = self.checker.latest
            if latest is None:
                raise FactoryError("No update is available.")
            self.job_id = secrets.token_hex(6)
            self.state = "running"
            self.server.jobs[self.job_id] = {"status": "running"}
        threading.Thread(target=self.work, args=(self.job_id, latest, ws), daemon=True).start()
        return self.job_id

    def holds(self):
        return self.state in ("running", "done", "failed")

    def job_read(self, job_id):
        self.end_hold(job_id, ("done",))

    def close(self):
        self.end_hold(self.job_id, ("failed",))

    def ended(self):
        return self.state == "ended"

    def end_hold(self, job_id, states):
        with self.lock:
            if job_id == self.job_id and self.state in states:
                self.state = "ended"

    def work(self, job_id, latest, ws):
        output = ""
        try:
            self.server.pause_for_update()
            status, output = run_install(latest)
            if status != 0 and installed_version() != latest:
                self.fail(job_id, output)
                return
            self.finish(job_id, *self.start_new(latest, ws, status, output))
        except Exception as e:
            output = f"{output}\n{e}".strip()
            if installed_version() != latest:
                self.fail(job_id, output)
            else:
                self.finish(job_id, *not_started(output))

    def start_new(self, latest, ws, status, output):
        from . import server as server_mod
        warn = status != 0
        if warn:
            fsio.atomic_write_text(workspaces.home() / "update.log", output)
        try:
            info = self.start()
        except Exception:
            return not_started(output)
        params = {"ws": ws} if ws else {}
        params["updated"] = latest
        if warn:
            params["warn"] = "1"
        url = server_mod.page_url(info, "dashboard", **params)
        return "done", {"status": "done", "result": {"url": url, "version": latest, "output": output}}

    def finish(self, job_id, state, job):
        with self.lock:
            self.state = state
            timer = threading.Timer(HOLD_SECONDS, self.end_hold, args=(job_id, (state,)))
            timer.daemon = True
            timer.start()
            self.server.jobs[job_id] = job

    def fail(self, job_id, output):
        self.server.resume_after_update()
        with self.lock:
            self.state = None
            self.server.jobs[job_id] = {"status": "error", "error": "The update failed.", "output": output}
