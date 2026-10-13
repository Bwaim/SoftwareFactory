# Step editor and typed task keys Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Typed task keys, the `ai` / `command` / `group` step types with computed keys and declared outputs, `factory pipeline keys`, a step form in the pipeline editor, no task without a worktree, and the data format version 2 with its migration.

**Architecture:** Three new rule modules hold all logic: `keys.py` (key rules, placeholders, used keys, outputs, available keys), `step_format.py` (validate and dump a step), `render.py` (the `factory next` text). The engine, the pipeline checks, the launch, the server API (`step_store.py`) and the pages call them. A self-contained `migrations/1-to-2.py` converts version 1 data.

**Tech Stack:** Python 3.12, pyyaml, pytest, plain HTML/CSS/JS pages with no library, `uv`.

**Spec:** `specs/2026-10-13-step-editor-design.md`. Requirements and Definition Of Done: `prompts/factory_step_editor.md`.

## Global Constraints

- All code lives in `software-factory/`. Verification files go in `verification/software-factory/`. Only `specs/` and `plans/` are allowed outside them.
- Never change a real library or a real `.factory/`. Tests use the `inited` fixture: a test repository, a test library in its own git repository, and the fake adapter.
- Never close a Herdr workspace, tab, pane or session that the build did not create. This build runs no Herdr test.
- No code comments. Rename things or split functions instead.
- Simple English and short sentences in every user-facing text and in the README.
- Every refusal is a `FactoryError`. The CLI prints `Error: <text>` and exits 1. The API returns 400 `{"error": <text>}`, and 409 for `ExistsError`.
- Key name rule: `[a-z][a-z0-9_]*`. Key types: `text`, `long-text`, `file`. A missing type means `text`.
- Factory keys: `task_id` (`text`), `description` (`text`), `summary` (`long-text`, maybe set).
- Exact texts:
  - `(not set)`
  - `When the step is done, run \`factory done\`.`
  - `End with a short report. If you need an answer from the user, say so in the report and stop.`
  - `Other repositories that use this library are not checked.`
  - `Factory library: add step <id>` / `Factory library: update step <id>` / `Factory library: migrate to version 2`
  - `Built-in steps cannot be edited. Copy the step to local instead.`
- `factory next` and the first prompt never print `--task`. The `--task` option stays on every command.
- Run the tests from `software-factory/`: `uv run --with pytest --with pyyaml pytest -q tests`. The full suite takes about 3 minutes.
- Git:
  - Work on the branch `step-editor`, created from `master`. `master` stays unchanged.
  - Commit messages have no co-author line.
- Each milestone ends with the full suite green and a commit. Record in `verification/software-factory/step-editor-updated-tests.md` each existing test you change, with one line saying why. Task 18 puts this list in the report.

## Review Focus

1. A prompt that holds literal braces, for example a JSON sample `{"a": {"b": 1}}`. Only `{{...}}` with no brace inside is a placeholder, so single braces must pass the load untouched. Test: Task 2 `test_single_braces_are_not_placeholders`.
2. A key value with shell characters (`$(rm -rf x)`, quotes, new lines) given to a `command` step. It must reach the command as an environment value and never run. Test: Task 6 `test_command_key_value_is_never_run`.
3. A `file` output set with a relative path from a sub-folder of the worktree. It must resolve against the caller's folder. Test: Task 6 `test_state_set_file_relative_to_caller`.
4. A step form save sent without a body, or with empty strings for `run_in`, `model` and `outputs`. Empty fields must be dropped before validation, never stored, and never fail the save. Test: Task 13 `test_save_drops_empty_fields`.
5. Two steps run the same `command` position after a `goto`. The old `command_result` must not let `factory done` pass. Test: Task 6 `test_goto_clears_command_result`.

---

## Milestone 1: Step format and runtime

### Task 0: Branch

- [ ] **Step 1: Create the branch and commit the spec and the plan**

```bash
cd /Users/fabienboismoreau/Documents/Projects/SoftwareFactory/SoftwareFactory
git switch master && git switch -c step-editor
git add specs/2026-10-13-step-editor-design.md plans/2026-10-13-step-editor.md
git commit -m "step editor: spec and plan"
```

---

### Task 1: Key rules module

**Files:**
- Create: `software-factory/lib/factory/keys.py`
- Test: `software-factory/tests/test_keys.py`

**Interfaces:**
- Produces:
  - `KEY_RE`, `KEY_TYPES`, `FACTORY_KEYS`, `PLACEHOLDER_RE`, `ENV_PREFIX = "FACTORY_KEY_"`
  - `is_key(name) -> bool`, `key_type(spec) -> str`, `env_name(key) -> str`
  - `placeholders(text) -> (keys: list[str], config: list[str], invalid: list[str])`
  - `has_placeholder(text) -> bool`, `env_refs(text) -> list[str]`
  - `outputs_of(step) -> dict[str, {"type", "description", "optional"}]`
  - `leaf_uses(step) -> list[str]`
  - `step_uses(reg, sid) -> list[str]`, `step_outputs(reg, sid) -> dict`
- Task 10 adds `available()` to this module.

- [ ] **Step 1: Write the failing tests**

```python
from types import SimpleNamespace

from factory import keys


def step(stype, body="", manifest=None):
    m = {"type": stype, **(manifest or {})}
    return SimpleNamespace(type=stype, body=body, done_check=m.get("done_check"), get=m.get)


def test_key_rule_and_env_name():
    assert keys.is_key("crash_url") and keys.is_key("a1")
    assert not keys.is_key("Crash") and not keys.is_key("1a") and not keys.is_key("a-b") and not keys.is_key(None)
    assert keys.env_name("crash_url") == "FACTORY_KEY_CRASH_URL"
    assert keys.key_type(None) == "text" and keys.key_type({"type": "file"}) == "file" and keys.key_type({}) == "text"


def test_placeholders():
    found = keys.placeholders("Use {{spec}} and {{config.plan_style}}, {{spec}} again, {{Bad}} and {{config.}}.")
    assert found == (["spec"], ["plan_style"], ["{{Bad}}", "{{config.}}"])
    assert keys.has_placeholder("a {{x}} b") and not keys.has_placeholder("a {x} b")


def test_env_refs():
    text = 'echo "$FACTORY_KEY_MR_URL" ${FACTORY_KEY_BRANCH:-none} $FACTORY_CONFIG_X $FACTORY_KEY_MR_URL'
    assert keys.env_refs(text) == ["mr_url", "branch"]


def test_outputs_and_leaf_uses():
    ai = step("ai", "Read {{spec}} with {{config.style}}.", {"done_check": 'test -n "$FACTORY_KEY_PLAN"',
                                                          "outputs": {"plan": {"type": "file", "description": "Plan"}, "note": None}})
    assert keys.leaf_uses(ai) == ["spec", "plan"]
    assert keys.outputs_of(ai) == {"plan": {"type": "file", "description": "Plan", "optional": False},
                                   "note": {"type": "text", "description": "", "optional": False}}
    cmd = step("command", 'bash x.sh "$FACTORY_KEY_BRANCH"')
    assert keys.leaf_uses(cmd) == ["branch"]
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `uv run --with pytest --with pyyaml pytest -q tests/test_keys.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'factory.keys'` or `ImportError`.

- [ ] **Step 3: Write the module**

```python
import re

KEY_RE = re.compile(r"[a-z][a-z0-9_]*")
KEY_TYPES = ("text", "long-text", "file")
FACTORY_KEYS = {
    "task_id": {"type": "text", "set": "always"},
    "description": {"type": "text", "set": "always"},
    "summary": {"type": "long-text", "set": "maybe"},
}
PLACEHOLDER_RE = re.compile(r"\{\{([^{}]*)\}\}")
ENV_PREFIX = "FACTORY_KEY_"
ENV_RE = re.compile(r"\$\{?" + ENV_PREFIX + r"([A-Z][A-Z0-9_]*)")
CONFIG_PREFIX = "config."


def is_key(name):
    return isinstance(name, str) and KEY_RE.fullmatch(name) is not None


def key_type(spec):
    value = spec.get("type") if isinstance(spec, dict) else None
    return value or "text"


def env_name(key):
    return ENV_PREFIX + key.upper()


def add_once(items, value):
    if value not in items:
        items.append(value)


def placeholders(text):
    found_keys, found_config, invalid = [], [], []
    for m in PLACEHOLDER_RE.finditer(text or ""):
        inner = m.group(1)
        if inner.startswith(CONFIG_PREFIX) and is_key(inner[len(CONFIG_PREFIX):]):
            add_once(found_config, inner[len(CONFIG_PREFIX):])
        elif is_key(inner):
            add_once(found_keys, inner)
        else:
            add_once(invalid, m.group(0))
    return found_keys, found_config, invalid


def has_placeholder(text):
    return PLACEHOLDER_RE.search(text or "") is not None


def env_refs(text):
    found = []
    for m in ENV_RE.finditer(text or ""):
        add_once(found, m.group(1).lower())
    return found


def outputs_of(step):
    out = {}
    for name, spec in (step.get("outputs") or {}).items():
        spec = spec if isinstance(spec, dict) else {}
        out[name] = {"type": key_type(spec), "description": spec.get("description") or "", "optional": bool(spec.get("optional"))}
    return out


def leaf_uses(step):
    used = placeholders(step.body)[0] if step.type == "ai" else env_refs(step.body)
    used = list(used)
    for key in env_refs(step.done_check or ""):
        add_once(used, key)
    return used


def step_uses(reg, sid):
    step = reg.step(sid)
    if step.type != "group":
        return leaf_uses(step)
    used, set_before = [], set()
    for path in reg.leaves(sid):
        leaf = reg.step(path[-1])
        for key in leaf_uses(leaf):
            if key not in set_before:
                add_once(used, key)
        set_before |= set(outputs_of(leaf))
    return used


def step_outputs(reg, sid):
    step = reg.step(sid)
    if step.type != "group":
        return outputs_of(step)
    out = {}
    for path in reg.leaves(sid):
        out.update(outputs_of(reg.step(path[-1])))
    return out
```

- [ ] **Step 4: Run the tests to see them pass**

Run: `uv run --with pytest --with pyyaml pytest -q tests/test_keys.py`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add software-factory/lib/factory/keys.py software-factory/tests/test_keys.py
git commit -m "step editor: key rules module"
```

---

### Task 2: Step format module

**Files:**
- Create: `software-factory/lib/factory/step_format.py`
- Test: `software-factory/tests/test_step_format.py`

**Interfaces:**
- Consumes: `keys.is_key`, `keys.key_type`, `keys.KEY_TYPES`, `keys.placeholders`, `keys.has_placeholder`
- Produces:
  - `STEP_ID_RE`, `is_valid_id(value) -> bool`. These move here from `registry.py`. `registry.py` imports and re-exports them.
  - `TYPES = ("ai", "command", "group")`, `FIELD_ORDER`
  - `validate(manifest, body) -> (errors: list[str], warnings: list[str])`
  - `clean(manifest) -> dict`: drops empty values except `required`
  - `dump(manifest, body) -> str`

- [ ] **Step 1: Write the failing tests**

```python
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
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `uv run --with pytest --with pyyaml pytest -q tests/test_step_format.py`
Expected: FAIL with `ImportError: cannot import name 'step_format'`.

- [ ] **Step 3: Write the module**

```python
import re

import yaml

from . import keys

STEP_ID_RE = re.compile(r"[a-z][a-z0-9_-]{0,63}")
TYPES = ("ai", "command", "group")
OLD_TYPES = ("prompt", "skill", "script", "composite")
RUN_IN = ("session", "subagent")
FIELD_ORDER = ("id", "description", "category", "type", "outputs", "done_when", "done_check", "config", "required",
               "run_in", "model", "effort", "requires", "column", "wait_external", "steps")
KEY_RULE = "must use lowercase letters, digits and `_`, and start with a letter"


def is_valid_id(value):
    return isinstance(value, str) and STEP_ID_RE.fullmatch(value) is not None


def is_empty(value):
    return value is None or value is False or value == "" or value == [] or value == {}


def clean(manifest):
    return {k: v for k, v in manifest.items() if k == "required" or not is_empty(v)}


def check_outputs(manifest, errors, warnings):
    outputs = manifest.get("outputs") or {}
    if not isinstance(outputs, dict):
        errors.append("`outputs` must be a mapping of key names.")
        return
    for name, spec in outputs.items():
        if not keys.is_key(name):
            errors.append(f"The output `{name}` {KEY_RULE}.")
        if spec is not None and not isinstance(spec, dict):
            errors.append(f"The output `{name}` must be a mapping with `type` and `description`.")
            continue
        if keys.key_type(spec) not in keys.KEY_TYPES:
            errors.append(f"The output `{name}` has an unknown type `{keys.key_type(spec)}`. Use text, long-text or file.")
        elif not (spec or {}).get("description"):
            warnings.append(f"The output `{name}` has no description.")


def config_of(manifest, errors):
    config = manifest.get("config") or {}
    if not isinstance(config, dict):
        errors.append("`config` must be a mapping of config keys.")
        return {}
    for name in config:
        if not keys.is_key(name):
            errors.append(f"The config key `{name}` {KEY_RULE}.")
    return config


def check_body(stype, manifest, body, config, errors):
    text = body or ""
    if stype == "ai":
        _, used_config, invalid = keys.placeholders(text)
        for p in invalid:
            errors.append(f"Invalid placeholder {p}. Use {{{{<key>}}}} or {{{{config.<key>}}}}.")
        for name in used_config:
            if name not in config:
                errors.append(f"The placeholder {{{{config.{name}}}}} uses a config key that `config` does not declare.")
        if not text.strip():
            errors.append("The prompt is empty.")
    elif stype == "command":
        if keys.has_placeholder(text):
            errors.append("A command cannot use `{{...}}` placeholders. Use $FACTORY_KEY_<KEY> and $FACTORY_CONFIG_<KEY>.")
        if not text.strip():
            errors.append("The command is empty.")
    elif stype == "group":
        children = manifest.get("steps")
        if not isinstance(children, list) or not children:
            errors.append("A group step needs a `steps` list of child step ids.")
        if text.strip():
            errors.append("A group step has no body.")
        if manifest.get("outputs"):
            errors.append("A group step computes its outputs from its child steps. Remove `outputs`.")


def check_run(stype, manifest, errors, warnings):
    run_in = manifest.get("run_in")
    if run_in is not None and run_in not in RUN_IN:
        errors.append("`run_in` must be `session` or `subagent`.")
    if stype in ("command", "group"):
        for name in ("run_in", "model", "effort"):
            if manifest.get(name):
                warnings.append(f"`{name}` applies only to `ai` steps.")
    elif stype == "ai" and (run_in or "session") == "session":
        for name in ("model", "effort"):
            if manifest.get(name):
                warnings.append(f"`{name}` has no effect on a step that runs in the session.")


def validate(manifest, body):
    if not isinstance(manifest, dict):
        return ["The manifest must be a YAML mapping."], []
    errors, warnings = [], []
    sid = manifest.get("id")
    if not is_valid_id(sid):
        errors.append(f"The id `{sid}` must be lowercase: letters, digits, `-` or `_`, starting with a letter.")
    stype = manifest.get("type")
    if stype in OLD_TYPES:
        errors.append(f"The type `{stype}` is from data version 1. Run the migration.")
    elif stype not in TYPES:
        errors.append("The type must be `ai`, `command` or `group`.")
    for old in ("reads", "writes"):
        if old in manifest:
            errors.append(f"`{old}` is from data version 1. Run the migration.")
    check_outputs(manifest, errors, warnings)
    config = config_of(manifest, errors)
    check_body(stype, manifest, body, config, errors)
    if keys.has_placeholder(str(manifest.get("done_check") or "")):
        errors.append("`done_check` cannot use `{{...}}` placeholders. Use $FACTORY_KEY_<KEY>.")
    check_run(stype, manifest, errors, warnings)
    if not manifest.get("description"):
        warnings.append("The description is empty.")
    return errors, warnings


def dump(manifest, body):
    data = clean(manifest)
    ordered = {k: data[k] for k in FIELD_ORDER if k in data}
    ordered.update({k: v for k, v in data.items() if k not in ordered})
    text = "---\n" + yaml.safe_dump(ordered, sort_keys=False, allow_unicode=True) + "---\n"
    if manifest.get("type") != "group" and (body or "").strip():
        text += "\n" + body.strip("\n") + "\n"
    return text
