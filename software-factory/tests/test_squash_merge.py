
import pytest

from conftest import commit_all, git, write_pipeline, write_step
from factory import delete, launch, repo, state

SQUASH_TEXT = "The branch is merged into origin/main (squash merge). Its commits are not lost."


@pytest.fixture
def env(inited):
    write_step(inited.fdir, "w", {})
    write_pipeline(inited.fdir, {"id": "b", "inputs": {"branch": {"description": "b"}}, "steps": ["w"]})
    write_pipeline(inited.fdir, {"id": "nb", "steps": ["w"]})
    ctx = repo.load_ctx(cwd=inited.repo)
    other = inited.work / "other"
    git("clone", str(inited.work / "origin.git"), str(other), cwd=inited.work)
    git("config", "user.name", "Test", cwd=other)
    git("config", "user.email", "test@example.com", cwd=other)
    return inited, ctx, other


def task_with_commit(inited, ctx, branch, name="f.txt", text="one\n"):
    task = launch.launch(ctx, "b", f"Task {branch}", {"branch": branch})
    wt = inited.worktrees / task["id"]
    (wt / name).write_text(text)
    commit_all(wt, f"change {name}")
    git("push", "-u", "origin", branch, cwd=wt)
    return task, wt


def squash_into_main(other, branch, delete_remote=True):
    git("fetch", "origin", cwd=other)
    git("checkout", "main", cwd=other)
    git("pull", "origin", "main", cwd=other)
    git("merge", "--squash", f"origin/{branch}", cwd=other)
    git("commit", "-m", f"squash {branch}", cwd=other)
    git("push", "origin", "main", cwd=other)
    if delete_remote:
        git("push", "origin", "--delete", branch, cwd=other)


def finish(ctx, tid):
    state.update(ctx, tid, lambda t: state.set_status(t, "finished"))


def test_squash_merged_branch_loses_nothing_and_is_deleted(env):
    inited, ctx, other = env
    task, _ = task_with_commit(inited, ctx, "feat/sq")
    squash_into_main(other, "feat/sq")
    plan = delete.plan_delete(ctx, task["id"])
    assert plan["squash_merged"] and plan["unpushed"] == [] and plan["delete_branch"] and not plan["needs_confirm"]
    assert SQUASH_TEXT in delete.render_plan(plan)
    delete.delete(ctx, task["id"])
    assert git("branch", "--list", "feat/sq", cwd=inited.repo) == ""


def test_local_commit_after_squash_is_listed(env):
    inited, ctx, other = env
    task, wt = task_with_commit(inited, ctx, "feat/late")
    squash_into_main(other, "feat/late")
    (wt / "late.txt").write_text("late\n")
    commit_all(wt, "late work")
    plan = delete.plan_delete(ctx, task["id"])
    assert not plan["squash_merged"] and plan["needs_confirm"]
    assert any("late work" in line for line in plan["unpushed"])
    assert not plan["delete_branch"]


def test_merge_commit_is_unchanged(env):
    inited, ctx, other = env
    task, _ = task_with_commit(inited, ctx, "feat/mc")
    git("fetch", "origin", cwd=other)
    git("merge", "--no-ff", "-m", "merge", "origin/feat/mc", cwd=other)
    git("push", "origin", "main", cwd=other)
    plan = delete.plan_delete(ctx, task["id"])
    assert plan["unpushed"] == [] and plan["delete_branch"] and not plan["squash_merged"]


def test_never_pushed_branch_is_unchanged(env):
    inited, ctx, _ = env
    task = launch.launch(ctx, "b", "Local only", {"branch": "feat/local"})
    wt = inited.worktrees / task["id"]
    (wt / "l.txt").write_text("l\n")
    commit_all(wt, "local work")
    plan = delete.plan_delete(ctx, task["id"])
    assert plan["needs_confirm"] and not plan["delete_branch"] and not plan["squash_merged"]
    assert any("local work" in line for line in plan["unpushed"])


def test_clean_reports_squash_when_worktree_is_gone(env):
    inited, ctx, other = env
    task, wt = task_with_commit(inited, ctx, "feat/gone")
    squash_into_main(other, "feat/gone")
    git("worktree", "remove", "--force", str(wt), cwd=inited.repo)
    finish(ctx, task["id"])
    rows = {r["id"]: r for r in inited.factory.json("clean")}
    assert rows[task["id"]]["merged"] and rows[task["id"]]["reason"] == "merged (squash)"


def test_later_change_of_same_lines_is_merged_by_patch_id(env):
    inited, ctx, other = env
    task, _ = task_with_commit(inited, ctx, "feat/conf", name="README.md", text="branch\n")
    squash_into_main(other, "feat/conf", delete_remote=False)
    (other / "README.md").write_text("main later\n")
    commit_all(other, "main later")
    git("push", "origin", "main", cwd=other)
    finish(ctx, task["id"])
    rows = {r["id"]: r for r in inited.factory.json("clean")}
    assert rows[task["id"]]["merged"] and rows[task["id"]]["reason"] == "merged (squash)"
