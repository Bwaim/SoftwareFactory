import json
import os

import pytest
import yaml

from conftest import fake_config, git
from factory import init, menu, repo


def test_init_creates_files_and_exclude(factory, origin_repo, library_path, work):
    gitignore_before = (origin_repo / ".gitignore").exists()
    out = factory.json("init", "--library", library_path, "--create-library")
    f = origin_repo / ".factory"
    data = yaml.safe_load((f / "factory.yaml").read_text())
    assert data["version"] == 1 and data["library"] == str(library_path) and data["terminal"] == "fake"
    for name in ("config.yaml", "backlog.md", "claude-settings.json", "steps", "pipelines", "tasks/archive"):
        assert (f / name).exists()
    assert json.loads((f / "claude-settings.json").read_text()) == init.SETTINGS
    exclude = (origin_repo / ".git" / "info" / "exclude").read_text().splitlines()
    assert ".factory/" in exclude and ".factory.backup-*/" in exclude
    assert (origin_repo / ".gitignore").exists() == gitignore_before
    assert yaml.safe_load((library_path / "factory.yaml").read_text())["version"] == 1
    assert out["library_git"] is True
    assert os.path.realpath(work / "bin" / "factory").endswith("bin/factory")


def test_init_never_overwrites(factory, origin_repo, library_path):
    factory("init", "--library", library_path, "--create-library")
    (origin_repo / ".factory" / "backlog.md").write_text("# Backlog\n\n## Keep me\n")
    factory("init", "--library", library_path)
    assert "Keep me" in (origin_repo / ".factory" / "backlog.md").read_text()


def test_init_needs_existing_library_or_flag(factory, library_path):
    r = factory("init", "--library", library_path, check=False)
    assert r.returncode == 1 and "--create-library" in r.stderr


def test_init_reports_failed_prerequisite(factory, origin_repo, library_path):
    git("remote", "remove", "origin", cwd=origin_repo)
    r = factory("init", "--library", library_path, "--create-library", check=False)
    assert r.returncode == 1 and "origin" in (r.stdout + r.stderr)


def test_link_fixes_wrong_target(factory, work):
    link = work / "bin" / "factory"
    link.unlink()
    link.symlink_to(work / "elsewhere")
    out = factory.json("link")
    assert out["changed"] is True and os.path.realpath(link).endswith("bin/factory")


def test_menu_before_and_after_init(factory, origin_repo, library_path):
    before = factory.json("menu")
    assert [a["key"] for g in before["groups"] for a in g["actions"]] == ["init"]
    factory("init", "--library", library_path, "--create-library")
    keys = [a["key"] for g in factory.json("menu")["groups"] for a in g["actions"]]
    assert "init" not in keys and keys[0] == "launch" and keys[-1] == "exit"
    fake_config(origin_repo / ".factory", capabilities=["state"])
    keys = [a["key"] for g in factory.json("menu")["groups"] for a in g["actions"]]
    assert "focus" not in keys and "send-prompt" not in keys
    numbers = [a["n"] for g in factory.json("menu")["groups"] for a in g["actions"]]
    assert numbers == list(range(1, len(numbers) + 1))


def test_terminal_defaults_to_herdr_and_init_saves_it(origin_repo, library_path, monkeypatch):
    from factory import adapters
    monkeypatch.delenv("FACTORY_TERMINAL", raising=False)
    ctx = repo.load_ctx(origin_repo)
    assert adapters.terminal_name(ctx) == "herdr"
    monkeypatch.setattr(init, "terminal_check", lambda c: {"name": "terminal", "ok": True, "message": "ok"})
    init.init(origin_repo, library_path, create_library=True)
    assert yaml.safe_load((origin_repo / ".factory" / "factory.yaml").read_text())["terminal"] == "herdr"


def test_init_lists_failed_terminal_check(origin_repo, library_path, monkeypatch):
    from factory.errors import FactoryError
    monkeypatch.setattr(init, "terminal_check", lambda c: {"name": "terminal", "ok": False, "message": "Run this inside Herdr."})
    with pytest.raises(FactoryError) as e:
        init.init(origin_repo, library_path, create_library=True)
    assert "terminal: Run this inside Herdr." in str(e.value)
    assert not (origin_repo / ".factory").exists()


def test_init_lists_missing_uv_with_fix(origin_repo, library_path, monkeypatch):
    from factory.errors import FactoryError
    monkeypatch.setattr(init.shutil, "which", lambda name: None)
    monkeypatch.setattr(init, "terminal_check", lambda c: {"name": "terminal", "ok": True, "message": "ok"})
    checks = {c["name"]: c for c in init.prerequisites(origin_repo)}
    assert checks["uv"]["ok"] is False and "brew install uv" in checks["uv"]["message"]
    assert checks["git"]["ok"] is True
    with pytest.raises(FactoryError) as e:
        init.init(origin_repo, library_path, create_library=True)
    assert "uv: uv is missing." in str(e.value)
