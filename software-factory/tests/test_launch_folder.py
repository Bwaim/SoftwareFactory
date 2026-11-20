import json

import pytest

from conftest import fake_calls, git, make_task, task_json, write_pipeline, write_step
from factory import launch, registry, repo, session
from factory.errors import FactoryError


def folder_pipeline(fdir, pid="folder"):
    write_step(fdir, "work", {})
    write_pipeline(fdir, {"id": pid, "steps": ["work"], "worktree": False})


def test_folder_launch_in_git_workspace(inited):
    folder_pipeline(inited.fdir)
    out = inited.factory.json("launch", "folder", "--description", "Do it")
    tid = out["id"]
    task = task_json(inited.fdir, tid)
    assert task["worktree"] is None and task["position"] == 0
    assert git("worktree", "list", cwd=inited.repo).count("\n") == 0
    assert fake_calls(inited.fdir)[0]["cwd"] == str(inited.repo)


def test_folder_launch_plain(plain, no_git):
    folder_pipeline(plain / ".factory")
    ctx = repo.load_ctx(cwd=plain)
    task = launch.launch(ctx, "folder", "Do it", {})
    assert task["worktree"] is None and task["position"] == 0
    assert fake_calls(plain / ".factory")[0]["cwd"] == str(plain)


def test_worktree_pipeline_in_plain_fails(plain):
    write_step(plain / ".factory", "work", {})
    write_pipeline(plain / ".factory", {"id": "wt", "steps": ["work"]})
    report = launch.plan_launch(repo.load_ctx(cwd=plain), "wt", "Do it", {})
    assert registry.NEEDS_GIT.format(id="wt") in report["errors"]


def test_task_settings_env(inited):
    folder_pipeline(inited.fdir)
    shared = inited.fdir / "claude-settings.json"
    shared.write_text(json.dumps({"permissions": {"allow": ["Bash(ls)"]}, "env": {"KEEP": "1"}}))
    ctx = repo.load_ctx(cwd=inited.repo)
    task = launch.launch(ctx, "folder", "Do it", {})
    path = session.task_settings_path(ctx, task)
    data = json.loads(path.read_text())
    assert data["env"] == {"KEEP": "1", "FACTORY_TASK": task["id"]}
    assert data["permissions"] == {"allow": ["Bash(ls)"]}
    shared.write_text(json.dumps({"permissions": {"allow": ["Bash(pwd)"]}}))
    session.start(ctx, task, "hi", resume=True)
    data = json.loads(path.read_text())
    assert data["permissions"] == {"allow": ["Bash(pwd)"]}
    assert data["env"] == {"FACTORY_TASK": task["id"]}


def test_missing_worktree_key_in_plain_gives_check_error(plain, no_git):
    write_step(plain / ".factory", "work", {})
    path = write_pipeline(plain / ".factory", {"id": "nokey", "steps": ["work"]})
    path.write_text(path.read_text().replace("worktree: true\n", ""))
    report = launch.plan_launch(repo.load_ctx(cwd=plain), "nokey", "Do it", {})
    assert report["errors"] == ["The pipeline has no `worktree` key. Set `worktree: true` or `worktree: false`."]
    assert report["missing_config"] == []


@pytest.mark.parametrize("text, message", [
    ("{not json", "is not valid JSON"),
    ("[1, 2]", "must hold a JSON object"),
    ('{"env": ["A"]}', "`env` must be a JSON object"),
])
def test_bad_shared_settings_raise_clear_error(inited, text, message):
    shared = inited.fdir / "claude-settings.json"
    shared.write_text(text)
    with pytest.raises(FactoryError, match=message) as e:
        session.write_task_settings(repo.load_ctx(cwd=inited.repo), {"id": "t1"})
    assert str(shared) in str(e.value)


def test_missing_worktree_folder(inited):
    ctx = repo.load_ctx(cwd=inited.repo)
    gone = inited.work / "gone"
    task = make_task(ctx, tid="lost", worktree=str(gone))
    with pytest.raises(FactoryError) as e:
        session.start(ctx, task, "hi")
    assert str(e.value) == f"The worktree {gone} of task lost does not exist."


def test_worktree_task_resume_unchanged(inited):
    write_step(inited.fdir, "work", {})
    write_pipeline(inited.fdir, {"id": "wt", "steps": ["work"]})
    ctx = repo.load_ctx(cwd=inited.repo)
    task = launch.launch(ctx, "wt", "Do it", {})
    session.start(ctx, task, "hi", resume=True)
    assert fake_calls(inited.fdir)[-1]["cwd"] == task["worktree"]
