import os
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

from factory import server as server_mod
from factory import update
from factory.errors import FactoryError

SWAP = 'printf "0.3.0\\n" > "$FACTORY_INSTALL_DIR/VERSION"\n'


class FakeServer:
    def __init__(self):
        self.jobs = {}
        self.calls = []
        self.resumed = False
        self.stopped = False

    def pause_for_update(self, timeout=None):
        self.calls.append("pause")

    def resume_after_update(self):
        self.resumed = True

    def stop(self):
        self.stopped = True


class FakeChecker:
    latest = "0.3.0"


class Fakes:
    script = SWAP
    start_error = False
    job_id = None

    def start(self):
        if self.start_error:
            raise FactoryError("The local server did not start.")
        return {"port": 4321, "token": "tok"}

    def finish(self, job_id):
        self.job_id = job_id
        deadline = time.time() + 10
        while self.server.jobs[job_id]["status"] == "running":
            assert time.time() < deadline
            time.sleep(0.01)
        return self.server.jobs[job_id]


@pytest.fixture
def fakes(tmp_path, monkeypatch):
    f = Fakes()
    f.server = FakeServer()
    f.checker = FakeChecker()
    f.flag = tmp_path / "flag"
    sf = tmp_path / "sf"
    sf.mkdir()
    (sf / "VERSION").write_text("0.2.0\n")
    monkeypatch.setenv("FACTORY_UPDATE_ROOT", str(sf))
    monkeypatch.setattr(update, "HOLD_SECONDS", 5)

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            f.server.calls.append("install")
            data = f.script.encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *args):
            pass

    http = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=http.serve_forever, args=(0.01,), daemon=True).start()
    monkeypatch.setenv("FACTORY_UPDATE_INSTALL_URL", f"http://127.0.0.1:{http.server_port}/install.sh")
    f.updater = update.Updater(f.server, f.checker, start=f.start)
    yield f
    f.flag.write_text("")
    http.shutdown()
    http.server_close()


def test_install_env(monkeypatch, tmp_path, factory_home):
    monkeypatch.setenv("FACTORY_UPDATE_ROOT", str(tmp_path / "sf"))
    factory_home.mkdir(parents=True, exist_ok=True); (factory_home / "terminal").write_text("herdr\n")
    env = update.install_env("0.3.0")
    assert env["FACTORY_INSTALL_DOWNLOAD_BASE"] == "https://github.com/Bwaim/SoftwareFactory/releases/download/v0.3.0"
    assert env["FACTORY_INSTALL_DIR"] == str(tmp_path / "sf")
    assert env["FACTORY_INSTALL_TERMINAL"] == "herdr"
    assert not Path(env["FACTORY_INSTALL_TTY"]).exists()


def test_install_env_without_saved_terminal(factory_home, monkeypatch):
    monkeypatch.delenv("FACTORY_INSTALL_TERMINAL", raising=False)
    assert "FACTORY_INSTALL_TERMINAL" not in update.install_env("0.3.0")


def test_install_url_uses_the_checked_version(monkeypatch):
    monkeypatch.delenv("FACTORY_UPDATE_INSTALL_URL", raising=False)
    assert update.install_url("0.3.0") == "https://github.com/Bwaim/SoftwareFactory/releases/download/v0.3.0/install.sh"


def test_run_install_download_error(monkeypatch):
    monkeypatch.setenv("FACTORY_UPDATE_INSTALL_URL", "http://127.0.0.1:9/install.sh")
    status, output = update.run_install("0.3.0")
    assert status == 1 and output


def test_run_refused_without_checked_version(fakes):
    fakes.checker.latest = None
    with pytest.raises(FactoryError, match="No update is available."):
        fakes.updater.run(None)


def test_second_run_returns_the_same_job(fakes):
    fakes.script = f'while [ ! -f "{fakes.flag}" ]; do sleep 0.02; done\n' + SWAP
    first = fakes.updater.run(None)
    assert fakes.updater.run(None) == first
    fakes.flag.write_text("")
    assert fakes.finish(first)["status"] == "done"


def test_success_returns_new_url_and_holds_until_read(fakes):
    job = fakes.finish(fakes.updater.run("repo"))
    url = job["result"]["url"]
    assert "ws=repo" in url and "updated=0.3.0" in url and job["result"]["version"] == "0.3.0"
    assert "warn=" not in url
    assert fakes.updater.holds()
    fakes.updater.job_read(fakes.job_id)
    assert not fakes.updater.holds() and not fakes.server.stopped


