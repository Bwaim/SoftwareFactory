import json
import shutil
import time
from types import SimpleNamespace

from conftest import make_repo, task_from_pipeline, task_json, write_pipeline, write_step
from serverutil import alive, info, request, wait_dead

POLL = {"FACTORY_POLL_SECONDS": "1"}
BROKEN = "version: 2\ncolumns: [a, b\n"


def second(inited):
    repo = make_repo(inited.work / "second")
    inited.factory("init", cwd=repo)
    return repo


def waiting_task(inited, repo, tid):
    fdir = repo / ".factory"
    flag = inited.work / f"{tid}.flag"
    write_step(fdir, "wait-review", {"wait_external": True, "done_when": "Approved.", "done_check": f"test -f {flag}"})
    write_pipeline(fdir, {"id": "w", "steps": ["wait-review"]})
    task_from_pipeline(SimpleNamespace(repo=repo), "w", tid=tid, terminal_handle={"agent": tid})
    inited.factory("next", "--task", tid, cwd=repo)
    inited.factory("wait", "--task", tid, cwd=repo, env=POLL)
    assert task_json(fdir, tid)["status"] == "waiting_external"
    return flag


def moved_on(fdir, tid, seconds=15):
    end = time.time() + seconds
    while time.time() < end:
        if task_json(fdir, tid)["status"] != "waiting_external":
            return True
        time.sleep(0.5)
    return False


def test_dashboard_runs_outside_a_repo(factory, factory_home, tmp_path):
    out = factory("dashboard", cwd=tmp_path).stdout
    try:
        assert (factory_home / "server.json").exists()
        assert "Dashboard: http://127.0.0.1:" in out and "ws=" not in out
    finally:
        factory("server", "stop", cwd=tmp_path, check=False)


def test_dashboard_in_repo_selects_workspace(inited):
    assert "ws=repo" in inited.factory("dashboard").stdout


def test_two_workspaces_one_server(inited):
    other = second(inited)
    inited.factory("dashboard")
    inited.factory("dashboard", cwd=other)
    assert (inited.home / "server.json").exists()
    assert not (inited.fdir / "server.json").exists() and not (other / ".factory" / "server.json").exists()
    i = info()
    assert request(i, "GET", "/api/w/repo/tasks")[0] == 200
    assert request(i, "GET", "/api/w/repo-2/tasks")[0] == 200
    assert request(i, "GET", "/api/w/nope/tasks")[0] == 404
    assert request(i, "GET", "/api/tasks")[0] == 404


def test_poll_covers_all_workspaces(inited):
    other = second(inited)
    flags = [waiting_task(inited, inited.repo, "t1"), waiting_task(inited, other, "t2")]
    inited.factory("server", "stop")
    for flag in flags:
        flag.write_text("ok")
    inited.factory("dashboard", env=POLL)
    assert moved_on(inited.fdir, "t1")
    assert moved_on(other / ".factory", "t2")


def test_broken_workspace_does_not_stop_others(inited):
    other = second(inited)
    flag = waiting_task(inited, inited.repo, "t1")
    inited.factory("server", "stop")
    inited.factory("dashboard", env=POLL)
    i = info()
    assert request(i, "GET", "/api/w/repo-2/tasks")[0] == 200
    shutil.rmtree(other)
    status, data = request(i, "GET", "/api/w/repo-2/tasks")
    assert status == 400 and data["error"]
    assert request(i, "GET", "/api/w/repo/tasks")[0] == 200
    flag.write_text("ok")
    assert moved_on(inited.fdir, "t1")
    assert alive(i["pid"])


def test_error_runtime_recovers(inited):
    from factory import server
    path = inited.fdir / "factory.yaml"
    good = path.read_text()
    srv = server.Server()
    try:
        assert srv.runtime("repo").error is None
        path.write_text(BROKEN)
        srv.reload()
        assert srv.runtime("repo").error
        path.write_text(good)
        srv.reload()
        assert srv.runtime("repo").error is None
        path.write_text(BROKEN)
        assert srv.fresh("repo").error
        path.write_text(good)
        srv.reload_if_changed()
        assert srv.runtime("repo").error is None
    finally:
        srv.httpd.server_close()


def test_legacy_server_file_is_removed(inited):
    legacy = inited.fdir / "server.json"
    legacy.write_text(json.dumps({"port": 1, "token": "x", "pid": 999999}))
    inited.factory("dashboard")
    assert not legacy.exists()


def test_legacy_server_of_new_workspace_is_removed(inited):
    from factory import workspaces
    inited.factory("dashboard")
    try:
        other = second(inited)
        legacy = other / ".factory" / "server.json"
        legacy.write_text(json.dumps({"port": 1, "token": "x", "pid": 999999}))
        workspaces.register(other)
        assert request(info(), "GET", "/api/workspaces")[0] == 200
        assert not legacy.exists()
    finally:
        inited.factory("server", "stop", check=False)


def test_stop_legacy_without_port(tmp_path):
    import os
    from factory import server
    (tmp_path / "server.json").write_text(json.dumps({"token": "x", "pid": os.getpid()}))
    assert not server.stop_legacy(tmp_path)
    assert not (tmp_path / "server.json").exists()


def test_stop_legacy_calls_shutdown(tmp_path, monkeypatch):
    from factory import server
    (tmp_path / "server.json").write_text(json.dumps({"port": 4321, "token": "tok", "pid": 1}))
    seen = []

    class Reply:
        def read(self):
            return b"{}"

    def fake_urlopen(req, timeout=None):
        seen.append((req.full_url, req.get_method(), req.get_header("X-factory-token")))
        return Reply()

    monkeypatch.setattr(server, "pid_alive", lambda pid: True)
    monkeypatch.setattr(server, "ping", lambda i: True)
    monkeypatch.setattr(server.urllib.request, "urlopen", fake_urlopen)
    assert server.stop_legacy(tmp_path)
    assert seen == [("http://127.0.0.1:4321/api/shutdown", "POST", "tok")]
    assert not (tmp_path / "server.json").exists()


def test_server_stop_from_anywhere(inited, tmp_path):
    inited.factory("dashboard")
    pid = info()["pid"]
    assert inited.factory("server", "stop", cwd=tmp_path).stdout.strip() == "Server stopped."
    assert wait_dead(pid)
    assert not (inited.home / "server.json").exists()


def test_keep_polling_registers(inited):
    from factory import workspaces
    write_step(inited.fdir, "wait-review", {"wait_external": True, "done_when": "Approved.", "done_check": "false"})
    write_pipeline(inited.fdir, {"id": "w", "steps": ["wait-review"]})
    task_from_pipeline(inited, "w", worktree=str(inited.repo), status="waiting_external")
    workspaces.remove("repo")
    assert workspaces.list_all() == []
    inited.factory("tasks")
    assert [w["id"] for w in workspaces.list_all()] == ["repo"]


def test_editor_url_has_ws(inited):
    assert "ws=repo" in inited.factory("pipeline", "edit").stdout
    assert "ws=repo" in inited.factory("step", "edit").stdout


def test_editor_needs_a_listed_workspace(inited):
    from factory import workspaces
    workspaces.remove("repo")
    r = inited.factory("pipeline", "edit", check=False)
    assert r.returncode == 1
    assert "This repository is not in the dashboard. Run `factory dashboard` in it first." in r.stderr
    assert workspaces.list_all() == []
