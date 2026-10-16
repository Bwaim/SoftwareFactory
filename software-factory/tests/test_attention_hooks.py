import json
import os
import subprocess
import sys
import time

import pytest

from conftest import BIN, events, fake_calls, fake_config, make_task, task_json
from factory import repo, state


@pytest.fixture
def att(inited):
    ctx = repo.load_ctx(cwd=inited.repo)
    make_task(ctx, "t1", session_id="sid-1", terminal_handle={"agent": "t1"})
    return inited


def hook(inited, kind, payload, delay="60", stdin=None, cwd=None):
    text = stdin if stdin is not None else json.dumps(payload)
    return inited.factory("hook", kind, input=text, cwd=cwd, check=False, env={"FACTORY_ATTENTION_DELAY": delay})


def notifies(inited):
    return [c["text"] for c in fake_calls(inited.fdir) if c["op"] == "notify"]


def wait_until(check, timeout):
    end = time.time() + timeout
    while time.time() < end:
        if check():
            return True
        time.sleep(0.1)
    raise AssertionError("condition not met in time")


def silent(r):
    assert r.returncode == 0 and r.stdout == "" and r.stderr == ""


def test_stop_on_active_sets_attention_and_notifies(att):
    r = hook(att, "stop", {"session_id": "sid-1", "last_assistant_message": "Which API?\nA or B"})
    silent(r)
    a = task_json(att.fdir, "t1")["attention"]
    assert a["message"] == "Which API?\nA or B"
    assert notifies(att) == ["t1 may wait for you: Which API?"]
    logged = [e for e in events(att.fdir, "t1") if e["type"] == "attention"]
    assert logged and logged[0]["message"] == "Which API?"


def test_stop_without_message_notifies_short_text(att):
    silent(hook(att, "stop", {"session_id": "sid-1"}))
    assert task_json(att.fdir, "t1")["attention"]["message"] is None
    assert notifies(att) == ["t1 may wait for you."]


def test_stop_uses_display_name(att):
    ctx = repo.load_ctx(cwd=att.repo)
    state.update(ctx, "t1", lambda t: t.__setitem__("display_name", "Login fix"))
    silent(hook(att, "stop", {"session_id": "sid-1", "last_assistant_message": "Done?"}))
    assert notifies(att) == ["Login fix may wait for you: Done?"]


def test_message_is_trimmed(att):
    text = "\n".join(f"line {i}" for i in range(30))
    silent(hook(att, "stop", {"session_id": "sid-1", "last_assistant_message": text}))
    message = task_json(att.fdir, "t1")["attention"]["message"]
    assert message.splitlines() == [f"line {i}" for i in range(18, 30)]
    silent(hook(att, "stop", {"session_id": "sid-1", "last_assistant_message": "x" * 5000}))
    assert task_json(att.fdir, "t1")["attention"]["message"] == "x" * 2000


@pytest.mark.parametrize("status", ["blocked", "waiting_external", "awaiting_approval", "paused", "finished"])
def test_stop_other_status_changes_nothing(att, status):
    ctx = repo.load_ctx(cwd=att.repo)
    state.update(ctx, "t1", lambda t: t.__setitem__("status", status))
    before = task_json(att.fdir, "t1")
    silent(hook(att, "stop", {"session_id": "sid-1", "last_assistant_message": "Q?"}))
    assert task_json(att.fdir, "t1") == before
    assert notifies(att) == []


def test_stop_with_background_tasks_changes_nothing(att):
    before = task_json(att.fdir, "t1")
    silent(hook(att, "stop", {"session_id": "sid-1", "last_assistant_message": "Q?", "background_tasks": [{"id": "x"}]}))
    assert task_json(att.fdir, "t1") == before
    assert notifies(att) == []


def test_stop_with_empty_background_tasks_sets_attention(att):
    silent(hook(att, "stop", {"session_id": "sid-1", "last_assistant_message": "Q?", "background_tasks": []}))
    assert task_json(att.fdir, "t1")["attention"]["message"] == "Q?"


