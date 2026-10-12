import pytest
import yaml

from conftest import write_pipeline, write_step
from serverutil import info, request


@pytest.fixture
def ed(inited):
    write_step(inited.library, "gen", {"category": "git", "writes": ["x"]})
    write_step(inited.fdir, "loc", {"category": "review", "run_in": "subagent", "reads": ["x"]})
    write_step(inited.fdir, "box", {"type": "composite", "steps": ["gen", "loc"]}, body="")
    write_pipeline(inited.fdir, {"id": "base", "steps": ["gen", "loc"]})
    inited.factory("pipeline", "edit", "base")
    yield inited, info(inited.fdir)
    inited.factory("server", "stop", check=False)


def test_steps_list_and_detail(ed):
    inited, i = ed
    status, steps = request(i, "GET", "/api/steps")
    by_id = {s["id"]: s for s in steps}
    assert by_id["gen"]["level"] == "generic" and by_id["loc"]["run_in"] == "subagent"
    assert by_id["user-validation"]["level"] == "builtin"
    status, box = request(i, "GET", "/api/steps/box")
    assert box["children"] == ["gen", "loc"] and box["reads"] == [] and box["writes"] == ["x"]
    assert request(i, "GET", "/api/steps/nope")[0] == 400


def test_load_copy_check_save(ed):
    inited, i = ed
    status, loaded = request(i, "GET", "/api/pipelines/base")
    assert loaded["level"] == "local" and loaded["data"]["steps"] == ["gen", "loc"]
    status, copied = request(i, "POST", "/api/pipelines/copy", {"source": "base", "new_id": "base-copy"})
    data = copied["data"]
    assert data["id"] == "base-copy"
    data["steps"].insert(0, "create-worktree")
    data["steps"].append("create-worktree")
    status, problems = request(i, "POST", "/api/pipelines/check", {"data": data, "level": "generic"})
    assert any(p["level"] == "error" for p in problems)
    assert any("local step" in p["message"] for p in problems)
    assert request(i, "POST", "/api/pipelines/save", {"data": data, "level": "local"})[0] == 400
    data["steps"].pop()
    status, saved = request(i, "POST", "/api/pipelines/save", {"data": data, "level": "generic"})
    assert status == 200 and saved["library_commit"]["message"] == "Factory library: add pipeline base-copy"
    stored = yaml.safe_load((inited.library / "pipelines" / "base-copy.yaml").read_text())
    assert stored["steps"] == ["create-worktree", "gen", "loc"]


def test_cli_lists(ed):
    inited, i = ed
    ids = [p["id"] for p in inited.factory.json("pipeline", "list")]
    assert "base" in ids
    assert "gen" in [s["id"] for s in inited.factory.json("step", "list")]
