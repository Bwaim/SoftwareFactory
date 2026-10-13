# Authoring Skill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the `factory-authoring` skill to the factory plugin. With it, an agent writes valid step and pipeline files and checks them with `factory pipeline check`.

**Architecture:** One new skill file, `skills/factory-authoring/SKILL.md`. It holds the workflow, the rules, the format reference and examples. A new test file checks the skill against the factory code. The README gets one section. No code under `lib/` changes.

**Tech Stack:** Markdown, Python 3.12, pytest, pyyaml, uv.

**Spec:** `specs/2026-10-13-authoring-skill-design.md`

## Global Constraints

- All work is under `software-factory/`. Verification files are under `verification/software-factory/`.
- Work on the branch `authoring-skill`, created from `master`. `master` stays unchanged.
- No change to files under `software-factory/lib/`, to `skills/software-factory/SKILL.md`, or to `.claude-plugin/plugin.json`.
- No new CLI command. No change to the step or pipeline format.
- Tests use the fixtures of `tests/conftest.py`: a test repository and a test library. Never a real library or a real `.factory/`.
- No code comments.
- Commit messages have no co-author line.
- Simple English and short sentences in the skill and in the README.
- Run tests from `software-factory/`: `uv run --with pytest --with pyyaml pytest -q tests/<file>`.

## Review Focus

1. The example script fails at run time, so `factory pipeline check` passes but the pipeline breaks. Expected: the command step of the example runs and sets its output. Test: `test_example_command_step_runs` in Task 1.
2. The frontmatter is invalid YAML, so Claude never loads the skill. Expected: the frontmatter parses, with `name` and `description`. Test: `test_skill_file_and_frontmatter` in Task 1.
3. `factory` is not on PATH, and the fallback path in the skill is wrong. Expected: `<skill base>/../../bin/factory` exists. Test: `test_fallback_factory_path_exists` in Task 1.
4. The pipeline fields of the code change, and the skill does not follow. Expected: the field test reads the field names from the code. Test: `test_every_field_is_described` in Task 1.
5. The skill names a built-in step that does not exist. Expected: each named built-in step has a file. Test: `test_named_builtin_steps_exist` in Task 1.

---

## Milestone 1: Authoring skill

### Task 0: Branch (controller)

- [ ] **Step 1: Create the branch and commit the spec and the plan**

```bash
cd /Users/fabienboismoreau/Documents/Projects/SoftwareFactory/SoftwareFactory
git switch -c authoring-skill master
git add specs/2026-10-13-authoring-skill-design.md plans/2026-10-13-authoring-skill.md
git commit -m "authoring skill: spec and plan"
```

### Task 1: The skill file and its tests

**Files:**
- Create: `software-factory/skills/factory-authoring/SKILL.md`
- Create: `software-factory/tests/test_authoring_skill.py`

**Interfaces:**
- Consumes: `tests/test_docs.py` functions `check(text, names)` and `command_names()`. `factory.step_format.FIELD_ORDER`. `factory.registry` source. Fixture `inited` of `tests/conftest.py`: `inited.repo`, `inited.factory(*args, check=True)`, `inited.factory.json(*args)`.
- Produces: `tests/test_authoring_skill.py` with `SKILL`, `skill_text()`, `examples(text)`. Task 2 adds one test to this file.

- [ ] **Step 1: Write the failing tests**

Create `software-factory/tests/test_authoring_skill.py`:

```python
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
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `cd software-factory && uv run --with pytest --with pyyaml pytest -q tests/test_authoring_skill.py`
Expected: 7 failed, each with `FileNotFoundError` on `SKILL.md`. `test_fallback_factory_path_exists` fails the same way.

- [ ] **Step 3: Write the skill file**

Create `software-factory/skills/factory-authoring/SKILL.md` with exactly this content:

````markdown
---
name: factory-authoring
description: Create or change Software Factory pipelines and steps by writing their files directly (.factory/steps, .factory/pipelines, library steps and pipelines), then check them with `factory pipeline check`. Use when the user asks to create, change or fix a factory pipeline or step, or gives a file that describes one, for example "Implement prompts/crash-pipeline.md". Works without the factory orchestrator, the local server or the browser.
argument-hint: <prompt file or request>
---

# Factory authoring

You write Software Factory step files and pipeline files, then you check them with the factory, the same way code is checked with tests.

Request: $ARGUMENTS

`factory` below is the factory CLI. Run `command -v factory`. If it prints nothing, use `<this skill's base directory>/../../bin/factory` everywhere this skill says `factory`. Never create a link for it.

