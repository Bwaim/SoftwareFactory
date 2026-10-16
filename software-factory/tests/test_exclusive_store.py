import shutil

import pytest

from conftest import events, fake_calls, task_from_pipeline, task_json, write_pipeline, write_step


@pytest.fixture
def ctx3(inited, monkeypatch):
    from factory import repo
    for key, value in inited.factory.env.items():
        monkeypatch.setenv(key, value)
    monkeypatch.chdir(inited.repo)
    write_step(inited.fdir, "emu-run", {"exclusive": "emu"})
    write_step(inited.fdir, "emu-check", {"exclusive": "emu"})
    write_step(inited.fdir, "plain", {})
    write_pipeline(inited.fdir, {"id": "e", "steps": ["emu-run", "emu-check", "plain"]})
    for tid in ("t1", "t2", "t3"):
        task_from_pipeline(inited, "e", tid=tid, worktree=str(inited.repo), terminal_handle={"agent": tid})
    return repo.load_ctx(cwd=inited.repo)


def ex():
    from factory import exclusive
    return exclusive


def queue(ctx, name="emu"):
    return [q["task"] for q in ex().read(ctx, name)["queue"]]


def sent(ctx):
    return [c["text"] for c in fake_calls(ctx.fdir) if c["op"] == "send_prompt"]


def move(ctx, tid, sid):
    from factory import state

    def fn(t):
        ids = [e["id"] for e in t["steps"]]
        t.update(position=ids.index(sid) if sid else len(ids), started=None)

    state.update(ctx, tid, fn)


def test_claim_free_resource(ctx3):
    assert ex().claim(ctx3, "t1", "emu", "next") == (True, None)
    assert ex().read(ctx3, "emu")["holder"] == "t1"
    assert ex().read(ctx3, "emu")["since"]


def test_read_unknown_resource_is_free(ctx3):
    assert ex().read(ctx3, "emu") == {"holder": None, "since": None, "queue": []}


def test_claim_by_holder_is_true(ctx3):
    ex().claim(ctx3, "t1", "emu", "next")
    assert ex().claim(ctx3, "t1", "emu", "next") == (True, None)


def test_claim_busy_waits(ctx3):
    ex().claim(ctx3, "t1", "emu", "next")
    assert ex().claim(ctx3, "t2", "emu", "next") == (False, "t1")
    t = task_json(ctx3.fdir, "t2")
    assert t["status"] == "waiting_external" and t["status_reason"] == "Waiting for emu, used by t1"
    assert t["exclusive_wait"] == {"name": "emu", "mode": "next"}
    wait = [e for e in events(ctx3.fdir, "t2") if e["type"] == "exclusive_wait"]
    assert wait[0]["name"] == "emu" and wait[0]["holder"] == "t1"


def test_claim_twice_queues_once(ctx3):
    ex().claim(ctx3, "t1", "emu", "next")
    ex().claim(ctx3, "t2", "emu", "next")
    ex().claim(ctx3, "t2", "emu", "next")
    assert queue(ctx3) == ["t2"]
    assert len([e for e in events(ctx3.fdir, "t2") if e["type"] == "exclusive_wait"]) == 1


def test_claim_again_keeps_wait_status(ctx3):
    from factory import state
    ex().claim(ctx3, "t1", "emu", "next")
    ex().claim(ctx3, "t2", "emu", "next")
    state.update(ctx3, "t2", lambda t: t.__setitem__("status_since", "2000-01-01T00:00:00Z"))
    ex().claim(ctx3, "t2", "emu", "next")
    t = task_json(ctx3.fdir, "t2")
    assert t["status_since"] == "2000-01-01T00:00:00Z" and t["status"] == "waiting_external"


def test_release_hands_over_in_order(ctx3):
    for tid in ("t1", "t2", "t3"):
        ex().claim(ctx3, tid, "emu", "next")
    assert ex().release(ctx3, "t1", "emu") is True
    assert ex().read(ctx3, "emu")["holder"] == "t2"
    assert queue(ctx3) == ["t3"]
    t2 = task_json(ctx3.fdir, "t2")
    assert t2["status"] == "active" and "exclusive_wait" not in t2
    assert sent(ctx3) == ["`emu` is yours now. Run `factory next`."]
    start = [e for e in events(ctx3.fdir, "t2") if e["type"] == "exclusive_start"]
    assert start[0]["name"] == "emu" and start[0]["mode"] == "next"


