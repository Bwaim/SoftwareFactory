import json
import os
import stat

import pytest
import yaml

from conftest import SF, events, fake_calls, fake_config, make_task, task_json, write_pipeline, write_step
from factory import engine, launch, rename, repo


@pytest.fixture
def tp(inited):
    write_step(inited.fdir, "w", {})
    write_pipeline(inited.fdir, {"id": "tp", "inputs": {"ticket": {"description": "Jira ticket"}}, "steps": ["w"]})
    return inited


def launched_id(inited, ticket, description="Fix the list"):
    return inited.factory.json("launch", "tp", "--description", description, "--input", f"ticket={ticket}")["id"]


@pytest.mark.parametrize("value, key", [
    ("HT-4549", "ht-4549"),
    ("https://x.atlassian.net/browse/HT-4549", "ht-4549"),
    ("HT-4549 Fix the list", "ht-4549"),
    ("none yet", None),
    ("", None),
    (None, None),
])
def test_ticket_key(value, key):
    assert launch.ticket_key(value) == key


def test_long_key_is_cut():
    assert len(launch.ticket_key("ABCDEFGHIJKLMNOPQRSTUVWXYZ-1234567")) <= launch.ID_BASE_MAX


def test_launch_ids_from_ticket(tp):
    assert launched_id(tp, "HT-4549") == "ht-4549"
    assert launched_id(tp, "HT-4549") == "ht-4549-2"
    assert launched_id(tp, "https://x.atlassian.net/browse/HT-77") == "ht-77"


def test_launch_without_key_uses_the_slug(tp):
    assert launched_id(tp, "none yet") == "fix-the-list"


def test_dry_run_shows_the_id(tp):
    out = tp.factory("launch", "tp", "--description", "Fix", "--input", "ticket=HT-9", "--dry-run").stdout
    assert "Task id: ht-9" in out


def ticket_task(inited, tid="fix-the-list", **fields):
    ctx = repo.load_ctx(cwd=inited.repo)
    make_task(ctx, tid=tid, worktree=str(inited.repo), terminal_handle={"agent": tid, "fake": True}, **fields)
    return ctx, tid


def set_ticket(inited, tid, value, check=True):
    return inited.factory("state", "set", "ticket", value, "--task", tid, check=check)


def test_state_set_ticket_renames_and_keeps_the_id(tp):
    ctx, tid = ticket_task(tp)
    r = set_ticket(tp, tid, "HT-4549")
    assert r.returncode == 0
    task = task_json(tp.fdir, tid)
    assert task["id"] == tid and task["worktree"] == str(tp.repo)
    assert task["display_name"] == "ht-4549" and task["claude_rename_pending"] == "ht-4549"
    assert task["terminal_handle"]["agent"] == "ht-4549"
    assert [c for c in fake_calls(tp.fdir) if c["op"] == "rename"][-1]["name"] == "ht-4549"
    assert any(e["type"] == "task_renamed" for e in events(tp.fdir, tid))
    assert (tp.fdir / "tasks" / tid).exists()


def test_old_value_without_key_still_renames(tp):
    ctx, tid = ticket_task(tp, state={"ticket": "none yet"})
    set_ticket(tp, tid, "HT-4549")
    assert task_json(tp.fdir, tid)["display_name"] == "ht-4549"


def test_second_ticket_does_not_rename_again(tp):
    ctx, tid = ticket_task(tp)
    set_ticket(tp, tid, "HT-4549")
    set_ticket(tp, tid, "HT-1")
    assert task_json(tp.fdir, tid)["display_name"] == "ht-4549"
    assert len([c for c in fake_calls(tp.fdir) if c["op"] == "rename"]) == 1


def test_display_name_is_unique(tp):
    ticket_task(tp, tid="ht-4549")
    ctx, tid = ticket_task(tp, tid="other")
    set_ticket(tp, tid, "HT-4549")
    assert task_json(tp.fdir, tid)["display_name"] == "ht-4549-2"


