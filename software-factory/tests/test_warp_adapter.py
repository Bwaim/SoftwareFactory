import json
import os
import stat

import pytest

from conftest import SF
from factory import attention, repo, session_activity
from factory.adapters import warp
from factory.adapters.base import AdapterError
from factory.adapters.warp import WarpAdapter

SID = "0c9692af-40ed-4797-82ef-59fde82c86ca"
ARGS = ["--name", "t1", "--session-id", SID, "--add-dir", "/a b/artifacts"]


@pytest.fixture
def warp_env(tmp_path, monkeypatch, origin_repo):
    bindir = tmp_path / "bin"
    bindir.mkdir()
    for tool in ("tmux", "open", "osascript"):
        exe = bindir / tool
        exe.write_text(f"#!/bin/sh\nexec python3 {SF / 'tests' / 'fake_tmux.py'} {tool} \"$@\"\n")
        exe.chmod(exe.stat().st_mode | stat.S_IEXEC)
    log = tmp_path / "tmux.log"
    monkeypatch.setenv("PATH", f"{bindir}:{os.environ['PATH']}")
    monkeypatch.setenv("FAKE_TMUX_LOG", str(log))
    monkeypatch.setenv("FACTORY_WARP_TAB_CONFIGS", str(tmp_path / "tab_configs"))
    monkeypatch.setattr(warp, "START_WAIT_SECONDS", 0.3)
    monkeypatch.setattr(warp, "START_POLL_SECONDS", 0.05)
    monkeypatch.setattr(warp, "PASTE_SETTLE_SECONDS", 0)
    monkeypatch.setattr(warp, "WAIT_POLL_SECONDS", 0.05)
    adapter = WarpAdapter(repo.load_ctx(cwd=origin_repo))
    calls = lambda: [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []
    return adapter, calls, tmp_path / "tab_configs"


def tmux_calls(calls, command):
    return [c[3:] for c in calls() if c[0] == "tmux" and c[3] == command]


def test_start_runs_claude_in_tmux_and_opens_a_warp_tab(warp_env, origin_repo):
    adapter, calls, configs = warp_env
    prompt = 'Run `factory next`. Say "hi"\nthen $HOME'
    handle = adapter.start_session("T1 task", origin_repo / "wt", prompt, ARGS)
    assert handle == {"agent": "t1-task", "session_id": SID, "tab_config": "captn-t1-task"}
    new = tmux_calls(calls, "new-session")[0]
    assert new[new.index("-s") + 1] == "t1-task" and new[new.index("-c") + 1] == str(origin_repo / "wt")
    assert new[new.index("claude") + 1:] == [*ARGS, "--", prompt]
    text = (configs / "captn-t1-task.toml").read_text()
    assert 'title = "t1-task"' in text and f'directory = "{origin_repo / "wt"}"' in text
    assert "exec " in text and "-L captn attach-session -t =t1-task" in text
    assert ["open", "warp://tab_config/captn-t1-task"] in calls()


def test_start_returns_as_soon_as_the_first_prompt_hook_fired(warp_env, origin_repo, monkeypatch):
    adapter, calls, _ = warp_env
    monkeypatch.setattr(warp, "START_WAIT_SECONDS", 30)
    session_activity.record(adapter.ctx, SID, "prompt")
    adapter.start_session("t1", origin_repo, "p", ARGS)
    assert len(tmux_calls(calls, "capture-pane")) == 1


def test_start_fails_on_the_trust_question_and_cleans_up(warp_env, origin_repo, monkeypatch):
    adapter, calls, configs = warp_env
    monkeypatch.setenv("FAKE_TMUX_SCREEN", "Is this a project you created or one you trust?\n")
    with pytest.raises(AdapterError, match="trust the folder"):
        adapter.start_session("t1", origin_repo, "p", ARGS)
    assert tmux_calls(calls, "kill-session") and not adapter.exists({"agent": "t1"})
    assert not any(c[0] == "open" for c in calls()) and not (configs / "captn-t1.toml").exists()


def test_start_fails_when_claude_exits(warp_env, origin_repo, monkeypatch):
    adapter, _, _ = warp_env
    monkeypatch.setenv("FAKE_TMUX_EXITS", "1")
    with pytest.raises(AdapterError, match="exited right after it started"):
        adapter.start_session("t1", origin_repo, "p", ARGS)


def test_start_refuses_an_existing_session(warp_env, origin_repo):
    adapter, _, _ = warp_env
    adapter.start_session("t1", origin_repo, "p", ARGS)
    with pytest.raises(AdapterError, match="already exists"):
        adapter.start_session("t1", origin_repo, "p", ARGS)


def test_send_prompt_pastes_then_presses_enter(warp_env, origin_repo):
    adapter, calls, _ = warp_env
    handle = adapter.start_session("t1", origin_repo, "p", ARGS)
    adapter.send_prompt(handle, "line one\nline two")
    tmux = [c[3:] for c in calls() if c[0] == "tmux" and c[3] in ("load-buffer", "paste-buffer", "send-keys")]
    assert tmux[0][-1] == {"stdin": "line one\nline two"}
    assert tmux[1][:2] == ["paste-buffer", "-p"] and tmux[1][-1] == "=t1"
    assert tmux[2] == ["send-keys", "-t", "=t1", "Enter"]


def test_calls_on_a_gone_session_fail(warp_env):
    adapter, _, _ = warp_env
    handle = {"agent": "gone", "session_id": SID}
    for call in (lambda: adapter.send_prompt(handle, "x"), lambda: adapter.focus(handle), lambda: adapter.attach_command(handle)):
        with pytest.raises(AdapterError, match="is gone"):
            call()
    assert adapter.state(handle) == "gone"


def test_state_follows_the_claude_hooks(warp_env, inited):
    _, _, _ = warp_env
    adapter = WarpAdapter(repo.load_ctx(cwd=inited.repo))
    handle = adapter.start_session("t1", inited.repo, "p", ARGS)
    assert adapter.state(handle) == "unknown"
    attention.run_hook("prompt", json.dumps({"session_id": SID}), str(inited.repo))
    assert adapter.state(handle) == "working"
    attention.run_hook("stop", json.dumps({"session_id": SID}), str(inited.repo))
    assert adapter.state(handle) == "idle"
    adapter.wait_idle(handle, 1)


def test_wait_idle_times_out_while_working(warp_env, origin_repo):
    adapter, _, _ = warp_env
    handle = adapter.start_session("t1", origin_repo, "p", ARGS)
    session_activity.record(adapter.ctx, SID, "prompt")
    with pytest.raises(AdapterError, match="did not become idle"):
        adapter.wait_idle(handle, 0.1)


def test_activity_ignores_unsafe_session_ids(warp_env):
    adapter, _, _ = warp_env
    session_activity.record(adapter.ctx, "../../evil", "stop")
    assert session_activity.read(adapter.ctx, "../../evil") is None
    assert not (adapter.ctx.fdir / "session-activity").exists()


def test_question_box_reads_the_screen(warp_env, origin_repo, monkeypatch):
    adapter, _, _ = warp_env
    handle = adapter.start_session("t1", origin_repo, "p", ARGS)
    assert adapter.question_box(handle) is False
    monkeypatch.setenv("FAKE_TMUX_SCREEN", "Pick one\n❯ 1. Yes\n  2. No\nEnter to select · ↑/↓ to navigate · Esc to cancel\n")
    assert adapter.question_box(handle) is True


def test_focus_brings_warp_to_front_when_a_tab_is_attached(warp_env, origin_repo, monkeypatch):
    adapter, calls, _ = warp_env
    handle = adapter.start_session("t1", origin_repo, "p", ARGS)
    monkeypatch.setenv("FAKE_TMUX_CLIENTS", "/dev/ttys004: t1 [200x50]\n")
    adapter.focus(handle)
    assert calls()[-1] == ["open", "-a", "Warp"]


def test_focus_reopens_the_tab_when_the_user_closed_it(warp_env, origin_repo):
    adapter, calls, configs = warp_env
    handle = adapter.start_session("t1", origin_repo, "p", ARGS)
    (configs / "captn-t1.toml").unlink()
    adapter.focus(handle)
    assert calls()[-1] == ["open", "warp://tab_config/captn-t1"] and (configs / "captn-t1.toml").exists()


def test_attach_command_uses_the_captn_socket(warp_env, origin_repo):
    adapter, _, _ = warp_env
    handle = adapter.start_session("t1", origin_repo, "p", ARGS)
    argv = adapter.attach_command(handle)
    assert argv[:3] == ["env", "-u", "TMUX"] and argv[4:] == ["-L", "captn", "attach-session", "-t", "=t1"]


def test_tmux_runs_without_the_calling_claude_session_variables(monkeypatch):
    monkeypatch.setenv("CLAUDECODE", "1")
    monkeypatch.setenv("CLAUDE_CODE_ENTRYPOINT", "cli")
    monkeypatch.setenv("TMUX", "/tmp/x,1,0")
    env = warp.clean_env()
    assert "CLAUDECODE" not in env and "CLAUDE_CODE_ENTRYPOINT" not in env and "TMUX" not in env and env["PATH"]


def test_rename_renames_the_tmux_session(warp_env, origin_repo):
    adapter, _, _ = warp_env
    handle = adapter.start_session("t1", origin_repo, "p", ARGS)
    new, problems = adapter.rename(handle, "ht-12")
    assert new["agent"] == "ht-12" and problems == [] and adapter.exists(new) and not adapter.exists(handle)


def test_close_stops_claude_and_removes_the_tab_config(warp_env, origin_repo):
    adapter, calls, configs = warp_env
    handle = adapter.start_session("t1", origin_repo, "p", ARGS)
    session_activity.record(adapter.ctx, SID, "stop")
    assert adapter.close(handle) == []
    assert tmux_calls(calls, "send-keys")[-1] == ["send-keys", "-t", "=t1", "C-c", "C-c"]
    assert not adapter.exists(handle) and not (configs / "captn-t1.toml").exists()
    assert session_activity.read(adapter.ctx, SID) is None
    assert adapter.close(handle) == []


def test_notify_passes_the_text_as_an_argument(warp_env):
    adapter, calls, _ = warp_env
    adapter.notify('Task "t1" is blocked')
    call = calls()[-1]
    assert call[0] == "osascript" and call[-1] == 'Task "t1" is blocked'


def test_check_needs_tmux(warp_env, monkeypatch):
    adapter, _, _ = warp_env
    monkeypatch.setattr(warp.sys, "platform", "darwin")
    assert adapter.check() == (True, "Warp and tmux are available.")
    monkeypatch.setattr(WarpAdapter, "tmux_path", lambda self: None)
    ok, message = adapter.check()
    assert not ok and "brew install tmux" in message


def test_focus_does_not_ask_for_the_terminal_app(warp_env):
    assert WarpAdapter.front_app == "Warp" and "focused" not in WarpAdapter(None).capabilities()


def test_install_choice_is_the_default_terminal(origin_repo, monkeypatch, tmp_path):
    from factory import adapters
    monkeypatch.delenv("FACTORY_TERMINAL", raising=False)
    monkeypatch.setenv("FACTORY_HOME", str(tmp_path / "home"))
    ctx = repo.load_ctx(cwd=origin_repo)
    assert adapters.terminal_name(ctx) == "herdr"
    (tmp_path / "home").mkdir()
    (tmp_path / "home" / "terminal").write_text("warp\n")
    assert adapters.terminal_name(ctx) == "warp"
    monkeypatch.setenv("FACTORY_TERMINAL", "fake")
    assert adapters.terminal_name(ctx) == "fake"
