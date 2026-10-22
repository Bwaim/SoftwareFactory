import pytest

from conftest import fake_config, git, write_pipeline, write_step
from factory import delete, launch, repo, state
from factory.errors import FactoryError


@pytest.fixture
def started(inited):
    write_step(inited.fdir, "work", {})
    write_pipeline(inited.fdir, {"id": "branchy", "inputs": {"branch": {"description": "b"}}, "steps": ["work"]})
    ctx = repo.load_ctx(cwd=inited.repo)
    task = launch.launch(ctx, "branchy", "Del me", {"branch": "feat/del"})
    return inited, ctx, task


def test_close_failure_changes_nothing(started):
    inited, ctx, task = started
    fake_config(inited.fdir, fail_close=True)
    with pytest.raises(FactoryError, match="failed to close"):
        delete.delete(ctx, task["id"], confirm_unpushed=True)
    assert (inited.worktrees / task["id"]).exists()
    assert git("branch", "--list", "feat/del", cwd=inited.repo)
    assert (inited.fdir / "tasks" / task["id"] / "task.json").exists()
    assert "task_deleted" not in (inited.fdir / "tasks" / task["id"] / "events.jsonl").read_text()


def test_gone_terminal_is_success(started):
    inited, ctx, task = started
    fake_config(inited.fdir, states={task["terminal_handle"]["agent"]: "gone"})
    delete.delete(ctx, task["id"], confirm_unpushed=True)
    assert (inited.fdir / "tasks" / "archive" / task["id"] / "task.json").exists()


def test_branch_delete_failure_still_archives(started):
    inited, ctx, task = started
    git("push", "-u", "origin", "feat/del", cwd=task["worktree"])
    lock = inited.repo / ".git" / "refs" / "heads" / "feat" / "del.lock"
    lock.write_text("")
    try:
        with pytest.raises(delete.RemovalIncomplete) as e:
            delete.delete(ctx, task["id"])
    finally:
        lock.unlink()
    assert str(e.value).startswith(f"Task {task['id']} deleted and archived, but some parts are left:")
    assert e.value.details["archived"] is True
    assert any(item.startswith("The branch feat/del was not deleted:") for item in e.value.details["left"])
    assert (inited.fdir / "tasks" / "archive" / task["id"] / "task.json").exists()
    assert not (inited.fdir / "tasks" / task["id"]).exists()
