import pytest

from conftest import SF, make_task
from factory import events, repo, task_detail
from serverutil import info, request

STEPS = [{"id": sid, "path": path, "with": {}, "column": None, "model": None, "effort": None}
         for sid, path in [("create-worktree", ["create-worktree"]), ("spec", ["spec"]), ("build", ["implement", "build"]), ("review", ["review"])]]
PAGE = (SF / "lib" / "factory" / "web" / "dashboard.html").read_text()


@pytest.fixture
def ctx(inited):
    return repo.load_ctx(cwd=inited.repo)


@pytest.fixture
def served(inited):
    inited.factory("dashboard")
    yield inited, info(inited.fdir)
    inited.factory("server", "stop", check=False)


def test_steps_before_the_position_are_done_and_the_rest_todo():
    rows = task_detail.step_rows({"steps": STEPS, "position": 2, "status": "active"})
    assert [r["state"] for r in rows] == ["done", "done", "current", "todo"]
    assert rows[2] == {"index": 2, "id": "build", "path": ["implement", "build"], "state": "current"}


def test_every_step_is_done_when_the_task_is_finished():
    rows = task_detail.step_rows({"steps": STEPS, "position": 4, "status": "finished"})
    assert [r["state"] for r in rows] == ["done"] * 4


def test_detail_has_row_steps_info_values_and_events(ctx):
    make_task(ctx, tid="t1", worktree="/wt/t1", steps=STEPS, position=1, state={"branch": "feature/x", "ticket": "AB-1", "summary": "Long text"})
    events.log(ctx, "t1", "step_started", "spec")
    data = task_detail.detail(ctx, "t1")
    assert data["row"]["id"] == "t1" and data["row"]["ticket"] == "AB-1"
    assert [s["state"] for s in data["steps"]] == ["done", "current", "todo", "todo"]
    assert data["info"]["branch"] == "feature/x" and data["info"]["worktree"] == "/wt/t1" and data["info"]["base_ref"] == "main"
    assert data["values"] == {"branch": "feature/x", "ticket": "AB-1", "summary": "Long text"}
    assert [(e["type"], e["step"]) for e in data["events"]] == [("step_started", "spec")]


def test_detail_keeps_only_the_last_events(ctx, monkeypatch):
    make_task(ctx, tid="t1")
    for n in range(5):
        events.log(ctx, "t1", "prompt_sent", "s", n=n)
    monkeypatch.setattr(task_detail, "EVENT_LIMIT", 2)
    assert [e["n"] for e in task_detail.detail(ctx, "t1")["events"]] == [3, 4]






def test_detail_route(served):
    inited, i = served
    ctx = repo.load_ctx(cwd=inited.repo)
    make_task(ctx, tid="t1", steps=STEPS, position=2)
    status, data = request(i, "GET", "/api/tasks/t1/detail")
    assert status == 200 and data["row"]["id"] == "t1" and [s["state"] for s in data["steps"]][2] == "current"
    status, error = request(i, "GET", "/api/tasks/nope/detail")
    assert status == 400 and "Unknown task" in error["error"]


def test_dashboard_page_has_the_detail_panel():
    for text in ('id="detail"', "/detail`", "#task=", "Close details", "Pipeline", "Timeline", "closeDetail", "DETAIL_REFRESH_MS"):
        assert text in PAGE