```

- [ ] **Step 4: Run the tests to see them pass**

Run: `uv run --with pytest --with pyyaml pytest -q tests/test_step_format.py`
Expected: all passed.

- [ ] **Step 5: Commit**

```bash
git add software-factory/lib/factory/step_format.py software-factory/tests/test_step_format.py
git commit -m "step editor: step format validate and dump"
```

---

### Task 3: Built-in and catalog steps in the version 2 format

**Files:**
- Modify: every file in `software-factory/builtin/steps/*.md` and `software-factory/catalog/steps/*.md`
- Delete: `software-factory/builtin/steps/new-step.md`, `software-factory/builtin/pipelines/new-step-assistant.yaml`
- Test: `software-factory/tests/test_builtin.py`, `software-factory/tests/test_catalog.py`

**Interfaces:**
- Consumes: `step_format.validate`

- [ ] **Step 1: Write the failing tests**

Replace `tests/test_builtin.py` with:

```python
from conftest import SF
from factory import step_format
from factory.registry import parse_step_text

BUILTINS = ["create-task", "create-worktree", "delete-task", "backlog-add", "backlog-remove", "migrate", "user-validation"]


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
```

Add to `tests/test_catalog.py`:

```python
from factory import step_format

TYPED_OUTPUTS = {"brainstorm": {"spec": ("file", False)}, "write-plan": {"plan": ("file", False)},
                 "review": {"review": ("file", False)}, "create-pr": {"mr_url": ("text", False)},
                 "commit": {"branch": ("text", True)}}


def test_catalog_steps_are_version_2():
    for path in sorted((SF / "catalog" / "steps").glob("*.md")):
        manifest, body = parse_step_text(path.read_text(), path)
        assert step_format.validate(manifest, body)[0] == [], path.name
        assert manifest["type"] in ("ai", "command")
        assert "factory state get" not in str(manifest.get("done_check") or ""), path.name
        for key, (ktype, optional) in TYPED_OUTPUTS.get(manifest["id"], {}).items():
            out = manifest["outputs"][key]
            assert out["type"] == ktype and bool(out.get("optional")) is optional and out["description"]
    for sid, script in (("push", "push.sh"), ("run-tests", "run-tests.sh")):
        manifest, body = parse_step_text((SF / "catalog" / "steps" / f"{sid}.md").read_text(), sid)
        assert manifest["type"] == "command" and body.strip() == f'bash "$FACTORY_STEP_DIR/{script}"'


def test_catalog_prompts_use_placeholders():
    expected = {"brainstorm": ["{{description}}", "{{summary}}"], "write-plan": ["{{spec}}", "{{config.plan_style}}"],
                "execute-plan": ["{{plan}}"], "create-pr": ["{{branch}}", "{{config.forge}}"],
                "implement": ["{{description}}", "{{summary}}"], "address-review-comments": ["{{mr_url}}"],
                "wait-review": ["{{mr_url}}"]}
    for sid, needles in expected.items():
        text = (SF / "catalog" / "steps" / f"{sid}.md").read_text()
        for needle in needles:
            assert needle in text, (sid, needle)
```

In the existing `test_replace_needs_flag_and_shows_diff`, replace `(inited.library / "steps" / "push.md").write_text("changed\n")` with:

```python
    push_md = inited.library / "steps" / "push.md"
    push_md.write_text(push_md.read_text() + "\nchanged\n")
```

Why: an invalid step file now stops `Registry.load`. Record this in `step-editor-updated-tests.md`.

- [ ] **Step 2: Run the tests to see them fail**

Run: `uv run --with pytest --with pyyaml pytest -q tests/test_builtin.py tests/test_catalog.py`
Expected: FAIL. The types are still `prompt` and `script`, and `new-step.md` exists.

- [ ] **Step 3: Delete the assistant files**

```bash
git rm software-factory/builtin/steps/new-step.md software-factory/builtin/pipelines/new-step-assistant.yaml
```

- [ ] **Step 4: Rewrite the built-in steps**

For `create-worktree`, `delete-task`, `backlog-add` and `backlog-remove`:

- Set `type: ai`.
- Remove `reads:` and `writes:`.
- Keep every other line.

Write `builtin/steps/create-task.md`:

```markdown
---
id: create-task
description: Create a task from a pipeline, with its worktree and session
category: factory
type: ai
done_when: The task exists and its session started.
required: true
---

Run in the orchestrator session, never in a task session.

1. Collect the pipeline id, the description and every pipeline input from the user. Offer to start from a backlog entry first (`factory backlog list --json`). `factory pipeline list --json` gives the inputs of each pipeline, with their type and description:
   - `text`: ask for one line.
   - `long-text`: tell the user they can write several lines.
   - `file`: ask for a path, absolute or relative to the main repository.
2. Run `factory launch <pipeline> --description "<text>" --input <key>=<value> ... --dry-run --json` and show the result: task id, worktree path, branch case, missing inputs, missing config and errors.
3. For each missing config value, ask the user and run `factory config set <step> <key> <value>`. Then run the dry run again.
4. Launch only after the user confirms: the same command without `--dry-run`. Add `--from-backlog <id>` when started from a backlog entry.
```

Write `builtin/steps/migrate.md`:

```markdown
---
id: migrate
description: Migrate the factory data and the library to the current data version
category: factory
type: ai
done_when: factory version check reports the same version.
done_check: "factory version check --json | grep -q '\"state\": \"same\"'"
required: true
---

Run in the orchestrator session, before the menu.

1. Run `factory migrate --dry-run --json`. Show what will be migrated and backed up, the `errors` and the `warnings`. If there are errors, show them, tell the user how to fix them, and stop.
2. Run `factory migrate --json`. Show the summary, the warnings and the backup paths.
3. If the library changed and is in a git repository, show the changed files and the commit message `Factory library: migrate to version <n>`. Commit with `factory library commit` only after approval.
```

Write `builtin/steps/user-validation.md`. Keep the manifest and set `type: ai`. Replace the body's step 1 with:

```markdown
1. Show what to validate. The target is `{{config.target}}`:
   - `artifact`: the path stored in the task key `{{config.artifact_key}}` (`factory state get {{config.artifact_key}}`), and a short summary of the file.
   - `worktree`: `git status` and a short summary of the diff. Offer `factory open-ide`.
```

Keep steps 2 to 6 unchanged.

- [ ] **Step 5: Rewrite the catalog steps**

`catalog/steps/implement.md`:

```markdown
---
id: implement
description: Do the task described in the task description and summary
category: code
type: ai
done_when: The change is made in the worktree and the code builds.
required: false
column: Implementation
---

Task: {{description}}

Summary: {{summary}}

Make the change in this worktree. Keep it small and focused.
If something is unclear, run `factory block "<question>"`, ask the user, then run `factory unblock` when the user answers.
```

`catalog/steps/brainstorm.md`:

```markdown
---
id: brainstorm
description: Brainstorm the task with the user and write a spec
category: planning
type: ai
outputs:
  spec:
    type: file
    description: The spec file
done_when: The spec file is written and its path is saved.
required: false
run_in: session
requires: [/superpowers:brainstorming]
column: Specification
---

Run `/superpowers:brainstorming` on this task.

Task: {{description}}

Summary: {{summary}}

Save the spec file at the path printed by `factory artifact path spec.md`, not in the repository.
Stop when the spec is written. The next step asks the user to validate it.
```

`catalog/steps/write-plan.md`:

```markdown
---
id: write-plan
description: Write an implementation plan from the spec
category: planning
type: ai
outputs:
  plan:
    type: file
    description: The implementation plan
done_when: The plan file is written and its path is saved.
config:
  plan_style:
    description: Extra instructions for the plan, for example the commit size
    default: small commits
required: false
run_in: session
requires: [/superpowers:writing-plans]
column: Plan
---

Run `/superpowers:writing-plans` on the spec file {{spec}}, following this style: {{config.plan_style}}.
Save the plan at the path printed by `factory artifact path plan.md`, not in the repository.
Stop when the plan is written. The next step asks the user to validate it.
```

`catalog/steps/execute-plan.md`:

- Set `type: ai` and remove `reads`.
- Body:

```markdown
Run `/superpowers:executing-plans` on the plan file {{plan}}.
Work in this worktree. When the skill offers to finish the branch, stop there: the next steps run the tests, push and create the pull request.
```

`catalog/steps/commit.md`:

```markdown
---
id: commit
description: Commit the changes with a message in the repository's commit style
category: git
type: ai
outputs:
  branch:
    type: text
    description: The branch of the task, set when this step creates it
    optional: true
done_when: All changes are committed on a branch.
done_check: test -z "$(git status --porcelain)" && git symbolic-ref -q HEAD >/dev/null
required: false
---

1. If HEAD is detached, create a branch named after the task id: `git switch -c {{task_id}}`. Save it with `factory state set branch {{task_id}}`.
2. Read `git log -n 10 --oneline` and follow the same message style.
3. Stage and commit all changes of the task. Do not commit unrelated files.
```

`catalog/steps/rebase.md`:

- Set `type: ai`.
- Body:

```markdown
1. Run `git fetch origin {{config.base_ref}}` and `git rebase origin/{{config.base_ref}}`.
2. Resolve simple conflicts: imports, formatting, independent changes in the same file.
3. On a complex conflict, run `git rebase --abort`, then `factory block "Complex rebase conflict in <files>"`, and explain the conflict to the user.
```

`catalog/steps/review.md`:

```markdown
---
id: review
description: Review the branch diff and save the findings as an artifact
category: review
type: ai
outputs:
  review:
    type: file
    description: The review findings
done_when: The review file is written and its path is saved.
config:
  base_ref:
    description: The base branch to compare with
    default: main
required: false
run_in: subagent
model: opus
effort: high
---

1. Run `git fetch origin {{config.base_ref}}` and read `git diff origin/{{config.base_ref}}...HEAD`.
2. Find real problems: bugs, missing tests, security issues. Skip style comments.
3. Write the findings to the path printed by `factory artifact path review.md`, one numbered item per finding with the file and line.
```

`catalog/steps/create-pr.md`:

```markdown
---
id: create-pr
description: Create a pull request or merge request with gh or glab
category: forge
type: ai
outputs:
  mr_url:
    type: text
    description: The URL of the pull request or merge request
done_when: The pull request or merge request exists and its URL is saved.
config:
  forge:
    description: The forge of this repository, `github` or `gitlab`
  target_branch:
    description: The branch the pull request targets
    default: main
required: false
column: Review
---

The forge is {{config.forge}}. The branch is {{branch}}. The target branch is {{config.target_branch}}.

1. When the forge is `github`, run `gh pr create --base {{config.target_branch}} --head {{branch}} --title "<title>" --body "<body>"`. When it is `gitlab`, run `glab mr create --target-branch {{config.target_branch}} --source-branch {{branch}} --title "<title>" --description "<body>" --yes`.
2. Write a short title and a body from the task description, the summary and the commits.

Task: {{description}}

Summary: {{summary}}
```

`catalog/steps/address-review-comments.md`:

- Set `type: ai` and remove `reads`.
- Body:

```markdown
1. Read the open comments of {{mr_url}}: `gh pr view {{mr_url}} --comments` when the forge is `github`, `glab mr view {{mr_url}} --comments` when it is `gitlab`. The forge is {{config.forge}}.
2. Fix each comment in the code. If a comment is wrong or unclear, ask the user before you answer it.
3. Commit the fixes and push the branch.
```

`catalog/steps/wait-review.md`:

- Set `type: ai` and remove `reads`.
- In `done_check`, replace both `$(factory state get mr_url)` with `$FACTORY_KEY_MR_URL`. The two parts become:
  - `gh pr view "$FACTORY_KEY_MR_URL" --json reviewDecision -q .reviewDecision | grep -qx APPROVED`
  - `glab api "projects/:id/merge_requests/$(basename "$FACTORY_KEY_MR_URL")/approvals"`
- Body line 1: `Tell the user the pull request {{mr_url}} is waiting for review.`

`catalog/steps/wait-qa.md`: set `type: ai`.

`catalog/steps/push.md`:

```markdown
---
id: push
description: Push the branch to origin
category: git
type: command
outputs:
  branch:
    type: text
    description: The pushed branch
done_when: The branch is on origin with all local commits.
done_check: b=$(git symbolic-ref --short -q HEAD) && git rev-parse --verify -q "refs/remotes/origin/$b" >/dev/null && test -z "$(git log "origin/$b..HEAD" --oneline)"
required: false
requires: [git]
---

bash "$FACTORY_STEP_DIR/push.sh"
```

`catalog/steps/run-tests.md`:

- Set `type: command`.
- Remove `done_check`. The run-command exit check replaces it, so the tests do not run twice.
- Body: `bash "$FACTORY_STEP_DIR/run-tests.sh"`.

- [ ] **Step 6: Run the tests to see them pass**

Run: `uv run --with pytest --with pyyaml pytest -q tests/test_builtin.py tests/test_catalog.py`
Expected: all passed.

- [ ] **Step 7: Commit**

```bash
git add -A software-factory/builtin software-factory/catalog software-factory/tests/test_builtin.py software-factory/tests/test_catalog.py
git commit -m "step editor: built-in and catalog steps in the version 2 format"
```

---

### Task 4: Registry loads version 2 steps

**Files:**
- Modify: `software-factory/lib/factory/registry.py`, `software-factory/lib/factory/pipeline_store.py`, `software-factory/lib/factory/step_delete.py`, `software-factory/lib/factory/pipeline_check.py` (temporary: drop the `reads` warning, see Step 3), `software-factory/lib/factory/web/editor.html` (`userText` label only)
- Modify tests: `tests/conftest.py`, `tests/test_registry.py`, `tests/test_editor_api.py`, `tests/test_step_delete.py`, `tests/test_pipeline_check.py`, `tests/test_engine.py` (only `write_step` calls)
- Test: `software-factory/tests/test_registry.py`

**Interfaces:**
- Consumes: `step_format.validate`, `step_format.is_valid_id`, `keys.step_uses`, `keys.step_outputs`
- Produces:
  - `Registry.load` raises `FactoryError("<path>: <errors>")` for an invalid step.
  - `Step.type` returns the raw `type`, with no default.
  - `Registry.leaves` and `check_loops` walk `group`.
  - `Registry.io` is removed.
  - `registry.NO_WORKTREE_PIPELINES` is removed. `expand` always puts `create-worktree` first.
  - `pipeline_store.step_detail` returns `uses`, `outputs` and `children` in place of `reads` and `writes`.
  - `step_delete.find_users` uses the kind `group`. `describe` prints `group step`.

- [ ] **Step 1: Update the test helper and write the failing tests**

In `tests/conftest.py` `write_step`, change the default `"type": "prompt"` to `"type": "ai"`.

Replace `test_composite_paths_and_io` and `test_composite_loop_refused` in `tests/test_registry.py`:

```python
def test_group_paths_uses_and_outputs(inited):
    from factory import keys
    write_step(inited.fdir, "rebase", {"outputs": {"rebased": {"type": "text", "description": "r"}}}, body="Rebase {{base}}.\n")
    write_step(inited.fdir, "commit", {"outputs": {"sha": {"type": "text", "description": "s"}}}, body="Commit {{rebased}} with {{msg}}.\n")
    write_step(inited.fdir, "rebase-and-commit", {"type": "group", "steps": ["rebase", "commit"]}, body="")
    reg = Registry.load(ctx_of(inited))
    assert reg.leaves("rebase-and-commit") == [["rebase-and-commit", "rebase"], ["rebase-and-commit", "commit"]]
    assert keys.step_uses(reg, "rebase-and-commit") == ["base", "msg"]
    assert list(keys.step_outputs(reg, "rebase-and-commit")) == ["rebased", "sha"]


def test_group_loop_refused(inited):
    write_step(inited.fdir, "a", {"type": "group", "steps": ["b"]}, body="")
    write_step(inited.fdir, "b", {"type": "group", "steps": ["a"]}, body="")
    with pytest.raises(FactoryError, match="loop"):
        Registry.load(ctx_of(inited))


def test_invalid_step_stops_the_load_with_its_file(inited):
    path = write_step(inited.fdir, "bad", {"type": "command"}, body="echo {{x}}\n")
    with pytest.raises(FactoryError) as e:
        Registry.load(ctx_of(inited))
    assert str(path) in str(e.value) and "A command cannot use" in str(e.value)


def test_expand_always_adds_create_worktree(inited):
    write_step(inited.fdir, "only", {})
    write_pipeline(inited.fdir, {"id": "solo", "steps": ["only"]})
    reg = Registry.load(ctx_of(inited))
    assert [e["id"] for e in reg.expand(reg.pipeline("solo"))] == ["create-worktree", "only"]
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `uv run --with pytest --with pyyaml pytest -q tests/test_registry.py`
Expected: FAIL. `group` is unknown, the invalid step loads, and `io` still exists.

- [ ] **Step 3: Implement the changes**

`registry.py`:

- Replace the `STEP_ID_RE` and `is_valid_id` definitions with `from .step_format import STEP_ID_RE, is_valid_id, validate`.
- Remove `NO_WORKTREE_PIPELINES`.
- `Step.type`: `return self.get("type")`.
- In `Registry.load`, after `parse_step_text`:

```python
                errors, _ = validate(manifest, body)
                if errors:
                    raise FactoryError(f"{p}: " + " ".join(errors))
```

- In `check_loops` and `leaves`, replace `"composite"` with `"group"`. Change the loop message to `"Group step loop: "`.
- Delete `io`.
- In `expand`, replace the first `if` with `if not entries or entries[0].get("id") != CREATE_WORKTREE:`.

`pipeline_store.step_detail`:

```python
def step_detail(reg, step, hidden_ids=()):
    from . import keys
    return {**step_summary(step, hidden_ids), "manifest": step.manifest, "body": step.body,
            "uses": keys.step_uses(reg, step.id), "outputs": keys.step_outputs(reg, step.id), "children": step.children}
```

`step_delete.py`:

- In `find_users`, change `step.type == "composite"` to `step.type == "group"` and the kind `"composite"` to `"group"`.
- In `describe`, write `kind = "pipeline" if user["kind"] == "pipeline" else "group step"`.
- Replace `script_of` and `script_files` with:

```python
SCRIPT_REF_RE = re.compile(r"\$\{?FACTORY_STEP_DIR\}?/([A-Za-z0-9._-]+)")


def scripts_of(step):
    if step.type != "command":
        return []
    return [(step.path.parent / name).resolve() for name in SCRIPT_REF_RE.findall(step.body)]


def script_files(reg, target):
    step_files = {s.path.resolve() for variants in reg.variants.values() for s in variants}
    others = [s for variants in reg.variants.values() for s in variants if s.path.resolve() != target.path.resolve()]
    out = []
    for script in scripts_of(target):
        if not script.is_file() or script.parent != target.path.parent.resolve() or script in step_files:
            continue
        if any(script in scripts_of(other) for other in others):
            continue
        out.append(script)
    return out
```

- Add `import re` at the top.

`editor.html` `userText`: replace `"composite step "` with `"group step "`.

`pipeline_check.py`: replace the two lines that read `leaf.get("reads")` and `leaf.get("writes")` with nothing. Task 10 adds the new key checks. Keep `ALWAYS_AVAILABLE` and `available` until Task 10.

- [ ] **Step 4: Update the tests that use version 1 manifests**

Make these exact changes, then add one line each to `step-editor-updated-tests.md`:

- `test_editor_api.py` fixture `ed`:
  - `write_step(inited.library, "gen", {"category": "git", "outputs": {"x": {"type": "text", "description": "x"}}})`
  - `write_step(inited.fdir, "loc", {"category": "review", "run_in": "subagent"}, body="Use {{x}}.\n")`
  - `"type": "group"` for `box`
  - In `test_steps_list_and_detail`: `assert box["children"] == ["gen", "loc"] and box["uses"] == [] and list(box["outputs"]) == ["x"]`
  - Why: `reads` and `writes` became computed `uses` and declared `outputs`.
- `test_step_delete.py`:
  - every `{"type": "script"}` becomes `{"type": "command"}`
  - every body `X.sh\n` becomes `bash "$FACTORY_STEP_DIR/X.sh"\n`, with the same `X`. For `bad`, the body becomes `bash "$FACTORY_STEP_DIR/other.md"\n`.
  - `{"type": "composite", ...}` becomes `{"type": "group", ...}`
  - the expected tuple `("composite", "combo", "local")` becomes `("group", "combo", "local")`
  - the expected line `"- composite step combo (local)"` becomes `"- group step combo (local)"`
  - Why: the version 2 types.
- `test_pipeline_check.py`:
  - `write_step(inited.fdir, "local-step", {"column": "Nowhere"}, body="Use {{nothing}}.\n")`
  - remove the assertion `"reads \`nothing\`" in warnings`. Task 10 adds it back with the new text.
  - in `test_valid_pipeline_has_no_problem`: `write_step(inited.fdir, "a", {"outputs": {"x": {"type": "text", "description": "x"}}})` and `write_step(inited.fdir, "b", {}, body="Use {{x}} and {{ticket_in}}.\n")`
  - Why: `reads` and `writes` are gone.
- `test_engine.py` fixture `flow`:
  - `"writes": ["out"]` becomes `"outputs": {"out": {"type": "text", "description": "o", "optional": True}}`
  - `"type": "composite"` becomes `"type": "group"`
  - In `test_subagent_call_model_effort_precedence`: remove `"reads": ["ticket"]` and use body `"Analyze {{ticket}}.\n"`.
  - Task 5 rewrites the output assertions.
- `test_goto.py`:
  - `{"writes": [f"{sid}_out"]}` becomes `{"outputs": {f"{sid}_out": {"type": "text", "description": "o", "optional": True}}}`
  - `"composite"` becomes `"group"`
- `test_approval.py` fixture: `write_step(inited.fdir, "spec", {"outputs": {"spec": {"type": "text", "description": "s", "optional": True}}})`.
- `test_backlog.py` line 42: `write_step(inited.fdir, "w", {}, body="Use {{summary}}.\n")`.

- [ ] **Step 5: Run the touched tests**

Run: `uv run --with pytest --with pyyaml pytest -q tests/test_registry.py tests/test_editor_api.py tests/test_step_delete.py tests/test_pipeline_check.py tests/test_builtin.py tests/test_catalog.py`
Expected: all passed.

- [ ] **Step 6: Commit**

```bash
git add -A software-factory
git commit -m "step editor: registry loads and validates version 2 steps"
```

---

### Task 5: `factory next` prints the exact prompt and the footer

**Files:**
- Create: `software-factory/lib/factory/render.py`
- Modify: `software-factory/lib/factory/engine.py`, `software-factory/lib/factory/session.py`, `software-factory/lib/factory/repo.py`
- Test: `software-factory/tests/test_runtime_v2.py`
- Modify tests: `tests/test_engine.py`, `tests/test_approval.py:27`, `tests/test_waiting.py:92`, `tests/test_question_box.py:84`

**Interfaces:**
- Consumes: `keys.outputs_of`, `keys.PLACEHOLDER_RE`
- Produces:
  - `render.NOT_SET`, `render.fill(text, values, config_values) -> str`, `render.show_names(text) -> str`
  - `render.step_text(step, prompt, step_line, outputs, model=None, effort=None) -> str`
  - `engine.key_values(task) -> dict`, `engine.step_line(task) -> str`

- [ ] **Step 1: Write the failing tests**

`tests/test_runtime_v2.py`:

```python
import pytest

from conftest import task_from_pipeline, write_pipeline, write_step


def run(inited, *args, check=True):
    return inited.factory(*args, "--task", "t1", check=check)


@pytest.fixture
def ai(inited):
    write_step(inited.fdir, "plan", {
        "config": {"style": {"description": "Style", "default": "small"}},
        "outputs": {"plan": {"type": "file", "description": "The plan"},
                    "note": {"type": "long-text", "description": "Notes", "optional": True}},
        "done_when": "The plan is written.",
    }, body="Plan {{spec}} for {{task_id}} ({{description}}), style {{config.style}}. Ticket: {{ticket}}.\n")
    write_pipeline(inited.fdir, {"id": "p", "steps": ["plan"]})
    task_from_pipeline(inited, "p", description="Add login", state={"spec": "/tmp/spec.md"})
    return inited


def test_next_prints_exact_prompt_then_footer(ai):
    out = run(ai, "next").stdout
    prompt, footer = out.split("\n---\n", 1)
    assert prompt.rstrip("\n") == "Plan /tmp/spec.md for t1 (Add login), style small. Ticket: (not set)."
    assert footer.splitlines()[0] == "Step 2 of 2: plan"
    assert "- `plan` (file): The plan. Set it with `factory state set plan <path>`. Get a path in the artifacts folder with `factory artifact path <name>`." in footer
    assert "- `note` (long-text, optional): Notes. Set it with `factory state set note <value>`." in footer
    assert "Done when: The plan is written." in footer
    assert footer.rstrip().endswith("When the step is done, run `factory done`.")
    assert "--task" not in out


def test_subagent_prompt_is_the_same_text_with_a_report_line(inited):
    write_step(inited.fdir, "sub", {"run_in": "subagent", "model": "haiku", "effort": "low",
                                    "outputs": {"review": {"type": "file", "description": "Review"}}}, body="Review {{ticket}}.\n")
    write_pipeline(inited.fdir, {"id": "s", "steps": [{"id": "sub", "model": "opus"}]})
    task_from_pipeline(inited, "s", state={"ticket": "ABC-1"})
    out = run(inited, "next").stdout
    inner = out.split("<<<\n", 1)[1].split("\n>>>", 1)[0]
    assert inner.startswith("Review ABC-1.\n\n---\nStep 2 of 2: sub\n")
    assert "- `review` (file): Review." in inner
    assert inner.endswith("End with a short report. If you need an answer from the user, say so in the report and stop.")
    assert "factory done" not in inner
    assert "- model: opus" in out and "- effort: low" in out
    assert out.rstrip().endswith("Otherwise run `factory done`.")


def test_wait_external_ends_with_factory_wait(inited):
    write_step(inited.fdir, "w", {"wait_external": True}, body="Wait.\n")
    write_pipeline(inited.fdir, {"id": "wp", "steps": ["w"]})
    task_from_pipeline(inited, "wp")
    assert run(inited, "next").stdout.rstrip().endswith("The factory tells you when the external event happens.")


def test_group_step_shows_full_path(inited):
    write_step(inited.fdir, "a", {})
    write_step(inited.fdir, "b", {})
    write_step(inited.fdir, "ab", {"type": "group", "steps": ["a", "b"]}, body="")
    write_pipeline(inited.fdir, {"id": "g", "steps": ["ab"]})
    task_from_pipeline(inited, "g")
    run(inited, "next"); run(inited, "done")
    assert "Step 3 of 3: ab > b" in run(inited, "next").stdout


def test_first_prompt_never_adds_task_flag():
    from factory import session
    text = session.first_prompt({"id": "t1", "worktree": "/w"})
    assert "`factory next`" in text and "`factory done`" in text and "--task" not in text
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `uv run --with pytest --with pyyaml pytest -q tests/test_runtime_v2.py`
Expected: FAIL. The old header and context lines are printed.

- [ ] **Step 3: Write `render.py`**

```python
from . import keys

NOT_SET = "(not set)"
IF_NEEDED = [
    "If needed:",
    '- If you cannot continue without the user, run `factory block "<question>"`, ask the user, then run `factory unblock` when the user answers.',
    "- Only after the user approves: skip this step with `factory skip`, or go back to an earlier step with `factory goto <step path> --reason \"<why>\"`.",
]
SESSION_END = "When the step is done, run `factory done`."
WAIT_END = "When the actions of this step are done, run `factory wait`. The factory tells you when the external event happens."
SUBAGENT_END = "End with a short report. If you need an answer from the user, say so in the report and stop."
SUBAGENT_AFTER = "When the subagent ends, read its report. If it needs the user, ask the user, then run `factory next` again. Otherwise run `factory done`."
COMMAND_RUN = "Run `factory run-command`. It runs the step command and prints its output and its exit code."
COMMAND_RETRY = "If the exit code is not 0, fix the cause or ask the user, then run `factory run-command` again."
SEPARATOR = "---"


def fill(text, values, config_values):
    def sub(m):
        inner = m.group(1)
        if inner.startswith(keys.CONFIG_PREFIX):
            value = config_values.get(inner[len(keys.CONFIG_PREFIX):])
        else:
            value = values.get(inner)
        return NOT_SET if value is None or value == "" else str(value)
    return keys.PLACEHOLDER_RE.sub(sub, text or "")


def show_names(text):
    return keys.PLACEHOLDER_RE.sub(lambda m: f"<{m.group(1)}>", text or "")


def output_line(name, out):
    flag = ", optional" if out["optional"] else ""
    desc = out["description"].strip().rstrip(".")
    line = f"- `{name}` ({out['type']}{flag})" + (f": {desc}. " if desc else ". ")
    if out["type"] == "file":
        return line + f"Set it with `factory state set {name} <path>`. Get a path in the artifacts folder with `factory artifact path <name>`."
    return line + f"Set it with `factory state set {name} <value>`."


def output_lines(outputs, title):
    if not outputs:
        return []
    return [title] + [output_line(name, out) for name, out in outputs.items()]


def end_line(step):
    return WAIT_END if step.wait_external else SESSION_END


def footer(step_line, step, outputs, last, help_lines):
    lines = [SEPARATOR, step_line] + output_lines(outputs, "Outputs to set:")
    if step.done_when:
        lines.append(f"Done when: {step.done_when}")
    if help_lines:
        lines += IF_NEEDED
    return lines + [last]


def prompt_with_footer(prompt, step_line, step, outputs, last, help_lines):
    return "\n".join([prompt.rstrip("\n"), ""] + footer(step_line, step, outputs, last, help_lines))


def subagent_text(prompt, step_line, step, outputs, model, effort):
    inner = prompt_with_footer(prompt, step_line, step, outputs, SUBAGENT_END, False)
    return "\n".join([step_line, "Run this step in a subagent. Call the Agent tool with:",
                      f"- model: {model or 'inherit'}", f"- effort: {effort or 'inherit'}",
                      "- prompt:", "<<<", inner, ">>>", SUBAGENT_AFTER])


def command_text(step_line, step, outputs):
    lines = [step_line, COMMAND_RUN] + output_lines(outputs, "The command sets these outputs:")
    if step.done_when:
        lines.append(f"Done when: {step.done_when}")
    return "\n".join(lines + [COMMAND_RETRY] + IF_NEEDED + [end_line(step)])


def step_text(step, prompt, step_line, outputs, model=None, effort=None):
    if step.type == "command":
        return command_text(step_line, step, outputs)
    if step.run_in == "subagent":
        return subagent_text(prompt, step_line, step, outputs, model, effort)
    return prompt_with_footer(prompt, step_line, step, outputs, end_line(step), True)
```

- [ ] **Step 4: Change `engine.py`, `session.py` and `repo.py`**

`engine.py`:

- Remove `FACTORY_SPAN_RE`, `with_task_flag`, `header`, `context_lines`, `subagent_block`, `end_line` and `IF_NEEDED`.
- `cmd` becomes `def cmd(task, text): return f"factory {text}"`.
- Add `from . import keys, render` to the imports.
- Add:

```python
def key_values(task):
    return {**(task.get("state") or {}), "task_id": task["id"], "description": task.get("description") or ""}


def step_line(task):
    return f"Step {task['position'] + 1} of {len(task['steps'])}: {state.step_path_str(task)}"


def render_step(task, entry, step, values):
    prompt = render.fill(step.body, key_values(task), values) if step.type == "ai" else ""
    model, effort = settings(entry, step)
    return render.step_text(step, prompt, step_line(task), keys.outputs_of(step), model, effort)


def render_missing(task, step, missing):
    lines = [step_line(task), "", "Some config values are missing. Ask the user for each one, then save it:"]
    for key in missing:
        desc = step.config_spec[key].get("description", "")
        lines.append(f"- `{key}`: {desc} Save it with `factory config set {step.id} {key} <value>`.")
    lines.append("Then run `factory next` again.")
    return "\n".join(lines)
```

- In `next_step`, replace `return render(ctx, task, entry, step, values)` with `return render_step(task, entry, step, values)`.
- Delete the old `render` function.

`session.py`:

- Delete `factory_cmd`.
- `first_prompt(task)`: `return FIRST_PROMPT.format(id=task["id"], next="factory next", done="factory done")`.
- `resume_prompt`: use `status="factory status", next="factory next"`.

`repo.py`: delete `task_flag`.

- [ ] **Step 5: Update the old output assertions**

Add one line each to `step-editor-updated-tests.md`, with the reason "`factory next` now prints the exact prompt and footer, never `--task`":

- `test_engine.py` `test_next_done_check_fails_then_passes`:
  - `assert "Step 2 of 5: make" in out`
  - `assert "Create \`made.txt\`. Then run \`factory state set out made.txt\`." in out`
- `test_engine.py` `test_missing_config_asks`: after the config is set, assert `"Do the step." in` the output. The config value is no longer printed when the prompt does not use it.
- `test_engine.py` `test_subagent_call_model_effort_precedence`:
  - replace `"- ticket: ABC-1" in out` and `"Analyze it." in out` with `"Analyze ABC-1." in out`
- `test_engine.py` `test_next_tells_session_about_block_skip_and_goto`: `"\`factory skip\`" in out`.
- `test_engine.py` `test_run_script_gets_config_and_task`: delete it. Task 6 replaces it with the `run-command` tests.
- `test_approval.py:27`: `.startswith("The user approved. Run \`factory done\`")`.
- `test_waiting.py:92`: `"The external event happened: QA is done. Run \`factory next\`."`.
- `test_question_box.py:84`: keep the call with `{"id": "t1", "worktree": "/w"}`.

- [ ] **Step 6: Run the tests**

Run: `uv run --with pytest --with pyyaml pytest -q tests/test_runtime_v2.py tests/test_engine.py tests/test_approval.py tests/test_waiting.py tests/test_question_box.py tests/test_goto.py`
Expected: all passed.

- [ ] **Step 7: Commit**

```bash
git add -A software-factory
git commit -m "step editor: factory next prints the exact prompt and one footer"
```

---

### Task 6: Command steps, done checks and typed state set

**Files:**
- Modify: `software-factory/lib/factory/engine.py`, `software-factory/lib/factory/commands.py`
- Test: `software-factory/tests/test_runtime_v2.py`

**Interfaces:**
- Consumes: `keys.outputs_of`, `keys.is_key`, `keys.env_name`, `keys.ENV_PREFIX`
- Produces:
  - `engine.step_env(ctx, task, step, values) -> dict`
  - `engine.run_check(ctx, task, step, command, timeout, values)`: new signature
  - `engine.run_command(ctx, tid) -> int`
  - `engine.output_problem(task, step) -> str | None`
  - `engine.set_state(ctx, tid, key, value) -> str` (returns the saved value)
  - task field `command_result`: `{"position", "exit_code"}` or `None`
  - CLI `factory run-command`. `factory run-script` is removed.

- [ ] **Step 1: Write the failing tests** (append to `tests/test_runtime_v2.py`)

```python
import json

from conftest import task_json


@pytest.fixture
def cmd(inited):
    step = write_step(inited.fdir, "echo", {
        "type": "command", "config": {"word": {"description": "w", "default": "hello"}},
        "outputs": {"echoed": {"type": "file", "description": "Echo file"}},
    }, body='bash "$FACTORY_STEP_DIR/echo.sh"\n')
    (step.parent / "echo.sh").write_text(
        'p="$(factory artifact path echo.txt)"\n'
        'printf "%s|%s|%s|%s" "$FACTORY_KEY_TICKET" "$FACTORY_CONFIG_WORD" "$FACTORY_KEY_TASK_ID" "$FACTORY_STEP_DIR" > "$p"\n'
        'factory state set echoed "$p"\n'
        'exit "${FACTORY_KEY_CODE:-0}"\n')
    write_pipeline(inited.fdir, {"id": "c", "steps": ["echo"]})
    task_from_pipeline(inited, "c", state={"ticket": "T-1"})
    return inited, step


def test_command_next_and_env(cmd):
    inited, step = cmd
    out = run(inited, "next").stdout
    assert "Run `factory run-command`." in out and "The command sets these outputs:" in out
    r = run(inited, "run-command")
    assert r.stdout.rstrip().endswith("Exit code: 0")
    text = (inited.fdir / "tasks" / "t1" / "artifacts" / "echo.txt").read_text()
    assert text == f"T-1|hello|t1|{step.parent.resolve()}"
    assert "Step done" in run(inited, "done").stdout


def test_done_refused_until_command_exits_0(cmd):
    inited, _ = cmd
    run(inited, "next")
    r = run(inited, "done", check=False)
    assert r.returncode == 1 and "The output `echoed` is not set" in r.stderr
    run(inited, "state", "set", "echoed", str(inited.repo / "README.md"))
    r = run(inited, "done", check=False)
    assert r.returncode == 1 and "Run `factory run-command` first." in r.stderr
    run(inited, "state", "set", "code", "3")
    assert run(inited, "run-command", check=False).returncode == 3
    r = run(inited, "done", check=False)
    assert r.returncode == 1 and "exited with code 3" in r.stderr
    assert json.loads((inited.fdir / "tasks" / "t1" / "events.jsonl").read_text().splitlines()[-1])["type"] == "done_check_failed"
    run(inited, "state", "set", "code", "0")
    run(inited, "run-command")
    run(inited, "done")


def test_goto_clears_command_result(cmd):
    inited, _ = cmd
    write_step(inited.fdir, "after", {})
    write_pipeline(inited.fdir, {"id": "c2", "steps": ["echo", "after"]})
    task_from_pipeline(inited, "c2", tid="t2", state={"ticket": "T-1"})
    r2 = lambda *a, check=True: inited.factory(*a, "--task", "t2", check=check)
    r2("next"); r2("run-command"); r2("done"); r2("next")
    r2("goto", "echo", "--reason", "again")
    assert task_json(inited.fdir, "t2")["command_result"] is None
    r = r2("done", check=False)
    assert r.returncode == 1 and "Run `factory run-command` first." in r.stderr


def test_command_key_value_is_never_run(inited):
    write_step(inited.fdir, "safe", {"type": "command"}, body='printf "%s" "$FACTORY_KEY_EVIL" > "$(factory artifact path out.txt)"\n')
    write_pipeline(inited.fdir, {"id": "s", "steps": ["safe"]})
    evil = '$(touch pwned) `touch pwned2` "quote\nline'
    task_from_pipeline(inited, "s", state={"evil": evil})
    run(inited, "next"); run(inited, "run-command")
    assert (inited.fdir / "tasks" / "t1" / "artifacts" / "out.txt").read_text() == evil
    assert not (inited.repo / "pwned").exists() and not (inited.repo / "pwned2").exists()


def test_file_output_must_exist(ai):
    run(ai, "next")
    run(ai, "state", "set", "note", "free text, not checked")
    r = run(ai, "state", "set", "plan", "missing.md", check=False)
    assert r.returncode == 1 and "The path does not exist" in r.stderr
    task = task_json(ai.fdir, "t1")
    task["state"]["plan"] = "/nowhere/plan.md"
    (ai.fdir / "tasks" / "t1" / "task.json").write_text(json.dumps(task))
    r = run(ai, "done", check=False)
    assert r.returncode == 1 and "The output `plan` points to a path that does not exist: /nowhere/plan.md" in r.stderr


def test_state_set_file_relative_to_caller(ai):
    run(ai, "next")
    sub = ai.repo / "docs"
    sub.mkdir()
    (sub / "plan.md").write_text("x")
    ai.factory("state", "set", "plan", "plan.md", "--task", "t1", cwd=sub)
    assert task_json(ai.fdir, "t1")["state"]["plan"] == str((sub / "plan.md").resolve())
    run(ai, "state", "set", "free_key", "anything")
    run(ai, "done")


def test_run_script_is_gone(inited):
    r = inited.factory("run-script", "--task", "t1", check=False)
    assert r.returncode != 0
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `uv run --with pytest --with pyyaml pytest -q tests/test_runtime_v2.py`
Expected: FAIL with `invalid choice: 'run-command'`.

- [ ] **Step 3: Implement**

`engine.py`:

- Add `from pathlib import Path` to the imports.
- Replace `script_env` and `run_script` with:

```python
def step_env(ctx, task, step, values):
    env = {k: v for k, v in os.environ.items() if not k.startswith(keys.ENV_PREFIX)}
    env["FACTORY_TASK"] = task["id"]
    for key, value in key_values(task).items():
        if keys.is_key(key) and value is not None:
            env[keys.env_name(key)] = str(value)
    for key, value in values.items():
        env["FACTORY_CONFIG_" + key.upper().replace("-", "_")] = str(value)
    env["FACTORY_STEP_DIR"] = str(step.path.parent.resolve())
    return env


def run_command(ctx, tid):
    task = state.load(ctx, tid)
    require_running(task)
    entry, step = load_step(ctx, task)
    if step.type != "command":
        raise FactoryError(f"The step `{step.id}` is not a `command` step.")
    values, missing = config.resolve(ctx, step, entry.get("with"))
    if missing:
        raise FactoryError("Some config values are missing. Run `factory next` first.")
    print("", end="", flush=True)
    r = subprocess.run(["bash", "-c", step.body], cwd=task_cwd(ctx, task), env=step_env(ctx, task, step, values))
    position = task["position"]
    state.update(ctx, tid, lambda t: t.__setitem__("command_result", {"position": position, "exit_code": r.returncode}))
    print(f"Exit code: {r.returncode}", flush=True)
    return r.returncode
```

- `run_check` becomes:

```python
def run_check(ctx, task, step, command, timeout, values=None):
    env = step_env(ctx, task, step, values or {})
    try:
        r = subprocess.run(command, shell=True, cwd=task_cwd(ctx, task), env=env,
                           capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return False, f"Timed out after {timeout} s."
    except OSError as e:
        return False, f"Cannot run the check: {e.strerror or e}."
    return r.returncode == 0, (r.stdout + r.stderr).strip()
```

- Pass `step` in both callers: `done` and `poll_task`.
- Add:

```python
def output_problem(task, step):
    values = task.get("state") or {}
    outputs = keys.outputs_of(step)
    for key, out in outputs.items():
        value = values.get(key)
        if not out["optional"] and (value is None or str(value).strip() == ""):
            return f"The output `{key}` is not set. Set it with `factory state set {key} <value>`."
    for key, out in outputs.items():
        value = values.get(key)
        if out["type"] == "file" and value not in (None, "") and not Path(str(value)).exists():
            return f"The output `{key}` points to a path that does not exist: {value}."
    if step.type == "command":
        result = task.get("command_result")
        if not result or result.get("position") != task["position"]:
            return "Run `factory run-command` first."
        if result.get("exit_code") != 0:
            return f"The last `factory run-command` exited with code {result.get('exit_code')}. Fix it and run it again."
    return None
```

- In `done`, before the `if step.done_check:` block:

```python
    problem = output_problem(task, step)
    if problem:
        events.log(ctx, tid, "done_check_failed", state.step_path_str(task), output=problem)
        raise FactoryError(f"The step is not done. {problem}")
```

- In `advance.change` and `goto.change`, add `t["command_result"] = None` next to `t["started"] = None`.
- Add:

```python
def set_state(ctx, tid, key, value):
    task = state.load(ctx, tid)
    entry = state.current_entry(task)
    if entry is not None and task["status"] != "finished":
        step = Registry.load(ctx).steps.get(entry["id"])
        out = keys.outputs_of(step).get(key) if step else None
        if out and out["type"] == "file":
            path = (ctx.cwd / Path(value).expanduser()).resolve()
            if not path.exists():
                raise FactoryError(f"The path does not exist: {path}. The output `{key}` is a file.")
            value = str(path)
    state.set_key(ctx, tid, key, value)
    return value
```

`commands.py`:

- In `register`, replace `"run-script"` with `"run-command"` in the `for name in (...)` loop.
- Replace `run_script_cmd` with:

```python
@cli.command("run-command")
def run_command_cmd(args):
    from . import engine
    ctx, tid = task_of(args)
    return engine.run_command(ctx, tid)
```

- `state_set` calls `engine.set_state(ctx, tid, args.key, args.value)`.

- [ ] **Step 4: Run the tests**

Run: `uv run --with pytest --with pyyaml pytest -q tests/test_runtime_v2.py tests/test_engine.py tests/test_waiting.py tests/test_minor_fixes.py tests/test_goto.py`
Expected: all passed.

- [ ] **Step 5: Commit**

```bash
git add -A software-factory
git commit -m "step editor: command steps, output checks and typed state set"
```

---

### Task 7: Every task runs in a worktree

**Files:**
- Modify: `software-factory/lib/factory/launch.py`, `session.py`, `adapters/base.py`, `adapters/fake.py`, `adapters/herdr.py`, `commands.py`
- Modify tests: `tests/test_launch.py`, `tests/test_terminal_cli.py`, `tests/test_herdr_adapter.py`, `tests/test_step_assistant.py`, `tests/test_minor_fixes.py`, `tests/test_step_hide.py`, plus the tests listed in Step 4

**Interfaces:**
- Produces:
  - `Adapter.start_session(name, cwd, prompt, claude_args)`, with no `in_worktree`. The fake adapter records no `in_worktree` field.
  - `factory terminal start-session <name> <cwd> <prompt> -- <args>`, with no `--worktree`.
  - `session.start` raises `FactoryError("Task <id> has no worktree. Every task runs in its own worktree.")` when `task["worktree"]` is empty.

- [ ] **Step 1: Write the failing tests**

Replace `tests/test_step_assistant.py`:

```python
import pytest

from conftest import make_task, task_from_pipeline, write_pipeline, write_step
from factory import repo, session
from factory.errors import FactoryError
from factory.registry import Registry


def test_assistant_pipeline_and_step_do_not_exist(inited):
    reg = Registry.load(repo.load_ctx(cwd=inited.repo))
    assert "new-step-assistant" not in reg.pipelines and "new-step" not in reg.steps


def test_next_never_prints_task_flag(inited):
    write_step(inited.fdir, "s", {"done_when": "Done."}, body="Run `factory status` first.\n")
    write_pipeline(inited.fdir, {"id": "p", "steps": ["s"]})
    task_from_pipeline(inited, "p")
    assert "--task" not in inited.factory("next", "--task", "t1").stdout


def test_task_without_worktree_cannot_start(inited):
    ctx = repo.load_ctx(cwd=inited.repo)
    task = make_task(ctx, tid="nowt")
    with pytest.raises(FactoryError, match="has no worktree"):
        session.start(ctx, task, "hi")
```

In `tests/test_launch.py`:

- Delete `test_no_worktree_pipeline_uses_task_flag`.
- In the test at line 56, replace `assert call["in_worktree"] is True and call["cwd"] == str(wt)` with `assert "in_worktree" not in call and call["cwd"] == str(wt)`.

In `tests/test_terminal_cli.py`:

- Remove `"--worktree"` from the first `start-session` call and remove `and call["in_worktree"] is True`.
- Delete `test_start_session_without_worktree_flag_or_args`.
- Add:

```python
def test_start_session_has_no_worktree_flag(inited):
    r = inited.factory("terminal", "start-session", "t9", str(inited.repo), "p", "--worktree", check=False)
    assert r.returncode != 0
```

In `tests/test_herdr_adapter.py`:

- Delete `test_main_repo_uses_existing_workspace` and `test_main_repo_creates_workspace_when_missing`.
- In every other `start_session(..., True)` and `start_session(..., prompt, [...], True)` call, remove the last `True` argument.

In `tests/test_minor_fixes.py:116`: replace `"new-step-assistant"` with `"user-validation"`. Then `pipeline_store.copy` raises because `user-validation` is not a pipeline. The test checks that a `FactoryError` is raised, so it still holds.

In `tests/test_step_hide.py` `test_docs_describe_hide`: delete the `assistant = ...` line and the `assert "factory step list --all" in assistant` line.

Record every change in `step-editor-updated-tests.md` with the reason "tasks without a worktree and the step assistant are removed".

- [ ] **Step 2: Run the tests to see them fail**

Run: `uv run --with pytest --with pyyaml pytest -q tests/test_step_assistant.py tests/test_terminal_cli.py tests/test_herdr_adapter.py`
Expected: FAIL. The flag still exists, and `session.start` falls back to the main repository.

- [ ] **Step 3: Implement**

`launch.py`:

- Remove `NO_WORKTREE_PIPELINES` from the import.
- In `plan_launch`, replace `if pipeline_id not in NO_WORKTREE_PIPELINES:\n        plan_worktree(...)` with `plan_worktree(ctx, reg, pipeline, report, inputs)`.
- In `launch`, remove `if report["worktree"]:`. The worktree block always runs.
- In `launch_cmd` (`commands.py`), print `f"Task {task['id']} started. Worktree: {task['worktree']}"`.

`session.py`:

- Remove the `NO_WORKTREE_PIPELINES` import and the library `--add-dir` lines in `claude_args`.
- `start`:

```python
def start(ctx, task, prompt, resume=False):
    if not task.get("worktree"):
        raise FactoryError(f"Task {task['id']} has no worktree. Every task runs in its own worktree.")
    return adapters.get_adapter(ctx).start_session(task["id"], task["worktree"], prompt, claude_args(ctx, task, resume))
```

`adapters/base.py`: `def start_session(self, name, cwd, prompt, claude_args):`.

`adapters/fake.py`: change the signature the same way, and record `self.record("start_session", name=name, cwd=str(cwd), prompt=prompt, args=list(claude_args))`.

`adapters/herdr.py`:

- Delete `open_main_repo`.
- `start_session(self, name, cwd, prompt, claude_args)`:
  - `before = set(self.main_repo_workspace_ids(self.workspaces()))`
  - `pane = self.open_worktree(handle, cwd)`
  - `if "workspace" in handle:` for the extra workspaces
- Keep `create_tab`, which `open_worktree` uses for `already_open`.

`commands.py`:

- In `register`, remove `tt.add_argument("--worktree", action="store_true")`.
- `terminal_start_session` calls `adapter_of(args).start_session(args.name, args.cwd, args.prompt, args.passthrough)`.

- [ ] **Step 4: Fix tests that start a task with no worktree**

Run: `uv run --with pytest --with pyyaml pytest -q tests`

Each failure with "has no worktree" comes from a test that resumes or delivers to a task made by `make_task` or `task_from_pipeline` without a worktree. Add `worktree=str(inited.repo)` to that call. The task folder still lives in `.factory/`, and the fake adapter records the cwd only. The known places are:

- `tests/test_session.py:11`
- `tests/test_dashboard_api.py:35`
- the task creation in `tests/test_event_log.py`
- `tests/test_waiting.py:15` (`waits` fixture)

Record each one with the reason "a task now needs a worktree to start a session".

- [ ] **Step 5: Run the full suite**

Run: `uv run --with pytest --with pyyaml pytest -q tests`
Expected: all passed. If `test_migrate.py` fails, that is fixed in Task 8. Do not change it here.

- [ ] **Step 6: Commit**

```bash
git add -A software-factory
git commit -m "step editor: every task runs in its own worktree"
```

---

### Task 8: Data version 2 and the migration

**Files:**
- Create: `software-factory/migrations/1-to-2.py`
- Modify: `software-factory/lib/factory/version.py`, `software-factory/lib/factory/migrate.py`, `software-factory/lib/factory/commands.py` (`migrate_cmd`)
- Modify test: `software-factory/tests/test_migrate.py`
- Test: `software-factory/tests/test_migrate_v2.py`

**Interfaces:**
- Produces:
  - `version.DATA_VERSION == 2` by default
  - migration module functions `check_repo(fdir)`, `check_library(lib)`, `migrate_repo(fdir)`, `migrate_library(lib)`
  - `migrate.migrate()` result gets `errors: list[str]` and `warnings: list[str]`. Errors raise unless `dry_run`.

- [ ] **Step 1: Write the failing tests**

`tests/test_migrate_v2.py`:

```python
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
```

In `tests/test_migrate.py` fixture `v2`:

- Before `make_task`, set both `factory.yaml` files to version 1. Do this for the repository after `git add/commit` and for the library before the commit, using the same `yaml` load and dump as `set_version` above.
- Remove `"FACTORY_DATA_VERSION": "2"` from `env`, because 2 is now the default. Keep `FACTORY_MIGRATIONS_DIR`.
- Record: "the data version default is now 2, so the fixture writes version 1 data".

- [ ] **Step 2: Run the tests to see them fail**

Run: `uv run --with pytest --with pyyaml pytest -q tests/test_migrate_v2.py tests/test_migrate.py`
Expected: FAIL. The version is 1 and the script is missing.

- [ ] **Step 3: Write `migrations/1-to-2.py`**

```python
import json
import os
import re
from pathlib import Path

import yaml

KEY_RE = re.compile(r"[a-z][a-z0-9_]*")
FRONT_RE = re.compile(r"^---\n(.*?)\n---\n?(.*)$", re.S)
PLACEHOLDER_RE = re.compile(r"\{\{([^{}]*)\}\}")
TYPE_MAP = {None: "ai", "prompt": "ai", "skill": "ai", "composite": "group", "script": "command"}
NEW_TYPES = ("ai", "command", "group")
REMOVED_PIPELINE = "new-step-assistant"
FIELD_ORDER = ("id", "description", "category", "type", "outputs", "done_when", "done_check", "config", "required",
               "run_in", "model", "effort", "requires", "column", "wait_external", "steps")
KEY_RULE = "must use lowercase letters, digits and `_`, and start with a letter"


def is_key(name):
    return isinstance(name, str) and KEY_RE.fullmatch(name) is not None


def read_step(path):
    m = FRONT_RE.match(path.read_text())
    if not m:
        return None
    return yaml.safe_load(m.group(1)) or {}, m.group(2).lstrip("\n")


def key_block(title, lines):
    return title + "\n" + "\n".join(lines)


def convert(manifest, body):
    m = dict(manifest)
    old_type = m.get("type")
    new_type = TYPE_MAP.get(old_type, old_type)
    m["type"] = new_type
    reads = list(m.pop("reads", None) or [])
    writes = list(m.pop("writes", None) or [])
    if writes and new_type != "group":
        outputs = dict(m.get("outputs") or {})
        for key in writes:
            outputs.setdefault(key, {"type": "text", "description": "", "optional": True})
        m["outputs"] = outputs
    if old_type == "script":
        first = next((line.strip() for line in body.splitlines() if line.strip()), "")
        body = f'bash "$FACTORY_STEP_DIR/{first}"\n'
    if new_type == "ai":
        blocks = []
        if reads:
            blocks.append(key_block("Task keys:", [f"- {k}: {{{{{k}}}}}" for k in reads]))
        config = m.get("config") or {}
        if config:
            blocks.append(key_block("Config:", [f"- {k}: {{{{config.{k}}}}}" for k in config]))
        if blocks:
            body = body.rstrip("\n") + "\n\n" + "\n\n".join(blocks) + "\n"
    if new_type == "group":
        body = ""
    return m, body, reads + writes


def dump(manifest, body):
    data = {k: v for k, v in manifest.items() if k == "required" or v not in (None, "", [], {})}
    ordered = {k: data[k] for k in FIELD_ORDER if k in data}
    ordered.update({k: v for k, v in data.items() if k not in ordered})
    text = "---\n" + yaml.safe_dump(ordered, sort_keys=False, allow_unicode=True) + "---\n"
    if ordered.get("type") != "group" and body.strip():
        text += "\n" + body.strip("\n") + "\n"
    return text


STEP_ID_RE = re.compile(r"[a-z][a-z0-9_-]{0,63}")
RUN_IN = ("session", "subagent")


def ai_errors(path, new_body, config):
    errors = []
    for m in PLACEHOLDER_RE.finditer(new_body):
        inner = m.group(1)
        if inner.startswith("config."):
            if inner[len("config."):] not in config:
                errors.append(f"{path}: the placeholder {m.group(0)} uses a config key that the step does not declare.")
        elif not is_key(inner):
            errors.append(f"{path}: the text {m.group(0)} is not a valid placeholder. Change it, then migrate again.")
    if not new_body.strip():
        errors.append(f"{path}: the prompt is empty. Write a prompt, then migrate again.")
    return errors


def type_errors(path, manifest, new_m, new_body, config):
    stype = new_m["type"]
    if stype not in NEW_TYPES:
        return [f"{path}: unknown step type `{manifest.get('type')}`."]
    if stype == "ai":
        return ai_errors(path, new_body, config)
    if stype == "command":
        errors = []
        if PLACEHOLDER_RE.search(new_body):
            errors.append(f"{path}: the command contains `{{{{`. Remove it, then migrate again.")
        if not new_body.strip() or new_body.strip() == 'bash "$FACTORY_STEP_DIR/"':
            errors.append(f"{path}: the script step names no script file. Write the file name in the body, then migrate again.")
        return errors
    children = new_m.get("steps")
    if not isinstance(children, list) or not children:
        return [f"{path}: the composite step has no `steps` list. Add its child steps, then migrate again."]
    return []


def step_errors(path, manifest, new_m, new_body, used):
    errors = []
    if not (isinstance(new_m.get("id"), str) and STEP_ID_RE.fullmatch(new_m["id"])):
        errors.append(f"{path}: the step id `{new_m.get('id')}` must be lowercase: letters, digits, `-` or `_`, starting with a letter.")
    for key in used:
        if not is_key(key):
            errors.append(f"{path}: the key `{key}` {KEY_RULE}.")
    config = new_m.get("config") or {}
    if not isinstance(config, dict):
        errors.append(f"{path}: `config` must be a mapping of config keys.")
        config = {}
    for key in config:
        if not is_key(key):
            errors.append(f"{path}: the config key `{key}` {KEY_RULE}.")
    errors += type_errors(path, manifest, new_m, new_body, config)
    if PLACEHOLDER_RE.search(str(new_m.get("done_check") or "")):
        errors.append(f"{path}: the done check contains `{{{{`. Remove it, then migrate again.")
    run_in = new_m.get("run_in")
    if run_in is not None and run_in not in RUN_IN:
        errors.append(f"{path}: `run_in` must be `session` or `subagent`.")
    return errors


def folder_errors(root):
    root = Path(root)
    errors = []
    for path in sorted((root / "steps").glob("*.md")):
        parsed = read_step(path)
        if parsed is None:
            errors.append(f"{path}: the step file has no YAML frontmatter.")
            continue
        manifest, body = parsed
        manifest.setdefault("id", path.stem)
        new_m, new_body, used = convert(manifest, body)
        errors += step_errors(path, manifest, new_m, new_body, used)
    for path in sorted((root / "pipelines").glob("*.yaml")):
        data = yaml.safe_load(path.read_text()) or {}
        for key in (data.get("inputs") or {}):
            if not is_key(key):
                errors.append(f"{path}: the input `{key}` {KEY_RULE}.")
    return errors


def task_problems(factory_dir):
    errors, warnings = [], []
    for path in sorted((Path(factory_dir) / "tasks").glob("*/task.json")):
        task = json.loads(path.read_text())
        if task.get("status") == "finished":
            continue
        tid = task.get("id")
        if task.get("pipeline") == REMOVED_PIPELINE:
            errors.append(f"Task {tid} uses the removed pipeline `{REMOVED_PIPELINE}`. Delete it with the previous factory version, "
                          f"or move `.factory/tasks/{tid}` to `.factory/tasks/archive/{tid}`, then migrate again.")
        for key in (task.get("state") or {}):
            if not is_key(key):
                warnings.append(f"Task {tid}: the state key `{key}` does not follow the key name rule. Steps cannot use it in a placeholder.")
    return errors, warnings


