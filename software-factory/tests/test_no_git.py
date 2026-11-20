import pytest

from conftest import make_task
from factory import init, library, repo, workspaces
from factory.errors import FactoryError


def test_git_missing_error(no_git, tmp_path):
    with pytest.raises(FactoryError, match="not installed") as e:
        repo.git(["status"], tmp_path, check=False)
    assert str(e.value) == repo.GIT_MISSING
    assert repo.git_installed() is False
    assert repo.in_git(tmp_path) is False
    assert repo.has_origin(tmp_path) is False


def test_plain_root_lookup(plain):
    deep = plain / "a" / "b"
    deep.mkdir(parents=True)
    assert repo.main_repo(deep) == plain
    assert repo.load_ctx(plain).git is False


def test_plain_root_without_factory(tmp_path):
    assert repo.main_repo(tmp_path) == tmp_path.resolve()


def test_git_wins_over_factory_folder(origin_repo):
    nested = origin_repo / "notes" / ".factory"
    nested.mkdir(parents=True)
    (nested / "factory.yaml").write_text("{}\n")
    assert repo.main_repo(origin_repo / "notes") == origin_repo.resolve()


def test_plain_init(plain):
    assert (plain / ".factory" / "factory.yaml").exists()
    assert not (plain / ".git").exists()
    check = next(c for c in repo.load_ctx(plain) and init.prerequisites(plain) if c["name"] == "git")
    assert check == {"name": "git", "ok": True, "message": init.PLAIN_MESSAGE}


def test_plain_init_without_git_program(no_git, work, monkeypatch):
    monkeypatch.setenv("FACTORY_TERMINAL", "fake")
    monkeypatch.setenv("FACTORY_NO_OPEN", "1")
    path = work / "plain"
    path.mkdir()
    report = init.init(path)
    assert (path / ".factory" / "factory.yaml").exists()
    assert not (path / ".git").exists()
    check = next(c for c in report["checks"] if c["name"] == "git")
    assert check == {"name": "git", "ok": True, "message": init.PLAIN_MESSAGE}


def test_task_lookup_plain(plain, monkeypatch):
    monkeypatch.delenv("FACTORY_TASK", raising=False)
    ctx = repo.load_ctx(plain)
    with pytest.raises(FactoryError, match="Cannot find the task"):
        repo.current_task_id(ctx)
    make_task(ctx, "t1")
    monkeypatch.setenv("FACTORY_TASK", "t1")
    assert repo.current_task_id(ctx) == "t1"


def test_library_not_in_git(no_git, tmp_path):
    assert library.in_git(tmp_path) is False


def test_workspace_add_plain(plain):
    assert workspaces.resolve_main(str(plain)) == plain
