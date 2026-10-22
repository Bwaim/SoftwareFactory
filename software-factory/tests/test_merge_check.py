import pytest

from conftest import commit_all, git
from factory import delete, launch, state
from factory.errors import FactoryError
from test_squash_merge import env, finish, squash_into_main, task_with_commit


def main_change(other, name, text):
    (other / name).write_text(text)
    commit_all(other, f"main {name}")
    git("push", "origin", "main", cwd=other)


def test_patch_id_finds_squash_after_later_change(env):
    inited, ctx, other = env
    task, _ = task_with_commit(inited, ctx, "feat/x", name="README.md", text="branch\n")
    squash_into_main(other, "feat/x")
    main_change(other, "README.md", "main later\n")
    finish(ctx, task["id"])
    git("fetch", "origin", "--prune", cwd=inited.repo)
    assert delete.merge_state(ctx, "feat/x", "main") == (True, "merged (squash)", True)
    rows = {r["id"]: r for r in inited.factory.json("clean")}
    assert rows[task["id"]]["reason"] == "merged (squash)"


def test_empty_branch_diff_is_not_patch_merged(env):
    inited, ctx, other = env
    task = launch.launch(ctx, "b", "Empty", {"branch": "feat/empty"})
    git("push", "-u", "origin", "feat/empty", cwd=inited.worktrees / task["id"])
    main_change(other, "other.txt", "other\n")
    git("fetch", "origin", cwd=inited.repo)
    assert delete.patch_id_merged(ctx, "feat/empty", "main") is False


def test_commit_on_other_files_is_ignored(env):
    inited, ctx, other = env
    task_with_commit(inited, ctx, "feat/a", name="a.txt", text="a\n")
    main_change(other, "b.txt", "b\n")
    git("fetch", "origin", cwd=inited.repo)
    assert delete.patch_id_merged(ctx, "feat/a", "main") is False


def test_file_name_with_space(env):
    inited, ctx, other = env
    task_with_commit(inited, ctx, "feat/sp", name="a b.txt", text="one\n")
    squash_into_main(other, "feat/sp")
    main_change(other, "a b.txt", "two\n")
    git("fetch", "origin", cwd=inited.repo)
    assert delete.patch_id_merged(ctx, "feat/sp", "main") is True


def test_missing_base_is_no_match(env):
    inited, ctx, _ = env
    task_with_commit(inited, ctx, "feat/x")
    assert delete.patch_id_merged(ctx, "feat/x", "no-such-base") is False


def test_task_branch_prefers_worktree(env):
    inited, ctx, _ = env
    task = launch.launch(ctx, "b", "Real", {"branch": "feat/real"})
    task["state"]["branch"] = "old"
    assert delete.task_branch(ctx, task) == "feat/real"


def test_task_branch_uses_state_when_worktree_gone_or_detached(env):
    inited, ctx, _ = env
    task = launch.launch(ctx, "b", "Gone", {"branch": "feat/st"})
    wt = inited.worktrees / task["id"]
    git("checkout", "--detach", cwd=wt)
    assert delete.task_branch(ctx, task) == "feat/st"
    git("worktree", "remove", "--force", str(wt), cwd=inited.repo)
    assert delete.task_branch(ctx, task) == "feat/st"


def test_task_branch_missing_local_ref_is_none(env):
    inited, ctx, _ = env
    task = launch.launch(ctx, "b", "Deleted", {"branch": "feat/deleted"})
    wt = inited.worktrees / task["id"]
    git("worktree", "remove", "--force", str(wt), cwd=inited.repo)
    git("branch", "-D", "feat/deleted", cwd=inited.repo)
    branch = delete.task_branch(ctx, task)
    assert branch is None
    assert delete.merge_state(ctx, branch, "main")[1] == "no branch"


def test_remote_deleted_without_merge_is_not_by_content(env):
    inited, ctx, other = env
    task_with_commit(inited, ctx, "feat/p")
    git("push", "origin", "--delete", "feat/p", cwd=other)
    git("fetch", "origin", "--prune", cwd=inited.repo)
    assert delete.merge_state(ctx, "feat/p", "main") == (True, "pushed, and its remote branch was deleted", False)


def squashed_task_with_later_change(inited, ctx, other):
    task, wt = task_with_commit(inited, ctx, "feat/x", name="README.md", text="branch\n")
    squash_into_main(other, "feat/x")
    main_change(other, "README.md", "main later\n")
    return task, wt


def test_delete_removes_squash_merged_branch_after_later_change(env):
    inited, ctx, other = env
    task, _ = squashed_task_with_later_change(inited, ctx, other)
    plan = delete.plan_delete(ctx, task["id"])
    assert plan["unpushed"] == [] and not plan["needs_confirm"] and plan["delete_branch"]
    assert plan["reason"] == "merged (squash)" and plan["by_content"] and plan["squash_merged"]
    delete.delete(ctx, task["id"])
    assert git("branch", "--list", "feat/x", cwd=inited.repo) == ""


def test_local_commit_after_squash_is_lost_work(env):
    inited, ctx, other = env
    task, wt = squashed_task_with_later_change(inited, ctx, other)
    (wt / "late.txt").write_text("late\n")
    commit_all(wt, "late work")
    plan = delete.plan_delete(ctx, task["id"])
    assert plan["needs_confirm"] and not plan["delete_branch"]
    assert any("late work" in line for line in plan["unpushed"])
    with pytest.raises(FactoryError, match="--confirm-unpushed"):
        delete.delete(ctx, task["id"])


def test_worktree_removed_by_hand_squash_branch_is_deleted(env):
    inited, ctx, other = env
    task, wt = task_with_commit(inited, ctx, "feat/h")
    squash_into_main(other, "feat/h")
    git("worktree", "remove", "--force", str(wt), cwd=inited.repo)
    delete.delete(ctx, task["id"])
    assert git("branch", "--list", "feat/h", cwd=inited.repo) == ""


def test_remote_deleted_without_merge_asks_and_keeps_branch(env):
    inited, ctx, other = env
    task, wt = task_with_commit(inited, ctx, "feat/p")
    git("push", "origin", "--delete", "feat/p", cwd=other)
    finish(ctx, task["id"])
    rows = {r["id"]: r for r in inited.factory.json("clean")}
    assert rows[task["id"]]["selected"] is True
    plan = delete.plan_delete(ctx, task["id"])
    assert plan["needs_confirm"] and plan["unpushed"] and not plan["by_content"]
    delete.delete(ctx, task["id"], confirm_unpushed=True)
    assert not wt.exists()
    assert git("branch", "--list", "feat/p", cwd=inited.repo) != ""


def test_detached_worktree_commits_are_listed(env):
    inited, ctx, _ = env
    task = launch.launch(ctx, "nb", "Detached", {})
    wt = inited.worktrees / task["id"]
    (wt / "d.txt").write_text("d\n")
    commit_all(wt, "detached work")
    plan = delete.plan_delete(ctx, task["id"])
    assert plan["needs_confirm"]
    assert any("detached work" in line for line in plan["unpushed"])
