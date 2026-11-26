import base64
import http.client
import json
import sys
import threading
import time

import pytest

from conftest import SF, events, fake_config, make_task, task_json
from factory import pty_sessions, repo, task_attach
from factory.errors import FactoryError
from serverutil import api_path, info, request

PAGE = (SF / "lib" / "factory" / "web" / "dashboard.html").read_text()
LIVE = {"agent": "t1"}
ECHO = [sys.executable, "-c", (
    "import os, signal, sys\n"
    "signal.signal(signal.SIGWINCH, lambda *a: print('size', *os.get_terminal_size(), flush=True))\n"
    "print('ready', *os.get_terminal_size(), flush=True)\n"
    "for line in sys.stdin: print('got', line.strip(), flush=True)\n"
)]
WAIT_SECONDS = 5


def collect(stream, until):
    """Read stream lines on a thread until the decoded output contains `until`."""
    out = []
    done = threading.Event()

    def read():
        for raw in stream:
            msg = json.loads(raw)
            if "d" in msg:
                out.append(base64.b64decode(msg["d"]).decode(errors="replace"))
            if msg.get("closed"):
                out.append("<closed>")
            if until in "".join(out) or msg.get("closed"):
                done.set()
                return

    threading.Thread(target=read, daemon=True).start()
    done.wait(WAIT_SECONDS)
    return "".join(out)


@pytest.fixture
def registry():
    reg = pty_sessions.Registry()
    yield reg
    reg.close_all()


@pytest.fixture
def ctx(inited):
    return repo.load_ctx(cwd=inited.repo)


@pytest.fixture
def clean_registry():
    yield
    pty_sessions.REGISTRY.close_all()


def test_session_runs_the_program_at_the_given_size(registry):
    session, started = registry.open("k", ECHO, 100, 30)
    assert started and "ready 100 30" in collect(session.stream(), "ready")


def test_session_input_reaches_the_program(registry):
    session, _ = registry.open("k", ECHO, 100, 30)
    stream = session.stream()
    session.write("hello\r")
    assert "got hello" in collect(stream, "got hello")


def test_resize_reaches_the_program_as_a_window_change(registry):
    session, _ = registry.open("k", ECHO, 100, 30)
    stream = session.stream()
    collect(stream, "ready")
    session.resize(80, 24)
    assert "size 80 24" in collect(stream, "size")


def test_a_new_viewer_gets_the_earlier_output(registry):
    session, _ = registry.open("k", ECHO, 100, 30)
    collect(session.stream(), "ready")
    assert "ready 100 30" in collect(session.stream(), "ready")


def test_open_reuses_the_live_session_and_resizes_it(registry):
    first, _ = registry.open("k", ECHO, 100, 30)
    again, started = registry.open("k", ["false"], 90, 20)
    assert again is first and started is False


def test_stream_ends_when_the_program_exits(registry):
    session, _ = registry.open("k", [sys.executable, "-c", "print('bye')"], 80, 24)
    assert collect(session.stream(), "<closed>").endswith("<closed>")


def test_a_missing_program_says_so_in_the_terminal(registry):
    session, _ = registry.open("k", ["no-such-program-for-the-factory"], 80, 24)
    assert "Could not start no-such-program-for-the-factory" in collect(session.stream(), "<closed>")


def test_close_stops_the_program(registry):
    session, _ = registry.open("k", ECHO, 80, 24)
    registry.close("k")
    assert session.poll() is not None
    with pytest.raises(FactoryError, match="not open"):
        registry.get("k")


def test_reap_stops_sessions_nobody_watches(registry, monkeypatch):
    session, _ = registry.open("k", ECHO, 80, 24)
    registry.reap(now=time.time() + pty_sessions.IDLE_CLOSE_SECONDS + 1)
    assert session.poll() is not None and registry.sessions == {}


def test_reap_keeps_watched_sessions(registry):
    session, _ = registry.open("k", ECHO, 80, 24)
    stream = session.stream()
    collect(stream, "ready")
    registry.reap(now=time.time() + pty_sessions.IDLE_CLOSE_SECONDS + 1)
    assert registry.get("k") is session
    stream.close()


@pytest.mark.parametrize("cols, rows", [(10, 24), (80, 2), (600, 24), ("80", 24), (None, None)])
def test_bad_sizes_are_refused(registry, cols, rows):
    with pytest.raises(FactoryError, match="terminal size"):
        registry.open("k", ECHO, cols, rows)