## Workflow

1. **Find the repository.**
   - The main repository is the parent folder of `git rev-parse --path-format=absolute --git-common-dir`. This also works inside a worktree.
   - If `<main repo>/.factory/factory.yaml` does not exist, stop. Tell the user to add the factory to the repository first: run `/software-factory:software-factory` and choose "Init the factory".
   - Run `factory version check --json`. If `state` is `older`, stop and tell the user to start the orchestrator, which runs the migration. If `state` is `newer`, stop and tell the user to update the factory plugin.
2. **Read the request.**
   - Read the request or the prompt file.
   - Ask the user only what the file or the request does not say.
   - When the level is not given, use local.
   - For a generic file, read the `library` key of `.factory/factory.yaml`. If it is missing, stop and tell the user that no library is set.
3. **List what exists.**
   - Run `factory step list --all --json` and `factory pipeline list --json`.
   - Reuse an existing step when it does the job.
   - Never create a step with the id of an existing step at the same level. The list shows only the step that wins, so also check that the target file does not exist before you write it.
   - A local step with the id of a generic or built-in step overrides it. Do this only when the user asks for it, and say so.
4. **Plan the key flow.**
   - For each step, list the keys it uses.
   - Each key must come from a pipeline input, an output of an earlier step, or a factory key.
   - `summary` is maybe set. A step that uses it must still work when it is `(not set)`.
5. **Write the files.** Write the step files first, then the pipeline files. Follow the format reference below.
6. **Check.**
   - Run `factory pipeline check <id>` for each new or changed pipeline.
   - After a step change, run it for every pipeline listed by `factory pipeline list --json`. No command lists the pipelines that use a step, and checking all of them also covers group steps.
   - An error stops the check. A step file that does not load gives `<path>: <problem>`. Fix the file and run the check again, until there is no error.
   - Read each warning. Fix it, or tell the user why it stays.
   - Run `factory pipeline keys <id> --at <position>` for the position of each step. Check that each key the step uses is in the list.
   - The check sees the keys of a command line, not the keys used inside a script file. Check the keys of a script by hand.
7. **Generic changes.** Tell the user that other repositories that use the library are not checked.
8. **Library commit.** For new or changed generic files:
   - Show the files and the message `Factory library: <action> <kind> <id>`. The action is `add`, `update` or `delete`. The kind is `step` or `pipeline`. Examples: `Factory library: add step fix-crash`, `Factory library: update pipeline crash-fix`.
   - Run `factory library commit "<message>" <paths...>` only after the user approves.
   - If the library is not in a git repository, skip the commit and say so.
   - Never push.
   - Local files are never committed. `.factory/` is excluded from git.
9. **Report.** List the files you created or changed, their level, and the check results. Tell the user they can review a pipeline with `factory pipeline edit <id>`.

## Rules

- Never edit a built-in step or pipeline. Built-in files are in the `builtin/` folder of the plugin. To change a built-in step, write a local step with the same id.
- Never edit files under `.factory/tasks/`.
- Never change a step that an unfinished task uses without telling the user first.
  - `factory tasks --json` lists the tasks. A task is unfinished when its `status` is not `finished`.
  - For each unfinished task, read `.factory/tasks/<id>/task.json`. Only read it. Its `steps` list holds the saved step entries.
  - The task uses a step when the step id is in the `path` of any entry, not only in its `id`. A group id is in the `path` of each of its child steps.
  - The task uses the changed step from its next step on.
- A generic pipeline uses only generic or built-in steps. So each new step of a generic pipeline is generic too. If not, `factory pipeline check` warns "This generic pipeline uses the local step".
- A step that calls a skill is an `ai` step. Its prompt calls the skill, and `requires` lists it. Example: `requires: [/superpowers:writing-plans]`.
- The file name is the id: `<id>.md` for a step, `<id>.yaml` for a pipeline.

## Format reference

### Where files go