def test_success_hold_ends_without_read(fakes, monkeypatch):
    monkeypatch.setattr(update, "HOLD_SECONDS", 0.2)
    fakes.finish(fakes.updater.run(None))
    time.sleep(0.5)
    assert not fakes.updater.holds() and not fakes.server.stopped


def test_failure_before_swap_resumes(fakes):
    fakes.script = "echo boom\nexit 1\n"
    job = fakes.finish(fakes.updater.run(None))
    assert job["status"] == "error" and job["error"] == "The update failed." and "boom" in job["output"]
    assert fakes.server.resumed and not fakes.updater.holds() and not fakes.server.stopped


def test_failure_after_swap_goes_on(fakes, factory_home):
    fakes.script = SWAP + "echo link failed >&2\nexit 1\n"
    job = fakes.finish(fakes.updater.run(None))
    assert job["status"] == "done" and "link failed" in job["result"]["output"]
    assert "warn=1" in job["result"]["url"]
    assert "link failed" in (factory_home / "update.log").read_text()


def test_new_server_failure_holds_until_close(fakes):
    fakes.start_error = True
    job = fakes.finish(fakes.updater.run(None))
    assert job["error"].startswith("The update is installed, but the new server did not start. See ")
    fakes.updater.job_read(fakes.job_id)
    assert fakes.updater.holds()
    fakes.updater.close()
    assert not fakes.updater.holds() and not fakes.server.stopped


def test_pause_runs_before_install(fakes):
    fakes.finish(fakes.updater.run(None))
    assert fakes.server.calls[:2] == ["pause", "install"]


def test_close_does_nothing_on_success(fakes):
    fakes.finish(fakes.updater.run(None))
    fakes.updater.close()
    assert fakes.updater.holds() and not fakes.updater.ended()


def test_error_after_swap_keeps_paused_and_holds(fakes, monkeypatch):
    def broken(*args, **kwargs):
        raise RuntimeError("no url")
    monkeypatch.setattr(server_mod, "page_url", broken)
    job = fakes.finish(fakes.updater.run(None))
    assert job["error"].startswith("The update is installed, but the new server did not start. See ")
    assert "no url" in job["output"]
    assert not fakes.server.resumed and fakes.updater.holds()
    fakes.updater.close()
    assert fakes.updater.ended()


def test_ended_after_read_on_success(fakes):
    fakes.finish(fakes.updater.run(None))
    assert not fakes.updater.ended()
    fakes.updater.job_read(fakes.job_id)
    assert fakes.updater.ended()


def test_ended_after_close_on_failure(fakes):
    fakes.start_error = True
    fakes.finish(fakes.updater.run(None))
    assert not fakes.updater.ended()
    fakes.updater.close()
    assert fakes.updater.ended()


def test_ended_after_hold_timer(fakes, monkeypatch):
    monkeypatch.setattr(update, "HOLD_SECONDS", 0.2)
    fakes.finish(fakes.updater.run(None))
    assert not fakes.updater.ended()
    time.sleep(0.5)
    assert fakes.updater.ended()


def test_not_ended_after_failure_before_swap(fakes):
    fakes.script = "echo boom\nexit 1\n"
    fakes.finish(fakes.updater.run(None))
    assert fakes.server.resumed and not fakes.updater.ended()


def test_install_timeout_kills_the_script_and_resumes(fakes, monkeypatch, tmp_path):
    monkeypatch.setattr(update, "INSTALL_TIMEOUT_SECONDS", 1)
    pidfile = tmp_path / "child.pid"
    fakes.script = f'echo started\nsleep 30 &\necho $! > "{pidfile}"\nwait\n'
    job = fakes.finish(fakes.updater.run(None))
    assert job["status"] == "error" and job["error"] == "The update failed."
    assert "started" in job["output"] and "The install timed out after 1 s." in job["output"]
    assert fakes.server.resumed and not fakes.updater.holds()
    pid = int(pidfile.read_text())
    deadline = time.time() + 5
    while time.time() < deadline:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            break
        time.sleep(0.05)
    else:
        pytest.fail("the install script left a child process")