def check_repo(factory_dir):
    errors, warnings = task_problems(factory_dir)
    return folder_errors(factory_dir) + errors, warnings


def check_library(library_dir):
    return folder_errors(library_dir), []


def write_atomic(path, text):
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text)
    os.replace(tmp, path)


def convert_folder(root):
    for path in sorted((Path(root) / "steps").glob("*.md")):
        parsed = read_step(path)
        if parsed is None:
            continue
        manifest, body = parsed
        manifest.setdefault("id", path.stem)
        new_m, new_body, _ = convert(manifest, body)
        write_atomic(path, dump(new_m, new_body))


def migrate_repo(factory_dir):
    convert_folder(factory_dir)


def migrate_library(library_dir):
    convert_folder(library_dir)
```

- [ ] **Step 4: Change `version.py`, `migrate.py` and the CLI**

`version.py`: `DATA_VERSION = int(os.environ.get("FACTORY_DATA_VERSION", "2"))`.

`migrate.py`:

- Add:

```python
def run_checks(ctx, p):
    errors, warnings = [], []
    targets = [("library", ctx.library(), "check_library"), ("repo", ctx.fdir, "check_repo")]
    for part, root, name in targets:
        if not p[part]["migrate"]:
            continue
        for v in range(p[part]["from"], p["current"]):
            check = getattr(load_script(v), name, None)
            if check:
                e, w = check(root)
                errors += e
                warnings += w
    return errors, warnings
