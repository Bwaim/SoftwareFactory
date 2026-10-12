import json
import os
import stat

import pytest

from conftest import SF
from factory import repo
from factory.adapters.base import AdapterError
from factory.adapters.herdr import HerdrAdapter


@pytest.fixture
def herdr_env(tmp_path, monkeypatch, origin_repo):
    bindir = tmp_path / "bin"
    bindir.mkdir()
    exe = bindir / "herdr"
    exe.write_text(f"#!/bin/sh\nexec python3 {SF / 'tests' / 'fake_herdr.py'} \"$@\"\n")
    exe.chmod(exe.stat().st_mode | stat.S_IEXEC)
    log = tmp_path / "herdr.log"
    monkeypatch.setenv("PATH", f"{bindir}:{os.environ['PATH']}")
    monkeypatch.setenv("FAKE_HERDR_LOG", str(log))
    monkeypatch.setenv("FAKE_HERDR_MAIN", str(origin_repo))
    monkeypatch.setenv("HERDR_ENV", "1")
    adapter = HerdrAdapter(repo.load_ctx(cwd=origin_repo))
    return adapter, lambda: [json.loads(line) for line in log.read_text().splitlines()]


def closed(calls):
    return [c[2] for c in calls if c[:2] == ["workspace", "close"]]


def test_start_in_worktree(herdr_env, origin_repo):
    adapter, calls = herdr_env
    prompt = 'Run `factory next`. Say "hi" $HOME'
    handle = adapter.start_session("t1", origin_repo / "wt", prompt, ["--name", "t1", "--settings", "/a b/c.json"], True)
    assert handle == {"agent": "t1", "workspace": "w9", "tab": "w9:t1"}
    c = [call for call in calls() if call[:2] not in (["workspace", "list"], ["agent", "get"])]
    assert c[0][:2] == ["worktree", "open"] and "--no-focus" in c[0] and "--trust-repository" not in c[0]
    assert c[1][:3] == ["agent", "start", "t1"] and c[1][c[1].index("--pane") + 1] == "w9:p1"
    assert c[1][c[1].index("--") + 1:] == ["--name", "t1", "--settings", "/a b/c.json"]
    assert c[2] == ["agent", "prompt", "t1", prompt]


def test_extra_workspace_recorded_and_closed(herdr_env, origin_repo, monkeypatch):
    adapter, calls = herdr_env
    monkeypatch.setenv("FAKE_HERDR_EXTRA_WS", "1")
    handle = adapter.start_session("t1", origin_repo / "wt", "p", [], True)
    assert handle == {"agent": "t1", "workspace": "w9", "tab": "w9:t1", "extra_workspaces": ["w8"]}
    adapter.close(handle)
    assert closed(calls()) == ["w9", "w8"]


def test_extra_workspace_with_live_agent_left_open(herdr_env, origin_repo, monkeypatch):
    adapter, calls = herdr_env
    monkeypatch.setenv("FAKE_HERDR_EXTRA_WS", "1")
    monkeypatch.setenv("FAKE_HERDR_W8_STATUS", "idle")
    handle = adapter.start_session("t1", origin_repo / "wt", "p", [], True)
    adapter.close(handle)
    assert closed(calls()) == ["w9"]


def test_workspace_with_other_tab_only_our_tab_closed(herdr_env, origin_repo, monkeypatch):
    adapter, calls = herdr_env
    handle = adapter.start_session("t1", origin_repo / "wt", "p", [], True)
    monkeypatch.setenv("FAKE_HERDR_OTHER_TAB", "1")
    adapter.close(handle)
    assert closed(calls()) == []
    assert calls()[-1] == ["tab", "close", "w9:t1"]


