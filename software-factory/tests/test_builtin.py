import yaml

from conftest import SF
from factory import step_format
from factory.registry import parse_step_text

BUILTINS = ["create-task", "create-worktree", "delete-task", "backlog-add", "backlog-remove", "migrate", "user-validation", "implement", "get-user-request", "edit-step", "edit-pipeline"]


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


def test_quick_task_is_builtin():
    data = yaml.safe_load((SF / "builtin" / "pipelines" / "quick-task.yaml").read_text())
    assert [s if isinstance(s, str) else s["id"] for s in data["steps"]] == ["get-user-request", "implement", "user-validation"]
    assert not (SF / "catalog" / "pipelines" / "quick-task.yaml").exists()


def test_quick_task_check_has_no_problem(inited):
    assert inited.factory.json("pipeline", "check", "quick-task") == []


def test_edit_steps_run_in_the_orchestrator():
    assert sorted(p.stem for p in (SF / "builtin" / "pipelines").glob("*.yaml")) == ["quick-task"]
    skill = (SF / "skills" / "software-factory" / "SKILL.md").read_text()
    for sid in ("edit-step", "edit-pipeline"):
        _, body = parse_step_text((SF / "builtin" / "steps" / f"{sid}.md").read_text(), sid)
        assert "Run in the orchestrator session." in body and "factory block" not in body
        assert f"(`{sid}`): follow the built-in step `{sid}`." in skill


def test_implement_text_has_no_worktree():
    assert "worktree" not in (SF / "builtin" / "steps" / "implement.md").read_text()


def test_user_validation_without_git():
    assert "Without git" in (SF / "builtin" / "steps" / "user-validation.md").read_text()