- Local: `<main repo>/.factory/steps/<id>.md` and `<main repo>/.factory/pipelines/<id>.yaml`.
- Generic: `<library>/steps/<id>.md` and `<library>/pipelines/<id>.yaml`. `<library>` is the `library` key of `.factory/factory.yaml`.
- Built-in steps ship with the plugin. Never change them.
- Local wins over generic. Generic wins over built-in.
- A script of a `command` step goes next to the step file, in the same `steps/` folder.

### Ids and key names

- A step id or a pipeline id uses lowercase letters, digits, `-` and `_`. It starts with a letter. It has at most 64 characters.
  - Good: `fix-crash`, `run_tests2`. Bad: `Fix-Crash`, `2fix`, `fix crash`.
- A key name (input, output or config key) uses lowercase letters, digits and `_`. It starts with a letter. No `-`.
  - Good: `crash_log`, `plan2`. Bad: `crash-log`, `CrashLog`.

### Key types

- `text`: one line.
- `long-text`: several lines.
- `file`: an absolute path.
- A missing type means `text`.
- Factory keys:
  - `task_id`: always set.
  - `description`: always set. The task description.
  - `summary`: maybe set. It is set only when the task starts from a backlog entry.

### Step file

A step file is YAML frontmatter between two `---` lines, then the body.

| Field | Values | Applies to |
| --- | --- | --- |
| `id` | the step id | all |
| `description` | one line. Empty gives a warning. | all |
| `category` | free text, for example `build` | all |
| `type` | `ai`, `command` or `group` | all |
| `outputs` | map of key name to `type`, `description` and `optional` | `ai`, `command` |
| `done_when` | text shown to the agent | `ai`, `command` |
| `done_check` | shell command. Exit code 0 means done. Use `"$FACTORY_KEY_<KEY>"`, never `{{...}}`. | `ai`, `command` |
| `config` | map of key name to `description` and an optional `default` | `ai`, `command` |
| `required` | `true` or `false`. With `true`, `factory skip` is refused. | `ai`, `command` |
| `run_in` | `session` (the default) or `subagent` | `ai` |
| `model` | a model name, for example `opus` | `ai` with `run_in: subagent` |
| `effort` | for example `low` or `high` | `ai` with `run_in: subagent` |
| `requires` | list of skills (`/plugin:skill`) or programs on PATH | `ai`, `command` |
| `column` | a board column from `columns` in `.factory/factory.yaml` | `ai`, `command` |
| `wait_external` | `true`: the step ends with `factory wait` | `ai`, `command` |
| `steps` | list of child step ids | `group` |

- Leave out empty fields.
- A `group` step uses only `id`, `description`, `category`, `type` and `steps`. The factory reads the other fields from its child steps.
- `model` or `effort` on a step that runs in the session gives a warning.

### `ai` step

- The body is the exact prompt.
- `{{<key>}}` becomes the value of the task key. `{{config.<key>}}` becomes the config value.
- A key that is not set becomes `(not set)`.
- `{{config.<key>}}` needs the key in `config`. If not, the step does not load.
- Single braces, like `{name}`, stay text.
- Do not list the outputs or write "run factory done" in the prompt. The factory adds a footer with each output, the `factory state set` command for it, the `done_when` text and the end line.

### `command` step

- The body is a shell command. `factory run-command` runs it with `bash` in the task worktree.
- The command gets:
  - each task key as `"$FACTORY_KEY_<KEY>"`,
  - each config value as `"$FACTORY_CONFIG_<KEY>"`,
  - the folder of the step file as `"$FACTORY_STEP_DIR"`.
- `<KEY>` is the key name in upper case. Always put these variables in double quotes.
- No `{{...}}` in a command. The step does not load.
- Put a long command in a script next to the step, and run it with `bash "$FACTORY_STEP_DIR/<id>.sh"`.
- The command sets its own outputs with `factory state set <key> <value>`. For a `file` output, get a path with `factory artifact path <name>`. The session never sets them.
- Exit code 0 means success.

### `group` step

- `steps` lists the child step ids, in order. A child can be a group.
- No body.
- No `outputs`. They come from the child steps.
- No loop: a group cannot contain itself at any depth.

### Outputs and `factory done`