```

- In `migrate()`, right after `p = plan(ctx)`:

```python
    p["errors"], p["warnings"] = run_checks(ctx, p)
    p["backups"], p["library_commit"] = [], None
    if dry_run:
        return p
    if p["errors"]:
        raise FactoryError("The migration cannot start. Fix these first:\n" + "\n".join(f"- {e}" for e in p["errors"]))
```

- Remove the old `p["backups"], p["library_commit"] = [], None` line and the old `if dry_run: return p`.

`commands.py` `migrate_cmd`: in the text branch, after the version lines:

```python
    for e in result.get("errors", []):
        print(f"Error: {e}")
    for w in result.get("warnings", []):
        print(f"Warning: {w}")
```

- [ ] **Step 5: Run the tests**

Run: `uv run --with pytest --with pyyaml pytest -q tests/test_migrate_v2.py tests/test_migrate.py tests/test_repo_version.py tests/test_init_menu.py`
Expected: all passed.

- [ ] **Step 6: Commit**

```bash
git add -A software-factory
git commit -m "step editor: data version 2 and the 1-to-2 migration"
```

---

### Task 9: Milestone 1 close

**Files:**
- Modify: `software-factory/tests/e2e_herdr.py`

- [ ] **Step 1: Move the end-to-end test data to `command` steps**

In `tests/e2e_herdr.py`:

- `STEP_ONE`:
  - `type: script` becomes `type: command`
  - remove the `done_check` line
  - the body `e2e-one.sh` becomes `bash "$FACTORY_STEP_DIR/e2e-one.sh"`
- `STEP_TWO`: the same changes, with `e2e-two.sh`.
- `STEP_HOLD`: `type: prompt` becomes `type: ai`.
- In the `record` text at line 283, "first script step" becomes "first command step".
- Search the file for `run-script` and replace it with `run-command`. Search for `--worktree` and remove it.

This file needs Herdr and is not run in this build.

- [ ] **Step 2: Run the full suite**

Run: `uv run --with pytest --with pyyaml pytest -q tests`
Expected: all passed. Fix any failure before you continue. Each test you change gets a line in `step-editor-updated-tests.md`.

- [ ] **Step 3: Commit the milestone**

```bash
git add -A software-factory verification/software-factory/step-editor-updated-tests.md
git commit -m "step editor: milestone 1, step format and runtime"
```

---

## Milestone 2: Available keys

### Task 10: `keys.available`, pipeline checks and `factory pipeline keys`

**Files:**
- Modify: `software-factory/lib/factory/keys.py`, `pipeline_check.py`, `commands.py`, `api.py`
- Test: `software-factory/tests/test_pipeline_keys.py`
- Modify test: `software-factory/tests/test_pipeline_check.py`

**Interfaces:**
- Consumes: `registry.normalize_entry`, `registry.CREATE_WORKTREE`
- Produces:
  - `keys.available(reg, data, at=None) -> list[{"name", "type", "source", "set"}]`
  - CLI `factory pipeline keys <id> [--at N] [--json]`
  - route `POST /api/pipelines/keys` with body `{data, at}`, which returns the rows

- [ ] **Step 1: Write the failing tests**

`tests/test_pipeline_keys.py`:

```python
import pytest