def test_working_session_gets_rename_later(tp, monkeypatch):
    for key, value in tp.factory.env.items():
        monkeypatch.setenv(key, value)
    ctx, tid = ticket_task(tp)
    fake_config(tp.fdir, states={"ht-4549": "working"})
    set_ticket(tp, tid, "HT-4549")
    assert not [c for c in fake_calls(tp.fdir) if c["op"] == "send_prompt"]
    assert rename.apply_pending(ctx, task_json(tp.fdir, tid)) is False
    assert task_json(tp.fdir, tid)["claude_rename_pending"] == "ht-4549"
    fake_config(tp.fdir, states={"ht-4549": "idle"})
    assert rename.apply_pending(ctx, task_json(tp.fdir, tid)) is True
    assert rename.apply_pending(ctx, task_json(tp.fdir, tid)) is False
    prompts = [c["text"] for c in fake_calls(tp.fdir) if c["op"] == "send_prompt"]
    assert prompts == ["/rename ht-4549"]
    assert "claude_rename_pending" not in task_json(tp.fdir, tid)


def test_question_box_blocks_the_live_rename(tp, monkeypatch):
    for key, value in tp.factory.env.items():
        monkeypatch.setenv(key, value)
    ctx, tid = ticket_task(tp)
    set_ticket(tp, tid, "HT-4549")
    fake_config(tp.fdir, question_box=True)
    assert rename.apply_pending(ctx, task_json(tp.fdir, tid)) is False
    assert task_json(tp.fdir, tid)["claude_rename_pending"] == "ht-4549"


def test_resume_applies_the_name(tp):
    ctx, tid = ticket_task(tp)
    fake_config(tp.fdir, states={"ht-4549": "working"})
    set_ticket(tp, tid, "HT-4549")
    tp.factory("pause", tid)
    tp.factory("resume", tid)
    start = [c for c in fake_calls(tp.fdir) if c["op"] == "start_session"][-1]
    assert start["name"] == "ht-4549"
    assert start["args"][start["args"].index("--name") + 1] == "ht-4549"
    assert "claude_rename_pending" not in task_json(tp.fdir, tid)


def test_failed_rename_does_not_fail_state_set(tp):
    ctx, tid = ticket_task(tp)
    fake_config(tp.fdir, fail_rename=True)
    r = set_ticket(tp, tid, "HT-4549")
    assert r.returncode == 0 and "rename failed" in r.stdout
    assert task_json(tp.fdir, tid)["state"]["ticket"] == "HT-4549"
    assert any(e["type"] == "rename_failed" for e in events(tp.fdir, tid))
    row = [r for r in tp.factory.json("tasks") if r["id"] == tid][0]
    assert row["rename_error"]


def test_partial_rename_keeps_the_new_agent_name(tp):
    ctx, tid = ticket_task(tp)
    fake_config(tp.fdir, rename_problems=["herdr tab rename failed: no tab"])
    set_ticket(tp, tid, "HT-4549")
    task = task_json(tp.fdir, tid)
    assert task["terminal_handle"]["agent"] == "ht-4549" and "tab rename" in task["rename_error"]


def test_claude_rename_keeps_the_tab_error(tp, monkeypatch):
    for key, value in tp.factory.env.items():
        monkeypatch.setenv(key, value)
    ctx, tid = ticket_task(tp)
    fake_config(tp.fdir, rename_problems=["herdr tab rename failed: no tab"])
    set_ticket(tp, tid, "HT-4549")
    assert rename.apply_pending(ctx, task_json(tp.fdir, tid)) is True
    task = task_json(tp.fdir, tid)
    assert "claude_rename_pending" not in task
    assert "tab rename" in task["rename_error"]
    row = [r for r in tp.factory.json("tasks") if r["id"] == tid][0]
    assert "tab rename" in row["rename_error"]


