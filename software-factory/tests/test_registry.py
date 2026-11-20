import pytest

from conftest import write_pipeline, write_step
from factory import repo
from factory.errors import FactoryError
from factory.registry import Registry


def ctx_of(inited):
    return repo.load_ctx(cwd=inited.repo)


def test_local_overrides_generic_overrides_builtin(inited):
    write_step(inited.library, "user-validation", {"description": "generic"})
    reg = Registry.load(ctx_of(inited))
    assert reg.step("user-validation").level == "generic"
    write_step(inited.fdir, "user-validation", {"description": "local"})
    reg = Registry.load(ctx_of(inited))
    assert reg.step("user-validation").level == "local"
    assert reg.step("user-validation").description == "local"


def test_group_paths_uses_and_outputs(inited):
    from factory import keys
    write_step(inited.fdir, "rebase", {"outputs": {"rebased": {"type": "text", "description": "r"}}}, body="Rebase {{base}}.\n")
    write_step(inited.fdir, "commit", {"outputs": {"sha": {"type": "text", "description": "s"}}}, body="Commit {{rebased}} with {{msg}}.\n")
    write_step(inited.fdir, "rebase-and-commit", {"type": "group", "steps": ["rebase", "commit"]}, body="")
    reg = Registry.load(ctx_of(inited))
    assert reg.leaves("rebase-and-commit") == [["rebase-and-commit", "rebase"], ["rebase-and-commit", "commit"]]
    assert keys.step_uses(reg, "rebase-and-commit") == ["base", "msg"]
    assert list(keys.step_outputs(reg, "rebase-and-commit")) == ["rebased", "sha"]


def test_group_loop_refused(inited):
    write_step(inited.fdir, "a", {"type": "group", "steps": ["b"]}, body="")
    write_step(inited.fdir, "b", {"type": "group", "steps": ["a"]}, body="")
    with pytest.raises(FactoryError, match="loop"):
        Registry.load(ctx_of(inited))


def test_invalid_step_stops_the_load_with_its_file(inited):
    path = write_step(inited.fdir, "bad", {"type": "command"}, body="echo {{x}}\n")
    with pytest.raises(FactoryError) as e:
        Registry.load(ctx_of(inited))
    assert str(path) in str(e.value) and "A command cannot use" in str(e.value)


def test_expand_always_adds_create_worktree(inited):
    write_step(inited.fdir, "only", {})
    write_pipeline(inited.fdir, {"id": "solo", "steps": ["only"]})
    reg = Registry.load(ctx_of(inited))
    assert [e["id"] for e in reg.expand(reg.pipeline("solo"))] == ["create-worktree", "only"]


def test_expand_adds_create_worktree_and_overrides(inited):
    write_step(inited.fdir, "s1", {"model": "haiku"})
    write_pipeline(inited.fdir, {"id": "p1", "steps": [{"id": "s1", "model": "opus", "column": "Plan", "with": {"k": 1}}]})
    reg = Registry.load(ctx_of(inited))
    snap = reg.expand(reg.pipeline("p1"))
    assert [e["id"] for e in snap] == ["create-worktree", "s1"]
    assert snap[1] == {"id": "s1", "path": ["s1"], "with": {"k": 1}, "column": "Plan", "model": "opus", "effort": None}


def test_expand_folder_pipeline(inited):
    write_step(inited.fdir, "only", {})
    write_pipeline(inited.fdir, {"id": "solo", "worktree": False, "steps": ["only"]})
    reg = Registry.load(ctx_of(inited))
    assert [e["id"] for e in reg.expand(reg.pipeline("solo"))] == ["only"]


def test_expand_worktree_pipeline(inited):
    write_step(inited.fdir, "only", {})
    write_pipeline(inited.fdir, {"id": "solo", "worktree": True, "steps": ["only"]})
    reg = Registry.load(ctx_of(inited))
    assert [e["id"] for e in reg.expand(reg.pipeline("solo"))] == ["create-worktree", "only"]
