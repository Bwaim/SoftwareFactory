import pytest
import yaml

from factory import step_format


def ok(manifest, body="Do it.\n"):
    base = {"id": "s", "description": "S", "type": "ai"}
    return step_format.validate({**base, **manifest}, body)


def errors(manifest, body="Do it.\n"):
    return " | ".join(ok(manifest, body)[0])


def test_valid_ai_step_has_no_error():
    assert ok({"config": {"style": {"description": "s"}}, "outputs": {"spec": {"type": "file", "description": "Spec"}}},
              "Use {{spec}} and {{config.style}}.") == ([], [])


@pytest.mark.parametrize("manifest,body,text", [
    ({"type": "prompt"}, "x", "data version 1"),
    ({"type": "nope"}, "x", "must be `ai`, `command` or `group`"),
    ({"reads": ["a"]}, "x", "`reads` is from data version 1"),
    ({"writes": ["a"]}, "x", "`writes` is from data version 1"),
    ({"id": "Bad"}, "x", "The id `Bad`"),
    ({"outputs": {"Bad-Key": {"type": "text", "description": "d"}}}, "x", "The output `Bad-Key`"),
    ({"outputs": {"a": {"type": "number", "description": "d"}}}, "x", "unknown type `number`"),
    ({"outputs": ["a"]}, "x", "`outputs` must be a mapping"),
    ({"config": {"Bad": {}}}, "x", "The config key `Bad`"),
    ({}, "Use {{Bad}}.", "Invalid placeholder {{Bad}}"),
    ({}, "Use {{config.style}}.", "{{config.style}} uses a config key"),
    ({}, "  \n", "The prompt is empty"),
    ({"type": "command"}, "echo {{x}}", "A command cannot use"),
    ({"type": "command"}, "", "The command is empty"),
    ({"type": "group"}, "", "needs a `steps` list"),
    ({"type": "group", "steps": ["a"]}, "text", "A group step has no body"),
    ({"type": "group", "steps": ["a"], "outputs": {"x": {}}}, "", "Remove `outputs`"),
    ({"done_check": "test -f {{spec}}"}, "x", "`done_check` cannot use"),
    ({"run_in": "elsewhere"}, "x", "`run_in` must be"),
])
def test_load_errors(manifest, body, text):
    assert text in errors(manifest, body)


@pytest.mark.parametrize("sid", [None, "", "  "])
def test_empty_id(sid):
    text = errors({"id": sid})
    assert "The id is empty." in text and "None" not in text and "must be lowercase" not in text


def test_warnings():
    _, w = ok({"type": "command", "run_in": "subagent", "description": "", "outputs": {"a": {"type": "text"}}}, "echo hi")
    text = " | ".join(w)
    assert "`run_in` applies only to `ai` steps" in text
    assert "The description is empty" in text
    assert "The output `a` has no description" in text
    _, w = ok({"model": "opus"})
    assert "`model` has no effect on a step that runs in the session" in " | ".join(w)


def test_single_braces_are_not_placeholders():
    assert ok({}, 'Send {"a": {"b": 1}} as JSON.') == ([], [])


def test_dump_order_and_empty_values():
    manifest = {"type": "ai", "id": "s", "required": False, "description": "S", "run_in": "", "outputs": {},
                "wait_external": False, "category": "x", "extra": "kept"}
    text = step_format.dump(manifest, "Body.\n")
    head = text.split("---\n")[1]
    assert list(yaml.safe_load(head)) == ["id", "description", "category", "type", "required", "extra"]
    assert text.endswith("---\n\nBody.\n")
    group = step_format.dump({"id": "g", "type": "group", "steps": ["a"]}, "ignored")
    assert group.endswith("---\n") and "ignored" not in group


def test_clean_keeps_required_only():
    assert step_format.clean({"a": "", "b": [], "c": {}, "d": None, "required": False, "e": False, "f": "x"}) == {"required": False, "f": "x"}