def test_failed_claude_rename_is_cleared_by_a_later_success(tp, monkeypatch):
    for key, value in tp.factory.env.items():
        monkeypatch.setenv(key, value)
    ctx, tid = ticket_task(tp)
    set_ticket(tp, tid, "HT-4549")
    fake_config(tp.fdir, send_prompt_fails=True)
    assert rename.apply_pending(ctx, task_json(tp.fdir, tid)) is False
    assert rename.apply_pending(ctx, task_json(tp.fdir, tid)) is False
    assert sum(1 for e in events(tp.fdir, tid) if e["type"] == "rename_failed") == 1
    assert task_json(tp.fdir, tid)["claude_rename_error"]
    assert task_json(tp.fdir, tid)["claude_rename_pending"] == "ht-4549"
    fake_config(tp.fdir)
    assert rename.apply_pending(ctx, task_json(tp.fdir, tid)) is True
    assert "claude_rename_error" not in task_json(tp.fdir, tid)


def test_rows_and_task_list_show_display_name(tp):
    ctx, tid = ticket_task(tp)
    set_ticket(tp, tid, "HT-4549")
    row = [r for r in tp.factory.json("tasks") if r["id"] == tid][0]
    assert row["display_name"] == "ht-4549"
    assert "ht-4549 (fix-the-list)" in tp.factory("tasks").stdout


def test_herdr_names_are_renamed_with_the_stub(tp, monkeypatch, tmp_path):
    for key, value in tp.factory.env.items():
        monkeypatch.setenv(key, value)
    yaml_path = tp.fdir / "factory.yaml"
    data = yaml.safe_load(yaml_path.read_text())
    data["terminal"] = "herdr"
    yaml_path.write_text(yaml.safe_dump(data))
    bindir = tmp_path / "bin"
    bindir.mkdir()
    exe = bindir / "herdr"
    exe.write_text(f"#!/bin/sh\nexec python3 {SF / 'tests' / 'fake_herdr.py'} \"$@\"\n")
    exe.chmod(exe.stat().st_mode | stat.S_IEXEC)
    log = tmp_path / "herdr.log"
    monkeypatch.setenv("PATH", f"{bindir}:{os.environ['PATH']}")
    monkeypatch.setenv("FAKE_HERDR_LOG", str(log))
    monkeypatch.setenv("FAKE_HERDR_MAIN", str(tp.repo))
    monkeypatch.setenv("FAKE_HERDR_PRESENT", "1")
    ctx = repo.load_ctx(cwd=tp.repo)
    tid = "fix-the-list"
    make_task(ctx, tid=tid, worktree=str(tp.repo), terminal_handle={"agent": tid, "workspace": "w9", "tab": "w9:t1"})
    engine.set_state(ctx, tid, "ticket", "HT-4549")
    calls = [json.loads(line) for line in log.read_text().splitlines()]
    assert ["agent", "rename", tid, "ht-4549"] in calls
    assert ["tab", "rename", "w9:t1", "ht-4549"] in calls
    assert ["workspace", "rename", "w9", "ht-4549"] in calls
    task = task_json(tp.fdir, tid)
    assert task["id"] == tid and task["worktree"] == str(tp.repo) and task["terminal_handle"]["agent"] == "ht-4549"
    assert "rename_error" not in task or task["rename_error"] is None


def test_unexpected_rename_error_is_saved_and_logged(tp, monkeypatch):
    for key, value in tp.factory.env.items():
        monkeypatch.setenv(key, value)
    ctx, tid = ticket_task(tp)

    def boom(*args):
        raise RuntimeError("boom")

    monkeypatch.setattr(rename, "rename", boom)
    value, problem = engine.set_state(ctx, tid, "ticket", "HT-4549")
    assert value == "HT-4549" and problem == "boom"
    assert task_json(tp.fdir, tid)["rename_error"] == "boom"
    assert any(e["type"] == "rename_failed" and e["reason"] == "boom" for e in events(tp.fdir, tid))
