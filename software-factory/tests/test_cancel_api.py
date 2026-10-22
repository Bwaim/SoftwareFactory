import json

import pytest

from conftest import fake_config, git, write_pipeline, write_step
from factory import launch, repo
from serverutil import info, request


@pytest.fixture
def dash(inited):
    write_step(inited.fdir, "work", {})
    write_pipeline(inited.fdir, {"id": "branchy", "inputs": {"branch": {"description": "b"}}, "steps": ["work"]})
    ctx = repo.load_ctx(cwd=inited.repo)
    task = launch.launch(ctx, "branchy", "Cancel me", {"branch": "feat/c"})
    inited.factory("dashboard")
    yield inited, info(inited.fdir), task
    inited.factory("server", "stop", check=False)


def test_dry_run_route_matches_cli(dash):
    inited, i, task = dash
    status, rep = request(i, "POST", f"/api/tasks/{task['id']}/cancel/dry-run", {})
    cli = inited.factory("cancel", task["id"], "--dry-run").stdout
    assert status == 200 and rep["task_id"] == task["id"]
    assert rep["text"].strip() == cli.strip()


def test_cancel_route_archives_and_removes_from_list(dash):
    inited, i, task = dash
    status, rep = request(i, "POST", f"/api/tasks/{task['id']}/cancel", {})
    assert status == 200 and rep["task_id"] == task["id"] and rep["text"]
    rows = request(i, "GET", "/api/tasks")[1]
    assert all(row["id"] != task["id"] for row in rows)
    archived = json.loads((inited.fdir / "tasks" / "archive" / task["id"] / "task.json").read_text())
    assert archived["status"] == "cancelled"


def test_routes_reject_missing_token(dash):
    inited, i, task = dash
    assert request(i, "POST", f"/api/tasks/{task['id']}/cancel/dry-run", {}, token=False)[0] == 401
    assert request(i, "POST", f"/api/tasks/{task['id']}/cancel", {}, token=False)[0] == 401


def test_parts_left_reply(dash):
    inited, i, task = dash
    lock = inited.repo / ".git" / "refs" / "heads" / "feat" / "c.lock"
    lock.write_text("")
    try:
        status, rep = request(i, "POST", f"/api/tasks/{task['id']}/cancel", {})
    finally:
        lock.unlink()
    assert status == 400 and rep["archived"] is True
    assert any(item.startswith("The branch feat/c was not deleted:") for item in rep["left"])


def test_close_failure_reply(dash):
    inited, i, task = dash
    fake_config(inited.fdir, fail_close=True)
    status, rep = request(i, "POST", f"/api/tasks/{task['id']}/cancel", {})
    assert status == 400 and "archived" not in rep and rep["error"]
    rows = request(i, "GET", "/api/tasks")[1]
    assert any(row["id"] == task["id"] for row in rows)
