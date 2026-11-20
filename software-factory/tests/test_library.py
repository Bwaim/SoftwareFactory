import pytest
import yaml

from conftest import git
from factory import library, repo
from factory.errors import FactoryError


def test_commit_only_given_files(inited):
    root = inited.library.parent
    git("add", "-A", cwd=root)
    git("commit", "-m", "library", cwd=root)
    (inited.library / "steps" / "a.md").write_text("a\n")
    (root / "other.txt").write_text("staged change\n")
    git("add", "other.txt", cwd=root)
    msg = library.message("add", "step", "a")
    assert msg == "Factory library: add step a"
    inited.factory("library", "commit", msg, inited.library / "steps" / "a.md")
    assert git("log", "-1", "--format=%s", cwd=root) == msg
    assert git("show", "--name-only", "--format=", "HEAD", cwd=root) == "factory-library/steps/a.md"
    assert git("diff", "--cached", "--name-only", cwd=root) == "other.txt"


def test_refuses_paths_outside_library(inited, work):
    with pytest.raises(FactoryError, match="library"):
        library.commit(repo.load_ctx(cwd=inited.repo), "x", [str(work / "x.txt")])


def test_disabled_without_git(inited, work, monkeypatch):
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(work))
    lib = work / "plain-lib"
    lib.mkdir()
    data = yaml.safe_load((inited.fdir / "factory.yaml").read_text())
    data["library"] = str(lib)
    (inited.fdir / "factory.yaml").write_text(yaml.safe_dump(data))
    (lib / "s.md").write_text("x")
    assert not library.in_git(lib)
    with pytest.raises(FactoryError, match="disabled"):
        library.commit(repo.load_ctx(cwd=inited.repo), "x", [str(lib / "s.md")])


def test_commit_adds_new_library_factory_yaml(inited):
    root = inited.library.parent
    (inited.library / "steps" / "a.md").write_text("a\n")
    inited.factory("library", "commit", "Factory library: add step a", inited.library / "steps" / "a.md")
    committed = git("show", "--name-only", "--format=", "HEAD", cwd=root).splitlines()
    assert sorted(committed) == ["factory-library/factory.yaml", "factory-library/steps/a.md"]
    assert git("status", "--porcelain", "--", "factory-library/factory.yaml", cwd=root) == ""


def test_commit_adds_changed_library_factory_yaml(inited):
    root = inited.library.parent
    git("add", "-A", cwd=root)
    git("commit", "-m", "library", cwd=root)
    (inited.library / "factory.yaml").write_text("version: 2\n")
    (inited.library / "steps" / "b.md").write_text("b\n")
    inited.factory("library", "commit", "Factory library: add step b", inited.library / "steps" / "b.md")
    committed = git("show", "--name-only", "--format=", "HEAD", cwd=root).splitlines()
    assert sorted(committed) == ["factory-library/factory.yaml", "factory-library/steps/b.md"]


def test_in_git_none():
    assert library.in_git(None) is False
