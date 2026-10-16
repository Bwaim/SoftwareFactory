import os
import stat

import pytest

from conftest import fake_calls, make_task
from factory import config, repo, session


@pytest.fixture
def focus_env(inited, monkeypatch, tmp_path):
    for key, value in inited.factory.env.items():
        monkeypatch.setenv(key, value)
    bindir = tmp_path / "bin"
    bindir.mkdir()
    log = tmp_path / "open.log"
    stub = bindir / "open"
    stub.write_text(f"#!/bin/sh\necho \"$@\" >> {log}\nexit ${{OPEN_EXIT:-0}}\n")
    stub.chmod(stub.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("PATH", f"{bindir}:{os.environ['PATH']}")
    monkeypatch.setattr(session, "is_macos", lambda: True)
    ctx = repo.load_ctx(cwd=inited.repo)
    make_task(ctx, tid="t1", worktree=str(inited.repo), terminal_handle={"agent": "t1"})
    return inited, ctx, log


def opened(log):
    return log.read_text().splitlines() if log.exists() else []


def test_open_runs_after_the_herdr_focus(focus_env):
    inited, ctx, log = focus_env
    config.set_value(ctx, "terminal", "terminal_app", "Ghostty")
    assert session.focus(ctx, "t1") == {"front": "ok", "app": "Ghostty"}
    assert fake_calls(inited.fdir)[-1]["op"] == "focus"
    assert opened(log) == ["-a Ghostty"]


def test_empty_app_skips_open(focus_env):
    inited, ctx, log = focus_env
    config.set_value(ctx, "terminal", "terminal_app", "")
    assert session.focus(ctx, "t1") == {"front": "off"}
    assert opened(log) == []
    assert fake_calls(inited.fdir)[-1]["op"] == "focus"


def test_missing_app_asks(focus_env):
    _, ctx, log = focus_env
    assert session.focus(ctx, "t1") == {"front": "ask"}
    assert opened(log) == []


def test_failed_open_keeps_the_focus(focus_env, monkeypatch):
    inited, ctx, log = focus_env
    config.set_value(ctx, "terminal", "terminal_app", "Nope")
    monkeypatch.setenv("OPEN_EXIT", "1")
    result = session.focus(ctx, "t1")
    assert result["front"] == "failed" and result["app"] == "Nope"
    assert fake_calls(inited.fdir)[-1]["op"] == "focus"


def test_not_macos_reports_failure(focus_env, monkeypatch):
    _, ctx, log = focus_env
    config.set_value(ctx, "terminal", "terminal_app", "Ghostty")
    monkeypatch.setattr(session, "is_macos", lambda: False)
    assert session.focus(ctx, "t1")["front"] == "failed"
    assert opened(log) == []