@pytest.mark.parametrize("data", ["", None, "x" * (pty_sessions.INPUT_MAX + 1)])
def test_bad_input_is_refused(registry, data):
    session, _ = registry.open("k", ECHO, 80, 24)
    with pytest.raises(FactoryError, match="Send `data`"):
        session.write(data)


def test_too_many_terminals_are_refused(registry, monkeypatch):
    monkeypatch.setattr(pty_sessions, "MAX_SESSIONS", 1)
    registry.open("a", ECHO, 80, 24)
    with pytest.raises(FactoryError, match="Too many open terminals"):
        registry.open("b", ECHO, 80, 24)


def test_open_terminal_needs_a_live_session_and_the_capability(ctx, inited, clean_registry):
    fake_config(inited.fdir, capabilities=["focus"])
    make_task(ctx, tid="t1")
    make_task(ctx, tid="t2", terminal_handle=LIVE)
    with pytest.raises(FactoryError, match="no live session"):
        task_attach.open_terminal(ctx, "t1", 80, 24)
    with pytest.raises(FactoryError, match="cannot attach"):
        task_attach.open_terminal(ctx, "t2", 80, 24)


def test_open_terminal_runs_the_adapter_command_and_logs_once(ctx, inited, clean_registry):
    fake_config(inited.fdir, capabilities=["attach"], attach_command=ECHO)
    make_task(ctx, tid="t1", terminal_handle=LIVE)
    assert task_attach.open_terminal(ctx, "t1", 80, 24) == {"ok": True, "started": True}
    assert task_attach.open_terminal(ctx, "t1", 80, 24) == {"ok": True, "started": False}
    assert [e["type"] for e in events(inited.fdir, "t1")].count("terminal_attached") == 1


def test_a_restarted_terminal_is_not_logged_again(ctx, inited, clean_registry):
    fake_config(inited.fdir, capabilities=["attach"], attach_command=ECHO)
    make_task(ctx, tid="t1", terminal_handle=LIVE)
    task_attach.open_terminal(ctx, "t1", 80, 24)
    task_attach.close(ctx, "t1")
    assert task_attach.open_terminal(ctx, "t1", 80, 24)["started"] is True
    assert [e["type"] for e in events(inited.fdir, "t1")].count("terminal_attached") == 1


def test_typing_in_the_live_terminal_clears_attention(ctx, inited, clean_registry):
    fake_config(inited.fdir, capabilities=["attach"], attach_command=ECHO)
    make_task(ctx, tid="t1", terminal_handle=LIVE, attention={"at": "2026-11-19T10:00:00+00:00", "message": "Which one?"})
    task_attach.open_terminal(ctx, "t1", 80, 24)
    task_attach.write(ctx, "t1", "1\r")
    assert "attention" not in task_json(inited.fdir, "t1")


def test_attach_routes_stream_the_terminal(inited, clean_registry):
    inited.factory("dashboard")
    try:
        i = info(inited.fdir)
        ctx = repo.load_ctx(cwd=inited.repo)
        fake_config(inited.fdir, capabilities=["attach"], attach_command=ECHO)
        make_task(ctx, tid="t1", terminal_handle=LIVE)
        assert request(i, "POST", "/api/tasks/t1/attach", {"cols": 90, "rows": 25}) == (200, {"ok": True, "started": True})
        conn = http.client.HTTPConnection("127.0.0.1", i["port"], timeout=WAIT_SECONDS)
        conn.request("GET", api_path(i, "/api/tasks/t1/attach/stream"), headers={"Host": f"127.0.0.1:{i['port']}", "X-Factory-Token": i["token"]})
        res = conn.getresponse()
        assert res.status == 200 and res.getheader("Content-Type") == "application/x-ndjson"
        assert request(i, "POST", "/api/tasks/t1/attach/input", {"data": "hi\r"})[0] == 200
        assert request(i, "POST", "/api/tasks/t1/attach/resize", {"cols": 70, "rows": 20})[0] == 200
        assert "got hi" in collect(iter(res.readline, b""), "size 70 20")
        conn.close()
        assert request(i, "POST", "/api/tasks/t1/attach/close", {}) == (200, {"ok": True})
        status, error = request(i, "POST", "/api/tasks/t1/attach/input", {"data": "x"})
        assert status == 400 and "not open" in error["error"]
    finally:
        inited.factory("server", "stop", check=False)


