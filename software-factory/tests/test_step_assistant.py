import pytest

from conftest import make_task, task_from_pipeline, write_pipeline, write_step
from factory import repo, session
from factory.errors import FactoryError
from factory.registry import Registry


def test_assistant_pipeline_and_step_do_not_exist(inited):
    reg = Registry.load(repo.load_ctx(cwd=inited.repo))
    assert "new-step-assistant" not in reg.pipelines and "new-step" not in reg.steps


def test_next_never_prints_task_flag(inited):
    write_step(inited.fdir, "s", {"done_when": "Done."}, body="Run `factory status` first.\n")
    write_pipeline(inited.fdir, {"id": "p", "steps": ["s"]})
    task_from_pipeline(inited, "p")
    assert "--task" not in inited.factory("next", "--task", "t1").stdout


def test_task_without_worktree_cannot_start(inited):
    ctx = repo.load_ctx(cwd=inited.repo)
    task = make_task(ctx, tid="nowt")
    with pytest.raises(FactoryError, match="has no worktree"):
        session.start(ctx, task, "hi")
