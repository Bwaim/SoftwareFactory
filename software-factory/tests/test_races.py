import pytest

from conftest import events, task_from_pipeline, task_json, write_pipeline, write_step
from factory import engine, repo, state
from factory.errors import FactoryError


@pytest.fixture
def ctx_two_steps(inited):
    write_step(inited.fdir, "one", {})
    write_step(inited.fdir, "two", {})
    write_step(inited.fdir, "three", {})
    write_pipeline(inited.fdir, {"id": "rp", "steps": ["one", "two", "three"]})
    task_from_pipeline(inited, "rp")
    return repo.load_ctx(cwd=inited.repo)


def interfere_once(monkeypatch, action):
    original = state.update
    fired = []

    def update(ctx, tid, fn):
        if not fired:
            fired.append(True)
            action()
        return original(ctx, tid, fn)

    monkeypatch.setattr(state, "update", update)
    return original


def test_second_advance_with_same_position_refused(ctx_two_steps):
    ctx = ctx_two_steps
    start = task_json(ctx.fdir, "t1")["position"]
    engine.advance(ctx, "t1", "step_done", start)
    with pytest.raises(FactoryError, match="changed"):
        engine.advance(ctx, "t1", "step_done", start)
    assert task_json(ctx.fdir, "t1")["position"] == start + 1
    assert [e["type"] for e in events(ctx.fdir, "t1")] == ["step_done"]


def test_done_racing_with_skip_advances_once(ctx_two_steps, monkeypatch):
    ctx = ctx_two_steps
    start = task_json(ctx.fdir, "t1")["position"]
    interfere_once(monkeypatch, lambda: engine.skip(ctx, "t1"))
    with pytest.raises(FactoryError, match="changed"):
        engine.done(ctx, "t1")
    assert task_json(ctx.fdir, "t1")["position"] == start + 1


def test_approve_after_request_changes_race_is_factory_error(inited, monkeypatch):
    write_step(inited.fdir, "user-validation", {})
    write_pipeline(inited.fdir, {"id": "ap", "steps": ["user-validation"]})
    task_from_pipeline(inited, "ap")
    inited.factory("next", "--task", "t1")
    ctx = repo.load_ctx(cwd=inited.repo)
    assert task_json(ctx.fdir, "t1")["status"] == "awaiting_approval"
    interfere_once(monkeypatch, lambda: engine.request_changes(ctx, "t1", "more"))
    with pytest.raises(FactoryError, match="not waiting for an approval"):
        engine.approve(ctx, "t1")


def test_request_changes_after_approve_race_is_factory_error(inited, monkeypatch):
    write_step(inited.fdir, "user-validation", {})
    write_pipeline(inited.fdir, {"id": "ap", "steps": ["user-validation"]})
    task_from_pipeline(inited, "ap")
    inited.factory("next", "--task", "t1")
    ctx = repo.load_ctx(cwd=inited.repo)
    interfere_once(monkeypatch, lambda: engine.approve(ctx, "t1"))
    with pytest.raises(FactoryError, match="not waiting for an approval"):
        engine.request_changes(ctx, "t1", "more")


def test_unblock_racing_with_unblock_refused(inited, monkeypatch):
    write_step(inited.fdir, "one", {})
    write_pipeline(inited.fdir, {"id": "bp", "steps": ["one"]})
    task_from_pipeline(inited, "bp")
    ctx = repo.load_ctx(cwd=inited.repo)
    engine.block(ctx, "t1", "why")
    interfere_once(monkeypatch, lambda: engine.unblock(ctx, "t1"))
    with pytest.raises(FactoryError, match="not blocked"):
        engine.unblock(ctx, "t1")


def test_end_wait_twice_ends_once(inited, monkeypatch):
    write_step(inited.fdir, "qa", {"wait_external": True, "done_when": "QA is done"})
    write_step(inited.fdir, "after", {})
    write_pipeline(inited.fdir, {"id": "wp", "steps": ["qa", "after"]})
    task_from_pipeline(inited, "wp")
    ctx = repo.load_ctx(cwd=inited.repo)
    inited.factory("next", "--task", "t1")
    inited.factory("wait", "--task", "t1")
    start = task_json(ctx.fdir, "t1")["position"]
    interfere_once(monkeypatch, lambda: engine.end_wait(ctx, "t1", "manual"))
    with pytest.raises(FactoryError):
        engine.end_wait(ctx, "t1", "check")
    assert task_json(ctx.fdir, "t1")["position"] == start + 1
    assert [e["type"] for e in events(ctx.fdir, "t1")].count("external_event") == 1
