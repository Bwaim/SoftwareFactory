import pytest

from conftest import commit_all, events, fake_calls, fake_config, git, task_json, write_pipeline, write_step
from factory import launch, repo
from factory.errors import FactoryError


@pytest.fixture
def lp(inited):
    write_step(inited.fdir, "work", {})
    write_pipeline(inited.fdir, {"id": "plain", "steps": ["work"], "claude": {"model": "sonnet", "effort": "medium"}})
    write_pipeline(inited.fdir, {"id": "branchy", "inputs": {"branch": {"description": "Branch"}}, "steps": ["work"]})
    return inited


def ctx(lp):
    return repo.load_ctx(cwd=lp.repo)


def commit_file(repo_dir, filename, message):
    git("add", filename, cwd=repo_dir)
    git("commit", "-m", message, cwd=repo_dir)


def push_branch(lp, name, filename):
    git("switch", "-c", name, cwd=lp.repo)
    (lp.repo / filename).write_text(name)
    commit_file(lp.repo, filename, name)
    git("push", "-u", "origin", name, cwd=lp.repo)
    git("switch", "main", cwd=lp.repo)


def test_slug_rules(lp):
    assert launch.slugify("Fix the Login crash!") == "fix-the-login-crash"
    assert launch.slugify("ÉÉ 2") == "ee-2"
    assert launch.slugify("!!!") == "task"
    assert launch.slugify("2 bugs") == "task-2-bugs"
    assert launch.TASK_ID_RE.match(launch.slugify("x" * 80))


def test_dry_run_changes_nothing_and_reports(lp):
    rep = launch.plan_launch(ctx(lp), "plain", "Fix it", {})
    assert rep["ok"] and rep["task_id"] == "fix-it" and rep["branch_case"] == "detached"
    assert rep["worktree"] == str(lp.worktrees / "fix-it")
    assert not (lp.worktrees / "fix-it").exists()
    assert not (lp.fdir / "tasks" / "fix-it").exists()


def test_launch_detached(lp):
    task = launch.launch(ctx(lp), "plain", 'Say "hi" $HOME', {})
    wt = lp.worktrees / task["id"]
    assert git("rev-parse", "HEAD", cwd=wt) == git("rev-parse", "origin/main", cwd=lp.repo)
    assert task_json(lp.fdir, task["id"])["position"] == 1
    call = fake_calls(lp.fdir)[0]
    args = call["args"]
    assert call["in_worktree"] is True and call["cwd"] == str(wt)
    assert args[args.index("--name") + 1] == task["id"]
    assert args[args.index("--session-id") + 1] == task["session_id"]
    assert args[args.index("--settings") + 1] == str(lp.fdir / "claude-settings.json")
    assert args[args.index("--model") + 1] == "sonnet" and args[args.index("--effort") + 1] == "medium"
    assert str(lp.fdir / "tasks" / task["id"] / "artifacts") in args
    assert "Run `factory next`" in call["prompt"]
    kinds = [e["type"] for e in events(lp.fdir, task["id"])]
    assert kinds[0] == "task_created"


def test_taken_id_gets_suffix(lp):
    launch.launch(ctx(lp), "plain", "Same", {})
    assert launch.plan_launch(ctx(lp), "plain", "Same", {})["task_id"] == "same-2"


def test_new_branch(lp):
    rep = launch.plan_launch(ctx(lp), "branchy", "B", {"branch": "feat/new"})
    assert rep["branch_case"] == "new"
    task = launch.launch(ctx(lp), "branchy", "B", {"branch": "feat/new"})
    assert git("branch", "--show-current", cwd=task["worktree"]) == "feat/new"


def test_existing_local_branch_behind_is_fast_forwarded(lp):
    push_branch(lp, "feat/ff", "a.txt")
    seed = lp.work / "seed"
    git("fetch", "origin", cwd=seed)
    git("switch", "feat/ff", cwd=seed)
    (seed / "b.txt").write_text("b")
    commit_all(seed, "more")
    git("push", "origin", "feat/ff", cwd=seed)
    rep = launch.plan_launch(ctx(lp), "branchy", "F", {"branch": "feat/ff"})
    assert rep["branch_case"] == "existing" and rep["fast_forward"] is True
    task = launch.launch(ctx(lp), "branchy", "F", {"branch": "feat/ff"})
    assert (lp.worktrees / task["id"] / "b.txt").exists()


