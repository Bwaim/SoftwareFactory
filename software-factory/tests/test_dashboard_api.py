import time

import pytest

from conftest import events, fake_calls, make_task, task_json, write_pipeline, write_step
from factory import repo
from serverutil import info, request


@pytest.fixture
def dash(inited):
    write_step(inited.fdir, "w", {"column": "Plan"})
    write_pipeline(inited.fdir, {"id": "p", "steps": ["w", "user-validation"]})
    inited.factory("dashboard")
    yield inited, info(inited.fdir)
    inited.factory("server", "stop", check=False)


def test_launch_dry_run_then_launch(dash):
    inited, i = dash
    body = {"pipeline": "p", "description": "From dashboard", "inputs": {}}
    status, rep = request(i, "POST", "/api/launch/dry-run", body)
    assert status == 200 and rep["task_id"] == "from-dashboard" and rep["ok"]
    assert not (inited.fdir / "tasks" / "from-dashboard").exists()
    status, task = request(i, "POST", "/api/launch", body)
    assert task["id"] == "from-dashboard"
    status, rows = request(i, "GET", "/api/tasks")
    row = rows[0]
    assert row["id"] == "from-dashboard" and row["status"] == "active" and row["session_state"] == "idle" and row["column"] == "Discovery"


def test_actions_call_cli_functions(dash):
    inited, i = dash
    ctx = repo.load_ctx(cwd=inited.repo)
    make_task(ctx, tid="t1", terminal_handle={"agent": "t1"})
    assert request(i, "POST", "/api/tasks/t1/focus", {})[0] == 200
    assert request(i, "POST", "/api/tasks/t1/send-prompt", {"text": "hi"})[0] == 200
    ops = [c["op"] for c in fake_calls(inited.fdir)]
    assert ops[-2:] == ["focus", "send_prompt"]
    assert events(inited.fdir, "t1")[-1]["type"] == "prompt_sent"
    status, job = request(i, "POST", "/api/tasks/t1/pause", {"wait": True})
    for _ in range(50):
        state = request(i, "GET", f"/api/jobs/{job['job']}")[1]
        if state["status"] != "running":
            break
        time.sleep(0.1)
    assert state["status"] == "done"
    assert [c["op"] for c in fake_calls(inited.fdir)][-2:] == ["wait_idle", "close"]
    assert request(i, "POST", "/api/tasks/t1/resume", {})[0] == 200
    assert task_json(inited.fdir, "t1")["status"] == "active"


def test_approve_from_card(dash):
    inited, i = dash
    request(i, "POST", "/api/launch", {"pipeline": "p", "description": "Card", "inputs": {}})
    inited.factory("next", "--task", "card", cwd=inited.worktrees / "card")
    inited.factory("done", "--task", "card", cwd=inited.worktrees / "card")
    inited.factory("next", "--task", "card", cwd=inited.worktrees / "card")
    rows = request(i, "GET", "/api/tasks")[1]
    assert rows[0]["status"] == "awaiting_approval" and rows[0]["approval"]["target"] == "worktree"
    assert request(i, "POST", "/api/tasks/card/approve", {})[0] == 200
    assert fake_calls(inited.fdir)[-1]["text"].startswith("The user approved.")


def test_backlog_routes(dash):
    inited, i = dash
    for title in ("A", "B", "C"):
        request(i, "POST", "/api/backlog/add", {"title": title, "summary": "", "pipeline": None})
    request(i, "POST", "/api/backlog/move", {"id": "b3", "to": 1})
    assert [e["title"] for e in request(i, "GET", "/api/backlog")[1]] == ["C", "A", "B"]
    request(i, "POST", "/api/backlog/remove", {"id": "b1"})
    assert [e["id"] for e in request(i, "GET", "/api/backlog")[1]] == ["b3", "b2"]


def test_artifact_and_errors(dash):
    inited, i = dash
    ctx = repo.load_ctx(cwd=inited.repo)
    make_task(ctx, tid="t1")
    (inited.fdir / "tasks" / "t1" / "artifacts" / "spec.md").write_text("# Spec")
    assert request(i, "GET", "/api/tasks/t1/artifacts/spec.md")[1]["text"] == "# Spec"
    assert request(i, "GET", "/api/tasks/t1/artifacts/..%2Fx")[0] in (400, 404)
    status, err = request(i, "POST", "/api/tasks/t1/approve", {})
    assert status == 400 and "approval" in err["error"]


def test_clean_and_delete_routes(dash):
    inited, i = dash
    request(i, "POST", "/api/launch", {"pipeline": "p", "description": "Del", "inputs": {}})
    from factory import state
    state.update(repo.load_ctx(cwd=inited.repo), "del", lambda t: state.set_status(t, "finished"))
    rows = request(i, "GET", "/api/clean")[1]
    assert rows[0]["id"] == "del" and rows[0]["merged"]
    assert request(i, "POST", "/api/delete/dry-run", {"id": "del"})[1]["needs_confirm"] is False
    assert request(i, "POST", "/api/delete", {"id": "del", "confirm_unpushed": False})[0] == 200
    assert (inited.fdir / "tasks" / "archive" / "del").exists()


def test_missing_body_field_is_400(dash):
    inited, i = dash
    ctx = repo.load_ctx(cwd=inited.repo)
    make_task(ctx, tid="t1", terminal_handle={"agent": "t1"})
    status, err = request(i, "POST", "/api/tasks/t1/send-prompt", {})
    assert status == 400 and "text" in err["error"]


@pytest.mark.parametrize("bad_id", ["../x", "archive/x"])
def test_delete_rejects_non_task_ids(dash, bad_id):
    inited, i = dash
    decoy = inited.fdir / "tasks" / "archive" / "x"
    decoy.mkdir(parents=True)
    (decoy / "task.json").write_text("{}")
    other = inited.fdir / "x"
    other.mkdir()
    assert request(i, "POST", "/api/delete/dry-run", {"id": bad_id})[0] == 400
    assert request(i, "POST", "/api/delete", {"id": bad_id, "confirm_unpushed": True})[0] == 400
    assert (decoy / "task.json").exists() and other.exists()


def test_artifact_for_unknown_task_creates_nothing(dash):
    inited, i = dash
    assert request(i, "GET", "/api/tasks/ghost/artifacts/spec.md")[0] == 400
    assert not (inited.fdir / "tasks" / "ghost").exists()


def test_artifact_symlink_outside_is_refused(dash, tmp_path):
    inited, i = dash
    ctx = repo.load_ctx(cwd=inited.repo)
    make_task(ctx, tid="t1")
    secret = tmp_path / "secret.md"
    secret.write_text("secret")
    (inited.fdir / "tasks" / "t1" / "artifacts" / "spec.md").symlink_to(secret)
    status, err = request(i, "GET", "/api/tasks/t1/artifacts/spec.md")
    assert status == 400 and "artifacts folder" in err["error"]


def test_confirm_unpushed_must_be_true(dash):
    inited, i = dash
    request(i, "POST", "/api/launch", {"pipeline": "p", "description": "Dirty", "inputs": {}})
    (inited.worktrees / "dirty" / "new.txt").write_text("x")
    assert request(i, "POST", "/api/delete/dry-run", {"id": "dirty"})[1]["needs_confirm"] is True
    assert request(i, "POST", "/api/delete", {"id": "dirty", "confirm_unpushed": "false"})[0] == 400
    assert (inited.fdir / "tasks" / "dirty").exists()