def test_already_open_worktree_workspace_not_owned(herdr_env, origin_repo, monkeypatch):
    adapter, calls = herdr_env
    monkeypatch.setenv("FAKE_HERDR_ALREADY_OPEN", "1")
    handle = adapter.start_session("t1", origin_repo / "wt", "p", [], True)
    assert handle == {"agent": "t1", "tab": "w9:t2"}
    tab_create = next(c for c in calls() if c[:2] == ["tab", "create"])
    assert tab_create[tab_create.index("--workspace") + 1] == "w9"
    assert tab_create[tab_create.index("--cwd") + 1] == str(origin_repo / "wt")
    agent_start = next(c for c in calls() if c[:2] == ["agent", "start"])
    assert agent_start[agent_start.index("--pane") + 1] == "w9:p2"
    adapter.close(handle)
    assert closed(calls()) == []
    assert calls()[-1] == ["tab", "close", "w9:t2"]


def test_exception_after_open_closes_what_was_opened(herdr_env, origin_repo, monkeypatch):
    adapter, calls = herdr_env

    def boom(before, handle):
        raise RuntimeError("boom")

    monkeypatch.setattr(adapter, "find_extra_workspaces", boom)
    with pytest.raises(AdapterError, match="boom"):
        adapter.start_session("t1", origin_repo / "wt", "p", [], True)
    assert closed(calls()) == ["w9"]


def test_preexisting_workspace_never_closed(herdr_env, origin_repo, monkeypatch):
    adapter, calls = herdr_env
    monkeypatch.setenv("FAKE_HERDR_EXISTING_WS", "1")
    handle = adapter.start_session("t1", origin_repo / "wt", "p", [], True)
    assert "extra_workspaces" not in handle
    adapter.close(handle)
    assert closed(calls()) == ["w9"]


def test_main_repo_uses_existing_workspace(herdr_env, origin_repo, monkeypatch):
    adapter, calls = herdr_env
    monkeypatch.setenv("FAKE_HERDR_EXISTING_WS", "1")
    handle = adapter.start_session("t2", origin_repo, "p", [], False)
    assert handle == {"agent": "t2", "tab": "w5:t2"}
    tab_create = next(c for c in calls() if c[:2] == ["tab", "create"])
    assert tab_create[tab_create.index("--workspace") + 1] == "w5"
    adapter.close(handle)
    assert calls()[-1] == ["tab", "close", "w5:t2"]
    assert closed(calls()) == []


def test_main_repo_creates_workspace_when_missing(herdr_env, origin_repo):
    adapter, calls = herdr_env
    handle = adapter.start_session("t2", origin_repo, "p", [], False)
    assert handle == {"agent": "t2", "workspace": "w7", "tab": "w7:t1", "created_workspace": True}
    create = next(c for c in calls() if c[:2] == ["workspace", "create"])
    assert "--no-focus" in create and create[create.index("--cwd") + 1] == str(origin_repo)
    assert not any(c[:2] == ["tab", "create"] for c in calls())
    adapter.close(handle)
    assert closed(calls()) == ["w7"]


def test_trust_dialog_reported_and_cleaned(herdr_env, origin_repo, monkeypatch):
    adapter, calls = herdr_env
    monkeypatch.setenv("FAKE_HERDR_MODE", "trust")
    with pytest.raises(AdapterError, match="trust the folder .*wt.*Open Claude once in the main repository"):
        adapter.start_session("t3", origin_repo / "wt", "p", [], True)
    assert closed(calls()) == ["w9"]


def test_state_gone(herdr_env, monkeypatch):
    adapter, _ = herdr_env
    monkeypatch.setenv("FAKE_HERDR_PRESENT", "1")
    assert adapter.state({"agent": "t1", "tab": "w9:t1"}) == "idle"
    monkeypatch.setenv("FAKE_HERDR_MODE", "gone")
    assert adapter.state({"agent": "t1", "tab": "w9:t1"}) == "gone"


def test_check_outside_herdr(herdr_env, monkeypatch):
    adapter, _ = herdr_env
    monkeypatch.setenv("HERDR_ENV", "0")
    ok, message = adapter.check()
    assert not ok and "Herdr" in message