def test_prompt_clears(att):
    silent(hook(att, "stop", {"session_id": "sid-1", "last_assistant_message": "Q?"}))
    silent(hook(att, "prompt", {"session_id": "sid-1", "prompt": "A"}))
    assert "attention" not in task_json(att.fdir, "t1")
    cleared = [e for e in events(att.fdir, "t1") if e["type"] == "attention_cleared"]
    assert [e["reason"] for e in cleared] == ["prompt"]
    silent(hook(att, "prompt", {"session_id": "sid-1", "prompt": "B"}))
    assert len([e for e in events(att.fdir, "t1") if e["type"] == "attention_cleared"]) == 1


def test_clear_returns_false_when_not_set(att):
    from factory import attention
    ctx = repo.load_ctx(cwd=att.repo)
    before = task_json(att.fdir, "t1")
    assert attention.clear(ctx, "t1", "status") is False
    assert task_json(att.fdir, "t1") == before
    state.update(ctx, "t1", lambda t: t.__setitem__("attention", {"at": "x", "message": None}))
    assert attention.clear(ctx, "t1", "status") is True
    assert [e["reason"] for e in events(att.fdir, "t1") if e["type"] == "attention_cleared"] == ["status"]


@pytest.mark.parametrize("stdin", ["", "not json", "[1, 2]", json.dumps({"session_id": "unknown"})])
@pytest.mark.parametrize("kind", ["stop", "prompt"])
def test_bad_input_is_silent(att, stdin, kind):
    before = task_json(att.fdir, "t1")
    silent(hook(att, kind, None, stdin=stdin))
    assert task_json(att.fdir, "t1") == before
    assert notifies(att) == []


def test_hook_outside_factory_is_silent(tmp_path, factory):
    for kind in ("stop", "prompt"):
        r = factory("hook", kind, input=json.dumps({"session_id": "sid-1"}), cwd=tmp_path, check=False)
        silent(r)


def test_hook_in_repo_without_factory_is_silent(factory, origin_repo):
    silent(factory("hook", "stop", input=json.dumps({"session_id": "sid-1"}), check=False))
    assert not (origin_repo / ".factory").exists()


def test_hook_other_data_version_is_silent(att):
    for v in ("1", "3"):
        r = att.factory("hook", "stop", input=json.dumps({"session_id": "sid-1", "last_assistant_message": "Q?"}), check=False, env={"FACTORY_DATA_VERSION": v})
        silent(r)
    assert "attention" not in task_json(att.fdir, "t1")


def test_hook_error_logs_hook_failed(att):
    (att.fdir / "fake_adapter_config.json").write_text("[1]")
    silent(hook(att, "stop", {"session_id": "sid-1", "last_assistant_message": "Q?"}))
    failed = [e for e in events(att.fdir, "t1") if e["type"] == "hook_failed"]
    assert len(failed) == 1 and failed[0]["hook"] == "stop" and failed[0]["error"]


def test_notify_later_bad_args_is_silent(att):
    for args in (["t1", "x"], ["BAD ID", "x"], ["nope", "x"]):
        r = att.factory("hook", "notify-later", *args, check=False, env={"FACTORY_ATTENTION_DELAY": "0"})
        silent(r)
    assert notifies(att) == []


def test_not_focused_notifies_at_once(att):
    fake_config(att.fdir, focused=False)
    silent(hook(att, "stop", {"session_id": "sid-1", "last_assistant_message": "Q?"}, delay="30"))
    assert notifies(att) == ["t1 may wait for you: Q?"]


def test_focused_uses_delay(att):
    fake_config(att.fdir, focused=True)
    start = time.time()
    silent(hook(att, "stop", {"session_id": "sid-1", "last_assistant_message": "Q?"}, delay="5"))
    assert time.time() - start < 3 and notifies(att) == []
    assert "attention" in task_json(att.fdir, "t1")
    wait_until(lambda: notifies(att) == ["t1 may wait for you: Q?"], timeout=15)


def test_focused_prompt_during_delay_no_notify(att):
    fake_config(att.fdir, focused=True)
    silent(hook(att, "stop", {"session_id": "sid-1", "last_assistant_message": "Q?"}, delay="1"))
    silent(hook(att, "prompt", {"session_id": "sid-1", "prompt": "A"}))
    time.sleep(2.5)
    assert notifies(att) == []


def test_no_handle_uses_delay(att):
    ctx = repo.load_ctx(cwd=att.repo)
    state.update(ctx, "t1", lambda t: t.__setitem__("terminal_handle", None))
    silent(hook(att, "stop", {"session_id": "sid-1", "last_assistant_message": "Q?"}, delay="1"))
    assert notifies(att) == []
    wait_until(lambda: notifies(att) == ["t1 may wait for you: Q?"], timeout=10)