from conftest import write_pipeline, write_step
from serverutil import info, request


@pytest.fixture
def kp(inited):
    write_step(inited.fdir, "spec", {"outputs": {"spec": {"type": "file", "description": "Spec"}}})
    write_step(inited.fdir, "branchy", {"outputs": {"branch": {"type": "text", "description": "B", "optional": True}}})
    write_step(inited.fdir, "uses", {}, body="Use {{spec}}, {{branch}}, {{summary}} and {{ghost}}.\n")
    write_pipeline(inited.fdir, {"id": "kp", "inputs": {"crash_url": {"type": "text", "description": "Link"},
                                                       "notes": {"type": "long-text", "description": "N"}},
                                 "steps": ["spec", "branchy", "uses"]})
    return inited


def test_keys_cli_text_and_json(kp):
    rows = {r["name"]: r for r in kp.factory.json("pipeline", "keys", "kp")}
    assert rows["task_id"] == {"name": "task_id", "type": "text", "source": "factory", "set": "always"}
    assert rows["summary"]["set"] == "maybe" and rows["summary"]["type"] == "long-text"
    assert rows["crash_url"]["source"] == "input" and rows["notes"]["type"] == "long-text"
    assert rows["spec"] == {"name": "spec", "type": "file", "source": "step spec", "set": "always"}
    assert rows["branch"]["set"] == "maybe"
    at2 = {r["name"] for r in kp.factory.json("pipeline", "keys", "kp", "--at", "2")}
    assert "spec" in at2 and "branch" not in at2
    at1 = {r["name"] for r in kp.factory.json("pipeline", "keys", "kp", "--at", "1")}
    assert "spec" not in at1
    text = kp.factory("pipeline", "keys", "kp").stdout
    assert "spec (file) from step spec, always set" in text and "summary (long-text) from factory, maybe set" in text
    r = kp.factory("pipeline", "keys", "kp", "--at", "9", check=False)
    assert r.returncode == 1 and "between 1 and 4" in r.stderr


def test_latest_source_wins(kp):
    write_step(kp.fdir, "respec", {"outputs": {"spec": {"type": "text", "description": "S", "optional": True}}})
    write_pipeline(kp.fdir, {"id": "two", "steps": ["spec", "respec"]})
    rows = {r["name"]: r for r in kp.factory.json("pipeline", "keys", "two")}
    assert rows["spec"]["source"] == "step respec" and rows["spec"]["set"] == "maybe"


def test_new_check_warnings(kp):
    write_step(kp.fdir, "retype", {"outputs": {"crash_url": {"type": "file", "description": "C"}}})
    write_pipeline(kp.fdir, {"id": "warn", "inputs": {"crash_url": {"type": "text"}}, "steps": ["uses", "retype"]})
    out = kp.factory("pipeline", "check", "warn").stdout
    assert "Step `uses` uses `ghost`, which no input, earlier step or factory key sets." in out
    assert "Step `uses` uses `spec`" in out
    assert "The key `crash_url` is set with two types: text (input) and file (step retype)." in out
    assert "uses `summary`" not in out


def test_own_output_is_not_an_unset_key(kp):
    write_step(kp.fdir, "selfcheck", {"outputs": {"plan": {"type": "file", "description": "P"}},
                                      "done_check": 'test -f "$FACTORY_KEY_PLAN"'}, body="Write the plan.\n")
    write_pipeline(kp.fdir, {"id": "own", "steps": ["selfcheck"]})
    out = kp.factory("pipeline", "check", "own").stdout
    assert "uses `plan`" not in out


def test_bad_input_name_and_type_are_errors(kp):
    write_pipeline(kp.fdir, {"id": "bad", "inputs": {"Bad-Name": {}, "ok": {"type": "number"}}, "steps": ["spec"]})
    r = kp.factory("pipeline", "check", "bad", check=False)
    assert r.returncode == 1 and "The input `Bad-Name`" in r.stdout and "unknown type `number`" in r.stdout


def test_keys_route(kp):
    kp.factory("pipeline", "edit", "kp")
    i = info(kp.fdir)
    try:
        data = {"id": "kp", "steps": ["spec", "uses"]}
        status, rows = request(i, "POST", "/api/pipelines/keys", {"data": data, "at": 2})
        assert status == 200 and "spec" in [r["name"] for r in rows]
        assert request(i, "POST", "/api/pipelines/keys", {"data": data, "at": 2}, token=False)[0] == 401
    finally:
        kp.factory("server", "stop", check=False)
```

In `tests/test_pipeline_check.py` `test_each_problem_type`, add `assert "uses \`nothing\`, which no input" in warnings`. Record it as "the `reads` warning was replaced by the computed-keys warning".

- [ ] **Step 2: Run the tests to see them fail**

Run: `uv run --with pytest --with pyyaml pytest -q tests/test_pipeline_keys.py`
Expected: FAIL with `invalid choice: 'keys'`.

- [ ] **Step 3: Implement**

Add to `keys.py`:

```python
def put(rows, name, ktype, source, set_state):
    rows.pop(name, None)
    rows[name] = {"name": name, "type": ktype, "source": source, "set": set_state}


def pipeline_entries(data):
    from .registry import normalize_entry
    return [normalize_entry(e) for e in data.get("steps") or []]


def start_rows(data):
    rows = {}
    for name, spec in FACTORY_KEYS.items():
        put(rows, name, spec["type"], "factory", spec["set"])
    for name, spec in (data.get("inputs") or {}).items():
        put(rows, name, key_type(spec), "input", "always")
    return rows


def entry_leaves(reg, entry):
    from .errors import FactoryError
    sid = entry.get("id")
    if sid not in reg.steps:
        return []
    try:
        return [reg.steps[path[-1]] for path in reg.leaves(sid) if path[-1] in reg.steps]
    except FactoryError:
        return []


def add_outputs(rows, leaf):
    for name, out in outputs_of(leaf).items():
        put(rows, name, out["type"], f"step {leaf.id}", "maybe" if out["optional"] else "always")


def available(reg, data, at=None):
    from .errors import FactoryError
    entries = pipeline_entries(data)
    last = len(entries) + 1
    at = last if at is None else at
    if not isinstance(at, int) or not 1 <= at <= last:
        raise FactoryError(f"The position must be between 1 and {last}.")
    rows = start_rows(data)
    for entry in entries[:at - 1]:
        for leaf in entry_leaves(reg, entry):
            add_outputs(rows, leaf)
    return list(rows.values())
```

`pipeline_check.py`:

- Remove `ALWAYS_AVAILABLE` and the `available = ...` line.
- Add `from . import keys` to the imports.
- Before the `for i, entry in enumerate(entries):` loop:

```python
    for name, spec in (data.get("inputs") or {}).items():
        if not keys.is_key(name):
            error(f"The input `{name}` must use lowercase letters, digits and `_`, and start with a letter.")
        elif keys.key_type(spec) not in keys.KEY_TYPES:
            error(f"The input `{name}` has an unknown type `{keys.key_type(spec)}`. Use text, long-text or file.")
    rows = keys.start_rows(data)
    first_type = {name: (r["type"], r["source"]) for name, r in rows.items() if r["source"] == "input"}
    warned_types = set()
```

- Inside the leaf loop, after the column check, replace the removed `reads`/`writes` lines with:

```python
            own_outputs = set(keys.outputs_of(leaf))
            for key in keys.leaf_uses(leaf):
                if key not in rows and key not in own_outputs:
                    warning(f"Step `{leaf.id}` uses `{key}`, which no input, earlier step or factory key sets.")
            for name, out in keys.outputs_of(leaf).items():
                seen = first_type.setdefault(name, (out["type"], f"step {leaf.id}"))
                if seen[0] != out["type"] and name not in warned_types:
                    warned_types.add(name)
                    warning(f"The key `{name}` is set with two types: {seen[0]} ({seen[1]}) and {out['type']} (step {leaf.id}).")
            keys.add_outputs(rows, leaf)
```

`commands.py` `register`: after `pc`, add `pk = ps.add_parser("keys", parents=[common]); pk.add_argument("id"); pk.add_argument("--at", type=int, default=None)`. Add:

```python
@cli.command("pipeline keys")
def pipeline_keys_cmd(args):
    from . import keys
    from .registry import Registry
    reg = Registry.load(ctx_of(args))
    rows = keys.available(reg, reg.pipeline(args.id).data, args.at)
    if args.json:
        cli.emit(rows, True)
        return
    for r in rows:
        print(f"{r['name']} ({r['type']}) from {r['source']}, {r['set']} set")
```

`api.py`:

```python
@route("POST", "/api/pipelines/keys")
def pipeline_keys(server, query, body):
    from . import keys
    return keys.available(registry(server), body["data"], body.get("at"))
