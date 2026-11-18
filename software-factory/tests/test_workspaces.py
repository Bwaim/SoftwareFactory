import pytest

from conftest import git
from factory import workspaces
from factory.errors import FactoryError


def test_home_uses_env(factory_home):
    assert workspaces.home() == factory_home


def test_slug_rules():
    assert workspaces.slug("SoftwareFactory") == "softwarefactory"
    assert workspaces.slug("My Repo_2") == "my-repo-2"
    assert workspaces.slug("--x--") == "x"
    assert workspaces.slug("ééé") == "workspace"
    assert len(workspaces.slug("a" * 50)) == 32


def test_add_and_list(origin_repo):
    entry = workspaces.add(origin_repo)
    assert entry == {"id": "repo", "name": "repo", "path": str(origin_repo)}
    assert workspaces.list_all() == [entry]
    assert workspaces.get("repo") == entry
    assert workspaces.get("nope") is None


def test_same_folder_name_gets_suffix(origin_repo, work):
    workspaces.add(origin_repo)
    other = work / "other" / "repo"
    other.mkdir(parents=True)
    git("init", "-b", "main", cwd=other)
    assert workspaces.add(other)["id"] == "repo-2"


def test_worktree_path_resolves_to_main(origin_repo, work):
    git("commit", "--allow-empty", "-m", "x", cwd=origin_repo)
    wt = work / "wt"
    git("worktree", "add", "-b", "feat", str(wt), cwd=origin_repo)
    assert workspaces.resolve_main(str(wt)) == origin_repo
    workspaces.add(origin_repo)
    with pytest.raises(FactoryError, match="repo"):
        workspaces.add(workspaces.resolve_main(str(wt)))


def test_resolve_main_refuses_missing_and_non_git(tmp_path):
    with pytest.raises(FactoryError):
        workspaces.resolve_main(str(tmp_path / "missing"))
    plain = tmp_path / "plain"
    plain.mkdir()
    with pytest.raises(FactoryError):
        workspaces.resolve_main(str(plain))


def test_rename_rules(origin_repo):
    workspaces.add(origin_repo)
    assert workspaces.rename("repo", "  New  ")["name"] == "New"
    for bad in ("", "   ", "a" * 65):
        with pytest.raises(FactoryError):
            workspaces.rename("repo", bad)
    with pytest.raises(FactoryError):
        workspaces.rename("nope", "x")
    assert workspaces.get("repo")["id"] == "repo"


def test_remove_and_register(origin_repo):
    workspaces.add(origin_repo)
    assert workspaces.remove("repo")["id"] == "repo"
    assert workspaces.list_all() == []
    with pytest.raises(FactoryError):
        workspaces.remove("repo")
    first = workspaces.register(origin_repo)
    assert workspaces.register(origin_repo) == first
    assert len(workspaces.list_all()) == 1
    assert workspaces.mtime() is not None


def test_mtime_missing():
    assert workspaces.mtime() is None
