from pathlib import Path

import pytest
import yaml

from conftest import git, make_task, task_json, write_pipeline, write_step
from factory import catalog, hidden, repo
from factory.registry import Registry, all_pipeline_files


@pytest.fixture
def ctx(inited):
    return repo.load_ctx(cwd=inited.repo)


def set_hidden(inited, ids):
    p = inited.fdir / "factory.yaml"
    data = yaml.safe_load(p.read_text())
    data["hidden_steps"] = ids
    p.write_text(yaml.safe_dump(data, sort_keys=False))


def test_registry_keeps_every_level(inited, ctx):
    write_step(inited.library, "dup", {"description": "generic one"})
    write_step(inited.fdir, "dup", {"description": "local one"})
    reg = Registry.load(ctx)
    assert [s.level for s in reg.variants["dup"]] == ["generic", "local"]
    assert reg.steps["dup"] is reg.variants["dup"][-1]
    assert [s.level for s in reg.variants["user-validation"]] == ["builtin"]


def test_all_pipeline_files_includes_overridden(inited, ctx):
    write_pipeline(inited.library, {"id": "same", "steps": ["a"]})
    write_pipeline(inited.fdir, {"id": "same", "steps": ["b"]})
    found = [(level, pid) for level, pid, _ in all_pipeline_files(ctx) if pid == "same"]
    assert found == [("generic", "same"), ("local", "same")]


def test_hidden_ids_and_discard(inited, ctx):
    assert hidden.ids(ctx) == []
    set_hidden(inited, ["a", "b"])
    assert hidden.ids(ctx) == ["a", "b"]
    hidden.discard(ctx, "a")
    assert hidden.ids(ctx) == ["b"]
    hidden.discard(ctx, "b")
    assert "hidden_steps" not in yaml.safe_load((inited.fdir / "factory.yaml").read_text())
    before = (inited.fdir / "factory.yaml").read_text()
    hidden.discard(ctx, "zzz")
    assert (inited.fdir / "factory.yaml").read_text() == before
