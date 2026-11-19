import pytest

from conftest import SF, events, fake_calls, fake_config, make_task, task_json
from factory import repo, task_terminal
from factory.errors import FactoryError
from serverutil import info, request

PAGE = (SF / "lib" / "factory" / "web" / "dashboard.html").read_text()
LIVE = {"agent": "t1"}


@pytest.fixture
def ctx(inited):
    return repo.load_ctx(cwd=inited.repo)


@pytest.fixture
def served(inited):
    inited.factory("dashboard")
    yield inited, info(inited.fdir)
    inited.factory("server", "stop", check=False)


def test_screen_without_a_session_says_why(ctx):
    make_task(ctx, tid="t1")
    assert task_terminal.screen(ctx, "t1") == {"available": False, "reason": "The task has no live session.", "can_type": False}


def test_screen_returns_the_text_and_whether_typing_works(ctx, inited):
    fake_config(inited.fdir, capabilities=["read_screen", "type_input"], screen="\x1b[32mok\x1b[0m")
    make_task(ctx, tid="t1", terminal_handle=LIVE)
    assert task_terminal.screen(ctx, "t1") == {"available": True, "text": "\x1b[32mok\x1b[0m", "can_type": True}


def test_screen_without_typing_capability_is_read_only(ctx, inited):
    fake_config(inited.fdir, capabilities=["read_screen"], screen="hi")
    make_task(ctx, tid="t1", terminal_handle=LIVE)
    assert task_terminal.screen(ctx, "t1")["can_type"] is False


def test_screen_says_when_the_adapter_cannot_read(ctx, inited):
    fake_config(inited.fdir, capabilities=["focus"])
    make_task(ctx, tid="t1", terminal_handle=LIVE)
    assert task_terminal.screen(ctx, "t1")["reason"] == "The fake terminal adapter cannot read the session."


def test_screen_reports_a_failed_read(ctx, inited):
    fake_config(inited.fdir, capabilities=["read_screen"], read_screen_fails=True)
    make_task(ctx, tid="t1", terminal_handle=LIVE)
    assert task_terminal.screen(ctx, "t1")["reason"] == "The fake adapter failed to read the screen."


def test_send_input_types_text_then_presses_keys(ctx, inited):
    fake_config(inited.fdir, capabilities=["type_input"])
    make_task(ctx, tid="t1", terminal_handle=LIVE)
    assert task_terminal.send_input(ctx, "t1", "yes please", ["enter"]) == {"ok": True}
    calls = [(c["op"], c.get("text"), c.get("keys")) for c in fake_calls(inited.fdir)]
    assert calls == [("send_text", "yes please", None), ("send_keys", None, ["enter"])]


def test_send_input_logs_the_keys_but_not_the_text(ctx, inited):
    fake_config(inited.fdir, capabilities=["type_input"])
    make_task(ctx, tid="t1", terminal_handle=LIVE)
    task_terminal.send_input(ctx, "t1", "secret", ["enter"])
    last = events(inited.fdir, "t1")[-1]
    assert last["type"] == "terminal_input" and last["chars"] == 6 and last["keys"] == ["enter"]
    assert "secret" not in str(last)


def test_send_input_clears_attention(ctx, inited):
    fake_config(inited.fdir, capabilities=["type_input"])
    make_task(ctx, tid="t1", terminal_handle=LIVE, attention={"at": "2026-11-19T10:00:00+00:00", "message": "Which one?"})
    task_terminal.send_input(ctx, "t1", "", ["down"])
    assert "attention" not in task_json(inited.fdir, "t1")
    last = events(inited.fdir, "t1")[-1]
    assert last["type"] == "attention_cleared" and last["reason"] == "input"


@pytest.mark.parametrize("text, keys, message", [
    ("", [], "Nothing to send."),
    ("a\nb", [], "control characters"),
    ("x" * (task_terminal.TEXT_MAX + 1), [], "longer than"),
    ("", ["f13"], "Unknown keys: f13."),
    (None, [], "as a string"),
])
def test_send_input_refuses_bad_input(ctx, inited, text, keys, message):
    fake_config(inited.fdir, capabilities=["type_input"])
    make_task(ctx, tid="t1", terminal_handle=LIVE)
    with pytest.raises(FactoryError, match=message):
        task_terminal.send_input(ctx, "t1", text, keys)
    assert fake_calls(inited.fdir) == []


def test_send_input_needs_a_live_session_and_the_capability(ctx, inited):
    fake_config(inited.fdir, capabilities=["read_screen"])
    make_task(ctx, tid="t1")
    make_task(ctx, tid="t2", terminal_handle=LIVE)
    with pytest.raises(FactoryError, match="no live session"):
        task_terminal.send_input(ctx, "t1", "hi", [])
    with pytest.raises(FactoryError, match="cannot type"):
        task_terminal.send_input(ctx, "t2", "hi", [])


def test_send_input_logs_a_failed_typing(ctx, inited):
    fake_config(inited.fdir, capabilities=["type_input"], type_fails=True)
    make_task(ctx, tid="t1", terminal_handle=LIVE)
    with pytest.raises(FactoryError, match="failed to type"):
        task_terminal.send_input(ctx, "t1", "hi", ["enter"])
    last = events(inited.fdir, "t1")[-1]
    assert last["type"] == "terminal_input_failed" and last["reason"] == "The fake adapter failed to type."


def test_screen_and_type_routes(served):
    inited, i = served
    ctx = repo.load_ctx(cwd=inited.repo)
    fake_config(inited.fdir, capabilities=["read_screen", "type_input"], screen="hello")
    make_task(ctx, tid="t1", terminal_handle=LIVE)
    assert request(i, "GET", "/api/tasks/t1/screen") == (200, {"available": True, "text": "hello", "can_type": True})
    assert request(i, "POST", "/api/tasks/t1/type", {"text": "y", "keys": ["enter"]}) == (200, {"ok": True})
    status, error = request(i, "POST", "/api/tasks/t1/type", {"keys": ["f13"]})
    assert status == 400 and "Unknown keys" in error["error"]


def test_dashboard_page_has_the_terminal_view():
    for text in ('id="detail-term"', "/screen`", "/type`", 'data-key="ctrl+c"', "ansiNodes", "SCREEN_REFRESH_MS", "factory.terminal", "Typed in the terminal"):
        assert text in PAGE
