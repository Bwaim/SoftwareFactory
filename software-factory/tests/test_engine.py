import pytest

from conftest import events, task_from_pipeline, task_json, write_pipeline, write_step
from factory import engine, repo
from factory.errors import FactoryError


@pytest.fixture
def flow(inited):
    write_step(inited.fdir, "make", {"done_check": "test -f made.txt", "outputs": {"out": {"type": "text", "description": "o", "optional": True}}}, body="Create `made.txt`. Then run `factory state set out made.txt`.\n")
    write_step(inited.fdir, "must", {"required": True})
    write_step(inited.fdir, "rebase", {})
    write_step(inited.fdir, "commit", {})
    write_step(inited.fdir, "rebase-and-commit", {"type": "group", "steps": ["rebase", "commit"]}, body="")
    write_pipeline(inited.fdir, {"id": "flow", "steps": ["make", "must", "rebase-and-commit"]})
    task_from_pipeline(inited, "flow")
    return inited


def run(flow, *args, check=True):
    return flow.factory(*args, "--task", "t1", check=check)


def test_next_done_check_fails_then_passes(flow):
    out = run(flow, "next").stdout
    assert "Step 2 of 5: make" in out
    assert "Create `made.txt`. Then run `factory state set out made.txt`." in out
    r = run(flow, "done", check=False)
    assert r.returncode == 1 and "done check failed" in r.stderr
    (flow.repo / "made.txt").write_text("x")
    assert "Step done" in run(flow, "done").stdout
    kinds = [e["type"] for e in events(flow.fdir, "t1")]
    assert kinds == ["step_started", "done_check_failed", "step_done"]


def test_skip_refused_for_required_and_composite_path(flow):
    (flow.repo / "made.txt").write_text("x")
    run(flow, "next"); run(flow, "done"); run(flow, "next")
    r = run(flow, "skip", check=False)
    assert r.returncode == 1 and "required" in r.stderr
    run(flow, "done")
    assert "rebase-and-commit > rebase" in run(flow, "next").stdout


def test_last_done_finishes(flow):
    (flow.repo / "made.txt").write_text("x")
    for _ in range(4):
        run(flow, "next"); run(flow, "done")
    t = task_json(flow.fdir, "t1")
    assert t["status"] == "finished"
    assert t["column"] == "Done"
    assert events(flow.fdir, "t1")[-1]["type"] == "task_finished"
    assert "finished" in run(flow, "next").stdout


def test_missing_config_asks(inited):
    write_step(inited.fdir, "cfg", {"config": {"target_branch": {"description": "Target branch"}}})
    write_pipeline(inited.fdir, {"id": "c", "steps": ["cfg"]})
    task_from_pipeline(inited, "c")
    out = inited.factory("next", "--task", "t1").stdout
    assert "factory config set cfg target_branch <value>" in out
    assert events(inited.fdir, "t1")[-1] == {**events(inited.fdir, "t1")[-1], "type": "config_asked", "key": "target_branch"}
    inited.factory("config", "set", "cfg", "target_branch", "release")
    assert "Do the step." in inited.factory("next", "--task", "t1").stdout


def test_subagent_call_model_effort_precedence(inited):
    write_step(inited.fdir, "sub", {"run_in": "subagent", "model": "haiku", "effort": "low"}, body="Analyze {{ticket}}.\n")
    write_pipeline(inited.fdir, {"id": "s", "steps": [{"id": "sub", "model": "opus"}]})
    task_from_pipeline(inited, "s", state={"ticket": "ABC-1"})
    out = inited.factory("next", "--task", "t1").stdout
    assert "Call the Agent tool" in out
    assert "- model: opus" in out
    assert "- effort: low" in out
    assert "Analyze ABC-1." in out
    started = events(inited.fdir, "t1")[0]
    assert (started["run_in"], started["model"], started["effort"]) == ("subagent", "opus", "low")


def test_done_check_timeout(inited, monkeypatch):
    write_step(inited.fdir, "slow", {"done_check": "sleep 5"})
    write_pipeline(inited.fdir, {"id": "slow", "steps": ["slow"]})
    task_from_pipeline(inited, "slow")
    monkeypatch.setattr(engine, "DONE_CHECK_TIMEOUT", 1)
    ctx = repo.load_ctx(cwd=inited.repo)
    with pytest.raises(FactoryError, match="Timed out"):
        engine.done(ctx, "t1")
    assert events(inited.fdir, "t1")[-1]["type"] == "done_check_failed"


def test_next_tells_session_about_block_skip_and_goto(flow):
    out = run(flow, "next").stdout
    assert "Only after the user approves" in out
    assert "`factory skip`" in out
