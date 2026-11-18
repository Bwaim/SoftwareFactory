import json

import pytest
import yaml

from conftest import git, make_task
from factory import migrate, repo

SCRIPT = '''
from pathlib import Path
def migrate_repo(factory_dir):
    (Path(factory_dir) / "migrated-repo.txt").write_text("ok")
def migrate_library(library_dir):
    (Path(library_dir) / "migrated-lib.txt").write_text("ok")
'''


def set_version(path, v):
    data = yaml.safe_load(path.read_text())
    data["version"] = v
    path.write_text(yaml.safe_dump(data))


@pytest.fixture
def v2(inited, work):
    mdir = work / "migrations"
    mdir.mkdir()
    (mdir / "1-to-2.py").write_text(SCRIPT)
    set_version(inited.library / "factory.yaml", 1)
    git("add", "-A", cwd=inited.library.parent)
    git("commit", "-m", "library", cwd=inited.library.parent)
    set_version(inited.fdir / "factory.yaml", 1)
    make_task(repo.load_ctx(cwd=inited.repo), tid="t1")
    env = {"FACTORY_MIGRATIONS_DIR": str(mdir)}
    return inited, env


def test_older_refused_then_migrated(v2):
    inited, env = v2
    assert inited.factory.json("version", "check", env=env)["state"] == "older"
    r = inited.factory("tasks", env=env, check=False)
    assert r.returncode == 1 and "version" in r.stderr
    out = inited.factory.json("migrate", env=env)
    assert len(out["backups"]) == 1 and (inited.repo / out["backups"][0].split("/")[-1]).exists()
    assert yaml.safe_load((inited.fdir / "factory.yaml").read_text())["version"] == 2
    assert yaml.safe_load((inited.library / "factory.yaml").read_text())["version"] == 2
    assert (inited.fdir / "migrated-repo.txt").exists() and (inited.library / "migrated-lib.txt").exists()
    assert out["library_commit"]["message"] == "Factory library: migrate to version 2"
    log = (inited.fdir / "tasks" / "t1" / "events.jsonl").read_text().splitlines()
    assert json.loads(log[-1])["type"] == "migrated"
    assert inited.factory("tasks", env=env).returncode == 0


def test_dirty_library_refused(v2):
    inited, env = v2
    (inited.library / "steps" / "dirty.md").write_text("x")
    r = inited.factory("migrate", env=env, check=False)
    assert r.returncode == 1 and "uncommitted" in r.stderr


def test_shared_library_migrated_once(v2, origin_repo, work):
    inited, env = v2
    inited.factory("migrate", env=env)
    (inited.library / "migrated-lib.txt").unlink()
    inited.fdir.joinpath("factory.yaml").write_text(
        yaml.safe_dump({**yaml.safe_load((inited.fdir / "factory.yaml").read_text()), "version": 1})
    )
    out = inited.factory.json("migrate", env=env)
    assert out["library"]["migrate"] is False
    assert not (inited.library / "migrated-lib.txt").exists()


def test_newer_refused(v2):
    inited, env = v2
    data = yaml.safe_load((inited.fdir / "factory.yaml").read_text())
    (inited.fdir / "factory.yaml").write_text(yaml.safe_dump({**data, "version": 3}))
    assert inited.factory.json("version", "check", env=env)["state"] == "newer"
    r = inited.factory("migrate", env=env, check=False)
    assert r.returncode == 1 and "Run the install script again to update it." in r.stderr


def test_migrate_plan_without_library(factory, origin_repo):
    factory("init")
    p = migrate.plan(repo.load_ctx(origin_repo))
    assert p["library"]["migrate"] is False and p["library"]["path"] is None