- Each output has a `type`, a `description`, and `optional: true` when the step may leave it unset.
- `factory done` checks, in this order:
  1. Every output that is not optional is set.
  2. Every `file` output points to a path that exists.
  3. For a `command` step, the last `factory run-command` exited with 0.
  4. The `done_check`, when there is one.

### Config and `with`

- `config` declares the values a step needs. Each one has a `description` and an optional `default`.
- A value comes from, in this order:
  1. `with` in the pipeline entry,
  2. the value saved in `.factory/config.yaml`,
  3. the `default`.
- When no value exists:
  - The launch dry run asks only for the config of `create-worktree`.
  - For any other step, `factory next` asks the user for the value when the step starts.
- `with` on a group entry applies to each child step that declares that config key.

### Pipeline file

- `id`: the pipeline id. It is also the file name.
- `description`: one line.
- `inputs`: map of key name to `type` and `description`. The launch asks for each one. A relative `file` path is resolved from the main repository.
- `steps`: the list of entries. An entry is a step id, or a map with:
  - `id`: the step id,
  - `with`: config values for this entry,
  - `model` and `effort`: for a step that runs in a subagent,
  - `column`: the board column when this entry starts.
- `claude`: `model` and `effort` of the task session.
- `start_column`: the board column of a new task.
- `create-worktree`: the factory adds the built-in step `create-worktree` as the first step. List it only to set its `with` values, and then only as the first step.

## Examples

One flow: collect a crash report with a command, fix the crash with the agent, then ask the user to validate with the built-in step `user-validation`.

#### .factory/steps/collect-crash.md

```markdown
---
id: collect-crash
description: Copy the end of the crash log into a crash report artifact
category: build
type: command
outputs:
  crash_report:
    type: file
    description: The last lines of the crash log
done_when: The crash report is written.
config:
  lines:
    description: How many lines of the log to keep
    default: 200
---

bash "$FACTORY_STEP_DIR/collect-crash.sh"
```

#### .factory/steps/collect-crash.sh

```bash
#!/usr/bin/env bash
set -euo pipefail
report="$(factory artifact path crash-report.md)"
tail -n "$FACTORY_CONFIG_LINES" "$FACTORY_KEY_CRASH_LOG" > "$report"
factory state set crash_report "$report"
```

#### .factory/steps/fix-crash.md

```markdown
---
id: fix-crash
description: Find the cause of a crash and fix it
category: build
type: ai
outputs:
  fix_summary:
    type: long-text
    description: What caused the crash and what changed
done_when: The cause is fixed and the tests pass.
config:
  test_hint:
    description: How to run the tests of this repository
    default: the test command of the README
---

Fix this crash: {{description}}.

1. Read the crash report at {{crash_report}}.
2. Find the cause in the code and fix it.
3. Run the tests. Use {{config.test_hint}}.
```

#### .factory/steps/crash-triage.md

```markdown
---
id: crash-triage
description: Collect the crash report, then fix the crash
category: build
type: group
steps:
  - collect-crash
  - fix-crash
---
```

#### .factory/pipelines/crash-fix.yaml

```yaml
id: crash-fix
description: Fix a crash from its log, then ask the user to validate
inputs:
  crash_log:
    type: file
    description: The crash log file
steps:
  - id: crash-triage
    with:
      lines: 100
  - user-validation
```

What the example shows:
- The input `crash_log` is used by the script as `"$FACTORY_KEY_CRASH_LOG"`.
- The output `crash_report` of `collect-crash` is used by `fix-crash` as `{{crash_report}}`.
- The config value `lines` is set with `with` on the group entry. `test_hint` uses its default.
````

- [ ] **Step 4: Run the tests to see them pass**

Run: `cd software-factory && uv run --with pytest --with pyyaml pytest -q tests/test_authoring_skill.py tests/test_docs.py tests/test_skill.py`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
cd /Users/fabienboismoreau/Documents/Projects/SoftwareFactory/SoftwareFactory
git add software-factory/skills/factory-authoring/SKILL.md software-factory/tests/test_authoring_skill.py
git commit -m "authoring skill: the factory-authoring skill and its tests"
```

### Task 2: README

**Files:**
- Modify: `software-factory/README.md`. Add one line in "Install and prerequisites", after the "Start the orchestrator" list and before "The first run creates the link". Add a section `### Authoring skill` in Reference, after `### Pipeline editor` and before `### Dashboard`.
- Modify: `software-factory/tests/test_authoring_skill.py`. Add one test.

