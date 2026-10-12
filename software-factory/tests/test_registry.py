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


def test_composite_paths_and_io(inited):
    write_step(inited.fdir, "rebase", {"reads": ["base"], "writes": ["rebased"]})
    write_step(inited.fdir, "commit", {"reads": ["rebased", "msg"], "writes": ["sha"]})
    write_step(inited.fdir, "rebase-and-commit", {"type": "composite", "steps": ["rebase", "commit"]}, body="")
    reg = Registry.load(ctx_of(inited))
    assert reg.leaves("rebase-and-commit") == [["rebase-and-commit", "rebase"], ["rebase-and-commit", "commit"]]
    assert reg.io("rebase-and-commit") == (["base", "msg"], ["rebased", "sha"])


def test_composite_loop_refused(inited):
    write_step(inited.fdir, "a", {"type": "composite", "steps": ["b"]}, body="")
    write_step(inited.fdir, "b", {"type": "composite", "steps": ["a"]}, body="")
    with pytest.raises(FactoryError, match="loop"):
        Registry.load(ctx_of(inited))


def test_expand_adds_create_worktree_and_overrides(inited):
    write_step(inited.fdir, "s1", {"model": "haiku"})
    write_pipeline(inited.fdir, {"id": "p1", "steps": [{"id": "s1", "model": "opus", "column": "Plan", "with": {"k": 1}}]})
    reg = Registry.load(ctx_of(inited))
    snap = reg.expand(reg.pipeline("p1"))
    assert [e["id"] for e in snap] == ["create-worktree", "s1"]
    assert snap[1] == {"id": "s1", "path": ["s1"], "with": {"k": 1}, "column": "Plan", "model": "opus", "effort": None}
