from conftest import events, fake_calls, fake_config, make_task, task_from_pipeline, task_json, write_pipeline, write_step
from factory import board, repo


def test_block_unblock_and_order(inited):
    ctx = repo.load_ctx(cwd=inited.repo)
    make_task(ctx, tid="a")
    make_task(ctx, tid="b")
    inited.factory("block", "Which DB?", "--task", "b")
    t = task_json(inited.fdir, "b")
    assert t["status"] == "blocked" and t["status_reason"] == "Which DB?"
    assert fake_calls(inited.fdir)[-1]["op"] == "notify"
    rows = inited.factory.json("tasks")
    assert [r["id"] for r in rows] == ["b", "a"]
    assert "Which DB?" in inited.factory("tasks").stdout
    inited.factory("unblock", "--task", "b")
    assert task_json(inited.fdir, "b")["status"] == "active"
    assert [e["type"] for e in events(inited.fdir, "b")] == ["task_blocked", "task_unblocked"]


def test_session_state_column(inited):
    ctx = repo.load_ctx(cwd=inited.repo)
    make_task(ctx, tid="a", terminal_handle={"agent": "a"})
    make_task(ctx, tid="g")
    rows = {r["id"]: r for r in inited.factory.json("tasks")}
    assert rows["a"]["session_state"] == "idle" and rows["g"]["session_state"] == "gone"
    fake_config(inited.fdir, capabilities=["notify"])
    rows = {r["id"]: r for r in inited.factory.json("tasks")}
    assert rows["a"]["session_state"] == "unknown"


def test_columns_follow_steps(inited):
    write_step(inited.fdir, "plan", {"column": "Plan"})
    write_step(inited.fdir, "code", {"column": "Plan"})
    write_step(inited.fdir, "nocol", {})
    write_pipeline(inited.fdir, {"id": "cols", "start_column": "Specification", "steps": ["plan", {"id": "code", "column": "Implementation"}, "nocol"]})
    task_from_pipeline(inited, "cols", column="Specification")
    run = lambda *a: inited.factory(*a, "--task", "t1")
    run("next")
    assert task_json(inited.fdir, "t1")["column"] == "Plan"
    run("done"); run("next")
    assert task_json(inited.fdir, "t1")["column"] == "Implementation"
    run("done"); run("next")
    assert task_json(inited.fdir, "t1")["column"] == "Implementation"
    changes = [(e["from"], e["to"]) for e in events(inited.fdir, "t1") if e["type"] == "column_changed"]
    assert changes == [("Specification", "Plan"), ("Plan", "Implementation")]


def test_launch_uses_start_column(inited):
    from factory import launch
    write_step(inited.fdir, "w", {})
    write_pipeline(inited.fdir, {"id": "sc", "start_column": "Plan", "steps": ["w"]})
    task = launch.launch(repo.load_ctx(cwd=inited.repo), "sc", "Start col", {})
    assert task["column"] == "Plan"