**Interfaces:**
- Consumes: `SF` from `conftest`.
- Produces: the README section `### Authoring skill`.

- [ ] **Step 1: Write the failing test**

Append to `software-factory/tests/test_authoring_skill.py`:

```python
def test_readme_describes_authoring_skill():
    text = (SF / "README.md").read_text()
    section = text.split("### Authoring skill\n", 1)[1].split("\n### ", 1)[0]
    for needle in ("/factory-authoring <file or request>", "/software-factory:factory-authoring",
                   "prompts/crash-pipeline.md", "Implement `prompts/crash-pipeline.md`", "factory pipeline check",
                   "library commit", ".factory/factory.yaml"):
        assert needle in section, needle
    install = text.split("## Install and prerequisites", 1)[1].split("## Tutorial", 1)[0]
    assert "`/factory-authoring`" in install
    tutorial = text.split("## Tutorial", 1)[1].split("## Reference", 1)[0]
    assert "factory-authoring" not in tutorial
```

- [ ] **Step 2: Run it to see it fail**

Run: `cd software-factory && uv run --with pytest --with pyyaml pytest -q tests/test_authoring_skill.py -k readme`
Expected: FAIL with `IndexError` (no `### Authoring skill` section).

- [ ] **Step 3: Edit the README**

In "Install and prerequisites", after the line `3. Run `/software-factory:software-factory`.` and its blank line, add:

```markdown
To write pipelines and steps with an agent, call `/factory-authoring` in any Claude session. See "Authoring skill" in the reference.
```

Then add this section after the `### Pipeline editor` section, before `### Dashboard`:

`````markdown
### Authoring skill

The `factory-authoring` skill writes step and pipeline files for you, in any Claude session.
You do not need the orchestrator, the local server or the browser.

What it does:

- It reads your request, or a prompt file that describes a pipeline.
- It reuses the existing steps. It writes the new step files, then the pipeline files.
- It runs `factory pipeline check` and `factory pipeline keys`. It fixes the files until the check has no error.
- It writes local files, unless you ask for generic files. For generic files, it offers the library commit.
- It needs the factory in the repository: `.factory/factory.yaml` must exist.

How to call it:

- Ask Claude in your own words, for example "Create a factory pipeline that fixes a crash". Claude loads the skill.
- Or call it: `/factory-authoring <file or request>`. The full name is `/software-factory:factory-authoring`.

Example. The file `prompts/crash-pipeline.md`:

```markdown
# Crash fix pipeline

- Input: `crash_log`, the path of a crash log file.
- Step 1, a command: copy the last 200 lines of the log into an artifact.
- Step 2, the agent: read that artifact, find the cause of the crash and fix it.
- Step 3: the user validates the change.
```

The request: "Implement `prompts/crash-pipeline.md`".

Then review the pipeline in the browser with `factory pipeline edit <id>`.
`````

- [ ] **Step 4: Run the tests**

Run: `cd software-factory && uv run --with pytest --with pyyaml pytest -q tests/test_authoring_skill.py tests/test_docs.py`
Expected: all pass. `test_docs::test_readme_commands_exist` also passes.

- [ ] **Step 5: Commit**

```bash
cd /Users/fabienboismoreau/Documents/Projects/SoftwareFactory/SoftwareFactory
git add software-factory/README.md software-factory/tests/test_authoring_skill.py
git commit -m "authoring skill: README section"
```

### Task 3: Verification report and manual check list

**Files:**
- Create: `software-factory/tests/report_authoring_skill.py`
- Create: `verification/software-factory/authoring-skill-dod.md`
- Create: `verification/software-factory/authoring-skill-updated-tests.md`
- Create: `verification/software-factory/authoring-skill-manual-check.md`
- Generated: `verification/software-factory/authoring-skill-junit.xml`, `verification/software-factory/authoring-skill-report.md`

**Interfaces:**
- Consumes: `tests/report.py` functions `cases(junit)` and `table(rows)`, and the constant `VERIF`.
- Produces: the report file.

- [ ] **Step 1: Write the report script**

Create `software-factory/tests/report_authoring_skill.py`:

