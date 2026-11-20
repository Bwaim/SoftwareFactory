import pytest

from conftest import commit_all, git, write_pipeline, write_step
from factory import delete, launch, repo, state


@pytest.fixture
def local(inited):
    write_step(inited.fdir, "work", {})
    write_pipeline(inited.fdir, {"id": "plain", "steps": ["work"]})
    write_pipeline(inited.fdir, {"id": "branchy", "inputs": {"branch": {"description": "Branch"}}, "steps": ["work"]})
    (inited.repo / "local.txt").write_text("local\n")
    commit_all(inited.repo, "local only")
    git("remote", "remove", "origin", cwd=inited.repo)
    return inited


def ctx(lp):
    return repo.load_ctx(cwd=lp.repo)


def test_init_without_origin_warns(factory, origin_repo, library_path):
    git("remote", "remove", "origin", cwd=origin_repo)
    r = factory("init", "--library", library_path, "--create-library")
    assert r.returncode == 0
    assert "OK: git:" in r.stdout
    assert "Warning: This repository has no `origin` remote. Tasks start from the local `main` branch. Push and pull request steps fail." in r.stdout


def test_init_outside_git_is_plain(factory, tmp_path, library_path):
    plain = tmp_path / "plain"
    plain.mkdir()
    env = {"GIT_CEILING_DIRECTORIES": str(tmp_path)}
    r = factory("init", "--library", library_path, "--create-library", cwd=plain, env=env)
    assert "not in a git repository" in r.stdout
    assert (plain / ".factory" / "factory.yaml").exists()


def test_launch_without_origin_new_branch(local):
    rep = launch.plan_launch(ctx(local), "branchy", "B", {"branch": "feat/new"})
    assert rep["ok"] and rep["branch_case"] == "new" and not rep["errors"]
    task = launch.launch(ctx(local), "branchy", "B", {"branch": "feat/new"})
    assert git("branch", "--show-current", cwd=task["worktree"]) == "feat/new"
    assert git("rev-parse", "HEAD", cwd=task["worktree"]) == git("rev-parse", "main", cwd=local.repo)


def test_launch_without_origin_existing_branch(local):
    git("branch", "feat/old", cwd=local.repo)
    rep = launch.plan_launch(ctx(local), "branchy", "B", {"branch": "feat/old"})
    assert rep["ok"] and rep["branch_case"] == "existing"


def test_launch_without_origin_detached(local):
    task = launch.launch(ctx(local), "plain", "Detached", {})
    assert git("rev-parse", "HEAD", cwd=task["worktree"]) == git("rev-parse", "main", cwd=local.repo)
    assert git("branch", "--show-current", cwd=task["worktree"]) == ""
    assert "detached HEAD on main" in launch.render_report(launch.plan_launch(ctx(local), "plain", "Other", {}))


def test_launch_without_origin_ignores_same_named_tag(local):
    git("tag", "main", "HEAD~1", cwd=local.repo)
    rep = launch.plan_launch(ctx(local), "plain", "Tagged", {})
    assert "detached HEAD on main" in launch.render_report(rep)
    task = launch.launch(ctx(local), "plain", "Tagged", {})
    assert git("rev-parse", "HEAD", cwd=task["worktree"]) == git("rev-parse", "refs/heads/main", cwd=local.repo)


def test_launch_without_origin_missing_base(local):
    local.factory("config", "set", "create-worktree", "base_ref", "nope")
    rep = launch.plan_launch(ctx(local), "plain", "Missing", {})
    assert not rep["ok"]
    assert rep["errors"] == ["The branch `nope` does not exist in this repository."]


def test_clean_without_origin_merged(local):
    c = ctx(local)
    task = launch.launch(c, "branchy", "Merged", {"branch": "feat/merged"})
    (local.worktrees / task["id"] / "m.txt").write_text("x")
    commit_all(local.worktrees / task["id"], "m")
    git("merge", "--ff-only", "feat/merged", cwd=local.repo)
    state.update(c, task["id"], lambda t: state.set_status(t, "finished"))
    rows = {r["id"]: r for r in local.factory.json("clean")}
    assert rows[task["id"]]["reason"] == "merged into main"
    assert rows[task["id"]]["merged"] and rows[task["id"]]["selected"]


def test_delete_without_origin_lost_commits(local):
    c = ctx(local)
    task = launch.launch(c, "branchy", "Lost", {"branch": "feat/lost"})
    (local.worktrees / task["id"] / "l.txt").write_text("x")
    commit_all(local.worktrees / task["id"], "lost work")
    plan = delete.plan_delete(c, task["id"])
    assert plan["reason"] == "not merged" and not plan["check_errors"]
    assert len(plan["unpushed"]) == 1 and plan["unpushed"][0].endswith("lost work")
    assert not plan["delete_branch"] and plan["needs_confirm"]
    text = delete.render_plan(plan)
    assert "Commits not in main:" in text and "pushed to origin" not in text


def test_delete_without_origin_merged_removes_branch(local):
    c = ctx(local)
    task = launch.launch(c, "branchy", "Done", {"branch": "feat/done"})
    (local.worktrees / task["id"] / "d.txt").write_text("x")
    commit_all(local.worktrees / task["id"], "done")
    git("merge", "--ff-only", "feat/done", cwd=local.repo)
    plan = delete.plan_delete(c, task["id"])
    assert plan["reason"] == "merged into main" and plan["delete_branch"] and not plan["unpushed"]


def test_base_ref_follows_origin(local):
    assert delete.base_ref(ctx(local), "main") == "refs/heads/main"
    git("remote", "add", "origin", str(local.work / "origin.git"), cwd=local.repo)
    assert delete.base_ref(ctx(local), "main") == "refs/remotes/origin/main"


def test_delete_with_origin_keeps_unpushed_text(inited):
    write_step(inited.fdir, "work", {})
    write_pipeline(inited.fdir, {"id": "branchy", "inputs": {"branch": {"description": "Branch"}}, "steps": ["work"]})
    c = ctx(inited)
    task = launch.launch(c, "branchy", "Kept", {"branch": "feat/kept"})
    (inited.worktrees / task["id"] / "k.txt").write_text("x")
    commit_all(inited.worktrees / task["id"], "kept work")
    assert "Commits not pushed to origin:" in delete.render_plan(delete.plan_delete(c, task["id"]))
