import inspect
import re

import yaml

from conftest import SF
from factory import registry, step_format
from test_docs import check, command_names

SKILL = SF / "skills" / "factory-authoring" / "SKILL.md"
EXAMPLE_RE = re.compile(r"^#### (\S+)\n\n```[a-z]*\n(.*?)```", re.M | re.S)
OUTPUT_FIELDS = ("type", "description", "optional")
CONFIG_FIELDS = ("description", "default")
PIPELINE_TOP_FIELDS = ("id", "description")


def skill_text():
    return SKILL.read_text()


def frontmatter(text):
    return yaml.safe_load(text.split("---\n", 2)[1])


def examples(text):
    return EXAMPLE_RE.findall(text)


def example_step_ids(text):
    return {path.split("/")[-1][:-3] for path, _ in examples(text)
            if path.startswith(".factory/steps/") and path.endswith(".md")}


def write_examples(repo, text):
    for path, body in examples(text):
        assert path.startswith(".factory/"), path
        target = repo / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body)


def test_skill_file_and_frontmatter():
    text = skill_text()
    assert text.startswith("---\nname: factory-authoring\n")
    fm = frontmatter(text)
    assert fm["name"] == "factory-authoring"
    assert "pipeline" in fm["description"] and "step" in fm["description"]
    assert "Implement" in fm["description"]
    assert len(fm["description"]) < 1536
    assert fm["argument-hint"]


def test_skill_commands_exist():
    assert check(skill_text(), command_names()) == []


def test_fallback_factory_path_exists():
    assert "<this skill's base directory>/../../bin/factory" in skill_text()
    assert (SKILL.parent / ".." / ".." / "bin" / "factory").resolve().is_file()


def test_examples_load_and_check_clean(inited):
    text = skill_text()
    write_examples(inited.repo, text)
    from factory import repo
    reg = registry.Registry.load(repo.load_ctx(cwd=inited.repo))
    assert {reg.steps[sid].type for sid in example_step_ids(text)} == {"ai", "command", "group"}
    assert inited.factory.json("pipeline", "check", "crash-fix") == []
    rows = {r["name"]: r for r in inited.factory.json("pipeline", "keys", "crash-fix", "--at", "2")}
    assert rows["crash_log"]["source"] == "input"
    assert rows["crash_report"]["source"] == "step collect-crash"


def test_example_command_step_runs(inited):
    write_examples(inited.repo, skill_text())
    log = inited.work / "crash.log"
    log.write_text("".join(f"line {i}\n" for i in range(150)))
    inited.factory("launch", "crash-fix", "--description", "App crashes", "--input", f"crash_log={log}", "--id", "c1")
    run = lambda *a: inited.factory(*a, "--task", "c1")
    run("next")
    assert "Exit code: 0" in run("run-command").stdout
    report = inited.repo / ".factory" / "tasks" / "c1" / "artifacts" / "crash-report.md"
    assert report.read_text().splitlines() == [f"line {i}" for i in range(50, 150)]
    run("done")
    assert "Read the crash report at " + str(report) in run("next").stdout


def test_every_field_is_described():
    text = skill_text()
    source = inspect.getsource(registry)
    pipeline_fields = set(re.findall(r'self\.data\.get\("([a-z_]+)"', source)) | set(PIPELINE_TOP_FIELDS)
    entry_fields = set(re.findall(r'entry\.get\("([a-z_]+)"', source)) | {"id"}
    assert {"steps", "inputs", "claude", "start_column"} <= pipeline_fields
    assert {"id", "with", "model", "effort", "column"} <= entry_fields
    names = set(step_format.FIELD_ORDER) | pipeline_fields | entry_fields | set(OUTPUT_FIELDS) | set(CONFIG_FIELDS)
    assert [n for n in sorted(names) if f"`{n}`" not in text] == []


def test_named_builtin_steps_exist():
    text = skill_text()
    named = set(re.findall(r"built-in step `([a-z][a-z0-9_-]*)`", text))
    pipeline = yaml.safe_load(dict(examples(text))[".factory/pipelines/crash-fix.yaml"])
    for entry in pipeline["steps"]:
        sid = entry if isinstance(entry, str) else entry["id"]
        if sid not in example_step_ids(text):
            named.add(sid)
    assert named
    assert [sid for sid in sorted(named) if not (SF / "builtin" / "steps" / f"{sid}.md").exists()] == []