```python
import subprocess
import sys
from datetime import datetime

from report import SF, VERIF, cases, table

JUNIT = VERIF / "authoring-skill-junit.xml"
REPORT = VERIF / "authoring-skill-report.md"
UPDATED = VERIF / "authoring-skill-updated-tests.md"
DOD = VERIF / "authoring-skill-dod.md"
MODULES = ["test_authoring_skill", "test_docs", "test_skill"]
ORCHESTRATOR_SKILL = "software-factory/skills/software-factory/SKILL.md"


def orchestrator_skill_diff():
    r = subprocess.run(["git", "diff", "master", "--", ORCHESTRATOR_SKILL], cwd=SF.parent, capture_output=True, text=True)
    return r.stdout.strip()


def main():
    rows = cases(JUNIT)
    lines = ["# Authoring skill verification report", "", f"Date: {datetime.now():%Y-%m-%d %H:%M}", ""]
    mine = [r for r in rows if r["module"] in MODULES]
    passed = sum(r["status"] == "PASS" for r in mine)
    lines += ["## Milestone 1. Authoring skill", "", f"{passed} of {len(mine)} tests pass.", ""] + table(mine) + [""]
    total = sum(r["status"] == "PASS" for r in rows)
    failed = [r for r in rows if r["status"] != "PASS"]
    lines += ["## Full test suite", "", f"{total} of {len(rows)} tests pass.", ""]
    if failed:
        lines += table(failed) + [""]
    diff = orchestrator_skill_diff()
    lines += ["## Orchestrator skill", "",
              "`git diff master -- " + ORCHESTRATOR_SKILL + "` is empty. The menu is unchanged." if not diff
              else "The orchestrator skill changed. This breaks the Definition Of Done.", ""]
    lines += ["## Updated tests", ""]
    updated = UPDATED.read_text().splitlines() if UPDATED.exists() else []
    updated = [line for line in updated if line != "# Updated tests"]
    lines += updated or ["None."]
    if DOD.exists():
        lines += [""] + DOD.read_text().splitlines()
    REPORT.write_text("\n".join(lines) + "\n")
    return 0 if rows and total == len(rows) and not diff else 1


if __name__ == "__main__":
    sys.exit(main())
```

Check that `tests/report.py` defines `SF`. It does: `SF = Path(__file__).resolve().parents[1]`.

- [ ] **Step 2: Write the updated-tests file**

Create `verification/software-factory/authoring-skill-updated-tests.md`:

```markdown
# Updated tests

None. No existing test changed.
```

If a later step must change an existing test, replace "None..." with one line per test: `- tests/<file>::<test>: <why>`.

- [ ] **Step 3: Write the DoD mapping**

Create `verification/software-factory/authoring-skill-dod.md`:

```markdown
## Definition Of Done

### Workflow Complete

- The plan exists under `plans/2026-10-13-authoring-skill.md`. It was committed before the implementation, in the first commit of the branch.
- The work is on the branch `authoring-skill`. `master` is unchanged.
- Every existing test still passes: see "Full test suite" above. Updated tests: see "Updated tests" above.

### Skill

- The skill file is `skills/factory-authoring/SKILL.md`. The plugin finds every `skills/<name>/SKILL.md`, so `plugin.json` is unchanged: covered by `test_authoring_skill::test_skill_file_and_frontmatter`.
- The description names pipelines, steps and the "Implement" example: covered by `test_skill_file_and_frontmatter`. Loading it from a request: manual check 1.
- Direct call `/factory-authoring <file or request>`: `argument-hint` and `$ARGUMENTS` in the skill. Manual check 5.
- No orchestrator, server or browser: the workflow uses only CLI commands. The fallback path to `bin/factory`: covered by `test_fallback_factory_path_exists`.

### Format reference

- Where files go, levels, override of built-in steps: the "Where files go" section of the skill.
- Ids and key names, key types, factory keys with "maybe set": the "Ids and key names" and "Key types" sections.
- Every step manifest field and every pipeline field: covered by `test_every_field_is_described`.
- The three step types, outputs, `done_when`, `done_check`, the order of the checks of `factory done`, `config` and `with`, typed `inputs`, the `create-worktree` rule: the sections of the same names in the skill.
- One example of each type and one pipeline with an input, an output used later and a config value: covered by `test_examples_load_and_check_clean` and `test_example_command_step_runs`.

### Workflow of the skill

- Steps 1 to 9 of the prompt: the "Workflow" section of the skill. Every `factory` command in it exists: covered by `test_skill_commands_exist`. Behavior with an agent: manual checks 1 to 4.

### Rules of the skill

- Built-in files, task files, unfinished tasks (with `path`), generic pipelines use generic or built-in steps, steps that call a skill: the "Rules" section of the skill.

### Orchestrator and documentation

- The `software-factory` skill is unchanged: see "Orchestrator skill" above.
- The README section and its example: covered by `test_readme_describes_authoring_skill`. No tutorial step: the same test.

### Verification

- This report, the CLI tests above, and the manual check list `authoring-skill-manual-check.md`.
- Built-in step ids named in the skill exist: covered by `test_named_builtin_steps_exist`.
```

