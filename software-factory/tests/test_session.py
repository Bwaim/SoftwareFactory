import pytest

from conftest import events, fake_calls, fake_config, make_task, task_json
from factory import repo, session
from factory.errors import FactoryError


@pytest.fixture
def live(inited):
    ctx = repo.load_ctx(cwd=inited.repo)
    make_task(ctx, tid="t1", worktree=str(inited.repo), terminal_handle={"agent": "t1"}, status="awaiting_approval", status_reason="check")
    return inited, ctx


def test_pause_saves_status_and_closes(live):
    inited, ctx = live
    inited.factory("pause", "t1")
    t = task_json(inited.fdir, "t1")
    assert t["status"] == "paused" and t["terminal_handle"] is None
    assert t["saved_status"] == {"status": "awaiting_approval", "reason": "check"}
    assert fake_calls(inited.fdir)[-1] == {"op": "close", "handle": {"agent": "t1"}}


def test_pause_wait_uses_wait_idle(live):
    inited, ctx = live
    inited.factory("pause", "t1", "--wait")
    ops = [c["op"] for c in fake_calls(inited.fdir)]
    assert ops == ["wait_idle", "close"]


def test_resume_restores_status_same_session(live):
    inited, ctx = live
    inited.factory("pause", "t1")
    inited.factory("resume", "t1")
    t = task_json(inited.fdir, "t1")
    assert t["status"] == "awaiting_approval" and t["terminal_handle"] == {"agent": "t1", "fake": True}
    call = fake_calls(inited.fdir)[-1]
    assert call["op"] == "start_session"
    assert call["args"][call["args"].index("--resume") + 1] == t["session_id"]
    assert "--session-id" not in call["args"]
    assert "The factory resumed this task" in call["prompt"]
    assert [e["type"] for e in events(inited.fdir, "t1")] == ["task_paused", "task_resumed"]


def test_resume_refused_when_session_runs(live):
    inited, ctx = live
    fake_config(inited.fdir, state="working")
    with pytest.raises(FactoryError, match="still running"):
        session.resume(ctx, "t1")


def test_deliver_to_gone_session_sends_one_prompt(live):
    inited, ctx = live
    fake_config(inited.fdir, state="gone")
    assert session.deliver(ctx, "t1", "The user approved.") == "resumed"
    calls = fake_calls(inited.fdir)
    assert [c["op"] for c in calls] == ["start_session"]
    assert calls[0]["prompt"].endswith("The user approved.")


def test_send_prompt_and_focus(live):
    inited, ctx = live
    inited.factory("terminal", "send-prompt", "t1", "Hello there")
    inited.factory("terminal", "focus", "t1")
    calls = fake_calls(inited.fdir)
    assert calls[-2] == {"op": "send_prompt", "handle": {"agent": "t1"}, "text": "Hello there"}
    assert calls[-1]["op"] == "focus"
    assert events(inited.fdir, "t1")[-1]["type"] == "prompt_sent"
    assert events(inited.fdir, "t1")[-1]["text"] == "Hello there"
    fake_config(inited.fdir, capabilities=["state"])
    r = inited.factory("terminal", "focus", "t1", check=False)
    assert r.returncode == 1 and "does not support focus" in r.stderr


def test_pause_all(live):
    inited, ctx = live
    make_task(ctx, tid="t2", terminal_handle={"agent": "t2"})
    make_task(ctx, tid="t3", status="finished")
    inited.factory("pause", "--all")
    assert [task_json(inited.fdir, t)["status"] for t in ("t1", "t2", "t3")] == ["paused", "paused", "finished"]
