import json

import pytest

from conftest import fake_calls, git, write_pipeline, write_step
from factory import delete, launch, repo, state
from factory.errors import FactoryError


@pytest.fixture
def started(inited):
    write_step(inited.fdir, "work", {})
    write_pipeline(inited.fdir, {"id": "branchy", "inputs": {"branch": {"description": "b"}}, "steps": ["work"]})
    ctx = repo.load_ctx(cwd=inited.repo)
    task = launch.launch(ctx, "branchy", "Del me", {"branch": "feat/del"})
    return inited, ctx, task


def test_dry_run_shows_changes_and_changes_nothing(started):
    inited, ctx, task = started
    wt = task["worktree"]
    (inited.worktrees / task["id"] / "new.txt").write_text("x")
    plan = delete.plan_delete(ctx, task["id"])
    assert plan["uncommitted"] and plan["needs_confirm"]
    git("add", "-A", cwd=wt)
    git("commit", "-m", "c", cwd=wt)
    plan = delete.plan_delete(ctx, task["id"])
    assert plan["unpushed"] and not plan["delete_branch"]
    assert (inited.fdir / "tasks" / task["id"]).exists()


def test_delete_refuses_without_confirm_then_archives(started):
    inited, ctx, task = started
    wt = inited.worktrees / task["id"]
    (wt / "kept.txt").write_text("k")
    git("add", "kept.txt", cwd=wt)
    git("commit", "-m", "kept", cwd=wt)
    (wt / "new.txt").write_text("x")
    with pytest.raises(FactoryError, match="--confirm-unpushed"):
        delete.delete(ctx, task["id"])
    delete.delete(ctx, task["id"], confirm_unpushed=True)
    assert not (inited.worktrees / task["id"]).exists()
    assert (inited.fdir / "tasks" / "archive" / task["id"] / "task.json").exists()
    assert fake_calls(inited.fdir)[-1]["op"] == "close"
    assert git("branch", "--list", "feat/del", cwd=inited.repo)
    log = inited.fdir / "tasks" / "archive" / task["id"] / "events.jsonl"
    assert json.loads(log.read_text().splitlines()[-1])["type"] == "task_deleted"


def test_launch_and_delete_never_call_herdr(inited, tmp_path):
    marker = tmp_path / "herdr-called"
    bindir = tmp_path / "bin"
    bindir.mkdir()
    (bindir / "herdr").write_text(f"#!/bin/sh\ntouch {marker}\nexit 1\n")
    (bindir / "herdr").chmod(0o755)
    env = {"PATH": f"{bindir}:{inited.factory.env['PATH']}"}
    write_step(inited.fdir, "work", {})
    write_pipeline(inited.fdir, {"id": "plain", "steps": ["work"]})
    tid = inited.factory.json("launch", "plain", "--description", "No herdr", env=env)["id"]
    inited.factory("delete", tid, env=env)
    assert not marker.exists()
    assert [c["op"] for c in fake_calls(inited.fdir)] == ["start_session", "close"]


def test_pushed_branch_is_deleted(started):
    inited, ctx, task = started
    git("push", "-u", "origin", "feat/del", cwd=task["worktree"])
    delete.delete(ctx, task["id"])
    assert not git("branch", "--list", "feat/del", cwd=inited.repo)


def test_branch_merged_then_deleted_on_origin_is_deleted(started):
    inited, ctx, task = started
    wt = task["worktree"]
    (inited.worktrees / task["id"] / "m.txt").write_text("m")
    git("add", "m.txt", cwd=wt)
    git("commit", "-m", "merged work", cwd=wt)
    git("push", "origin", "HEAD:main", cwd=wt)
    git("push", "origin", "feat/del", cwd=wt)
    git("push", "origin", "--delete", "feat/del", cwd=wt)
    git("fetch", "--prune", "origin", cwd=inited.repo)
    delete.delete(ctx, task["id"])
    assert not git("branch", "--list", "feat/del", cwd=inited.repo)


def test_failed_check_refuses_without_confirm(started):
    inited, ctx, task = started
    state.update(ctx, task["id"], lambda t: t.__setitem__("base_ref", "no-such-base"))
    with pytest.raises(FactoryError, match="--confirm-unpushed"):
        delete.delete(ctx, task["id"])
    assert (inited.worktrees / task["id"]).exists()
    assert delete.plan_delete(ctx, task["id"])["check_errors"]