- [ ] **Step 4: Write the manual check list**

Create `verification/software-factory/authoring-skill-manual-check.md`:

```markdown
# Authoring skill: manual checks

Use a test repository with the factory initialized and a test library in its own git repository. Never a real library or a real `.factory/`.

## Setup

1. Install the plugin from this branch: `/plugin marketplace add <path to the SoftwareFactory folder>`, then `/plugin install software-factory@software-factory`. Restart Claude.
2. In the test repository, check that `.factory/factory.yaml` exists and that its `library` key points to the test library.
3. Write the file `prompts/crash-pipeline.md` in the test repository:

   ```markdown
   # Crash fix pipeline

   - Input: `crash_log`, the path of a crash log file.
   - Step 1, a command: copy the last 200 lines of the log into an artifact. The artifact is a file output.
   - Step 2, the agent: read that artifact, find the cause of the crash and fix it.
   - Step 3: the user validates the change.
   ```

## Checks

1. **The skill loads from a request.** Start a normal Claude session in the test repository, not the orchestrator. Ask: "Implement `prompts/crash-pipeline.md`".
   - Expected: the `factory-authoring` skill loads.
   - Expected: the agent writes local files under `.factory/steps/` and `.factory/pipelines/`: one `ai` step, one `command` step with a `file` output, and a pipeline with the input `crash_log`.
   - Expected: the agent runs `factory pipeline check <id>`, and the last run has no error.
2. **The pipeline runs.** Launch the new pipeline from the orchestrator or with `factory launch <id> --input crash_log=<path>`. Run it to the end.
   - Expected: the command step sets its output, the `ai` step reads it, and the task ends `finished`.
3. **A generic step.** Ask: "Create a generic factory step that runs `make lint`".
   - Expected: the file is in `<library>/steps/`.
   - Expected: the agent offers `factory library commit "Factory library: add step <id>" <path>` and commits only after you approve.
4. **A changed step.** Ask: "Change the step `<id of step 2>` so it also writes a short summary".
   - Expected: the agent runs `factory pipeline list --json`, then `factory pipeline check` on every listed pipeline, including the one that uses the step.
5. **Direct call.** Run `/factory-authoring Create a local step that prints the git status`.
   - Expected: the skill runs with this request and writes the step.

Write the result of each check: pass or fail, with what you saw.
```

- [ ] **Step 5: Run the full suite and write the report**

Run:

```bash
cd /Users/fabienboismoreau/Documents/Projects/SoftwareFactory/SoftwareFactory/software-factory
uv run --with pytest --with pyyaml pytest -q tests --junitxml=../verification/software-factory/authoring-skill-junit.xml
cd tests && uv run --with pyyaml python report_authoring_skill.py
```

Expected: every test passes. The report script exits 0. `verification/software-factory/authoring-skill-report.md` shows "Milestone 1. Authoring skill", "Full test suite" with all tests passing, and "`git diff master -- ...` is empty".

If a test fails, fix the cause and run the suite again. If an existing test must change, list it in `authoring-skill-updated-tests.md`.

- [ ] **Step 6: Commit**

```bash
cd /Users/fabienboismoreau/Documents/Projects/SoftwareFactory/SoftwareFactory
git add software-factory/tests/report_authoring_skill.py verification/software-factory/authoring-skill-*.md verification/software-factory/authoring-skill-junit.xml
git commit -m "authoring skill: verification report and manual check list"
```
