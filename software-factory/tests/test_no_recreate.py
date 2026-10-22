import shutil

import pytest

from conftest import hook, make_task, silent
from factory import delete, events, repo, state
from factory.errors import FactoryError


def test_event_log_for_missing_task_writes_nothing(inited):
    ctx = repo.load_ctx(cwd=inited.repo)
    events.log(ctx, "ghost", "x")
    assert not (inited.fdir / "tasks" / "ghost").exists()


def test_state_update_after_folder_removed_raises(inited):
    ctx = repo.load_ctx(cwd=inited.repo)
    make_task(ctx, "t1")
    folder = inited.fdir / "tasks" / "t1"

    def move_away(task):
        shutil.move(str(folder), str(inited.work / "moved"))

    with pytest.raises(FactoryError, match="Unknown task"):
        state.update(ctx, "t1", move_away)
    assert not folder.exists()


def test_stop_hook_and_poll_after_delete_do_not_recreate(inited):
    ctx = repo.load_ctx(cwd=inited.repo)
    make_task(ctx, "t1", session_id="sid-1")
    delete.delete(ctx, "t1")
    silent(hook(inited, "stop", {"session_id": "sid-1", "last_assistant_message": "hi"}))
    inited.factory("poll", "--task", "t1", check=False)
    assert not (inited.fdir / "tasks" / "t1").exists()