def test_release_by_non_holder_is_false(ctx3):
    ex().claim(ctx3, "t1", "emu", "next")
    assert ex().release(ctx3, "t2", "emu") is False
    assert ex().read(ctx3, "emu")["holder"] == "t1"


def test_release_logs_event(ctx3):
    ex().claim(ctx3, "t1", "emu", "next")
    ex().release(ctx3, "t1", "emu", event="exclusive_release")
    rel = [e for e in events(ctx3.fdir, "t1") if e["type"] == "exclusive_release"]
    assert rel[0]["name"] == "emu"


def test_paused_waiter_is_skipped_and_keeps_place(ctx3):
    from factory import session
    for tid in ("t1", "t2", "t3"):
        ex().claim(ctx3, tid, "emu", "next")
    session.pause(ctx3, "t2")
    ex().release(ctx3, "t1", "emu")
    assert ex().read(ctx3, "emu")["holder"] == "t3"
    assert queue(ctx3) == ["t2"]


def test_free_resource_not_blocked_by_paused_waiter(ctx3):
    from factory import session
    ex().claim(ctx3, "t1", "emu", "next")
    ex().claim(ctx3, "t2", "emu", "next")
    session.pause(ctx3, "t2")
    ex().release(ctx3, "t1", "emu")
    assert ex().read(ctx3, "emu")["holder"] is None
    assert ex().claim(ctx3, "t3", "emu", "next") == (True, None)
    assert queue(ctx3) == ["t2"]


def test_acquire_mode_message(ctx3):
    from factory import state
    ex().claim(ctx3, "t1", "emu", "next")
    state.update(ctx3, "t2", lambda t: t.update(started=t["position"], exclusive_released="emu"))
    ex().claim(ctx3, "t2", "emu", "acquire")
    ex().release(ctx3, "t1", "emu")
    assert sent(ctx3) == ["`emu` is yours now. Continue the step."]
    assert "exclusive_released" not in task_json(ctx3.fdir, "t2")


def test_force_release_logs_both(ctx3):
    from factory import engine
    ex().claim(ctx3, "t1", "emu", "next")
    engine.block(ctx3, "t1", "stuck")
    ex().claim(ctx3, "t2", "emu", "next")
    assert ex().force_release(ctx3, "emu", by="t2") == "t1"
    for tid in ("t1", "t2"):
        forced = [e for e in events(ctx3.fdir, tid) if e["type"] == "exclusive_forced"]
        assert forced[0]["name"] == "emu" and forced[0]["holder"] == "t1" and forced[0]["by"] == "t2"
    assert task_json(ctx3.fdir, "t1")["exclusive_released"] == "emu"
    assert ex().read(ctx3, "emu")["holder"] == "t2"


def test_force_release_free_resource_errors(ctx3):
    from factory.errors import FactoryError
    with pytest.raises(FactoryError, match="`emu` is free."):
        ex().force_release(ctx3, "emu")


def test_names_do_not_block_each_other(ctx3):
    assert ex().claim(ctx3, "t1", "emu", "next") == (True, None)
    assert ex().claim(ctx3, "t2", "printer", "next") == (True, None)


def test_recheck_drops_missing_holder(ctx3):
    ex().claim(ctx3, "t1", "emu", "next")
    ex().claim(ctx3, "t2", "emu", "next")
    shutil.rmtree(ctx3.fdir / "tasks" / "t1")
    assert ex().recheck(ctx3) == ["emu"]
    assert ex().read(ctx3, "emu")["holder"] == "t2"


def test_recheck_keeps_paused_holder(ctx3):
    from factory import session
    ex().claim(ctx3, "t1", "emu", "next")
    ex().claim(ctx3, "t2", "emu", "next")
    session.pause(ctx3, "t1")
    assert ex().recheck(ctx3) == []
    assert ex().read(ctx3, "emu")["holder"] == "t1"


def test_handover_drops_invalid_waiters(ctx3):
    ex().claim(ctx3, "t1", "emu", "next")
    ex().claim(ctx3, "t2", "emu", "next")
    ex().claim(ctx3, "t3", "emu", "next")
    move(ctx3, "t2", "plain")
    ex().release(ctx3, "t1", "emu")
    assert ex().read(ctx3, "emu")["holder"] == "t3"
    assert queue(ctx3) == []