@pytest.mark.parametrize("output", ["not json", "{}", '{"result": {}}'])
def test_unreadable_tab_list_closes_only_our_tab(herdr_env, origin_repo, monkeypatch, output):
    adapter, calls = herdr_env
    handle = adapter.start_session("t1", origin_repo / "wt", "p", [], True)
    monkeypatch.setenv("FAKE_HERDR_TAB_LIST_OUTPUT", output)
    adapter.close(handle)
    assert closed(calls()) == []
    assert calls()[-1] == ["tab", "close", "w9:t1"]


def test_missing_key_after_open_still_cleans_up(herdr_env, origin_repo, monkeypatch):
    adapter, calls = herdr_env
    monkeypatch.setenv("FAKE_HERDR_NO_TAB_ID", "1")
    with pytest.raises(AdapterError):
        adapter.start_session("t1", origin_repo / "wt", "p", [], True)
    assert closed(calls()) == ["w9"]


def test_taken_agent_name_refused_and_untouched(herdr_env, origin_repo, monkeypatch):
    adapter, calls = herdr_env
    monkeypatch.setenv("FAKE_HERDR_TAKEN", "t1")
    with pytest.raises(AdapterError, match="A Herdr agent named t1 already exists. Close it or launch with another --id."):
        adapter.start_session("t1", origin_repo / "wt", "p", [], True)
    verbs = [c[:2] for c in calls()]
    assert ["agent", "start"] not in verbs
    assert not any(c[:2] in (["agent", "send-keys"], ["workspace", "close"], ["tab", "close"]) for c in calls())


def test_failed_start_does_not_send_keys_to_agent(herdr_env, origin_repo, monkeypatch):
    adapter, calls = herdr_env
    monkeypatch.setenv("FAKE_HERDR_MODE", "trust")
    with pytest.raises(AdapterError):
        adapter.start_session("t3", origin_repo / "wt", "p", [], True)
    assert not any(c[:2] == ["agent", "send-keys"] for c in calls())


def test_actions_refused_when_agent_in_other_tab(herdr_env, monkeypatch):
    adapter, calls = herdr_env
    monkeypatch.setenv("FAKE_HERDR_PRESENT", "1")
    monkeypatch.setenv("FAKE_HERDR_AGENT_TAB", "w3:t4")
    handle = {"agent": "t1", "tab": "w9:t1"}
    for action in (
        lambda: adapter.send_prompt(handle, "hi"),
        lambda: adapter.focus(handle),
        lambda: adapter.wait_idle(handle, 5),
    ):
        with pytest.raises(AdapterError, match="does not belong"):
            action()
    adapter.stop_agent(handle)
    assert not any(c[:2] in (["agent", "prompt"], ["agent", "focus"], ["agent", "wait"], ["agent", "send-keys"]) for c in calls())


def test_state_gone_when_agent_in_other_tab(herdr_env, monkeypatch):
    adapter, _ = herdr_env
    monkeypatch.setenv("FAKE_HERDR_PRESENT", "1")
    monkeypatch.setenv("FAKE_HERDR_AGENT_TAB", "w3:t4")
    assert adapter.state({"agent": "t1", "tab": "w9:t1"}) == "gone"


def test_actions_allowed_in_own_tab_or_workspace(herdr_env, monkeypatch):
    adapter, calls = herdr_env
    monkeypatch.setenv("FAKE_HERDR_PRESENT", "1")
    adapter.send_prompt({"agent": "t1", "tab": "w9:t1"}, "hi")
    monkeypatch.setenv("FAKE_HERDR_AGENT_TAB", "w9:t4")
    adapter.focus({"agent": "t1", "tab": "w9:t1", "workspace": "w9"})
    assert ["agent", "prompt", "t1", "hi"] in calls() and ["agent", "focus", "t1"] in calls()
