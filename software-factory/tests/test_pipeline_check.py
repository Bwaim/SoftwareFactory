from conftest import write_pipeline, write_step
from factory import repo
from factory.pipeline_check import check
from factory.registry import Registry

COLUMNS = ["Discovery", "Plan"]


def msgs(problems, level):
    return [p.message for p in problems if p.level == level]


def test_each_problem_type(inited):
    write_step(inited.fdir, "local-step", {"column": "Nowhere"}, body="Use {{nothing}}.\n")
    write_step(inited.fdir, "sess", {})
    reg = Registry.load(repo.load_ctx(cwd=inited.repo))
    data = {
        "id": "p",
        "steps": [
            {"id": "sess", "model": "opus"},
            {"id": "create-worktree"},
            {"id": "missing"},
            {"id": "local-step"},
        ],
    }
    problems = check(reg, data, COLUMNS, save_level="generic")
    errors = " | ".join(msgs(problems, "error"))
    warnings = " | ".join(msgs(problems, "warning"))
    assert "`create-worktree` is listed, but not as the first step" in errors
    assert "`missing` does not exist" in errors
    assert "column `Nowhere`" in errors
    assert "uses the local step `local-step`" in warnings
    assert "uses `nothing`, which no input" in warnings
    assert "runs in the session" in warnings


def test_valid_pipeline_has_no_problem(inited):
    write_step(inited.fdir, "a", {"outputs": {"x": {"type": "text", "description": "x"}}})
    write_step(inited.fdir, "b", {}, body="Use {{x}} and {{ticket_in}}.\n")
    reg = Registry.load(repo.load_ctx(cwd=inited.repo))
    data = {"id": "ok", "worktree": True, "inputs": {"ticket_in": {"description": "t"}}, "steps": ["a", "b"]}
    assert check(reg, data, COLUMNS) == []


def test_cli_pipeline_check(inited):
    write_pipeline(inited.fdir, {"id": "bad", "steps": [{"id": "nope"}]})
    r = inited.factory("pipeline", "check", "bad", check=False)
    assert r.returncode == 1
    assert "does not exist" in r.stdout


def folder(**extra):
    return {"id": "f", "worktree": False, "steps": ["a"], **extra}


def test_worktree_missing(inited):
    write_step(inited.fdir, "a", {})
    reg = Registry.load(repo.load_ctx(cwd=inited.repo))
    problems = check(reg, {"id": "f", "steps": ["a"]}, COLUMNS)
    assert msgs(problems, "error") == ["The pipeline has no `worktree` key. Set `worktree: true` or `worktree: false`."]


def test_worktree_not_bool(inited):
    write_step(inited.fdir, "a", {})
    reg = Registry.load(repo.load_ctx(cwd=inited.repo))
    problems = check(reg, {"id": "f", "worktree": "yes", "steps": ["a"]}, COLUMNS)
    assert msgs(problems, "error") == ["`worktree` must be `true` or `false`."]


def test_folder_with_create_worktree(inited):
    write_step(inited.fdir, "a", {})
    reg = Registry.load(repo.load_ctx(cwd=inited.repo))
    problems = check(reg, folder(steps=["create-worktree", "a"]), COLUMNS)
    assert msgs(problems, "error") == ["`create-worktree` cannot be in a pipeline with `worktree: false`."]


def test_folder_with_branch_input(inited):
    write_step(inited.fdir, "a", {})
    reg = Registry.load(repo.load_ctx(cwd=inited.repo))
    problems = check(reg, folder(inputs={"branch": {"type": "text"}}), COLUMNS)
    assert msgs(problems, "error") == ["A pipeline with `worktree: false` cannot have a `branch` input."]


def test_folder_git_step_warns(inited):
    write_step(inited.fdir, "a", {"category": "git"})
    reg = Registry.load(repo.load_ctx(cwd=inited.repo))
    problems = check(reg, folder(), COLUMNS)
    assert msgs(problems, "error") == []
    assert msgs(problems, "warning") == ["The step `a` is a git step, and the pipeline has `worktree: false`."]


def test_git_step_in_group_warns(inited):
    write_step(inited.fdir, "a", {"category": "git"})
    write_step(inited.fdir, "g", {"type": "group", "steps": ["a"]}, body="")
    reg = Registry.load(repo.load_ctx(cwd=inited.repo))
    problems = check(reg, folder(steps=["g"]), COLUMNS)
    assert msgs(problems, "warning") == ["The step `a` is a git step, and the pipeline has `worktree: false`."]


def test_worktree_pipeline_no_warning(inited):
    write_step(inited.fdir, "a", {"category": "git"})
    reg = Registry.load(repo.load_ctx(cwd=inited.repo))
    assert check(reg, {"id": "w", "worktree": True, "steps": ["a"]}, COLUMNS) == []


def test_shipped_pipelines_values(inited):
    inited.factory("catalog", "install", "plan-and-build", "--local", "--with-steps")
    reg = Registry.load(repo.load_ctx(cwd=inited.repo))
    assert reg.pipeline("quick-task").worktree is False
    assert reg.pipeline("plan-and-build").worktree is True
    columns = repo.load_ctx(cwd=inited.repo).columns()
    for pid in ("quick-task", "plan-and-build"):
        assert msgs(check(reg, reg.pipeline(pid).data, columns), "error") == []
