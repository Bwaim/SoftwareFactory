import json
import shlex


def settings(path):
    return json.loads((path / "claude-settings.json").read_text())


def test_init_writes_hooks(inited):
    s = settings(inited.fdir)
    assert s["permissions"]["allow"] == ["Bash(factory:*)", "Bash(factory *)"]
    stop = s["hooks"]["Stop"][0]["hooks"][0]
    assert stop["command"].endswith("factory hook stop") and stop["type"] == "command" and stop["timeout"] == 10
    assert s["hooks"]["UserPromptSubmit"][0]["hooks"][0]["command"].endswith("factory hook prompt")
    assert shlex.split(stop["command"])[0] == str(inited.work / "bin" / "factory")


def test_existing_settings_keep_rules_and_get_hooks_once(factory, origin_repo, library_path):
    f = origin_repo / ".factory"
    f.mkdir()
    (f / "claude-settings.json").write_text(json.dumps({"permissions": {"allow": ["Bash(ls:*)"]}, "hooks": {"Stop": [{"hooks": [{"type": "command", "command": "other"}]}]}}))
    factory("init", "--library", library_path, "--create-library")
    factory("init", "--library", library_path)
    s = settings(f)
    assert "Bash(ls:*)" in s["permissions"]["allow"] and "Bash(factory *)" in s["permissions"]["allow"]
    commands = [h["command"] for g in s["hooks"]["Stop"] for h in g["hooks"]]
    assert "other" in commands and sum(c.endswith("factory hook stop") for c in commands) == 1


def test_version_check_adds_missing_hooks(inited):
    path = inited.fdir / "claude-settings.json"
    path.write_text(json.dumps({"permissions": {"allow": ["Bash(factory:*)"]}}))
    assert inited.factory.json("version", "check")["settings_updated"] is True
    s = settings(inited.fdir)
    assert "hooks" in s and "Bash(factory *)" in s["permissions"]["allow"]
    assert inited.factory.json("version", "check")["settings_updated"] is False


def test_invalid_settings_do_not_crash(factory, origin_repo, library_path):
    f = origin_repo / ".factory"
    f.mkdir()
    (f / "claude-settings.json").write_text("{not json")
    out = factory.json("init", "--library", library_path, "--create-library")
    assert (f / "claude-settings.json").read_text() == "{not json"
    assert any("not valid JSON" in w for w in out["warnings"])
    assert str(f / "claude-settings.json") in out["kept"]
    v = factory.json("version", "check")
    assert v["settings_updated"] is False and "not valid JSON" in v["settings_message"]
    assert (f / "claude-settings.json").read_text() == "{not json"
