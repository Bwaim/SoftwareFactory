import pytest

from conftest import make_task, write_step
from factory import config, events, repo, state
from factory.errors import FactoryError
from factory.registry import Registry


def test_config_order(inited):
    write_step(inited.fdir, "s", {"config": {"a": {"description": "A", "default": "def"}, "b": {"description": "B"}, "c": {"description": "C", "default": 1}}})
    ctx = repo.load_ctx(cwd=inited.repo)
    step = Registry.load(ctx).step("s")
    config.set_value(ctx, "s", "c", "saved")
    values, missing = config.resolve(ctx, step, {"c": "with"})
    assert values == {"a": "def", "c": "with"}
    assert missing == ["b"]
    values, _ = config.resolve(ctx, step, {})
    assert values["c"] == "saved"


def test_cli_config_set_get(inited):
    inited.factory("config", "set", "s", "k", "v 1")
    assert inited.factory("config", "get", "s", "k").stdout.strip() == "v 1"


def test_state_set_get_and_artifact_path(inited):
    ctx = repo.load_ctx(cwd=inited.repo)
    make_task(ctx)
    inited.factory("state", "set", "plan", "/x/plan.md", "--task", "t1")
    assert inited.factory("state", "get", "plan", "--task", "t1").stdout.strip() == "/x/plan.md"
    r = inited.factory("state", "get", "nope", "--task", "t1", check=False)
    assert r.returncode == 1
    p = inited.factory("artifact", "path", "spec.md", "--task", "t1").stdout.strip()
    assert p == str((inited.fdir / "tasks" / "t1" / "artifacts" / "spec.md").resolve())


def test_artifact_name_must_be_simple(inited):
    ctx = repo.load_ctx(cwd=inited.repo)
    make_task(ctx)
    with pytest.raises(FactoryError):
        state.artifact_path(ctx, "t1", "../x")


def test_events_append(inited):
    ctx = repo.load_ctx(cwd=inited.repo)
    make_task(ctx)
    events.log(ctx, "t1", "step_started", "s", run_in="session")
    assert events.read(ctx, "t1")[0]["type"] == "step_started"
    assert events.read(ctx, "t1")[0]["run_in"] == "session"
