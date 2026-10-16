import json

import pytest

from conftest import events, hook, make_task, silent, task_json
from factory import repo, state
from serverutil import info, request

from test_dashboard_page import PAGE


def stop(inited, message="Q?"):
    silent(hook(inited, "stop", {"session_id": "sid-1", "last_assistant_message": message}))


def cleared(inited):
    return [e for e in events(inited.fdir, "t1") if e["type"] == "attention_cleared"]


@pytest.fixture
def att_server(att):
    att.factory("dashboard")
    yield att, info(att.fdir)
    att.factory("server", "stop", check=False)


def test_block_clears_attention(att):
    stop(att)
    att.factory("block", "--task", "t1", "q")
    assert "attention" not in task_json(att.fdir, "t1")
    assert [e["reason"] for e in cleared(att)] == ["status"]


def test_dashboard_send_prompt_clears(att_server):
    inited, i = att_server
    stop(inited)
    assert request(i, "POST", "/api/tasks/t1/send-prompt", {"text": "hi"})[0] == 200
    assert "attention" not in task_json(inited.fdir, "t1")
    assert [e["reason"] for e in cleared(inited)] == ["prompt"]


def test_failed_send_keeps_attention(att):
    from factory import session
    ctx = repo.load_ctx(cwd=att.repo)
    stop(att)
    state.update(ctx, "t1", lambda t: t.__setitem__("terminal_handle", None))
    with pytest.raises(Exception):
        session.send_prompt(ctx, "t1", "hi")
    assert "attention" in task_json(att.fdir, "t1")
    assert cleared(att) == []


def test_tasks_sort_attention_with_blocked(att):
    ctx = repo.load_ctx(cwd=att.repo)
    make_task(ctx, "t2", status="awaiting_approval", created_at="2026-01-01T00:00:00+00:00")
    make_task(ctx, "t3", created_at="2026-01-01T00:00:00+00:00")
    state.update(ctx, "t1", lambda t: t.__setitem__("created_at", "2026-02-01T00:00:00+00:00"))
    stop(att)
    assert [r["id"] for r in att.factory.json("tasks")] == ["t1", "t2", "t3"]


def test_row_has_attention(att):
    assert att.factory.json("tasks")[0]["attention"] is None
    stop(att)
    assert att.factory.json("tasks")[0]["attention"]["message"] == "Q?"


def test_text_list_says_may_wait(att):
    stop(att, "Q?\nmore")
    assert "may wait for you: Q?" in att.factory("tasks").stdout
    att.factory("block", "--task", "t1", "q")
    assert "may wait for you" not in att.factory("tasks").stdout


def test_text_list_without_message(att):
    silent(hook(att, "stop", {"session_id": "sid-1"}))
    assert "may wait for you" in att.factory("tasks").stdout


def test_cleared_logged_once(att):
    stop(att)
    att.factory("block", "--task", "t1", "q")
    att.factory("unblock", "--task", "t1")
    assert len(cleared(att)) == 1


def test_dashboard_page_has_attention():
    assert "May wait for you" in PAGE and "t.attention" in PAGE and "pre-wrap" in PAGE
