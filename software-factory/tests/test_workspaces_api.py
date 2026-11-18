import pytest
import yaml

from conftest import fake_config, git, make_repo, make_task
from factory import api, repo, state
from factory.errors import FactoryError
from serverutil import info, request


@pytest.fixture
def dash(inited):
    inited.factory("dashboard")
    yield inited, info()
    inited.factory("server", "stop", check=False)


def second(inited, name="second"):
    return make_repo(inited.work / name)


def rows(i):
    status, data = request(i, "GET", "/api/workspaces")
    assert status == 200
    return {w["id"]: w for w in data}


def test_list_has_counts(dash):
    inited, i = dash
    ctx = repo.load_ctx(cwd=inited.repo)
    make_task(ctx, "a", status="awaiting_approval")
    make_task(ctx, "b", status="blocked")
    make_task(ctx, "c", status="active", attention="needs a look")
    make_task(ctx, "d", status="finished")
    row = rows(i)["repo"]
    assert row["needs_you"] == 3 and row["open_tasks"] == 3 and row["error"] is None
    assert row["name"] == "repo" and row["path"] == str(inited.repo)


def test_add_needs_factory(dash):
    inited, i = dash
    other = second(inited)
    status, body = request(i, "POST", "/api/workspaces/add", {"path": str(other)})
    assert status == 400 and body["code"] == "no_factory" and body["main"] == str(other)
    assert body["error"] == api.NO_FACTORY


def test_add_with_init_without_library(dash):
    inited, i = dash
    other = second(inited)
    status, entry = request(i, "POST", "/api/workspaces/add", {"path": str(other), "init": True, "library": "  "})
    assert status == 200 and entry["path"] == str(other)
    assert yaml.safe_load((other / ".factory" / "factory.yaml").read_text())["library"] == ""
    assert all(p.is_file() for p in inited.home.iterdir())
    assert entry["id"] in rows(i)


def test_add_with_missing_library(dash):
    inited, i = dash
    other = second(inited)
    body = {"path": str(other), "init": True, "library": str(inited.work / "nope")}
    status, err = request(i, "POST", "/api/workspaces/add", body)
    assert status == 400 and err["checks"] == []
    assert err["error"] == "The library folder does not exist. Create it, or leave the field blank."


def test_add_with_failed_check(dash):
    inited, i = dash
    other = inited.work / "plain"
    other.mkdir()
    git("init", "-b", "main", cwd=other)
    (other / ".factory").mkdir()
    fake_config(other / ".factory", check_ok=False)
    status, err = request(i, "POST", "/api/workspaces/add", {"path": str(other), "init": True})
    assert status == 400 and [c["name"] for c in err["checks"]] == ["terminal"]


def test_add_duplicate(dash):
    inited, i = dash
    status, err = request(i, "POST", "/api/workspaces/add", {"path": str(inited.repo), "init": True})
    assert status == 400 and "repo" in err["error"]


def test_rename_and_delete(dash):
    inited, i = dash
    assert request(i, "POST", "/api/workspaces/repo/rename", {"name": "Shop"})[0] == 200
    assert rows(i)["repo"]["name"] == "Shop"
    assert request(i, "POST", "/api/workspaces/nope/rename", {"name": "x"})[0] == 404
    status, entry = request(i, "POST", "/api/workspaces/repo/delete", {})
    assert status == 200 and entry["id"] == "repo"
    assert "repo" not in rows(i)
    assert request(i, "GET", "/api/w/repo/tasks")[0] == 404
    assert request(i, "POST", "/api/workspaces/repo/delete", {})[0] == 404
    assert inited.fdir.exists()


def test_list_marks_deleted_folder(dash):
    inited, i = dash
    other = second(inited)
    inited.factory("init", cwd=other)
    inited.factory("dashboard", cwd=other)
    wid = next(w for w in rows(i) if w != "repo")
    assert request(i, "GET", f"/api/w/{wid}/tasks")[0] == 200
    moved = inited.work / "moved"
    other.rename(moved)
    assert rows(i)[wid]["error"]
    moved.rename(other)
    assert rows(i)[wid]["error"] is None


def test_list_sees_cli_init(dash):
    inited, i = dash
    assert len(rows(i)) == 1
    other = second(inited)
    inited.factory("init", cwd=other)
    inited.factory("dashboard", cwd=other)
    assert len(rows(i)) == 2


def test_pick_folder(monkeypatch):
    class Done:
        def __init__(self, code, out):
            self.returncode, self.stdout = code, out

    calls = []

    def fake_run(cmd, **kw):
        calls.append((cmd, kw["timeout"]))
        return Done(0, "/Users/x/repo/\n")

    monkeypatch.setattr(api.sys, "platform", "darwin")
    monkeypatch.setattr(api.subprocess, "run", fake_run)
    assert api.pick_folder(None, query={}, body={}) == {"path": "/Users/x/repo"}
    assert calls == [(["osascript", *api.PICKER_SCRIPT], 300)]
    assert 'tell application "System Events" to activate' in api.PICKER_SCRIPT
    monkeypatch.setattr(api.subprocess, "run", lambda *a, **k: Done(1, ""))
    assert api.pick_folder(None, query={}, body={}) == {"path": None}
    monkeypatch.setattr(api.sys, "platform", "linux")
    with pytest.raises(FactoryError, match="The folder picker works only on macOS."):
        api.pick_folder(None, query={}, body={})


def test_pick_folder_timeout(monkeypatch):
    def slow(cmd, **kw):
        raise api.subprocess.TimeoutExpired(cmd, kw["timeout"])

    monkeypatch.setattr(api.sys, "platform", "darwin")
    monkeypatch.setattr(api.subprocess, "run", slow)
    assert api.pick_folder(None, query={}, body={}) == {"path": None}


def test_add_needs_full_path(dash):
    _, i = dash
    for path in ("", "   ", "repo", "./repo"):
        status, err = request(i, "POST", "/api/workspaces/add", {"path": path})
        assert status == 400 and err["error"] == api.FULL_PATH


def test_add_and_rename_refuse_non_string(dash):
    _, i = dash
    status, err = request(i, "POST", "/api/workspaces/add", {"path": 5})
    assert status == 400 and err["error"] == api.FULL_PATH
    status, err = request(i, "POST", "/api/workspaces/repo/rename", {"name": ["x"]})
    assert status == 400 and err["error"] == "A name has 1 to 64 characters."


def test_host(dash):
    _, i = dash
    assert request(i, "GET", "/api/host")[1] == {"folder_picker": api.sys.platform == "darwin"}