def test_step_name(ctx3):
    from factory import state
    assert ex().step_name(ctx3, state.load(ctx3, "t1")) == "emu"
    move(ctx3, "t1", "plain")
    assert ex().step_name(ctx3, state.load(ctx3, "t1")) is None
    move(ctx3, "t1", None)
    assert ex().step_name(ctx3, state.load(ctx3, "t1")) is None


def test_sync_keeps_same_name(ctx3):
    ex().claim(ctx3, "t1", "emu", "next")
    move(ctx3, "t1", "emu-check")
    ex().sync(ctx3, "t1")
    assert ex().read(ctx3, "emu")["holder"] == "t1"


def test_sync_releases_other_name(ctx3):
    ex().claim(ctx3, "t1", "emu", "next")
    ex().claim(ctx3, "t2", "emu", "next")
    ex().claim(ctx3, "t3", "emu", "next")
    move(ctx3, "t1", "plain")
    move(ctx3, "t3", "plain")
    ex().sync(ctx3, "t3")
    assert queue(ctx3) == ["t2"]
    assert "exclusive_wait" not in task_json(ctx3.fdir, "t3")
    ex().sync(ctx3, "t1")
    assert ex().read(ctx3, "emu")["holder"] == "t2"


def test_forget_leaves_everything(ctx3):
    ex().claim(ctx3, "t1", "emu", "next")
    ex().claim(ctx3, "t2", "emu", "next")
    ex().claim(ctx3, "t3", "emu", "next")
    ex().forget(ctx3, "t2")
    assert queue(ctx3) == ["t3"]
    ex().forget(ctx3, "t1")
    assert ex().read(ctx3, "emu")["holder"] == "t3"


def test_task_info(ctx3):
    from factory import state
    ex().claim(ctx3, "t1", "emu", "next")
    ex().claim(ctx3, "t2", "emu", "next")
    assert ex().task_info(ctx3, state.load(ctx3, "t1")) == {
        "name": "emu", "holder": "t1", "holds": True, "waiting": False, "released": False, "paused": False}
    assert ex().task_info(ctx3, state.load(ctx3, "t2")) == {
        "name": "emu", "holder": "t1", "holds": False, "waiting": True, "released": False, "paused": False}
    move(ctx3, "t3", "plain")
    assert ex().task_info(ctx3, state.load(ctx3, "t3")) is None


def test_holder_text(ctx3):
    from factory import state
    ex().claim(ctx3, "t1", "emu", "next")
    ex().claim(ctx3, "t2", "emu", "next")
    assert ex().holder_text(ctx3, state.load(ctx3, "t1")) == "Exclusive: `emu`, held by this task"
    assert ex().holder_text(ctx3, state.load(ctx3, "t2")) == "Exclusive: waiting for `emu`, used by `t1`"
    assert ex().holder_text(ctx3, state.load(ctx3, "t3")) is None
    state.update(ctx3, "t3", lambda t: t.update(started=t["position"], exclusive_released="emu"))
    assert ex().holder_text(ctx3, state.load(ctx3, "t3")) == "Exclusive: `emu`, released"


def test_status_rows(ctx3):
    ex().claim(ctx3, "t1", "emu", "next")
    ex().claim(ctx3, "t2", "emu", "acquire")
    ex().claim(ctx3, "t3", "disk", "next")
    rows = {r["name"]: r for r in ex().status_rows(ctx3)}
    assert set(rows) == {"emu", "disk"}
    assert rows["emu"]["holder"] == "t1" and rows["emu"]["holder_status"] == "active"
    q = rows["emu"]["queue"]
    assert [(e["task"], e["status"], e["mode"]) for e in q] == [("t2", "waiting_external", "acquire")]
    assert q[0]["since"]
    assert rows["disk"]["holder"] == "t3"


def test_delivery_error_keeps_handover(ctx3):
    from conftest import fake_config
    ex().claim(ctx3, "t1", "emu", "next")
    ex().claim(ctx3, "t2", "emu", "next")
    fake_config(ctx3.fdir, send_prompt_fails=True)
    ex().release(ctx3, "t1", "emu")
    assert ex().read(ctx3, "emu")["holder"] == "t2"
    assert any(e["type"] == "prompt_failed" for e in events(ctx3.fdir, "t2"))
