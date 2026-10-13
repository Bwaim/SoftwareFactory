import json

import pytest
import yaml

from conftest import commit_all, make_task, task_json
from factory import repo

V1_ASK = "---\nid: ask\ndescription: Ask\ncategory: test\ntype: prompt\nreads: [ticket]\nwrites: [answer]\nconfig:\n  tone:\n    description: Tone\n    default: short\n---\n\nAnswer the ticket.\n"
V1_BUNDLE = "---\nid: bundle\ndescription: Bundle\ncategory: test\ntype: composite\nsteps: [ask, note]\n---\n"
V1_NOTE = "---\nid: note\ndescription: Note\ncategory: test\ntype: skill\n---\n\nWrite a note.\n"
V1_PLAIN = "---\nid: plain\ndescription: No type\ncategory: test\n---\n\nDo it.\n"
V1_SHOUT = "---\nid: shout\ndescription: Shout\ncategory: test\ntype: script\nreads: [ticket]\n---\n\nshout.sh\n"
SHOUT_SH = 'echo "$FACTORY_KEY_TICKET" > "$(factory artifact path shout.txt)"\n'
PIPELINE = {"id": "old", "description": "Old", "inputs": {"ticket": {"description": "Ticket"}}, "steps": ["bundle", "plain", "shout"]}


def set_version(path, v):
    data = yaml.safe_load(path.read_text())
    data["version"] = v
    path.write_text(yaml.safe_dump(data))


def make_v1(inited):
    steps, lib_steps = inited.fdir / "steps", inited.library / "steps"
    steps.mkdir(exist_ok=True)
    (steps / "ask.md").write_text(V1_ASK)
    (steps / "bundle.md").write_text(V1_BUNDLE)
    (steps / "plain.md").write_text(V1_PLAIN)
    (lib_steps / "note.md").write_text(V1_NOTE)
    (lib_steps / "shout.md").write_text(V1_SHOUT)
    (lib_steps / "shout.sh").write_text(SHOUT_SH)
    (inited.fdir / "pipelines").mkdir(exist_ok=True)
    (inited.fdir / "pipelines" / "old.yaml").write_text(yaml.safe_dump(PIPELINE, sort_keys=False))
    set_version(inited.fdir / "factory.yaml", 1)
    set_version(inited.library / "factory.yaml", 1)
    commit_all(inited.library.parent, "v1 library")


def snapshot(*roots):
    return {str(p): p.read_text() for root in roots for p in sorted(root.rglob("*")) if p.is_file() and "tasks" not in p.parts}


def test_converts_every_type(inited):
    make_v1(inited)
    out = inited.factory.json("migrate")
    assert out["errors"] == [] and out["library_commit"]["message"] == "Factory library: migrate to version 2"
    ask = (inited.fdir / "steps" / "ask.md").read_text()
    head = yaml.safe_load(ask.split("---\n")[1])
    assert head["type"] == "ai" and "reads" not in head and "writes" not in head
    assert head["outputs"] == {"answer": {"type": "text", "description": "", "optional": True}}
    assert ask.rstrip().endswith("Answer the ticket.\n\nTask keys:\n- ticket: {{ticket}}\n\nConfig:\n- tone: {{config.tone}}")
    assert yaml.safe_load((inited.fdir / "steps" / "bundle.md").read_text().split("---\n")[1])["type"] == "group"
    assert yaml.safe_load((inited.fdir / "steps" / "plain.md").read_text().split("---\n")[1])["type"] == "ai"
    assert yaml.safe_load((inited.library / "steps" / "note.md").read_text().split("---\n")[1])["type"] == "ai"
    shout = (inited.library / "steps" / "shout.md").read_text()
    assert "type: command" in shout and shout.rstrip().endswith('bash "$FACTORY_STEP_DIR/shout.sh"')
    assert "Task keys" not in shout


