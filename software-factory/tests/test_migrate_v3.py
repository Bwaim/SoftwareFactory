import yaml

from conftest import commit_all
from test_migrate_v2 import set_version


def make_v2(inited, repo_text, lib_text):
    (inited.fdir / "pipelines").mkdir(exist_ok=True)
    (inited.library / "pipelines").mkdir(exist_ok=True)
    (inited.fdir / "pipelines" / "mine.yaml").write_text(repo_text)
    (inited.library / "pipelines" / "shared.yaml").write_text(lib_text)
    set_version(inited.fdir / "factory.yaml", 2)
    set_version(inited.library / "factory.yaml", 2)
    commit_all(inited.library.parent, "v2 library")


def version_of(path):
    return yaml.safe_load(path.read_text())["version"]


def test_adds_worktree_true(inited):
    make_v2(inited, "id: mine\ndescription: Mine\nsteps: []\n", "id: shared\ndescription: Shared\nsteps: []\n")
    out = inited.factory.json("migrate")
    assert out["errors"] == []
    for path in (inited.fdir / "pipelines" / "mine.yaml", inited.library / "pipelines" / "shared.yaml"):
        assert yaml.safe_load(path.read_text())["worktree"] is True
    assert version_of(inited.fdir / "factory.yaml") == 3
    assert version_of(inited.library / "factory.yaml") == 3


def test_keeps_existing_value(inited):
    text = "id: mine\ndescription: Mine\nworktree: false\nsteps: []\n"
    make_v2(inited, text, "id: shared\ndescription: Shared\nsteps: []\n")
    inited.factory("migrate")
    assert (inited.fdir / "pipelines" / "mine.yaml").read_text() == text


def test_migration_keeps_text(inited):
    old = "id: mine\n# keep me\nsteps: []"
    make_v2(inited, old, "id: shared\nsteps: []\n")
    inited.factory("migrate")
    assert (inited.fdir / "pipelines" / "mine.yaml").read_text() == old + "\nworktree: true\n"


def test_bad_value_blocks(inited):
    text = "id: mine\nworktree: \"yes\"\nsteps: []\n"
    make_v2(inited, text, "id: shared\nsteps: []\n")
    r = inited.factory("migrate", check=False)
    assert r.returncode == 1 and "`worktree` must be `true` or `false`." in r.stderr
    assert (inited.fdir / "pipelines" / "mine.yaml").read_text() == text
    assert version_of(inited.fdir / "factory.yaml") == 2
