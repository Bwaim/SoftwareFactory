import json
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from types import SimpleNamespace

import pytest

from conftest import make_task
from factory import cli, server
from serverutil import info, request

STATUSES = ("active", "awaiting_approval", "waiting_external", "paused", "blocked", "finished")


@pytest.fixture
def fake_api():
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            data = json.dumps({"tag_name": "v99.0.0"}).encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *args):
            pass

    http = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=http.serve_forever, args=(0.01,), daemon=True).start()
    yield f"http://127.0.0.1:{http.server_port}/latest"
    http.shutdown()
    http.server_close()


def update_env(factory, fake_api, tmp_path):
    root = tmp_path / "sf"
    root.mkdir()
    (root / ".installed-by-script").write_text("")
    factory.env.pop("FACTORY_NO_UPDATE_CHECK", None)
    factory.env.update(FACTORY_UPDATE_URL=fake_api, FACTORY_UPDATE_ROOT=str(root))


def checked(i):
    deadline = time.time() + 10
    while time.time() < deadline:
        body = request(i, "GET", "/api/update")[1]
        if body.get("latest"):
            return body
        time.sleep(0.1)
    raise AssertionError("no checked version")


@pytest.fixture
def update_server(factory, fake_api, tmp_path):
    update_env(factory, fake_api, tmp_path)
    factory("dashboard", cwd=tmp_path)
    try:
        i = info()
        checked(i)
        yield SimpleNamespace(info=i)
    finally:
        factory("server", "stop", cwd=tmp_path, check=False)


@pytest.fixture
def update_server_with_tasks(inited):
    from factory import repo
    ctx = repo.load_ctx(cwd=inited.repo)
    for n, status in enumerate(STATUSES):
        make_task(ctx, f"t{n}", status=status)
    inited.factory("dashboard")
    return SimpleNamespace(info=info())


def test_update_info_shows_newer_release(update_server, factory_home):
    status, body = request(update_server.info, "GET", "/api/update")
    assert status == 200
    assert body["installed"] == cli.VERSION and body["latest"] == "99.0.0"
    assert body["dismissed"] is False and body["running_tasks"] == 0
    assert body["log"] == str(factory_home / "update.log")


def test_update_info_counts_running_tasks(update_server_with_tasks):
    assert request(update_server_with_tasks.info, "GET", "/api/update")[1]["running_tasks"] == 3


def test_dismiss_hides_this_version(update_server, factory_home):
    assert request(update_server.info, "POST", "/api/update/dismiss", {}) == (200, {"ok": True})
    assert request(update_server.info, "GET", "/api/update")[1]["dismissed"] is True
    assert (factory_home / "update-dismissed").read_text().strip() == "99.0.0"


def test_run_refuses_a_bad_ws(update_server):
    status, body = request(update_server.info, "POST", "/api/update/run", {"ws": "../x"})
    assert status == 400


def test_close_without_job(update_server):
    assert request(update_server.info, "POST", "/api/update/close", {}) == (200, {"ok": True})


def test_no_latest_when_check_is_off(factory, factory_home, tmp_path):
    factory("dashboard", cwd=tmp_path)
    try:
        status, body = request(info(), "GET", "/api/update")
        assert status == 200 and body["latest"] is None and body["dismissed"] is False
        status, body = request(info(), "POST", "/api/update/run", {})
        assert (status, body["error"]) == (400, "No update is available.")
    finally:
        factory("server", "stop", cwd=tmp_path, check=False)


@pytest.fixture
def live():
    srv = server.Server()
    thread = threading.Thread(target=srv.httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield SimpleNamespace(server=srv, info={"port": srv.port, "token": srv.token})
    finally:
        srv.httpd.shutdown()
        srv.httpd.server_close()


def test_job_read_marks_a_finished_job(live, monkeypatch):
    seen = []
    monkeypatch.setattr(live.server.updater, "job_read", seen.append)
    live.server.jobs["abc"] = {"status": "running"}
    request(live.info, "GET", "/api/jobs/abc")
    assert seen == []
    live.server.jobs["abc"] = {"status": "done", "result": {}}
    assert request(live.info, "GET", "/api/jobs/abc") == (200, {"status": "done", "result": {}})
    assert seen == ["abc"]


def test_should_stop_waits_for_the_hold(live):
    srv = live.server
    assert srv.replaced()
    srv.updater.state = "done"
    assert not srv.should_stop()
    srv.updater.state = None
    assert srv.should_stop()


def test_watch_idle_stops_when_update_ended(live, monkeypatch):
    srv = live.server
    stopped = threading.Event()
    monkeypatch.setattr(server, "IDLE_SECONDS", 0.05)
    monkeypatch.setattr(srv, "replaced", lambda: False)
    monkeypatch.setattr(srv, "stop", stopped.set)
    srv.last = time.time() + 1000
    srv.updater.state = "ended"
    threading.Thread(target=srv.watch_idle, daemon=True).start()
    assert stopped.wait(5)


def test_update_info_skips_a_broken_workspace(live, monkeypatch, capsys):
    from factory import state
    good = SimpleNamespace(id="good", error=None, ctx="good")
    bad = SimpleNamespace(id="bad", error=None, ctx="bad")
    monkeypatch.setattr(live.server, "reload_if_changed", lambda: None)
    monkeypatch.setattr(live.server, "snapshot", lambda: [bad, good])

    def list_tasks(ctx):
        if ctx == "bad":
            raise ValueError("broken state")
        return [{"status": "active"}, {"status": "finished"}]
    monkeypatch.setattr(state, "list_tasks", list_tasks)
    status, body = request(live.info, "GET", "/api/update")
    assert status == 200 and body["running_tasks"] == 1
    assert "running task count failed for bad: broken state" in capsys.readouterr().err


def test_update_info_when_reload_fails(live, monkeypatch):
    def broken():
        raise OSError("no list")
    monkeypatch.setattr(live.server, "reload_if_changed", broken)
    status, body = request(live.info, "GET", "/api/update")
    assert status == 200 and body["running_tasks"] == 0
