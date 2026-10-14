import json

import pytest

from factory import requires


@pytest.fixture
def plugin_version(tmp_path, monkeypatch):
    home = tmp_path / "claude-home"
    monkeypatch.setenv("FACTORY_CLAUDE_HOME", str(home))
    version = home / "plugins" / "cache" / "market" / "tools" / "abc123"
    version.mkdir(parents=True)
    return version


def write_skill(folder):
    folder.mkdir(parents=True)
    (folder / "SKILL.md").write_text("x")


def test_plugin_skill_in_skills_folder(plugin_version, tmp_path):
    write_skill(plugin_version / "skills" / "deploy")
    assert requires.missing(["/tools:deploy"], tmp_path) == []


def test_plugin_skill_listed_in_manifest(plugin_version, tmp_path):
    write_skill(plugin_version / "deploy")
    write_skill(plugin_version / "nested" / "review")
    manifest = plugin_version / ".claude-plugin"
    manifest.mkdir()
    (manifest / "marketplace.json").write_text(json.dumps(
        {"plugins": [{"name": "other", "skills": ["./review"]}, {"name": "tools", "skills": ["./deploy"]}]}))
    (manifest / "plugin.json").write_text(json.dumps({"name": "tools", "skills": ["./nested/review"]}))
    assert requires.missing(["/tools:deploy", "/tools:review"], tmp_path) == []


def test_plugin_skill_really_missing(plugin_version, tmp_path):
    write_skill(plugin_version / "deploy")
    write_skill(plugin_version / "unlisted")
    manifest = plugin_version / ".claude-plugin"
    manifest.mkdir()
    (manifest / "marketplace.json").write_text(json.dumps(
        {"plugins": [{"name": "other", "skills": ["./deploy"]}, {"name": "tools", "skills": ["./absent"]}]}))
    (manifest / "plugin.json").write_text("not json")
    assert requires.missing(["/tools:deploy", "/tools:unlisted", "/tools:absent"], tmp_path) == [
        "/tools:deploy", "/tools:unlisted", "/tools:absent"]
