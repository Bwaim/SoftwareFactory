import pytest

from conftest import events, fake_calls, fake_config, task_from_pipeline, task_json, write_pipeline
from factory import engine, repo, session
from factory.errors import FactoryError
from serverutil import info, request
from test_herdr_adapter import herdr_env

QUESTION_MESSAGE = "The session shows a question box. Answer it in the task tab: factory terminal focus t1."
CLAUDE_QUESTION_SCREEN = "Approve the result?\n❯ 1. Approve\n  2. Request changes\nEnter to select · ↑/↓ to navigate · Esc to cancel\n"


@pytest.fixture
def ctx(inited):
    return repo.load_ctx(cwd=inited.repo)


@pytest.fixture
def awaiting(inited):
    write_pipeline(inited.fdir, {"id": "ap", "steps": ["user-validation"]})
    task_from_pipeline(inited, "ap", terminal_handle={"agent": "t1"})
    inited.factory("next", "--task", "t1")
    assert task_json(inited.fdir, "t1")["status"] == "awaiting_approval"
    return inited


def sent_texts(fdir):
    return [c["text"] for c in fake_calls(fdir) if c["op"] == "send_prompt"]


def test_send_prompt_refused_when_question_box_shows(awaiting):
    fake_config(awaiting.fdir, question_box=True)
    r = awaiting.factory("terminal", "send-prompt", "t1", "Hello", check=False)
    assert r.returncode == 1 and QUESTION_MESSAGE in r.stderr
    assert sent_texts(awaiting.fdir) == []
    t = task_json(awaiting.fdir, "t1")
    assert t["status"] == "awaiting_approval" and not t["approval"].get("approved")
    last = events(awaiting.fdir, "t1")[-1]
    assert last["type"] == "prompt_failed" and last["text"] == "Hello" and last["reason"] == QUESTION_MESSAGE
    assert "prompt_sent" not in [e["type"] for e in events(awaiting.fdir, "t1")]


def test_send_prompt_failure_logs_prompt_failed(awaiting):
    fake_config(awaiting.fdir, capabilities=["state"])
    r = awaiting.factory("terminal", "send-prompt", "t1", "Hello", check=False)
    assert r.returncode == 1
    last = events(awaiting.fdir, "t1")[-1]
    assert last["type"] == "prompt_failed" and "send-prompt" in last["reason"]


def test_approve_send_refused_when_question_box_shows(awaiting, ctx):
    fake_config(awaiting.fdir, question_box=True)
    message, delivery_error = engine.approve(ctx, "t1", send=True)
    assert "Approved" in message and delivery_error == QUESTION_MESSAGE
    assert sent_texts(awaiting.fdir) == []
    assert events(awaiting.fdir, "t1")[-1]["type"] == "prompt_failed"


def test_request_changes_send_refused_when_question_box_shows(awaiting, ctx):
    fake_config(awaiting.fdir, question_box=True)
    _, delivery_error = engine.request_changes(ctx, "t1", "Add tests", send=True)
    assert delivery_error == QUESTION_MESSAGE and sent_texts(awaiting.fdir) == []


def test_approve_send_logs_prompt_sent(awaiting, ctx):
    _, delivery_error = engine.approve(ctx, "t1", send=True)
    assert delivery_error is None
    last = events(awaiting.fdir, "t1")[-1]
    assert last["type"] == "prompt_sent" and last["text"].startswith("The user approved.")


def test_dashboard_approve_shows_question_box_error(awaiting):
    fake_config(awaiting.fdir, question_box=True)
    awaiting.factory("dashboard")
    i = info(awaiting.fdir)
    try:
        status, body = request(i, "POST", "/api/tasks/t1/approve", {})
        assert status == 200 and body["delivery_error"] == QUESTION_MESSAGE
    finally:
        awaiting.factory("server", "stop", check=False)


def test_prompts_ask_in_plain_text(ctx, awaiting):
    assert session.ASK_IN_TEXT in session.first_prompt({"id": "t1", "worktree": "/w"})
    assert "never with the AskUserQuestion tool" in session.ASK_IN_TEXT
    out = awaiting.factory("block", "--task", "t1", "Which database?", check=False)
    assert session.ASK_IN_TEXT in out.stdout


def test_herdr_detects_question_box_on_screen(herdr_env, monkeypatch):
    adapter, calls = herdr_env
    monkeypatch.setenv("FAKE_HERDR_PRESENT", "1")
    handle = {"agent": "t1", "tab": "w9:t1"}
    monkeypatch.setenv("FAKE_HERDR_SCREEN", CLAUDE_QUESTION_SCREEN)
    assert adapter.question_box(handle) is True
    assert ["agent", "read", "t1", "--source", "visible"] in calls()
    monkeypatch.setenv("FAKE_HERDR_SCREEN", "Enter to select\n" + "output line\n" * 20 + "> \n")
    assert adapter.question_box(handle) is False