def test_no_focus_capability_uses_delay(att):
    fake_config(att.fdir, capabilities=["notify"])
    silent(hook(att, "stop", {"session_id": "sid-1", "last_assistant_message": "Q?"}, delay="1"))
    silent(hook(att, "prompt", {"session_id": "sid-1", "prompt": "A"}))
    time.sleep(2.5)
    assert notifies(att) == []
    silent(hook(att, "stop", {"session_id": "sid-1", "last_assistant_message": "Again?"}, delay="1"))
    assert notifies(att) == []
    wait_until(lambda: notifies(att) == ["t1 may wait for you: Again?"], timeout=10)


def test_no_notify_capability_sets_attention_only(att):
    fake_config(att.fdir, capabilities=["focused"], focused=False)
    silent(hook(att, "stop", {"session_id": "sid-1", "last_assistant_message": "Q?"}, delay="1"))
    assert task_json(att.fdir, "t1")["attention"]["message"] == "Q?"
    time.sleep(2)
    assert fake_calls(att.fdir) == []


def test_attention_at_is_unique(att):
    fake_config(att.fdir, focused=True)
    silent(hook(att, "stop", {"session_id": "sid-1", "last_assistant_message": "First?"}, delay="1"))
    first = task_json(att.fdir, "t1")["attention"]["at"]
    silent(hook(att, "stop", {"session_id": "sid-1", "last_assistant_message": "Second?"}, delay="1"))
    second = task_json(att.fdir, "t1")["attention"]["at"]
    assert first != second
    wait_until(lambda: notifies(att) == ["t1 may wait for you: Second?"], timeout=10)
    time.sleep(1)
    assert notifies(att) == ["t1 may wait for you: Second?"]


def test_transcript_fallback(att, tmp_path):
    transcript = tmp_path / "t.jsonl"
    lines = [
        {"type": "user", "message": {"role": "user", "content": "hi"}},
        {"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": "Old"}]}},
        "not json",
        {"type": "assistant", "message": {"role": "assistant", "content": [{"type": "tool_use", "name": "x"}, {"type": "text", "text": "Pick one?\nA or B"}]}},
    ]
    transcript.write_text("\n".join(l if isinstance(l, str) else json.dumps(l) for l in lines) + "\n")
    silent(hook(att, "stop", {"session_id": "sid-1", "transcript_path": str(transcript)}))
    assert task_json(att.fdir, "t1")["attention"]["message"] == "Pick one?\nA or B"


def test_transcript_missing_gives_no_message(att, tmp_path):
    silent(hook(att, "stop", {"session_id": "sid-1", "transcript_path": str(tmp_path / "missing.jsonl")}))
    assert task_json(att.fdir, "t1")["attention"]["message"] is None


def test_last_message_unit(tmp_path):
    from factory import attention
    assert attention.last_message({"last_assistant_message": "A"}) == "A"
    assert attention.last_message({}) is None
    assert attention.last_message({"transcript_path": 5}) is None
    p = tmp_path / "t.jsonl"
    p.write_text(json.dumps({"type": "assistant", "message": {"content": "Plain"}}) + "\n")
    assert attention.last_message({"transcript_path": str(p)}) == "Plain"


def test_now_precise_has_microseconds():
    from factory import attention
    assert "." in attention.now_precise()


def test_archived_task_not_found(att):
    ctx = repo.load_ctx(cwd=att.repo)
    archive = att.fdir / "tasks" / "archive" / "t2"
    archive.mkdir(parents=True)
    (archive / "task.json").write_text(json.dumps({"id": "t2", "status": "active", "session_id": "sid-2"}))
    from factory import attention
    assert attention.find_task(ctx, "sid-2") is None
    assert attention.find_task(ctx, "sid-1")["id"] == "t1"


def test_bad_delay_falls_back_to_60(monkeypatch):
    from factory import attention
    monkeypatch.setenv("FACTORY_ATTENTION_DELAY", "soon")
    assert attention.read_delay() == 60.0
    monkeypatch.setenv("FACTORY_ATTENTION_DELAY", "2.5")
    assert attention.read_delay() == 2.5