```

- [ ] **Step 4: Run the tests**

Run: `uv run --with pytest --with pyyaml pytest -q tests/test_pipeline_keys.py tests/test_pipeline_check.py tests/test_editor_api.py`
Expected: all passed.

- [ ] **Step 5: Commit**

```bash
git add -A software-factory
git commit -m "step editor: available keys, key checks and factory pipeline keys"
```

---

### Task 11: Typed pipeline inputs at launch

**Files:**
- Modify: `software-factory/lib/factory/launch.py`, `pipeline_store.py`, `web/dashboard.html`, `web/editor.html` (input type select), `skills/software-factory/SKILL.md`
- Test: `software-factory/tests/test_typed_inputs.py`

**Interfaces:**
- Produces:
  - `report["inputs"]`: the resolved input values. `launch` saves them.
  - `list_pipelines` rows get `inputs`.

- [ ] **Step 1: Write the failing tests**

```python
from conftest import task_json, write_pipeline, write_step
from serverutil import info, request


def setup(inited):
    write_step(inited.fdir, "w", {})
    write_pipeline(inited.fdir, {"id": "f", "inputs": {"log": {"type": "file", "description": "Log file"},
                                                      "notes": {"type": "long-text", "description": "Notes"}},
                                 "steps": ["w"]})


def test_missing_file_input_is_a_dry_run_error(inited):
    setup(inited)
    rep = inited.factory.json("launch", "f", "--description", "x", "--input", "log=nope.txt", "--input", "notes=a", "--dry-run", check=False)
    expected = f"The input `log` is a path that does not exist: {inited.repo / 'nope.txt'}."
    assert not rep["ok"] and expected in rep["errors"]


def test_relative_file_input_saved_absolute(inited):
    setup(inited)
    (inited.repo / "logs").mkdir()
    (inited.repo / "logs" / "a.txt").write_text("x")
    task = inited.factory.json("launch", "f", "--description", "x", "--input", "log=logs/a.txt", "--input", "notes=line one\nline two")
    saved = task_json(inited.fdir, task["id"])["state"]
    assert saved["log"] == str((inited.repo / "logs" / "a.txt").resolve())
    assert saved["notes"] == "line one\nline two"


def test_pipeline_list_has_typed_inputs(inited):
    setup(inited)
    rows = {r["id"]: r for r in inited.factory.json("pipeline", "list")}
    assert rows["f"]["inputs"]["notes"] == {"type": "long-text", "description": "Notes"}
    assert rows["f"]["inputs"]["log"]["type"] == "file"


def test_dashboard_has_textarea_for_long_text(inited):
    inited.factory("dashboard")
    i = info(inited.fdir)
    try:
        status, page = request(i, "GET", "/dashboard")
        assert 'type === "long-text"' in page and "relative to the main repository" in page
    finally:
        inited.factory("server", "stop", check=False)
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `uv run --with pytest --with pyyaml pytest -q tests/test_typed_inputs.py`
Expected: FAIL.

- [ ] **Step 3: Implement**

`launch.py`:

- Add `from . import keys` and `from pathlib import Path` (already there).
- Add:

```python
def resolve_inputs(ctx, pipeline, inputs, report):
    resolved = dict(inputs)
    for name, spec in pipeline.inputs.items():
        value = str(inputs.get(name, "")).strip()
        if keys.key_type(spec) != "file" or not value:
            continue
        path = (ctx.main / Path(value).expanduser()).resolve()
        if not path.exists():
            report["errors"].append(f"The input `{name}` is a path that does not exist: {path}.")
        resolved[name] = str(path)
    return resolved
```

- In `plan_launch`:
  - add `"inputs": {}` to the initial `report` dict
  - after the `missing_inputs` line: `report["inputs"] = resolve_inputs(ctx, pipeline, inputs, report)`
- In `new_task`, `task_state = dict(report["inputs"])`. Remove the `inputs` parameter use for the state.

`pipeline_store.list_pipelines`:

```python
def input_rows(data):
    from . import keys
    return {name: {"type": keys.key_type(spec), "description": (spec or {}).get("description", "") if isinstance(spec, dict) else ""}
            for name, spec in (data.get("inputs") or {}).items()}


def list_pipelines(reg):
    return [{"id": p.id, "description": p.data.get("description", ""), "level": p.level, "path": str(p.path),
             "inputs": input_rows(p.data)} for p in sorted(reg.pipelines.values(), key=lambda p: p.id)]
```

`dashboard.html` `loadInputs`: replace the `const node = el("input", { type: "text" });` line with:

```js
      const spec = detail.data.inputs[name] || {};
      const type = spec.type || "text";
      const node = type === "long-text"
        ? el("textarea", { rows: "4" })
        : el("input", { type: "text", placeholder: type === "file" ? "Path, absolute or relative to the main repository" : "" });
```

`editor.html`:

- Add `const KEY_TYPES = ["text", "long-text", "file"];` after `SHOW_HIDDEN_KEY`.
- In `modelOf`: `inputs: Object.entries(data.inputs || {}).map(([key, v]) => ({ key, type: (v && v.type) || "text", description: (v && v.description) || "" })),`.
- In `dataOf`: `for (const r of m.inputs) if (r.key) data.inputs[r.key] = { type: r.type, description: r.description };`.
- Add this function and use it in `renderForm` as `field("inputs", inputRows(m.inputs))`:

```js
function inputRows(rows) {
  const box = el("div");
  const draw = () => {
    clear(box);
    rows.forEach((r, i) => box.append(el("div", { class: "row" },
      textInput(r.key, (v) => { r.key = v; changed(); }, "key"),
      selectInput(KEY_TYPES, r.type || "text", (v) => { r.type = v; changed(); }),
      textInput(r.description, (v) => { r.description = v; changed(); }, "description"),
      el("button", { type: "button", onclick: () => { rows.splice(i, 1); draw(); changed(); } }, "Remove"))));
    box.append(el("button", { type: "button", onclick: () => { rows.push({ key: "", type: "text", description: "" }); draw(); } }, "Add"));
  };
  draw();
  return box;
}
```

`SKILL.md` "Launch a new pipeline": add this sentence after "follow the built-in step `create-task`": "Ask each input by its type: one line for `text`, several lines allowed for `long-text`, a path for `file`."

- [ ] **Step 4: Run the tests**

Run: `uv run --with pytest --with pyyaml pytest -q tests/test_typed_inputs.py tests/test_launch.py tests/test_dashboard_api.py tests/test_editor_api.py tests/test_docs.py`
Expected: all passed.

- [ ] **Step 5: Commit**

```bash
git add -A software-factory
git commit -m "step editor: typed pipeline inputs at launch"
```

---

### Task 12: Milestone 2 close

- [ ] **Step 1: Run the full suite**

Run: `uv run --with pytest --with pyyaml pytest -q tests`
Expected: all passed.

- [ ] **Step 2: Commit**

```bash
git add -A software-factory verification/software-factory/step-editor-updated-tests.md
git commit -m "step editor: milestone 2, available keys"
```

---

## Milestone 3: Step editor

### Task 13: Step store and API

**Files:**
- Create: `software-factory/lib/factory/step_store.py`
- Modify: `software-factory/lib/factory/api.py`
- Test: `software-factory/tests/test_step_editor_api.py`

**Interfaces:**
- Consumes: `step_format.validate/clean/dump`, `keys.*`, `render.*`, `step_delete.find_users`, `step_delete.OTHER_REPOS`, `pipeline_store.target_root`, `library.in_git`, `library.message`, `registry.Step`
- Produces:
  - `step_store.form_data(ctx) -> dict`
  - `step_store.check(ctx, manifest, body) -> {errors, warnings, uses, outputs}`
  - `step_store.preview(ctx, manifest, body) -> {text}`
  - `step_store.impact(ctx, sid) -> {pipelines, groups, tasks, warnings}`
  - `step_store.save(ctx, manifest, body, level, mode) -> {path, level, warnings, library_commit}`
  - routes:
    - `GET /api/step-form`
    - `POST /api/steps/check`, `/api/steps/preview`, `/api/steps/impact`, `/api/steps/save`
    - each POST takes the body `{manifest, body}`, `{id}` or `{manifest, body, level, mode}`

- [ ] **Step 1: Write the failing tests**

```python
import pytest
import yaml

from conftest import commit_all, make_task, write_pipeline, write_step
from factory import repo
from serverutil import info, request


@pytest.fixture
def se(inited):
    commit_all(inited.library.parent, "library")
    write_step(inited.library, "gen", {"category": "git"}, body="Generic.\n")
    write_step(inited.fdir, "loc", {"category": "review"}, body="Local.\n")
    write_pipeline(inited.fdir, {"id": "uses-loc", "steps": ["loc"]})
    make_task(repo.load_ctx(cwd=inited.repo), tid="busy",
              steps=[{"id": "loc", "path": ["loc"], "with": {}, "column": None, "model": None, "effort": None}])
    inited.factory("pipeline", "edit")
    yield inited, info(inited.fdir)
    inited.factory("server", "stop", check=False)


NEW = {"id": "fresh", "description": "Fresh", "category": "test", "type": "ai",
       "outputs": {"spec": {"type": "file", "description": "Spec"}}, "config": {"style": {"description": "S", "default": "x"}}}


def save(i, manifest, body, level="local", mode="new"):
    return request(i, "POST", "/api/steps/save", {"manifest": manifest, "body": body, "level": level, "mode": mode})


def test_save_new_local_step(se):
    inited, i = se
    status, out = save(i, NEW, "Write {{description}} with {{config.style}}.")
    assert status == 200 and out["library_commit"] is None
    path = inited.fdir / "steps" / "fresh.md"
    assert out["path"] == str(path) and "type: ai" in path.read_text()
    assert "fresh" in [s["id"] for s in request(i, "GET", "/api/steps")[1]]


def test_save_generic_offers_commit(se):
    inited, i = se
    status, out = save(i, {**NEW, "id": "fresh-gen"}, "Do it.", level="generic")
    assert status == 200 and out["library_commit"]["message"] == "Factory library: add step fresh-gen"
    status, out = save(i, {**NEW, "id": "fresh-gen", "description": "Changed"}, "Do it.", level="generic", mode="edit")
    assert status == 200 and out["library_commit"]["message"] == "Factory library: update step fresh-gen"


def test_duplicate_id_refused_hidden_included(se):
    inited, i = se
    assert save(i, {**NEW, "id": "loc"}, "x")[0] == 409
    inited.factory("step", "hide", "gen")
    status, body = save(i, {**NEW, "id": "gen"}, "x")
    assert status == 409 and "already exists" in body["error"]


def test_builtin_edit_refused_and_copy_to_local(se):
    inited, i = se
    status, detail = request(i, "GET", "/api/steps/user-validation")
    status, body = save(i, detail["manifest"], detail["body"], mode="edit", level="local")
    assert status == 400 and "Built-in steps cannot be edited" in body["error"]
    status, out = save(i, detail["manifest"], detail["body"], mode="copy-local")
    assert status == 200 and out["level"] == "local"
    assert request(i, "GET", "/api/steps/user-validation")[1]["level"] == "local"
    assert save(i, detail["manifest"], detail["body"], mode="copy-local")[0] == 409


def test_errors_block_save_warnings_do_not(se):
    inited, i = se
    status, body = save(i, {**NEW, "id": "broken", "type": "command"}, "echo {{x}}")
    assert status == 400 and "A command cannot use" in body["error"]
    status, out = save(i, {**NEW, "id": "warned", "description": ""}, "x")
    assert status == 200 and "The description is empty." in out["warnings"]


def test_save_drops_empty_fields(se):
    inited, i = se
    manifest = {**NEW, "id": "tidy", "run_in": "", "model": "", "effort": "", "column": "", "outputs": {}, "requires": [], "done_check": ""}
    assert save(i, manifest, "Body.")[0] == 200
    head = yaml.safe_load((inited.fdir / "steps" / "tidy.md").read_text().split("---\n")[1])
    assert not {"run_in", "model", "effort", "column", "outputs", "requires", "done_check"} & set(head)
    assert request(i, "POST", "/api/steps/save", {"manifest": {**NEW, "id": "nobody"}, "level": "local", "mode": "new"})[0] == 400


def test_check_returns_uses_and_group_problems(se):
    inited, i = se
    status, out = request(i, "POST", "/api/steps/check", {"manifest": NEW, "body": "Use {{spec}} and {{ticket}}."})
    assert out["errors"] == [] and out["uses"] == ["spec", "ticket"] and list(out["outputs"]) == ["spec"]
    group = {"id": "grp", "description": "G", "type": "group", "steps": ["loc", "missing"]}
    status, out = request(i, "POST", "/api/steps/check", {"manifest": group, "body": ""})
    assert "The child step `missing` does not exist." in out["errors"]
    loop = {"id": "loc", "description": "L", "type": "group", "steps": ["loc"]}
    status, out = request(i, "POST", "/api/steps/check", {"manifest": loop, "body": ""})
    assert any("loop" in e for e in out["errors"])


def test_impact(se):
    inited, i = se
    status, out = request(i, "POST", "/api/steps/impact", {"id": "loc"})
    assert out["pipelines"] == [{"id": "uses-loc", "level": "local"}] and out["tasks"] == [{"id": "busy"}]
    assert out["warnings"] == []
    status, out = request(i, "POST", "/api/steps/impact", {"id": "gen"})
    assert out["warnings"] == ["Other repositories that use this library are not checked."]


def test_preview(se):
    inited, i = se
    status, out = request(i, "POST", "/api/steps/preview", {"manifest": {**NEW, "done_when": "Done."}, "body": "Write {{description}} with {{config.style}}."})
    assert out["text"].startswith("Write <description> with <config.style>.\n\n---\nStep: fresh\n")
    assert "- `spec` (file): Spec." in out["text"] and out["text"].rstrip().endswith("run `factory done`.")


def test_form_data(se):
    inited, i = se
    status, out = request(i, "GET", "/api/step-form")
    assert "git" in out["categories"] and out["library"] is True
    assert [k["name"] for k in out["factory_keys"]] == ["task_id", "description", "summary"]
    assert "user-validation" in out["step_ids"]


def test_routes_need_token(se):
    inited, i = se
    for path in ("/api/steps/check", "/api/steps/preview", "/api/steps/impact", "/api/steps/save"):
        assert request(i, "POST", path, {}, token=False)[0] == 401
    assert request(i, "GET", "/api/step-form", token=False)[0] == 401
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `uv run --with pytest --with pyyaml pytest -q tests/test_step_editor_api.py`
Expected: FAIL with 404 on the new routes.

- [ ] **Step 3: Write `step_store.py`**

```python
from pathlib import Path

from . import fsio, keys, library, render, step_format
from .errors import ExistsError, FactoryError
from .registry import Registry, Step

BUILTIN_EDIT = "Built-in steps cannot be edited. Copy the step to local instead."
MODES = ("new", "edit", "copy-local")


def require_input(manifest, body):
    if not isinstance(manifest, dict):
        raise FactoryError("The manifest must be an object.")
    if not isinstance(body, str):
        raise FactoryError("The body must be text.")
    return step_format.clean(manifest)


def form_data(ctx):
    reg = Registry.load(ctx)
    factory_keys = [{"name": n, "type": s["type"], "source": "factory", "set": s["set"]} for n, s in keys.FACTORY_KEYS.items()]
    return {"categories": reg.categories(), "columns": ctx.columns(), "library": ctx.library() is not None,
            "factory_keys": factory_keys, "key_types": list(keys.KEY_TYPES), "step_ids": sorted(reg.variants)}


def candidate(manifest, body):
    sid = manifest.get("id")
    return Step(sid, "candidate", Path(f"{sid}.md"), dict(manifest), body)


def check(ctx, manifest, body):
    manifest = require_input(manifest, body)
    errors, warnings = step_format.validate(manifest, body)
    uses, outputs = [], {}
    if not errors:
        reg = Registry.load(ctx)
        step = candidate(manifest, body)
        if step.type == "group":
            errors += [f"The child step `{c}` does not exist." for c in step.children if c != step.id and c not in reg.steps]
        if not errors:
            reg.steps[step.id] = step
            try:
                reg.check_loops()
                uses, outputs = keys.step_uses(reg, step.id), keys.step_outputs(reg, step.id)
            except FactoryError as e:
                errors.append(str(e))
    return {"errors": errors, "warnings": warnings, "uses": uses, "outputs": outputs}


def preview(ctx, manifest, body):
    manifest = require_input(manifest, body)
    step = candidate(manifest, body)
    text = render.step_text(step, render.show_names(body), f"Step: {step.id}", keys.outputs_of(step), step.model, step.effort)
    return {"text": text}


def impact(ctx, sid):
    from .step_delete import OTHER_REPOS, find_users
    reg = Registry.load(ctx)
    step = reg.step(sid)
    users = find_users(ctx, reg, sid, step)
    return {
        "pipelines": [{"id": u["id"], "level": u["level"]} for u in users if u["kind"] == "pipeline"],
        "groups": [{"id": u["id"], "level": u["level"]} for u in users if u["kind"] == "group"],
        "tasks": [{"id": u["id"]} for u in users if u["kind"] == "task"],
        "warnings": [OTHER_REPOS] if step.level == "generic" else [],
    }


def target(ctx, reg, sid, level, mode):
    from .pipeline_store import target_root
    variants = reg.variants.get(sid, [])
    if mode == "new":
        path = target_root(ctx, level) / "steps" / f"{sid}.md"
        if variants or path.exists():
            raise ExistsError(f"A step named `{sid}` already exists.")
        return level, path, "add"
    if not variants:
        raise FactoryError(f"The step `{sid}` does not exist.")
    if mode == "edit":
        current = variants[-1]
        if current.level == "builtin":
            raise FactoryError(BUILTIN_EDIT)
        if current.level != level:
            raise FactoryError(f"The step `{sid}` in use is {current.level}, not {level}.")
        return level, current.path, "update"
    if any(s.level == "local" for s in variants):
        raise ExistsError(f"A local step named `{sid}` already exists.")
    return "local", ctx.fdir / "steps" / f"{sid}.md", "add"


