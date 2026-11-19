from conftest import SF
from factory import step_format
from factory.registry import parse_step_text

BUILTINS = ["create-task", "create-worktree", "delete-task", "backlog-add", "backlog-remove", "migrate", "user-validation", "implement"]


def test_builtin_steps_are_version_2():
    for sid in BUILTINS:
        path = SF / "builtin" / "steps" / f"{sid}.md"
        manifest, body = parse_step_text(path.read_text(), path)
        assert manifest["id"] == sid and manifest["type"] == "ai"
        assert manifest["description"] and manifest["category"] and manifest["done_when"]
        assert step_format.validate(manifest, body)[0] == []


def test_step_assistant_is_gone():
    assert not (SF / "builtin" / "steps" / "new-step.md").exists()
    assert not (SF / "builtin" / "pipelines" / "new-step-assistant.yaml").exists()
    assert sorted(p.stem for p in (SF / "builtin" / "steps").glob("*.md")) == sorted(BUILTINS)
