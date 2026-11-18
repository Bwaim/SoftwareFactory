import pytest
import yaml

from conftest import git
from factory import repo, version
from factory.errors import FactoryError


def test_main_repo_from_worktree(origin_repo, work):
    wt = work / "wt1"
    git("worktree", "add", "--detach", str(wt), cwd=origin_repo)
    assert repo.main_repo(wt) == origin_repo.resolve()


def test_current_task_matches_symlinked_path(origin_repo, work, tmp_path):
    wt = work / "wt2"
    git("worktree", "add", "--detach", str(wt), cwd=origin_repo)
    tdir = origin_repo / ".factory" / "tasks" / "t1"
    tdir.mkdir(parents=True)
    (tdir / "task.json").write_text('{"id": "t1", "worktree": "%s"}' % wt)
    link = tmp_path / "link"
    link.symlink_to(wt)
    ctx = repo.load_ctx(cwd=link)
    assert repo.current_task_id(ctx) == "t1"


def test_unknown_task_says_add_task(origin_repo):
    (origin_repo / ".factory" / "tasks").mkdir(parents=True)
    ctx = repo.load_ctx(cwd=origin_repo)
    with pytest.raises(FactoryError, match="--task <id>"):
        repo.current_task_id(ctx)


def test_factory_task_env(origin_repo, monkeypatch):
    tdir = origin_repo / ".factory" / "tasks" / "t9"
    tdir.mkdir(parents=True)
    (tdir / "task.json").write_text('{"id": "t9", "worktree": null}')
    monkeypatch.setenv("FACTORY_TASK", "t9")
    assert repo.current_task_id(repo.load_ctx(cwd=origin_repo)) == "t9"


def test_version_mismatch_refused(origin_repo):
    f = origin_repo / ".factory"
    f.mkdir()
    (f / "factory.yaml").write_text(yaml.safe_dump({"version": 1}))
    with pytest.raises(FactoryError, match="version"):
        version.require_repo(repo.load_ctx(cwd=origin_repo))


def test_version_report_states(origin_repo):
    f = origin_repo / ".factory"
    f.mkdir()
    (f / "factory.yaml").write_text(yaml.safe_dump({"version": 2}))
    assert version.report(repo.load_ctx(cwd=origin_repo))["state"] == "same"


def test_not_initialized_names_init(origin_repo):
    ctx = repo.load_ctx(cwd=origin_repo)
    with pytest.raises(FactoryError) as e:
        version.require_repo(ctx)
    assert str(e.value) == "The factory is not initialized in this repository. Run `factory init`."


def test_old_repo_names_migrate(origin_repo):
    fdir = origin_repo / ".factory"
    fdir.mkdir()
    (fdir / "factory.yaml").write_text(yaml.safe_dump({"version": 1}))
    with pytest.raises(FactoryError) as e:
        version.require_repo(repo.load_ctx(cwd=origin_repo))
    assert str(e.value).endswith("Run `factory migrate`, or run the install script again to update the factory.")


def test_old_library_names_migrate(tmp_path):
    (tmp_path / "factory.yaml").write_text(yaml.safe_dump({"version": 1}))
    with pytest.raises(FactoryError) as e:
        version.require_library(tmp_path)
    assert str(e.value).endswith("Run `factory migrate`, or run the install script again to update the factory.")