def save(ctx, manifest, body, level, mode):
    if mode not in MODES:
        raise FactoryError("The mode must be `new`, `edit` or `copy-local`.")
    result = check(ctx, manifest, body)
    if result["errors"]:
        raise FactoryError("The step has errors:\n" + "\n".join(result["errors"]))
    manifest = step_format.clean(manifest)
    reg = Registry.load(ctx)
    level, path, action = target(ctx, reg, manifest["id"], level, mode)
    path.parent.mkdir(parents=True, exist_ok=True)
    fsio.atomic_write_text(path, step_format.dump(manifest, body))
    offer = None
    if level == "generic" and library.in_git(ctx.library()):
        offer = {"message": library.message(action, "step", manifest["id"]), "paths": [str(path)]}
    return {"path": str(path), "level": level, "warnings": result["warnings"], "library_commit": offer}
```

Check that `fsio.atomic_write_text(path, text)` has this argument order (`lib/factory/fsio.py:11`). If not, use `fsio.atomic_write_text` with the order it defines.

`api.py`:

```python
@route("GET", "/api/step-form")
def step_form(server, query, body):
    from . import step_store
    return step_store.form_data(server.ctx)


@route("POST", "/api/steps/check")
def step_check(server, query, body):
    from . import step_store
    return step_store.check(server.ctx, body["manifest"], body.get("body", ""))


@route("POST", "/api/steps/preview")
def step_preview(server, query, body):
    from . import step_store
    return step_store.preview(server.ctx, body["manifest"], body.get("body", ""))


@route("POST", "/api/steps/impact")
def step_impact(server, query, body):
    from . import step_store
    return step_store.impact(server.ctx, body["id"])


@route("POST", "/api/steps/save")
def step_save(server, query, body):
    from . import step_store
    return step_store.save(server.ctx, body["manifest"], body["body"], body.get("level", "local"), body["mode"])
```

`/api/steps/save` reads `body["body"]` with no default, so a missing body is a 400 "Missing field: body.".

- [ ] **Step 4: Run the tests**

Run: `uv run --with pytest --with pyyaml pytest -q tests/test_step_editor_api.py tests/test_editor_api.py tests/test_server.py`
Expected: all passed.

- [ ] **Step 5: Commit**

```bash
git add -A software-factory
git commit -m "step editor: step store and its API"
```

---

### Task 14: `factory step edit` and the menu action

**Files:**
- Modify: `software-factory/lib/factory/commands.py`, `software-factory/skills/software-factory/SKILL.md`
- Test: `software-factory/tests/test_step_editor_api.py` (append)

- [ ] **Step 1: Write the failing tests**

```python
def test_step_edit_cli(inited):
    try:
        out = inited.factory("step", "edit").stdout
        assert "Step editor: http://127.0.0.1:" in out and "new_step=1" in out
        out = inited.factory("step", "edit", "user-validation").stdout
        assert "step=user-validation" in out
        r = inited.factory("step", "edit", "nope", check=False)
        assert r.returncode == 1 and "does not exist" in r.stderr
    finally:
        inited.factory("server", "stop", check=False)


def test_skill_create_step_runs_step_edit():
    from conftest import SF
    skill = (SF / "skills" / "software-factory" / "SKILL.md").read_text()
    assert "**Create a new step** (`new-step`): run `factory step edit`" in skill
    assert "new-step-assistant" not in skill
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `uv run --with pytest --with pyyaml pytest -q tests/test_step_editor_api.py -k "step_edit or skill_create"`
Expected: FAIL.

- [ ] **Step 3: Implement**

`commands.py` `register`: after `sd`, add `se = sts.add_parser("edit", parents=[common]); se.add_argument("id", nargs="?")`. Add:

```python
@cli.command("step edit")
def step_edit_cmd(args):
    from . import server
    from .registry import Registry
    ctx = ctx_of(args)
    if args.id:
        Registry.load(ctx).step(args.id)
    info = server.ensure_server(ctx)
    url = server.page_url(info, "editor", **({"step": args.id} if args.id else {"new_step": "1"}))
    server.open_page(url)
    print(f"Step editor: {url}")
```

`SKILL.md`: replace the "Create a new step" bullet with:

```markdown
- **Create a new step** (`new-step`): run `factory step edit`. Tell the user the step form is open in the pipeline editor in the browser. To change an existing step, run `factory step edit <id>`.
```

- [ ] **Step 4: Run the tests**

Run: `uv run --with pytest --with pyyaml pytest -q tests/test_step_editor_api.py tests/test_docs.py tests/test_skill.py tests/test_step_delete.py`
Expected: all passed.

- [ ] **Step 5: Commit**

```bash
git add -A software-factory
git commit -m "step editor: factory step edit and the menu action"
```

---

### Task 15: Editor detail panel and keys panel

**Files:**
- Modify: `software-factory/lib/factory/web/editor.html`
- Test: `software-factory/tests/test_step_editor_api.py` (append a page content test)

- [ ] **Step 1: Write the failing test**

```python
def test_editor_page_has_step_form_controls(se):
    inited, i = se
    status, page = request(i, "GET", "/editor")
    for text in ("New step", "Copy to local", "Duplicate", "Keys available here", "/api/pipelines/keys",
                 "/api/steps/save", "/api/steps/preview", "/api/steps/impact", "$FACTORY_KEY_", "new_step"):
        assert text in page, text
```

- [ ] **Step 2: Run the test to see it fail**

Run: `uv run --with pytest --with pyyaml pytest -q tests/test_step_editor_api.py -k page_has`
Expected: FAIL.

- [ ] **Step 3: Change the detail panel**

In `editor.html`:

1. Above `<div id="filters" class="row"></div>`, add `<div class="row"><button type="button" id="newstep">New step</button></div>`.
2. In `pipelineRow`, change the id link to `onclick: () => showDetail(s.id, i + 1)`. Use `guard(...)` the same way the existing click handler does.
3. Replace `showDetail` with:

```js
function outputsText(outputs) {
  return Object.entries(outputs).map(([k, o]) => `${k} (${o.type}${o.optional ? ", optional" : ""})`).join(", ");
}
function keyRow(r, onPick) {
  const name = el("span", onPick ? { class: "link" } : {}, r.name);
  if (onPick) name.addEventListener("click", () => onPick(r));
  return el("div", {}, name, " ", el("span", { class: "muted" }, `${r.type}, ${r.source}, ${r.set} set`));
}
async function keysAt(position) {
  return api("/api/pipelines/keys", { data: dataOf(state.model), at: position });
}
async function keysBlock(position) {
  const rows = await keysAt(position);
  const box = el("div", {}, el("div", { class: "muted" }, "Keys available here"));
  for (const r of rows) box.append(keyRow(r, null));
  return box;
}
async function showDetail(id, position = null) {
  const d = await api("/api/steps/" + encodeURIComponent(id));
  const box = clear(byId("detail"));
  box.classList.remove("muted");
  box.append(el("h4", {}, d.id), el("div", {}, d.description));
  const list = el("dl");
  const rows = Object.entries(d.manifest).filter(([k]) => !["id", "description", "outputs", "steps"].includes(k));
  for (const [k, v] of rows) list.append(el("dt", {}, k), el("dd", {}, valueText(v)));
  list.append(el("dt", {}, "uses"), el("dd", {}, d.uses.join(", ") || "none"));
  list.append(el("dt", {}, "outputs"), el("dd", {}, outputsText(d.outputs) || "none"));
  list.append(el("dt", {}, "level"), el("dd", {}, d.level), el("dt", {}, "file"), el("dd", {}, d.path));
  box.append(list);
  if (d.children.length) {
    const kids = el("div", {}, el("div", { class: "muted" }, "Child steps"));
    for (const c of d.children) kids.append(el("div", {}, el("span", { class: "link", onclick: guard(() => showDetail(c)) }, c)));
    box.append(kids);
  }
  box.append(el("div", { class: "muted" }, "Body"), el("pre", {}, d.body));
  const actions = el("div", { class: "row" });
  if (d.level !== "builtin") actions.append(el("button", { type: "button", onclick: () => openStepForm({ mode: "edit", detail: d, position }) }, "Edit"));
  if (d.level !== "local") actions.append(el("button", { type: "button", onclick: () => openStepForm({ mode: "copy-local", detail: d, position }) }, "Copy to local"));
  actions.append(el("button", { type: "button", onclick: () => openStepForm({ mode: "new", detail: d, duplicate: true, position }) }, "Duplicate"));
  if (d.level !== "builtin") {
    actions.append(el("button", { type: "button", onclick: guard(async () => {
      const plan = await api("/api/steps/" + encodeURIComponent(d.id) + "/delete/dry-run", { level: d.level });
      box.append(deletePlanBlock(d, plan));
    }) }, "Delete"));
  }
  box.append(actions);
  if (position && state.model) box.append(await keysBlock(position));
}
```

4. Add a temporary stub `function openStepForm(opts) {}`. Task 16 replaces it.

- [ ] **Step 4: Commit after Task 16**

The page test passes only after Task 16. Go on to Task 16, then commit both.

---

### Task 16: Editor step form

**Files:**
- Modify: `software-factory/lib/factory/web/editor.html`

**Interfaces:**
- Consumes the routes of Task 13 and `POST /api/pipelines/keys`.

- [ ] **Step 1: Add the overlay markup and CSS**

After `</main>`, add `<div id="stepform" hidden></div>`. Add this CSS to `<style>`:

```css
#stepform { position: fixed; inset: 0; background: var(--bg); overflow: auto; padding: 16px; z-index: 10; }
.formgrid { display: grid; grid-template-columns: minmax(0, 1fr) 380px; gap: 16px; align-items: start; }
#stepform textarea { width: 100%; min-height: 280px; box-sizing: border-box; font-family: ui-monospace, monospace; }
.formside { position: sticky; top: 0; }
```

- [ ] **Step 2: Replace the `openStepForm` stub with the form code**

```js
const MODELS = ["", "opus", "sonnet", "haiku"];
const EFFORTS = ["", "low", "medium", "high", "max"];
const FORM_CHECK_DELAY_MS = 300;

function formModelOf(detail, duplicate) {
  const m = detail ? detail.manifest : {};
  return {
    id: duplicate ? "" : (m.id || ""), description: m.description || "", category: m.category || "", newCategory: "",
    type: m.type || "ai", run_in: m.run_in || "", model: m.model || "", effort: m.effort || "", column: m.column || "",
    required: !!m.required, wait_external: !!m.wait_external, done_when: m.done_when || "", done_check: m.done_check || "",
    requires: [...(m.requires || [])],
    config: Object.entries(m.config || {}).map(([key, v]) => ({ key, description: (v && v.description) || "",
      default: v && "default" in v ? String(v.default) : "", hasDefault: !!(v && "default" in v) })),
    outputs: Object.entries(m.outputs || {}).map(([key, v]) => ({ key, type: (v && v.type) || "text",
      description: (v && v.description) || "", optional: !!(v && v.optional) })),
    steps: [...(m.steps || [])], body: detail && m.type !== "group" ? detail.body : "",
  };
}
function manifestOf(f) {
  const m = { id: f.id, description: f.description, category: f.newCategory || f.category, type: f.type,
    done_when: f.done_when, done_check: f.done_check, required: f.required, wait_external: f.wait_external,
    column: f.column, requires: f.requires.filter(Boolean), config: {} };
  if (f.type === "ai") Object.assign(m, { run_in: f.run_in, model: f.model, effort: f.effort });
  if (f.type === "group") m.steps = f.steps;
  else {
    m.outputs = {};
    for (const o of f.outputs) if (o.key) m.outputs[o.key] = { type: o.type, description: o.description, ...(o.optional ? { optional: true } : {}) };
  }
  for (const c of f.config) if (c.key) m.config[c.key] = { description: c.description, ...(c.hasDefault || c.default !== "" ? { default: c.default } : {}) };
  return m;
}
function formBody() { const f = state.form.f; return f.type === "group" ? "" : f.body; }

function openStepForm(opts) {
  const mode = opts.mode;
  state.form = { mode, level: mode === "edit" ? opts.detail.level : "local", position: opts.position || null,
    f: formModelOf(opts.detail, !!opts.duplicate), keys: [], check: null, preview: null, impact: null,
    commit: null, saved: null, textarea: null, timer: null, ticket: 0 };
  byId("stepform").hidden = false;
  renderStepForm();
  guard(refreshFormKeys)();
  formChanged();
}
function closeStepForm() { byId("stepform").hidden = true; state.form = null; }
async function refreshFormKeys() {
  const s = state.form;
  s.keys = s.position && state.model ? await keysAt(s.position) : state.formData.factory_keys;
  renderFormSide();
}
function formChanged() {
  const s = state.form;
  s.preview = null; s.impact = null; s.saved = null; s.commit = null;
  clearTimeout(s.timer);
  s.timer = setTimeout(guard(runFormCheck), FORM_CHECK_DELAY_MS);
  renderFormSide();
}
async function runFormCheck() {
  const s = state.form;
  if (!s) return;
  const ticket = ++s.ticket;
  const result = await api("/api/steps/check", { manifest: manifestOf(s.f), body: formBody() });
  if (state.form !== s || ticket !== s.ticket) return;
  s.check = result;
  renderFormSide();
}

function checkbox(value, onChange) {
  const c = el("input", { type: "checkbox" });
  c.checked = value;
  c.addEventListener("change", () => onChange(c.checked));
  return c;
}
function rowsEditor(rows, makeRow, blank) {
  const box = el("div");
  const draw = () => {
    clear(box);
    rows.forEach((r, i) => box.append(el("div", { class: "row" }, ...makeRow(r, i),
      el("button", { type: "button", onclick: () => { rows.splice(i, 1); draw(); formChanged(); } }, "Remove"))));
    box.append(el("button", { type: "button", onclick: () => { rows.push(blank()); draw(); formChanged(); } }, "Add"));
  };
  draw();
  return box;
}
function requiresRows(list) {
  const rows = list.map((value) => ({ value }));
  const sync = () => { list.splice(0, list.length, ...rows.map((r) => r.value)); formChanged(); };
  return rowsEditor(rows, (r) => [textInput(r.value, (v) => { r.value = v; sync(); }, "skill or tool, for example gh")], () => ({ value: "" }));
}
function configRows(rows) {
  return rowsEditor(rows, (r) => [
    textInput(r.key, (v) => { r.key = v; formChanged(); }, "key"),
    textInput(r.description, (v) => { r.description = v; formChanged(); }, "description"),
    textInput(r.default, (v) => { r.default = v; formChanged(); }, "default")], () => ({ key: "", description: "", default: "", hasDefault: false }));
}
function outputRows(rows) {
  return rowsEditor(rows, (r) => [
    textInput(r.key, (v) => { r.key = v; formChanged(); }, "key"),
    selectInput(KEY_TYPES, r.type, (v) => { r.type = v; formChanged(); }),
    textInput(r.description, (v) => { r.description = v; formChanged(); }, "description"),
    el("label", {}, checkbox(r.optional, (v) => { r.optional = v; formChanged(); }), " optional")],
    () => ({ key: "", type: "text", description: "", optional: false }));
}
function childList(children) {
  const box = el("div");
  const draw = () => {
    clear(box);
    children.forEach((c, i) => {
      const card = el("div", { class: "card head", draggable: "true" }, el("span", { class: "grow" }, c),
        el("button", { type: "button", onclick: () => { children.splice(i, 1); draw(); formChanged(); } }, "Remove"));
      card.addEventListener("dragstart", (e) => { e.dataTransfer.setData("text/plain", "child:" + i); });
      card.addEventListener("dragover", (e) => e.preventDefault());
      card.addEventListener("drop", (e) => {
        e.preventDefault();
        const [kind, value] = e.dataTransfer.getData("text/plain").split(":");
        if (kind !== "child") return;
        const [item] = children.splice(Number(value), 1);
        children.splice(i, 0, item);
        draw(); formChanged();
      });
      box.append(card);
    });
    const pick = selectInput(["", ...state.steps.filter((s) => !s.hidden).map((s) => s.id)], "", () => {});
    box.append(el("div", { class: "row" }, pick, el("button", { type: "button", onclick: () => {
      if (pick.value) { children.push(pick.value); draw(); formChanged(); }
    } }, "Add child step")));
  };
  draw();
  return box;
}
function categoryInput(f) {
  const options = ["", ...state.formData.categories];
  if (f.category && !options.includes(f.category)) options.push(f.category);
  return el("div", { class: "row" }, selectInput(options, f.category, (v) => { f.category = v; formChanged(); }),
    textInput(f.newCategory, (v) => { f.newCategory = v.trim(); formChanged(); }, "new category"));
}
function levelInput() {
  const s = state.form;
  const box = el("div", { class: "row" });
  for (const value of ["local", "generic"]) {
    if (value === "generic" && !state.formData.library) continue;
    const r = el("input", { type: "radio", name: "steplevel", value });
    r.checked = s.level === value;
    r.addEventListener("change", () => { s.level = value; formChanged(); });
    box.append(el("label", {}, r, " " + value + " "));
  }
  return box;
}
function bodyArea(f) {
  const t = el("textarea");
  t.value = f.body;
  t.addEventListener("input", () => { f.body = t.value; formChanged(); });
  state.form.textarea = t;
  return t;
}
function insertAtCursor(text) {
  const t = state.form.textarea;
  if (!t) return;
  const start = t.selectionStart, end = t.selectionEnd;
  t.value = t.value.slice(0, start) + text + t.value.slice(end);
  t.selectionStart = t.selectionEnd = start + text.length;
  t.focus();
  state.form.f.body = t.value;
  formChanged();
}
function insertKey(name, isConfig) {
  const f = state.form.f;
  if (f.type === "ai") insertAtCursor(isConfig ? `{{config.${name}}}` : `{{${name}}}`);
  else if (f.type === "command") insertAtCursor(isConfig ? `$FACTORY_CONFIG_${name.toUpperCase()}` : `$FACTORY_KEY_${name.toUpperCase()}`);
}

function renderStepForm() {
  const s = state.form, f = s.f, box = clear(byId("stepform"));
  const titles = { new: "New step", edit: "Edit step " + f.id, "copy-local": "Copy " + f.id + " to local" };
  const idInput = textInput(f.id, (v) => { f.id = v; formChanged(); }, "step id");
  if (s.mode !== "new") idInput.disabled = true;
  const left = el("div");
  left.append(el("div", { class: "head" }, el("h3", { class: "grow" }, titles[s.mode]),
      el("button", { type: "button", onclick: closeStepForm }, "Close")),
    field("id", idInput),
    field("description", textInput(f.description, (v) => { f.description = v; formChanged(); })),
    field("category", categoryInput(f)),
    field("type", selectInput(["ai", "command", "group"], f.type, (v) => { f.type = v; renderStepForm(); formChanged(); })));
  if (s.mode === "new") left.append(field("level", levelInput()));
  if (f.type === "ai") {
    left.append(field("run_in", selectInput(["", "session", "subagent"], f.run_in, (v) => { f.run_in = v; formChanged(); })),
      field("model", selectInput(MODELS, f.model, (v) => { f.model = v; formChanged(); })),
      field("effort", selectInput(EFFORTS, f.effort, (v) => { f.effort = v; formChanged(); })));
  }
  left.append(field("column", selectInput(["", ...state.columns], f.column, (v) => { f.column = v; formChanged(); })),
    field("required", checkbox(f.required, (v) => { f.required = v; formChanged(); })),
    field("wait_external", checkbox(f.wait_external, (v) => { f.wait_external = v; formChanged(); })),
    field("done_when", textInput(f.done_when, (v) => { f.done_when = v; formChanged(); })),
    field("done_check", textInput(f.done_check, (v) => { f.done_check = v; formChanged(); }, "optional shell command")),
    field("requires", requiresRows(f.requires)),
    field("config", configRows(f.config)));
  if (f.type !== "group") left.append(field("outputs", outputRows(f.outputs)));
  state.form.textarea = null;
  left.append(f.type === "group" ? field("child steps", childList(f.steps)) : field(f.type === "ai" ? "prompt" : "command", bodyArea(f)));
  box.append(el("div", { class: "formgrid" }, left, el("div", { id: "formside", class: "formside" })));
  renderFormSide();
}

function renderFormSide() {
  const s = state.form, side = byId("formside");
  if (!s || !side) return;
  clear(side);
  const f = s.f;
  if (f.type !== "group") {
    const keyBox = el("div", {}, el("div", { class: "muted" }, s.position && state.model ? "Keys available at this position" : "Factory keys"));
    for (const r of s.keys) keyBox.append(keyRow(r, (k) => insertKey(k.name, false)));
    for (const c of f.config) if (c.key) keyBox.append(keyRow({ name: "config." + c.key, type: "config", source: "this step", set: "always" }, () => insertKey(c.key, true)));
    side.append(keyBox);
  }
  const check = s.check;
  if (check) {
    for (const e of check.errors) side.append(el("div", { class: "problem error" }, "Error: " + e));
    for (const w of check.warnings) side.append(el("div", { class: "problem warning" }, "Warning: " + w));
    if (!check.errors.length) side.append(el("div", { class: "muted" }, "Uses: " + (check.uses.join(", ") || "none") + ". Outputs: " + (outputsText(check.outputs) || "none") + "."));
  }
  if (f.type === "ai") {
    side.append(el("button", { type: "button", onclick: guard(async () => {
      s.preview = (await api("/api/steps/preview", { manifest: manifestOf(f), body: formBody() })).text;
      renderFormSide();
    }) }, "Preview"));
    if (s.preview !== null) side.append(el("pre", {}, s.preview));
  }
  const save = el("button", { type: "button", class: "primary", onclick: guard(startSave) }, "Save");
  save.disabled = !check || check.errors.length > 0;
  side.append(el("div", { class: "row" }, save));
  if (s.impact) side.append(impactBlock(s.impact));
  if (s.saved) side.append(el("div", { class: "muted" }, "Saved to " + s.saved.path));
  if (s.saved) for (const w of s.saved.warnings) side.append(el("div", { class: "problem warning" }, "Warning: " + w));
  if (s.commit) side.append(commitBox(s.commit, () => { s.commit = null; side.append(el("div", { class: "muted" }, "Committed to the library.")); }));
}
function impactBlock(imp) {
  const b = el("div", { class: "card" }, el("div", {}, "This change applies to:"));
  for (const p of imp.pipelines) b.append(el("div", {}, `pipeline ${p.id} (${p.level})`));
  for (const g of imp.groups) b.append(el("div", {}, `group step ${g.id} (${g.level})`));
  for (const t of imp.tasks) b.append(el("div", {}, `task ${t.id}: the change applies from its next step`));
  if (!imp.pipelines.length && !imp.groups.length && !imp.tasks.length) b.append(el("div", { class: "muted" }, "No pipeline or task uses this step."));
  for (const w of imp.warnings) b.append(el("div", { class: "problem warning" }, w));
  b.append(el("div", { class: "row" },
    el("button", { type: "button", class: "primary", onclick: guard(doSave) }, "Confirm save"),
    el("button", { type: "button", onclick: () => { state.form.impact = null; renderFormSide(); } }, "Cancel")));
  return b;
}
async function startSave() {
  const s = state.form;
  if (s.mode === "edit") {
    s.impact = await api("/api/steps/impact", { id: s.f.id });
    renderFormSide();
    return;
  }
  await doSave();
}
async function doSave() {
  const s = state.form;
  let result;
  try {
    result = await api("/api/steps/save", { manifest: manifestOf(s.f), body: formBody(), level: s.level, mode: s.mode });
  } catch (e) {
    if (e.conflict) showError(e.message);
    return;
  }
  s.impact = null;
  s.saved = result;
  s.commit = result.library_commit;
  s.mode = "edit";
  s.level = result.level;
  await loadSteps();
  if (state.model) await runCheck();
  renderStepForm();
}
```