def test_every_converted_step_passes_version_2_validation(inited):
    from factory import step_format
    from factory.registry import parse_step_text
    make_v1(inited)
    inited.factory("migrate")
    paths = sorted((inited.fdir / "steps").glob("*.md")) + sorted((inited.library / "steps").glob("*.md"))
    assert len(paths) == 5
    for path in paths:
        manifest, body = parse_step_text(path.read_text(), path)
        assert step_format.validate(manifest, body)[0] == [], path.name


@pytest.mark.parametrize("name,text,needle", [
    ("empty", "---\nid: empty\ndescription: E\ntype: prompt\n---\n\n", "the prompt is empty"),
    ("noscript", "---\nid: noscript\ndescription: N\ntype: script\n---\n\n", "names no script file"),
    ("nokids", "---\nid: nokids\ndescription: K\ntype: composite\n---\n", "has no `steps` list"),
    ("badrun", "---\nid: badrun\ndescription: R\ntype: prompt\nrun_in: elsewhere\n---\n\nDo it.\n", "`run_in` must be"),
    ("Bad_Id", "---\nid: Bad_Id\ndescription: I\ntype: prompt\n---\n\nDo it.\n", "the step id `Bad_Id`"),
])
def test_refuses_what_version_2_refuses(inited, name, text, needle):
    make_v1(inited)
    (inited.fdir / "steps" / f"{name}.md").write_text(text)
    before = snapshot(inited.fdir, inited.library)
    r = inited.factory("migrate", check=False)
    assert r.returncode == 1 and needle in r.stderr
    assert snapshot(inited.fdir, inited.library) == before


def test_migrated_pipeline_runs_to_the_end(inited):
    make_v1(inited)
    inited.factory("migrate")
    task = inited.factory.json("launch", "old", "--description", "Migrated run", "--input", "ticket=T-1")
    tid = task["id"]
    first = inited.factory("next", "--task", tid).stdout
    assert "- ticket: T-1" in first and "- tone: short" in first
    for _ in range(10):
        out = inited.factory("next", "--task", tid).stdout
        if "pipeline is finished" in out:
            break
        if "factory run-command" in out:
            inited.factory("run-command", "--task", tid)
        inited.factory("done", "--task", tid)
    assert task_json(inited.fdir, tid)["status"] == "finished"
    assert (inited.fdir / "tasks" / tid / "artifacts" / "shout.txt").read_text().strip() == "T-1"


def test_bad_key_name_refuses_before_any_change(inited):
    make_v1(inited)
    (inited.fdir / "steps" / "ask.md").write_text(V1_ASK.replace("writes: [answer]", "writes: [Bad-Key]"))
    before = snapshot(inited.fdir, inited.library)
    r = inited.factory("migrate", check=False)
    assert r.returncode == 1 and "Bad-Key" in r.stderr
    assert snapshot(inited.fdir, inited.library) == before
    assert not list(inited.repo.glob(".factory.backup-*"))


def test_assistant_task_refuses_before_any_change(inited):
    make_v1(inited)
    make_task(repo.load_ctx(cwd=inited.repo), tid="helper", pipeline="new-step-assistant")
    before = snapshot(inited.fdir, inited.library)
    r = inited.factory("migrate", check=False)
    assert r.returncode == 1 and "Task helper uses the removed pipeline `new-step-assistant`" in r.stderr
    assert snapshot(inited.fdir, inited.library) == before


def test_bad_state_key_is_a_warning(inited):
    make_v1(inited)
    make_task(repo.load_ctx(cwd=inited.repo), tid="odd", state={"Bad Key": "v"})
    out = inited.factory.json("migrate")
    assert any("`Bad Key`" in w for w in out["warnings"])
    assert yaml.safe_load((inited.fdir / "factory.yaml").read_text())["version"] == 2


def test_dry_run_lists_errors_without_change(inited):
    make_v1(inited)
    (inited.fdir / "steps" / "ask.md").write_text(V1_ASK.replace("Answer the ticket.", "Answer {{Bad}}."))
    out = json.loads(inited.factory("migrate", "--dry-run", "--json").stdout)
    assert any("{{Bad}}" in e for e in out["errors"])