def test_server_serves_the_vendored_terminal_files(inited):
    inited.factory("dashboard")
    try:
        i = info(inited.fdir)
        conn = http.client.HTTPConnection("127.0.0.1", i["port"], timeout=WAIT_SECONDS)
        for path, kind in [("/static/xterm.js", "text/javascript"), ("/static/xterm.css", "text/css"), ("/static/addon-fit.js", "text/javascript"), ("/static/themes.css", "text/css")]:
            conn.request("GET", path, headers={"Host": f"127.0.0.1:{i['port']}"})
            res = conn.getresponse()
            body = res.read()
            assert res.status == 200 and res.getheader("Content-Type").startswith(kind) and len(body) > 1000
    finally:
        inited.factory("server", "stop", check=False)


def test_dashboard_page_has_the_live_terminal():
    for text in ('id="live-host"', "/static/xterm.js", "/attach/stream`", "/attach/input`", "/attach/resize`", "toggleTask("):
        assert text in PAGE
    assert 'class="keys"' not in PAGE and "data-key=" not in PAGE


def test_dashboard_page_has_the_terminal_tab_and_resize_handles():
    for text in ('id="term-tab"', 'aria-controls="detail-term"', 'id="resize-detail"', 'id="resize-term"', 'role="separator"', "factory.detailWidth", "factory.terminalWidth", "--detail-w", "--term-w"):
        assert text in PAGE
    assert "term-toggle" not in PAGE


def test_dashboard_page_has_no_snapshot_mode():
    for text in ("/screen`", "/type`", "Snapshot", "ansiNodes", "term-text", 'data-mode="live"', "factory.terminalMode"):
        assert text not in PAGE


def test_dashboard_page_keeps_a_selected_task_and_two_panel_tabs():
    for text in ('id="pcol-details"', 'id="pcol-term"', 'id="details-tab"', 'aria-controls="detail-main"', 'id="term-tab"', 'id="term-task"',
                 "factory.selectedTask.", "factory.details", "function firstTask", "function ensureSelection", 'data-both="1"', "33.3vw", "16.65vw"):
        assert text in PAGE
    for text in ('id="detail-tabs"', 'id="detail-rail"', "setTerminalOpen", "openDetail(", "NARROW_PANEL_PX"):
        assert text not in PAGE


def test_dashboard_page_has_a_workspace_column_tab_open_by_default():
    for text in ('id="lcol-ws"', 'id="ws-tab"', 'aria-controls="sidebar"', 'loadFlag("factory.workspaces", true)', "function renderWorkspacePanel"):
        assert text in PAGE


def test_panel_columns_close_only_from_their_tabs():
    for text in ('id="details-close"', 'id="term-close"', "pclose"):
        assert text not in PAGE


def test_browser_tab_title_is_captn_factory():
    assert "<title>CAPTN Factory</title>" in PAGE and 'PAGE_TITLE = "CAPTN Factory"' in PAGE


def test_board_and_panels_scroll_on_their_own():
    assert "height: 100vh; overflow: hidden;" in PAGE
    assert "#main, #sidebar, #detail-main, #live-host .xterm-viewport { overscroll-behavior: contain; }" in PAGE
    assert "main.scrollTop = top;" in PAGE
    for text in ("fitPanel", "window.scrollTo", "position: sticky; top: 0; height: 100vh"):
        assert text not in PAGE


def test_open_column_tabs_have_a_purple_title():
    assert '.rail-tab[aria-expanded="true"] { box-shadow: inset 3px 0 0 var(--accent); color: var(--tab-on);' in PAGE
    assert "--tab-on: #C9A2E6;" in PAGE and "--tab-on: #673888;" in PAGE


def test_column_titles_share_one_style():
    assert "#sidebar h2, #detail h2, #detail-term .thead h3 { margin: 0; font-size: 20px; font-weight: 800; line-height: 1.2; color: var(--muted-strong); }" in PAGE


def test_workspace_column_is_resizable_with_the_same_default():
    for text in ('id="resize-ws"', 'aria-label="Resize the workspaces"', '"factory.workspacesWidth"', "var(--ws-w, 220px)", 'side: "left"', "function grownBy"):
        assert text in PAGE


def test_selecting_a_task_keeps_its_board_column_in_view():
    assert "function revealTaskColumn" in PAGE and "revealTaskColumn(id);" in PAGE and "REVEAL_MARGIN" in PAGE
