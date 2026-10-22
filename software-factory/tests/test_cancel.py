import json
import re
import shutil

import pytest

from conftest import fake_calls, fake_config, git, make_task, write_pipeline, write_step
from factory import launch, repo, session, state

REFUSAL = "The task is finished. Use Clean or `factory delete <id>`."
WARNING = "The remote branch and the merge request stay open. Close them by hand."


@pytest.fixture
def started(inited):
    write_step(inited.fdir, "work", {})
    write_pipeline(inited.fdir, {"id": "branchy", "inputs": {"branch": {"description": "b"}}, "steps": ["work"]})
    ctx = repo.load_ctx(cwd=inited.repo)
    task = launch.launch(ctx, "branchy", "Cancel me", {"branch": "feat/c"})
    return inited, ctx, task


def commit_in(wt, name, message):
    (wt / name).write_text(name)
    git("add", name, cwd=wt)
    git("commit", "-m", message, cwd=wt)
    return git("rev-parse", "HEAD", cwd=wt)


def archived(inited, tid):
    return json.loads((inited.fdir / "tasks" / "archive" / tid / "task.json").read_text())


def last_event(inited, tid):
    log = inited.fdir / "tasks" / "archive" / tid / "events.jsonl"
    return json.loads(log.read_text().splitlines()[-1])["type"]


def saved_commit(out):
    return re.search(r"`git stash apply ([0-9a-f]+)`", out).group(1)


def test_cancel_removes_everything(started):
    inited, ctx, task = started
    wt = inited.worktrees / task["id"]
    sha = commit_in(wt, "w.txt", "work")
    out = inited.factory("cancel", task["id"]).stdout
    assert fake_calls(inited.fdir)[-1]["op"] == "close"
    assert not wt.exists()
    assert not git("branch", "--list", "feat/c", cwd=inited.repo)
    assert archived(inited, task["id"])["status"] == "cancelled"
    assert last_event(inited, task["id"]) == "task_cancelled"
    assert f"Task {task['id']} cancelled and archived." in out
    assert f"Restore it with `git branch feat/c {sha}`." in out
    assert "git stash apply" not in out


def test_cancel_saves_uncommitted_changes(started):
    inited, ctx, task = started
    wt = inited.worktrees / task["id"]
    (wt / "README.md").write_text("changed\n")
    (wt / "new.txt").write_text("n")
    out = inited.factory("cancel", task["id"]).stdout
    commit = saved_commit(out)
    assert f"Uncommitted changes saved in {commit}: `git stash apply {commit}`." in out
    stat = git("show", commit, "--stat", cwd=inited.repo)
    assert "README.md" in stat and "new.txt" in stat
    assert git("stash", "list", cwd=inited.repo) == ""


def test_dry_run_lists_and_changes_nothing(started):
    inited, ctx, task = started
    wt = inited.worktrees / task["id"]
    git("push", "-u", "origin", "feat/c", cwd=wt)
    commit_in(wt, "w.txt", "unpushed subject")
    sha = git("rev-parse", "HEAD", cwd=wt)
    (wt / "dirty.txt").write_text("d")
    state.set_key(ctx, task["id"], "mr_url", "https://example.com/mr/1")
    calls = len(fake_calls(inited.fdir))
    out = inited.factory("cancel", task["id"], "--dry-run").stdout
    assert out.startswith(f"Cancel task {task['id']}:")
    assert "Uncommitted changes (saved as a commit you can restore):" in out
    assert "dirty.txt" in out
    assert "Lost work:" in out and "unpushed subject" in out
    assert f"Restore the branch with `git branch feat/c {sha}`." in out
    assert WARNING in out and "https://example.com/mr/1" in out
    assert (inited.fdir / "tasks" / task["id"] / "task.json").exists()
    assert wt.exists() and git("branch", "--list", "feat/c", cwd=inited.repo)
    assert len(fake_calls(inited.fdir)) == calls
    plan = inited.factory.json("cancel", task["id"], "--dry-run")
    assert plan["remote_branch"] is True and plan["branch_commit"] == sha


def test_remote_branch_is_never_deleted(started):
    inited, ctx, task = started
    git("push", "-u", "origin", "feat/c", cwd=task["worktree"])
    inited.factory("cancel", task["id"])
    assert git("ls-remote", "origin", "feat/c", cwd=inited.repo)
    assert not git("branch", "--list", "feat/c", cwd=inited.repo)