`doSave` keeps `s.saved` and `s.commit`, because `renderStepForm` does not call `formChanged`.

- [ ] **Step 3: Wire the page start**

In `init()`, after `await loadSteps();`:

```js
  state.formData = await api("/api/step-form");
  byId("newstep").addEventListener("click", () => openStepForm({ mode: "new" }));
  const stepParam = params.get("step");
  if (params.get("new_step")) openStepForm({ mode: "new" });
  else if (stepParam) {
    try {
      const d = await api("/api/steps/" + encodeURIComponent(stepParam));
      openStepForm({ mode: d.level === "builtin" ? "copy-local" : "edit", detail: d });
    } catch (e) {}
  }
```

- [ ] **Step 4: Run the tests**

Run: `uv run --with pytest --with pyyaml pytest -q tests/test_step_editor_api.py tests/test_editor_api.py tests/test_step_hide.py`
Expected: all passed.

- [ ] **Step 5: Check the page in a browser**

Build a throwaway test repository under `verification/software-factory/work/editor-smoke/`:

- a bare `origin.git`
- a clone `repo` with one commit pushed to `main`
- a library folder `libroot/factory-library` inside its own `git init` folder

In `repo`, run `factory init --library <libroot>/factory-library --create-library`, then `FACTORY_NO_OPEN=1 factory step edit`. Open the printed URL with the Chrome tools, if the user allows browser use. Then:

- Create an `ai` step.
- Click a key and see `{{key}}` inserted.
- Click "Preview".
- Save it local.
- Check the browser console for errors.

Delete the temporary folder afterwards. If browser tools are not available, record this in the report and leave it to the manual check list.

- [ ] **Step 6: Commit**

```bash
git add -A software-factory
git commit -m "step editor: step form in the pipeline editor"
```

---

### Task 17: README

**Files:**
- Modify: `software-factory/README.md`
- Test: `software-factory/tests/test_docs.py` (append)

- [ ] **Step 1: Write the failing test**

```python
def test_readme_describes_step_editor():
    text = (SF / "README.md").read_text()
    for needle in ("`text`", "`long-text`", "`file`", "`task_id`", "`summary`", "`ai`", "`command`", "`group`",
                   "{{<key>}}", "{{config.<key>}}", "(not set)", "`outputs`", "FACTORY_KEY_", "FACTORY_STEP_DIR",
                   "factory pipeline keys", "factory step edit", "factory run-command", "step form"):
        assert needle in text, needle
    assert "run-script" not in text and "new-step-assistant" not in text and "Answer the questions of the assistant" not in text
```

- [ ] **Step 2: Run the test to see it fail**

Run: `uv run --with pytest --with pyyaml pytest -q tests/test_docs.py`
Expected: FAIL.

- [ ] **Step 3: Edit the README**

Replace the `- **Step types**: ...` line in Concepts with:

```markdown
- **Task keys**: values a task holds. A step uses them and sets them. A key name uses lowercase letters, digits and `_`, and starts with a letter.
- **Key types**: `text` (one line), `long-text` (several lines), `file` (an absolute path). A missing type means `text`.
- **Key sources**: a pipeline input, an output of an earlier step, or the factory. The factory keys are `task_id`, `description` and `summary`. `summary` is set only when the task starts from a backlog entry.
- **Step types**: `ai` (a prompt sent to the agent), `command` (a shell command), `group` (a list of other steps).
- **Placeholders**: in an `ai` prompt, `{{<key>}}` is replaced with a task key and `{{config.<key>}}` with a config value. A key that is not set becomes `(not set)`.
- **Outputs**: the keys a step sets, each with a type and a description. `optional: true` means the step may leave it unset.
- **Command variables**: a `command` step gets each key as `FACTORY_KEY_<KEY>`, each config value as `FACTORY_CONFIG_<KEY>`, and the folder of the step file as `FACTORY_STEP_DIR`.
```

Replace tutorial step 4 with:

```markdown
4. **Create a step.**
   - Choose "Create a new step". The pipeline editor opens on the step form.
   - Write the id, the description and the prompt. Click a key on the right to insert it.
   - Click "Preview". Choose local or generic. Click "Save".
   - Expected: the new step file is in `.factory/steps/` or in `<library>/steps/`.
```

In the Menu actions list: `- **Create a new step**: open the step form in the pipeline editor.`

In Commands:

- Step execution: replace the `factory run-script` line with ``- `factory run-command`: run the command of the current `command` step. It prints the output and the exit code.``
- Pipelines, steps and the library:
  - add ``- `factory pipeline keys <id> [--at <position>]`: list the task keys available before the step at this position, with their type, their source and "always set" or "maybe set".``
  - add ``- `factory step edit [<id>]`: open the step form in the pipeline editor.``
- Remove ``[--worktree]`` from the `factory terminal start-session` line.

In "Pipeline editor", add:

```markdown
- Keys: click a step in the pipeline to see the keys available at its position.
- Step form: "New step" above the available steps opens it. In the step detail, "Edit" changes a local or generic step, "Copy to local" copies a generic or built-in step to a local step with the same id, and "Duplicate" copies any step under a new id.
  - The form shows the fields of the manifest, a table for config keys, a table for outputs, and the prompt or the command. A `group` step shows a list of child steps. Drag them to change the order.
  - Next to the body, click a key to insert `{{<key>}}` in a prompt or `$FACTORY_KEY_<KEY>` in a command.
  - "Preview" shows the text `factory next` prints, with each placeholder shown as `<key>`.
  - Saving a step that exists first shows the pipelines and the unfinished tasks that use it. A task uses the change from its next step.
  - Errors block the save. Warnings do not. For a generic step, the editor offers the library commit.
  - Built-in steps cannot be edited. Copy them to local instead.
  - The form never writes a script file. Put a script next to the step by hand.
```

Replace "Step manifest fields" with:

```markdown
`id`, `description`, `category`, `type` (`ai`, `command` or `group`), `outputs`, `done_when`, `done_check`, `config`, `required`, `run_in`, `model`, `effort` (only for `ai`), `requires`, `column`, `wait_external`, `steps` (only for `group`).

`factory done` checks, in this order: every output that is not optional is set, every `file` output points to a path that exists, a `command` step's last `factory run-command` exited with 0, then the `done_check`.
```

Pipeline fields: change `inputs` to ``- `inputs`: values asked at launch, each with a `type` and a `description`. A relative `file` path is resolved from the main repository.``

In "Troubleshooting" "Data version mismatch", add: "The migration to version 2 stops if a key name breaks the rule or a task uses `new-step-assistant`. It lists what to fix."

- [ ] **Step 4: Run the tests**

Run: `uv run --with pytest --with pyyaml pytest -q tests/test_docs.py tests/test_step_hide.py`
Expected: all passed.

- [ ] **Step 5: Commit**

```bash
git add software-factory/README.md software-factory/tests/test_docs.py
git commit -m "step editor: README"
```

---

### Task 18: Verification report and milestone 3 close

**Files:**
- Create: `software-factory/tests/report_step_editor.py`
- Create: `verification/software-factory/step-editor-manual-check.md`
- Create: `verification/software-factory/step-editor-report.md` (generated)

- [ ] **Step 1: Write the report script**

```python
import sys
from datetime import datetime

from report import VERIF, cases, table

MILESTONES = {
    "1. Step format and runtime": ["test_keys", "test_step_format", "test_builtin", "test_catalog", "test_registry",
                                   "test_runtime_v2", "test_engine", "test_step_assistant", "test_migrate_v2", "test_migrate"],
    "2. Available keys": ["test_pipeline_keys", "test_pipeline_check", "test_typed_inputs"],
    "3. Step editor": ["test_step_editor_api", "test_docs"],
}
JUNIT = VERIF / "step-editor-junit.xml"
REPORT = VERIF / "step-editor-report.md"
UPDATED = VERIF / "step-editor-updated-tests.md"


def main():
    rows = cases(JUNIT)
    lines = ["# Step editor verification report", "", f"Date: {datetime.now():%Y-%m-%d %H:%M}", ""]
    for title, modules in MILESTONES.items():
        mine = [r for r in rows if r["module"] in modules]
        passed = sum(r["status"] == "PASS" for r in mine)
        lines += [f"## Milestone {title}", "", f"{passed} of {len(mine)} tests pass.", ""] + table(mine) + [""]
    passed = sum(r["status"] == "PASS" for r in rows)
    failed = [r for r in rows if r["status"] != "PASS"]
    lines += ["## Full test suite", "", f"{passed} of {len(rows)} tests pass.", ""]
    if failed:
        lines += table(failed) + [""]
    lines += ["## Updated tests", ""]
    lines += UPDATED.read_text().splitlines() if UPDATED.exists() else ["None."]
    REPORT.write_text("\n".join(lines) + "\n")
    return 0 if rows and passed == len(rows) else 1


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Write the manual check list**

`verification/software-factory/step-editor-manual-check.md`:

```markdown
# Step editor manual check list

Run these in a test repository, or on copies made by you. Never on a real `.factory/` or a real library you do not want to change.

1. Create a new `ai` step from the form.
   - Run `factory step edit`. Fill the id, the description and the prompt.
   - Click two keys on the right. Expected: `{{key}}` is inserted at the cursor.
   - Click "Preview". Expected: the prompt with `<key>`, then the footer with the outputs.
   - Save local. Expected: the file is in `.factory/steps/`. The step is in the list.
   - Add it to a pipeline and save the pipeline.
2. Edit a generic step.
   - Click the step, then "Edit". Change the description. Click "Save".
   - Expected: the pipelines and unfinished tasks that use it, and "Other repositories that use this library are not checked."
   - Click "Confirm save", then "Commit to library". Expected: `git log -1` in the library shows `Factory library: update step <id>`.
3. Copy a built-in step to local, and duplicate a step.
   - Click `user-validation`, then "Copy to local", then "Save". Expected: `.factory/steps/user-validation.md` exists. The list shows it as local.
   - Click any step, then "Duplicate". Give a new id and save. Expected: a new step with the same fields.
4. Create a `group` step.
   - Set the type to `group`. Add three child steps. Drag the last one to the top. Save.
   - Expected: the file lists the child steps in the new order. The detail shows them.
5. Select a step in a pipeline.
   - Open a pipeline with inputs. Click its third step. Expected: "Keys available here" lists the inputs, the outputs of the first two steps and the factory keys, with "always set" or "maybe set".
6. Launch from the dashboard.
   - Pick a pipeline with a `long-text` input. Expected: a text area.
   - Pick a pipeline with a `file` input. Type a path that does not exist and click "Check". Expected: a red error with the absolute path.
7. Orchestrator.
   - Choose "Create a new step". Expected: the step form opens in the browser.
8. Migration.
   - Make a copy of a real version 1 `.factory/` folder and of its library, in a test repository.
   - Start the orchestrator there. Expected: the migration dry run, then the summary with the backup path. The library commit `Factory library: migrate to version 2` is offered.
   - Launch a migrated pipeline and run it to the end.
```

- [ ] **Step 3: Run the full suite with JUnit output and build the report**

```bash
cd software-factory
uv run --with pytest --with pyyaml pytest -q tests --junitxml=../verification/software-factory/step-editor-junit.xml
uv run --with pyyaml python tests/report_step_editor.py
```

Expected: the report says all tests pass in every section. If a test fails, fix the cause, rerun, and rebuild the report.

- [ ] **Step 4: Check the Definition Of Done**

Read every bullet of `prompts/factory_step_editor.md` "Definition Of Done". For each one, point to the test or the file that covers it. Add a section "Definition Of Done" to `step-editor-report.md` with one line per bullet: covered by `<test or file>`, or the reason it is a manual check. Fix any gap and rerun.

- [ ] **Step 5: Commit**

```bash
git add -A software-factory verification/software-factory/step-editor-*.md verification/software-factory/step-editor-junit.xml
git commit -m "step editor: milestone 3, step editor and verification report"
```