def test_remote_only_branch(lp):
    push_branch(lp, "feat/remote", "r.txt")
    git("branch", "-D", "feat/remote", cwd=lp.repo)
    assert launch.plan_launch(ctx(lp), "branchy", "R", {"branch": "feat/remote"})["branch_case"] == "remote"
    task = launch.launch(ctx(lp), "branchy", "R", {"branch": "feat/remote"})
    assert git("rev-parse", "--abbrev-ref", "feat/remote@{upstream}", cwd=task["worktree"]) == "origin/feat/remote"


def test_diverged_branch_stops(lp):
    push_branch(lp, "feat/div", "d.txt")
    git("switch", "feat/div", cwd=lp.repo)
    (lp.repo / "local.txt").write_text("l")
    commit_file(lp.repo, "local.txt", "local")
    git("switch", "main", cwd=lp.repo)
    seed = lp.work / "seed"
    git("fetch", "origin", cwd=seed)
    git("switch", "feat/div", cwd=seed)
    (seed / "remote.txt").write_text("r")
    commit_all(seed, "remote")
    git("push", "origin", "feat/div", cwd=seed)
    rep = launch.plan_launch(ctx(lp), "branchy", "D", {"branch": "feat/div"})
    assert not rep["ok"] and "diverged" in " ".join(rep["errors"])


def test_branch_in_other_worktree_stops(lp):
    launch.launch(ctx(lp), "branchy", "First", {"branch": "feat/used"})
    rep = launch.plan_launch(ctx(lp), "branchy", "Second", {"branch": "feat/used"})
    assert not rep["ok"] and "first" in " ".join(rep["errors"])


def test_failed_start_rolls_back_but_keeps_existing_branch(lp):
    push_branch(lp, "feat/keep", "k.txt")
    fake_config(lp.fdir, fail_start=True)
    with pytest.raises(FactoryError, match="fake adapter"):
        launch.launch(ctx(lp), "branchy", "Keep", {"branch": "feat/keep"})
    with pytest.raises(FactoryError, match="fake adapter"):
        launch.launch(ctx(lp), "branchy", "Gone", {"branch": "feat/created"})
    assert not (lp.worktrees / "keep").exists() and not (lp.fdir / "tasks" / "keep").exists()
    assert git("branch", "--list", "feat/keep", cwd=lp.repo)
    assert not git("branch", "--list", "feat/created", cwd=lp.repo)


def test_failure_after_start_closes_the_terminal(lp, monkeypatch):
    def broken_update(*args, **kwargs):
        raise FactoryError("disk full")
    monkeypatch.setattr(launch.state, "update", broken_update)
    with pytest.raises(FactoryError, match="disk full"):
        launch.launch(ctx(lp), "branchy", "Late", {"branch": "feat/late"})
    ops = [c["op"] for c in fake_calls(lp.fdir)]
    assert ops == ["start_session", "close"]
    assert not (lp.worktrees / "late").exists()
    assert not git("branch", "--list", "feat/late", cwd=lp.repo)


def test_create_worktree_listed_late_refused(lp):
    write_pipeline(lp.fdir, {"id": "late", "steps": ["work", "create-worktree"]})
    rep = launch.plan_launch(ctx(lp), "late", "L", {})
    assert not rep["ok"] and "not as the first step" in " ".join(rep["errors"])


def test_no_worktree_pipeline_uses_task_flag(lp):
    write_step(lp.fdir, "new-step", {})
    write_pipeline(lp.fdir, {"id": "new-step-assistant", "steps": ["new-step"]})
    task = launch.launch(ctx(lp), "new-step-assistant", "Make a step", {})
    call = fake_calls(lp.fdir)[0]
    assert call["in_worktree"] is False and call["cwd"] == str(lp.repo)
    assert f"--task {task['id']}" in call["prompt"]
    assert str(lp.library) in call["args"]
    r = lp.factory("next", check=False)
    assert r.returncode == 1 and "--task <id>" in r.stderr


def test_missing_input_and_config(lp):
    rep = launch.plan_launch(ctx(lp), "branchy", "M", {})
    assert rep["missing_inputs"] == ["branch"]
    lp.factory("config", "set", "create-worktree", "worktree_root", "")
    (lp.fdir / "config.yaml").write_text("{}\n")
    rep = launch.plan_launch(ctx(lp), "plain", "M", {})
    assert rep["missing_config"][0]["key"] == "worktree_root" and not rep["ok"]


def test_cli_dry_run_json(lp):
    rep = lp.factory.json("launch", "plain", "--description", "Cli task", "--dry-run")
    assert rep["task_id"] == "cli-task"
    out = lp.factory("launch", "plain", "--description", "Cli task").stdout
    assert "cli-task" in out