def test_cancel_paused_task(started):
    inited, ctx, task = started
    session.pause(ctx, task["id"])
    calls = len(fake_calls(inited.fdir))
    inited.factory("cancel", task["id"])
    assert not any(c["op"] == "close" for c in fake_calls(inited.fdir)[calls:])
    assert archived(inited, task["id"])["status"] == "cancelled"


def test_cancel_gone_session_and_missing_worktree(started):
    inited, ctx, task = started
    fake_config(inited.fdir, states={task["terminal_handle"]["agent"]: "gone"})
    shutil.rmtree(inited.worktrees / task["id"])
    inited.factory("cancel", task["id"])
    assert not git("branch", "--list", "feat/c", cwd=inited.repo)
    assert archived(inited, task["id"])["status"] == "cancelled"


def test_cancel_task_without_worktree_or_handle(inited):
    ctx = repo.load_ctx(cwd=inited.repo)
    make_task(ctx, "bare")
    out = inited.factory("cancel", "bare").stdout
    assert "Task bare cancelled and archived." in out
    assert archived(inited, "bare")["status"] == "cancelled"


def test_finished_task_is_refused(started):
    inited, ctx, task = started
    state.update(ctx, task["id"], lambda t: state.set_status(t, "finished"))
    r = inited.factory("cancel", task["id"], check=False)
    assert r.returncode == 1
    assert REFUSAL in r.stdout + r.stderr
    r = inited.factory("cancel", task["id"], "--dry-run", check=False)
    assert r.returncode == 1 and REFUSAL in r.stdout + r.stderr
    assert (inited.fdir / "tasks" / task["id"] / "task.json").exists()


def test_cancel_close_failure_changes_nothing(started):
    inited, ctx, task = started
    fake_config(inited.fdir, fail_close=True)
    r = inited.factory("cancel", task["id"], check=False)
    assert r.returncode == 1
    assert (inited.worktrees / task["id"]).exists()
    assert git("branch", "--list", "feat/c", cwd=inited.repo)
    assert (inited.fdir / "tasks" / task["id"] / "task.json").exists()
    assert state.load(ctx, task["id"])["status"] != "cancelled"


def test_cancel_branch_delete_failure_still_archives(started):
    inited, ctx, task = started
    lock = inited.repo / ".git" / "refs" / "heads" / "feat" / "c.lock"
    lock.write_text("")
    try:
        r = inited.factory("cancel", task["id"], check=False)
    finally:
        lock.unlink()
    assert r.returncode == 1
    assert "The branch feat/c was not deleted:" in r.stdout + r.stderr
    assert archived(inited, task["id"])["status"] == "cancelled"
    assert not (inited.fdir / "tasks" / task["id"]).exists()


def test_change_made_during_close_is_saved(started):
    inited, ctx, task = started
    wt = inited.worktrees / task["id"]
    fake_config(inited.fdir, on_close={"cwd": str(wt), "commands": [["sh", "-c", "echo late > late.txt"]]})
    out = inited.factory("cancel", task["id"]).stdout
    assert "late.txt" in git("show", saved_commit(out), "--stat", cwd=inited.repo)


def test_commit_made_during_close_is_restore_commit(started):
    inited, ctx, task = started
    wt = inited.worktrees / task["id"]
    sha_file = inited.work / "sha.txt"
    script = f"git commit --allow-empty -m during-close && git rev-parse HEAD > {sha_file}"
    fake_config(inited.fdir, on_close={"cwd": str(wt), "commands": [["sh", "-c", script]]})
    out = inited.factory("cancel", task["id"]).stdout
    assert f"Restore it with `git branch feat/c {sha_file.read_text().strip()}`." in out


def test_stash_failure_stops(started):
    inited, ctx, task = started
    wt = inited.worktrees / task["id"]
    (wt / "dirty.txt").write_text("d")
    lock = (wt / git("rev-parse", "--git-dir", cwd=wt)).resolve() / "index.lock"
    lock.write_text("")
    try:
        r = inited.factory("cancel", task["id"], check=False)
    finally:
        lock.unlink()
    assert r.returncode == 1
    assert wt.exists()
    assert git("branch", "--list", "feat/c", cwd=inited.repo)
    assert (inited.fdir / "tasks" / task["id"] / "task.json").exists()
    assert not (inited.fdir / "tasks" / "archive" / task["id"]).exists()


def test_cancelled_task_missing_from_lists(started):
    inited, ctx, task = started
    inited.factory("cancel", task["id"])
    assert not any(row.get("id") == task["id"] for row in inited.factory.json("tasks"))
