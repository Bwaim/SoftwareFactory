from conftest import fake_calls, make_task, task_json
from factory import delete, repo


def folder_task(ctx, tid="t1"):
    return make_task(ctx, tid, terminal_handle={"agent": tid})


def closes(fdir):
    return [c for c in fake_calls(fdir) if c["op"] == "close"]


def test_delete_folder_task_plain(plain, no_git):
    ctx = repo.load_ctx(cwd=plain)
    folder_task(ctx)
    delete.delete(ctx, "t1")
    assert len(closes(plain / ".factory")) == 1
    assert not (plain / ".factory" / "tasks" / "t1").exists()
    assert (plain / ".factory" / "tasks" / "archive" / "t1").exists()


def test_cancel_folder_task_plain(plain, no_git):
    ctx = repo.load_ctx(cwd=plain)
    folder_task(ctx)
    delete.cancel(ctx, "t1")
    assert len(closes(plain / ".factory")) == 1
    archived = task_json(plain / ".factory", "archive/t1")
    assert archived["status"] == "cancelled"


def test_delete_folder_task_git(inited):
    ctx = repo.load_ctx(cwd=inited.repo)
    folder_task(ctx)
    (inited.repo / "mine.txt").write_text("keep")
    delete.delete(ctx, "t1")
    assert (inited.repo / "mine.txt").read_text() == "keep"
    assert (inited.fdir / "tasks" / "archive" / "t1").exists()


def test_folder_plans_have_no_worktree_or_branch(plain, no_git):
    ctx = repo.load_ctx(cwd=plain)
    folder_task(ctx)
    plan = delete.plan_cancel(ctx, "t1")
    assert (plan["branch_commit"], plan["detached_commit"], plan["remote_branch"]) == (None, None, False)
    for text in (delete.render_cancel_plan(plan), delete.render_plan(delete.plan_delete(ctx, "t1"))):
        assert "Worktree" not in text and "branch" not in text.lower()
