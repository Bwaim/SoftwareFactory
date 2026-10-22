import threading
import time

import pytest

from conftest import fake_calls, hook, make_task, silent, task_from_pipeline, task_json, write_pipeline, write_step
from factory import delete, exclusive, fsio, repo, session, state
from factory.errors import FactoryError


def test_cancel_waits_for_running_check(inited):
    ctx = repo.load_ctx(cwd=inited.repo)
    make_task(ctx, "t1")
    held = threading.Event()

    def holder():
        with fsio.try_locked(state.task_dir(ctx, "t1") / "check") as got:
            assert got
            held.set()
            time.sleep(1.5)

    thread = threading.Thread(target=holder)
    thread.start()
    assert held.wait(10)
    began = time.monotonic()
    delete.cancel(ctx, "t1")
    elapsed = time.monotonic() - began
    thread.join()
    assert elapsed >= 1.0
    assert not (inited.fdir / "tasks" / "t1").exists()
    assert (inited.fdir / "tasks" / "archive" / "t1" / "task.json").exists()


@pytest.fixture
def emu(inited):
    write_step(inited.fdir, "emu", {"exclusive": "emu"})
    write_step(inited.fdir, "after", {})
    write_pipeline(inited.fdir, {"id": "e", "steps": ["emu", "after"]})
    for tid in ("t1", "t2"):
        task_from_pipeline(inited, "e", tid=tid, worktree=str(inited.repo), terminal_handle={"agent": tid})
    inited.factory("next", "--task", "t1")
    inited.factory("next", "--task", "t2")
    ctx = repo.load_ctx(cwd=inited.repo)
    for tid in ("t1", "t2"):
        state.update(ctx, tid, lambda t: t.__setitem__("worktree", None))
    assert exclusive.read(ctx, "emu")["holder"] == "t1"
    assert [q["task"] for q in exclusive.read(ctx, "emu")["queue"]] == ["t2"]
    return inited, ctx


def test_cancelled_holder_hands_resource_to_next(emu):
    inited, ctx = emu
    delete.cancel(ctx, "t1")
    assert exclusive.read(ctx, "emu")["holder"] == "t2"
    assert task_json(inited.fdir, "t2")["status"] == "active"


def test_cancelled_waiting_task_leaves_queue(emu):
    inited, ctx = emu
    delete.cancel(ctx, "t2")
    assert exclusive.read(ctx, "emu")["queue"] == []
    assert exclusive.read(ctx, "emu")["holder"] == "t1"


def test_stop_hook_and_poll_after_cancel_do_not_recreate(inited):
    ctx = repo.load_ctx(cwd=inited.repo)
    make_task(ctx, "t1", session_id="sid-1")
    delete.cancel(ctx, "t1")
    silent(hook(inited, "stop", {"session_id": "sid-1", "last_assistant_message": "hi"}))
    r = inited.factory("poll", "--task", "t1", check=False)
    assert r.returncode == 1 and "Unknown task" in r.stderr
    assert not (inited.fdir / "tasks" / "t1").exists()


def test_second_cancel_fails_cleanly(inited):
    ctx = repo.load_ctx(cwd=inited.repo)
    make_task(ctx, "t1")
    delete.cancel(ctx, "t1")
    with pytest.raises(FactoryError, match="Unknown task"):
        delete.cancel(ctx, "t1")
    assert not (inited.fdir / "tasks" / "t1").exists()


def test_resume_after_archive_closes_new_session(inited, monkeypatch):
    ctx = repo.load_ctx(cwd=inited.repo)
    make_task(ctx, "t1", worktree=str(inited.repo), status="paused",
              saved_status={"status": "active", "reason": None})
    real_update = state.update

    def archive_then_update(ctx, tid, fn):
        delete.archive(ctx, tid)
        return real_update(ctx, tid, fn)

    monkeypatch.setattr(session.state, "update", archive_then_update)
    with pytest.raises(FactoryError, match="Unknown task"):
        session.resume(ctx, "t1")
    calls = fake_calls(inited.fdir)
    assert [c["op"] for c in calls[-2:]] == ["start_session", "close"]
    assert calls[-1]["handle"]["agent"] == calls[-2]["herdr_name"]
    assert not (inited.fdir / "tasks" / "t1").exists()
