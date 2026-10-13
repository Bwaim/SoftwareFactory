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
    data = {"id": "ok", "inputs": {"ticket_in": {"description": "t"}}, "steps": ["a", "b"]}
    assert check(reg, data, COLUMNS) == []


def test_cli_pipeline_check(inited):
    write_pipeline(inited.fdir, {"id": "bad", "steps": [{"id": "nope"}]})
    r = inited.factory("pipeline", "check", "bad", check=False)
    assert r.returncode == 1
    assert "does not exist" in r.stdout
