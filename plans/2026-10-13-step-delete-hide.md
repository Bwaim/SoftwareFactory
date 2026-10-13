# Step delete and hide Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add "delete a step" (dry run, safety checks, library commit offer) and "hide a step" (per-repository list, editor and list filtering, check warning) to the existing software factory.

**Architecture:** Two new modules, `step_delete.py` and `hidden.py`, hold all logic. The CLI (`commands.py`), the server API (`api.py`), the editor page and the orchestrator call them. `Registry` gains `variants` so delete knows every level of an id.

**Tech Stack:** Python 3.12, pyyaml, pytest, plain HTML/JS page, `uv`.

**Spec:** `specs/2026-10-13-step-delete-hide-design.md`. Requirements and Definition Of Done: `prompts/factory_step_delete_hide.md`.

## Global Constraints

- All code lives in `software-factory/`. Verification files in `verification/software-factory/`. Nothing else outside `specs/` and `plans/`.
- Never change a real library or a real `.factory/`. Tests use the `inited` fixture (test repo, test library in its own git repo, fake adapter).
- No code comments. Simple English in every user-facing text and in the README.
- The data format version does not change. `hidden_steps` is optional.
- Every refusal is a `FactoryError`. The CLI prints `Error: <text>` and exits 1. The API returns 400 `{"error": <text>}`.
- Exact texts:
  - `Built-in steps cannot be deleted. Hide the step instead: \`factory step hide <id>\`.`
  - `Other repositories that use this library are not checked.`
  - `Factory library: delete step <id>`
  - ``A hidden step is used: `<id>`.``
  - `Step <id> is still used. Remove it from these first:`
- The library commit rule F1 stays (`library.commit` also takes the library `factory.yaml` when new or changed). Delete tests commit the library first.
- Run tests from `software-factory/`: `uv run --with pytest --with pyyaml pytest -q tests`. The full suite takes about 2.5 minutes.
- Commits: no co-author line. Branch `step-delete-hide`. `master` stays unchanged.
- Each milestone ends with the full suite green and a commit.

## Review Focus

1. A pipeline file that another level overrides still lists the step. Expected: it counts as a user (pinned in Task 2 `test_overridden_pipeline_is_a_user`).
2. A step id used only inside a composite step path of a running task (path `["combo", "core"]`). Expected: the task is a user (pinned in Task 2 `test_refused_while_used`, task path through a composite).
3. A `script` step whose body names a script that does not exist. Expected: delete works and lists only the `.md` file (pinned in Task 2 `test_script_step_with_missing_script`).
4. Unhide of the last hidden id. Expected: the key `hidden_steps` is removed, so the file looks like data without the key (pinned in Task 6 `test_data_without_hidden_steps`).
5. A hidden step listed twice in one pipeline. Expected: one warning, not two (pinned in Task 7 `test_pipeline_check_warns_hidden_once`).

---

## Task 0: Branch and documents

- [ ] **Step 1: Create the branch and commit the spec and the plan**

```bash
cd /Users/fabienboismoreau/Documents/Projects/SoftwareFactory/SoftwareFactory
git checkout master
git checkout -b step-delete-hide
git add specs/2026-10-13-step-delete-hide-design.md plans/2026-10-13-step-delete-hide.md
git commit -m "docs: spec and plan for step delete and hide"
```

# Milestone 1: Delete a step

## Task 1: Registry variants, all pipeline files, hidden ids

**Files:**
- Modify: `software-factory/lib/factory/registry.py`
- Create: `software-factory/lib/factory/hidden.py`
- Test: `software-factory/tests/test_step_delete.py` (new file, first tests)

**Interfaces:**
- Produces:
  - `Registry.variants: dict[str, list[Step]]`, levels in order builtin, generic, local. `Registry.steps[sid] is Registry.variants[sid][-1]`.
  - `registry.all_pipeline_files(ctx) -> list[tuple[str, str, dict]]` as `(level, pipeline_id, data)`, every level, overridden ones included.
  - `hidden.KEY = "hidden_steps"`, `hidden.ids(ctx) -> list[str]`, `hidden.discard(ctx, sid) -> None`.

- [ ] **Step 1: Write the failing tests**

Create `software-factory/tests/test_step_delete.py`:

```python
from pathlib import Path

import pytest
import yaml

from conftest import git, make_task, task_json, write_pipeline, write_step
from factory import catalog, hidden, repo
from factory.registry import Registry, all_pipeline_files


@pytest.fixture
def ctx(inited):
    return repo.load_ctx(cwd=inited.repo)


def set_hidden(inited, ids):
    p = inited.fdir / "factory.yaml"
    data = yaml.safe_load(p.read_text())
    data["hidden_steps"] = ids
    p.write_text(yaml.safe_dump(data, sort_keys=False))


def test_registry_keeps_every_level(inited, ctx):
    write_step(inited.library, "dup", {"description": "generic one"})
    write_step(inited.fdir, "dup", {"description": "local one"})
    reg = Registry.load(ctx)
    assert [s.level for s in reg.variants["dup"]] == ["generic", "local"]
    assert reg.steps["dup"] is reg.variants["dup"][-1]
    assert [s.level for s in reg.variants["user-validation"]] == ["builtin"]


def test_all_pipeline_files_includes_overridden(inited, ctx):
    write_pipeline(inited.library, {"id": "same", "steps": ["a"]})
    write_pipeline(inited.fdir, {"id": "same", "steps": ["b"]})
    found = [(level, pid) for level, pid, _ in all_pipeline_files(ctx) if pid == "same"]
    assert found == [("generic", "same"), ("local", "same")]


def test_hidden_ids_and_discard(inited, ctx):
    assert hidden.ids(ctx) == []
    set_hidden(inited, ["a", "b"])
    assert hidden.ids(ctx) == ["a", "b"]
    hidden.discard(ctx, "a")
    assert hidden.ids(ctx) == ["b"]
    hidden.discard(ctx, "b")
    assert "hidden_steps" not in yaml.safe_load((inited.fdir / "factory.yaml").read_text())
    before = (inited.fdir / "factory.yaml").read_text()
    hidden.discard(ctx, "zzz")
    assert (inited.fdir / "factory.yaml").read_text() == before
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run --with pytest --with pyyaml pytest -q tests/test_step_delete.py`
Expected: FAIL with `ImportError: cannot import name 'hidden'` (or `all_pipeline_files`).

- [ ] **Step 3: Implement**

In `registry.py`, add after `level_roots`:

```python
def all_pipeline_files(ctx):
    out = []
    for level, root in level_roots(ctx):
        for p in sorted((root / "pipelines").glob("*.yaml")):
            data = fsio.read_yaml(p, {}) or {}
            out.append((level, data.get("id") or p.stem, data))
    return out
```

Change `Registry.__init__` and `Registry.load`:

```python
class Registry:
    def __init__(self, steps, pipelines, variants=None):
        self.steps = steps
        self.pipelines = pipelines
        self.variants = variants if variants is not None else {sid: [s] for sid, s in steps.items()}

    @classmethod
    def load(cls, ctx):
        steps, pipelines, variants = {}, {}, {}
        for level, root in level_roots(ctx):
            for p in sorted((root / "steps").glob("*.md")):
                manifest, body = parse_step_text(p.read_text(), p)
                sid = manifest.get("id") or p.stem
                steps[sid] = Step(sid, level, p, manifest, body)
                variants.setdefault(sid, []).append(steps[sid])
            for p in sorted((root / "pipelines").glob("*.yaml")):
                data = fsio.read_yaml(p, {}) or {}
                pid = data.get("id") or p.stem
                pipelines[pid] = Pipeline(pid, level, p, data)
        reg = cls(steps, pipelines, variants)
        reg.check_loops()
        return reg
```

Create `lib/factory/hidden.py`:

```python
from . import fsio

KEY = "hidden_steps"


def path(ctx):
    return ctx.fdir / "factory.yaml"


def ids(ctx):
    return [str(i) for i in ctx.factory_yaml().get(KEY) or []]


def remove(data, sid):
    current = list(data.get(KEY) or [])
    if sid not in current:
        return False
    rest = [i for i in current if i != sid]
    if rest:
        data[KEY] = rest
    else:
        data.pop(KEY, None)
    return True


def discard(ctx, sid):
    if sid in ids(ctx):
        fsio.update_yaml(path(ctx), lambda data: remove(data, sid))
```

- [ ] **Step 4: Run the tests**

Run: `uv run --with pytest --with pyyaml pytest -q tests/test_step_delete.py tests/test_registry.py`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add software-factory/lib/factory/registry.py software-factory/lib/factory/hidden.py software-factory/tests/test_step_delete.py
git commit -m "registry: keep every level of a step id; hidden: ids and discard"
```

## Task 2: Delete plan and delete

**Files:**
- Create: `software-factory/lib/factory/step_delete.py`
- Test: `software-factory/tests/test_step_delete.py` (append)

**Interfaces:**
- Consumes: `Registry.variants`, `all_pipeline_files`, `hidden.discard`, `library.repo_root`, `library.message`, `repo.git(args, cwd, check=True)`, `state.list_tasks(ctx)`.
- Produces:
  - `step_delete.plan(ctx, sid, level=None) -> dict` with keys `id, level, files (list[str]), replaced_by (str|None), in_use_stays (str|None), users (list[{kind, id, level}]), warnings (list[str]), blocked (bool)`.
  - `step_delete.delete(ctx, sid, level=None) -> dict`: the plan plus `removed (list[str])` and `library_commit ({message, paths}|None)`.
  - `step_delete.describe(user) -> str`, `step_delete.render(result, dry_run) -> str`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_step_delete.py` (add `from factory import step_delete` and `from factory.errors import FactoryError` to the imports):

```python
def commit_library(inited):
    root = inited.library.parent
    git("add", "-A", cwd=root)
    git("commit", "-m", "library", cwd=root)
    return root


def snapshot(root):
    return {str(p.relative_to(root)): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


def entry(sid, path=None):
    return {"id": sid, "path": path or [sid], "with": {}, "column": None, "model": None, "effort": None}


def test_plan_local_step(inited, ctx):
    write_step(inited.fdir, "solo", {})
    out = step_delete.plan(ctx, "solo")
    assert out["level"] == "local" and [Path(p).name for p in out["files"]] == ["solo.md"]
    assert out["replaced_by"] is None and out["in_use_stays"] is None and out["users"] == []
    assert out["warnings"] == [] and out["blocked"] is False


def test_delete_local_step_removes_file(inited, ctx):
    write_step(inited.fdir, "solo", {})
    out = step_delete.delete(ctx, "solo")
    assert not (inited.fdir / "steps" / "solo.md").exists()
    assert [Path(p).name for p in out["removed"]] == ["solo.md"] and out["library_commit"] is None


def test_local_override_is_replaced_by_generic(inited, ctx):
    write_step(inited.library, "dup", {"description": "generic one"})
    write_step(inited.fdir, "dup", {"description": "local one"})
    write_pipeline(inited.fdir, {"id": "uses-dup", "steps": ["dup"]})
    out = step_delete.plan(ctx, "dup")
    assert out["level"] == "local" and out["replaced_by"] == "generic" and out["users"] == [] and not out["blocked"]
    step_delete.delete(ctx, "dup")
    assert Registry.load(ctx).steps["dup"].level == "generic"


def test_generic_under_local_override(inited, ctx):
    write_step(inited.library, "dup", {})
    write_step(inited.fdir, "dup", {})
    write_pipeline(inited.fdir, {"id": "p", "steps": ["dup"]})
    out = step_delete.delete(ctx, "dup", "generic")
    assert out["in_use_stays"] == "local" and out["replaced_by"] is None and not out["blocked"]
    assert not (inited.library / "steps" / "dup.md").exists() and (inited.fdir / "steps" / "dup.md").exists()
    with pytest.raises(FactoryError, match="There is no generic step `dup`."):
        step_delete.plan(ctx, "dup", "generic")


def test_unknown_step(inited, ctx):
    with pytest.raises(FactoryError, match="The step `nope` does not exist."):
        step_delete.plan(ctx, "nope")


def test_generic_step_offers_commit_of_removed_file_only(inited, ctx):
    write_step(inited.library, "gstep", {})
    root = commit_library(inited)
    (root / "other.txt").write_text("staged\n")
    git("add", "other.txt", cwd=root)
    out = step_delete.delete(ctx, "gstep")
    assert out["warnings"] == ["Other repositories that use this library are not checked."]
    offer = out["library_commit"]
    assert offer["message"] == "Factory library: delete step gstep"
    assert [Path(p).name for p in offer["paths"]] == ["gstep.md"]
    inited.factory("library", "commit", offer["message"], *offer["paths"])
    assert git("show", "--name-status", "--format=", "HEAD", cwd=root) == "D\tfactory-library/steps/gstep.md"
    assert git("diff", "--cached", "--name-only", cwd=root) == "other.txt"


def test_untracked_generic_step_has_no_commit_offer(inited, ctx):
    commit_library(inited)
    write_step(inited.library, "fresh", {})
    out = step_delete.delete(ctx, "fresh")
    assert out["library_commit"] is None and not (inited.library / "steps" / "fresh.md").exists()


def test_script_step_removes_its_script(inited, ctx):
    write_step(inited.fdir, "runner", {"type": "script"}, body="runner.sh\n")
    (inited.fdir / "steps" / "runner.sh").write_text("echo hi\n")
    out = step_delete.plan(ctx, "runner")
    assert [Path(p).name for p in out["files"]] == ["runner.md", "runner.sh"]
    step_delete.delete(ctx, "runner")
    assert not (inited.fdir / "steps" / "runner.sh").exists()


def test_shared_script_stays(inited, ctx):
    for sid in ("one", "two"):
        write_step(inited.fdir, sid, {"type": "script"}, body="shared.sh\n")
    (inited.fdir / "steps" / "shared.sh").write_text("echo hi\n")
    out = step_delete.delete(ctx, "one")
    assert [Path(p).name for p in out["removed"]] == ["one.md"]
    assert (inited.fdir / "steps" / "shared.sh").exists()


def test_script_step_with_missing_script(inited, ctx):
    write_step(inited.fdir, "broken", {"type": "script"}, body="missing.sh\n")
    out = step_delete.delete(ctx, "broken")
    assert [Path(p).name for p in out["removed"]] == ["broken.md"]


def test_builtin_step_cannot_be_deleted(inited, ctx):
    message = "Built-in steps cannot be deleted. Hide the step instead: `factory step hide user-validation`."
    for level in (None, "local", "generic"):
        with pytest.raises(FactoryError) as e:
            step_delete.plan(ctx, "user-validation", level)
        assert str(e.value) == message


def test_refused_while_used(inited, ctx):
    write_step(inited.library, "core", {})
    write_pipeline(inited.library, {"id": "gp", "steps": [{"id": "core", "with": {}}]})
    write_step(inited.fdir, "combo", {"type": "composite", "steps": ["core"]}, body="")
    make_task(ctx, tid="t1", steps=[entry("core", ["combo", "core"])])
    make_task(ctx, tid="t2", status="finished", steps=[entry("core")])
    out = step_delete.plan(ctx, "core")
    assert out["blocked"] is True
    assert {(u["kind"], u["id"], u["level"]) for u in out["users"]} == {
        ("pipeline", "gp", "generic"), ("composite", "combo", "local"), ("task", "t1", None)}
    with pytest.raises(FactoryError) as e:
        step_delete.delete(ctx, "core")
    text = str(e.value)
    assert text.startswith("Step core is still used. Remove it from these first:")
    for line in ("- pipeline gp (generic)", "- composite step combo (local)", "- task t1"):
        assert line in text
    assert "t2" not in text
    assert (inited.library / "steps" / "core.md").exists()


def test_overridden_pipeline_is_a_user(inited, ctx):
    write_step(inited.fdir, "old", {})
    write_step(inited.fdir, "new", {})
    write_pipeline(inited.library, {"id": "same", "steps": ["old"]})
    write_pipeline(inited.fdir, {"id": "same", "steps": ["new"]})
    users = step_delete.plan(ctx, "old")["users"]
    assert users == [{"kind": "pipeline", "id": "same", "level": "generic"}]


def test_dry_run_changes_nothing(inited, ctx):
    write_step(inited.library, "gone", {"type": "script"}, body="gone.sh\n")
    (inited.library / "steps" / "gone.sh").write_text("echo\n")
    write_step(inited.fdir, "gone", {})
    set_hidden(inited, ["gone"])
    before = snapshot(inited.fdir), snapshot(inited.library)
    for level in (None, "local", "generic"):
        step_delete.plan(ctx, "gone", level)
    inited.factory("step", "delete", "gone", "--dry-run")
    inited.factory("step", "delete", "gone", "--level", "generic", "--dry-run")
    assert (snapshot(inited.fdir), snapshot(inited.library)) == before


def test_delete_removes_id_from_hidden_steps(inited, ctx):
    write_step(inited.fdir, "lonely", {})
    write_step(inited.library, "both", {})
    write_step(inited.fdir, "both", {})
    set_hidden(inited, ["lonely", "both"])
    step_delete.delete(ctx, "lonely")
    step_delete.delete(ctx, "both")
    assert hidden.ids(ctx) == ["both"]


def test_config_section_is_kept(inited, ctx):
    write_step(inited.fdir, "cfg", {"config": {"k": {"description": "d"}}})
    inited.factory("config", "set", "cfg", "k", "v")
    step_delete.delete(ctx, "cfg")
    assert yaml.safe_load((inited.fdir / "config.yaml").read_text())["cfg"]["k"] == "v"


def test_deleted_catalog_step_shows_not_installed(inited, ctx):
    inited.factory("catalog", "install", "push", "--local")
    rows = {i["id"]: i for i in catalog.items(ctx)}
    assert rows["push"]["status"] == "installed"
    out = step_delete.delete(ctx, "push")
    assert sorted(Path(p).name for p in out["removed"]) == ["push.md", "push.sh"]
    rows = {i["id"]: i for i in catalog.items(ctx)}
    assert rows["push"]["status"] == "not installed"
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run --with pytest --with pyyaml pytest -q tests/test_step_delete.py`
Expected: FAIL with `ImportError: cannot import name 'step_delete'`. `test_dry_run_changes_nothing` needs Task 3 for its CLI lines; it passes after Task 3.

- [ ] **Step 3: Implement `lib/factory/step_delete.py`**

```python
import shlex
from pathlib import Path

from . import hidden, library, repo, state
from .errors import FactoryError
from .registry import Registry, all_pipeline_files, normalize_entry

LEVELS = ("local", "generic")
BUILTIN_REFUSAL = "Built-in steps cannot be deleted. Hide the step instead: `factory step hide {id}`."
OTHER_REPOS = "Other repositories that use this library are not checked."


def target_step(reg, sid, level):
    variants = reg.variants.get(sid)
    if not variants:
        raise FactoryError(f"The step `{sid}` does not exist.")
    if level is None:
        target = variants[-1]
    elif all(s.level == "builtin" for s in variants):
        target = variants[-1]
    elif level not in LEVELS:
        raise FactoryError("The level must be `local` or `generic`.")
    else:
        found = [s for s in variants if s.level == level]
        if not found:
            raise FactoryError(f"There is no {level} step `{sid}`.")
        target = found[-1]
    if target.level == "builtin":
        raise FactoryError(BUILTIN_REFUSAL.format(id=sid))
    return target


def script_of(step):
    if step.type != "script":
        return None
    lines = [line.strip() for line in step.body.splitlines() if line.strip()]
    return (step.path.parent / lines[0]).resolve() if lines else None


def script_files(reg, target):
    script = script_of(target)
    if script is None or not script.is_file() or script.parent != target.path.parent.resolve():
        return []
    for variants in reg.variants.values():
        for other in variants:
            if other.path.resolve() != target.path.resolve() and script_of(other) == script:
                return []
    return [script]


def entry_ids(data):
    steps = data.get("steps") if isinstance(data, dict) else None
    return [normalize_entry(e).get("id") for e in steps or [] if isinstance(e, (str, dict))]


def find_users(ctx, reg, sid, target):
    found = []
    for level, pid, data in all_pipeline_files(ctx):
        if sid in entry_ids(data):
            found.append({"kind": "pipeline", "id": pid, "level": level})
    for other_id in sorted(reg.variants):
        for step in reg.variants[other_id]:
            if step.type == "composite" and step.path != target.path and sid in step.children:
                found.append({"kind": "composite", "id": step.id, "level": step.level})
    for task in state.list_tasks(ctx):
        if task.get("status") == "finished":
            continue
        if any(sid in (e.get("path") or [e.get("id")]) for e in task.get("steps") or []):
            found.append({"kind": "task", "id": task["id"], "level": None})
    return found


def plan(ctx, sid, level=None):
    reg = Registry.load(ctx)
    target = target_step(reg, sid, level)
    variants = reg.variants[sid]
    others = [s for s in variants if s is not target]
    in_use = variants[-1]
    in_use_stays = in_use.level if in_use is not target else None
    replaced_by = others[-1].level if others and in_use is target else None
    users = [] if others else find_users(ctx, reg, sid, target)
    return {
        "id": sid,
        "level": target.level,
        "files": [str(p) for p in [target.path] + script_files(reg, target)],
        "replaced_by": replaced_by,
        "in_use_stays": in_use_stays,
        "users": users,
        "warnings": [OTHER_REPOS] if target.level == "generic" else [],
        "blocked": bool(users),
    }


def describe(user):
    if user["kind"] == "task":
        return f"- task {user['id']}"
    kind = "pipeline" if user["kind"] == "pipeline" else "composite step"
    return f"- {kind} {user['id']} ({user['level']})"


def tracked(ctx, files):
    top = library.repo_root(ctx.library())
    if top is None:
        return []
    return [p for p in files if repo.git(["ls-files", "--error-unmatch", "--", str(p)], top, check=False).returncode == 0]


def delete(ctx, sid, level=None):
    result = plan(ctx, sid, level)
    if result["blocked"]:
        raise FactoryError(f"Step {sid} is still used. Remove it from these first:\n" + "\n".join(describe(u) for u in result["users"]))
    files = [Path(p) for p in result["files"]]
    in_git = tracked(ctx, files) if result["level"] == "generic" else []
    removed = []
    for p in files:
        try:
            p.unlink()
        except FileNotFoundError:
            continue
        removed.append(str(p))
    if not result["replaced_by"] and not result["in_use_stays"]:
        hidden.discard(ctx, sid)
    offer = None
    if in_git:
        offer = {"message": library.message("delete", "step", sid), "paths": [str(p) for p in in_git]}
    return {**result, "removed": removed, "library_commit": offer}


def render(result, dry_run):
    sid = result["id"]
    lines = [f"{'Dry run: delete' if dry_run else 'Deleted'} the {result['level']} step `{sid}`."]
    lines.append("Files to remove:" if dry_run else "Removed files:")
    lines += [f"- {p}" for p in (result["files"] if dry_run else result["removed"])]
    if result["replaced_by"]:
        lines.append(f"The {result['replaced_by']} step `{sid}` is used {'after the delete' if dry_run else 'now'}.")
    if result["in_use_stays"]:
        lines.append(f"The {result['in_use_stays']} step `{sid}` stays in use.")
    if result["users"]:
        lines.append(f"Step {sid} is still used. Remove it from these first:")
        lines += [describe(u) for u in result["users"]]
    lines += [f"Warning: {w}" for w in result["warnings"]]
    offer = result.get("library_commit")
    if offer:
        paths = " ".join(shlex.quote(p) for p in offer["paths"])
        lines.append(f"Library commit offer: factory library commit {shlex.quote(offer['message'])} {paths}")
    return "\n".join(lines)
```

- [ ] **Step 4: Run the tests**

Run: `uv run --with pytest --with pyyaml pytest -q tests/test_step_delete.py`
Expected: all PASS except `test_dry_run_changes_nothing` (needs Task 3).

- [ ] **Step 5: Commit**

```bash
git add software-factory/lib/factory/step_delete.py software-factory/tests/test_step_delete.py
git commit -m "step delete: dry run plan, user checks, delete and library commit offer"
```

## Task 3: CLI `factory step delete`

**Files:**
- Modify: `software-factory/lib/factory/commands.py` (parser in `register`, new command after `step show`)
- Test: `software-factory/tests/test_step_delete.py` (append)

**Interfaces:**
- Consumes: `step_delete.plan`, `step_delete.delete`, `step_delete.render`.
- Produces: `factory step delete <id> [--level local|generic] [--dry-run] [--json]`.

- [ ] **Step 1: Write the failing tests**

```python
def test_cli_delete_and_dry_run(inited):
    write_step(inited.fdir, "solo", {})
    out = inited.factory.json("step", "delete", "solo", "--dry-run")
    assert out["blocked"] is False and (inited.fdir / "steps" / "solo.md").exists()
    text = inited.factory("step", "delete", "solo", "--dry-run").stdout
    assert "Dry run: delete the local step `solo`." in text and "solo.md" in text
    text = inited.factory("step", "delete", "solo").stdout
    assert "Deleted the local step `solo`." in text and not (inited.fdir / "steps" / "solo.md").exists()


def test_cli_refusals(inited):
    r = inited.factory("step", "delete", "user-validation", check=False)
    assert r.returncode == 1
    assert "Built-in steps cannot be deleted. Hide the step instead: `factory step hide user-validation`." in r.stderr
    write_step(inited.fdir, "kept", {})
    write_pipeline(inited.fdir, {"id": "pk", "steps": ["kept"]})
    r = inited.factory("step", "delete", "kept", check=False)
    assert r.returncode == 1 and "- pipeline pk (local)" in r.stderr
    r = inited.factory("step", "delete", "kept", "--level", "builtin", check=False)
    assert r.returncode == 2


def test_cli_generic_offer_text(inited):
    write_step(inited.library, "gstep", {})
    commit_library(inited)
    text = inited.factory("step", "delete", "gstep").stdout
    assert "Warning: Other repositories that use this library are not checked." in text
    assert "Library commit offer: factory library commit 'Factory library: delete step gstep'" in text
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run --with pytest --with pyyaml pytest -q tests/test_step_delete.py -k cli`
Expected: FAIL (argparse error `invalid choice: 'delete'`).

- [ ] **Step 3: Implement**

In `commands.py` `register`, after the `show` parser line:

```python
    sd = sts.add_parser("delete", parents=[common]); sd.add_argument("id"); sd.add_argument("--level", choices=["local", "generic"]); sd.add_argument("--dry-run", action="store_true")
```

After `step_show_cmd`:

```python
@cli.command("step delete")
def step_delete_cmd(args):
    from . import step_delete
    ctx = ctx_of(args)
    result = step_delete.plan(ctx, args.id, args.level) if args.dry_run else step_delete.delete(ctx, args.id, args.level)
    if args.json:
        cli.emit(result, True)
    else:
        print(step_delete.render(result, args.dry_run))
```

- [ ] **Step 4: Run the tests**

Run: `uv run --with pytest --with pyyaml pytest -q tests/test_step_delete.py`
Expected: all PASS, `test_dry_run_changes_nothing` included.

- [ ] **Step 5: Commit**

```bash
git add software-factory/lib/factory/commands.py software-factory/tests/test_step_delete.py
git commit -m "cli: factory step delete with --level and --dry-run"
```

## Task 4: Server API and editor Delete button

**Files:**
- Modify: `software-factory/lib/factory/api.py` (after the `GET /api/steps/<id>` route)
- Modify: `software-factory/lib/factory/web/editor.html`
- Test: `software-factory/tests/test_step_delete.py` (append)

**Interfaces:**
- Consumes: `step_delete.plan`, `step_delete.delete`.
- Produces:
  - `POST /api/steps/<id>/delete/dry-run` body `{"level": "local"|"generic"|null}` → plan dict.
  - `POST /api/steps/<id>/delete` same body → delete dict. Refusal → 400 `{"error"}`.
  - JS `commitBox(offer, done)` in `editor.html`, used by save and delete.

- [ ] **Step 1: Write the failing tests**

Put the import at the top of the file, the tests at the end.

```python
from serverutil import info, request


def test_api_dry_run_and_delete(inited, ctx):
    write_step(inited.fdir, "apistep", {})
    write_step(inited.fdir, "kept", {})
    write_pipeline(inited.fdir, {"id": "pk", "steps": ["kept"]})
    inited.factory("pipeline", "edit")
    i = info(inited.fdir)
    try:
        status, plan = request(i, "POST", "/api/steps/apistep/delete/dry-run", {"level": None})
        assert status == 200 and plan == step_delete.plan(ctx, "apistep")
        assert (inited.fdir / "steps" / "apistep.md").exists()
        assert request(i, "POST", "/api/steps/apistep/delete/dry-run", {}, token=False)[0] == 401
        assert request(i, "POST", "/api/steps/apistep/delete", {}, token=False)[0] == 401
        assert (inited.fdir / "steps" / "apistep.md").exists()
        status, done = request(i, "POST", "/api/steps/apistep/delete", {"level": "local"})
        assert status == 200 and [Path(p).name for p in done["removed"]] == ["apistep.md"]
        assert not (inited.fdir / "steps" / "apistep.md").exists()
        status, err = request(i, "POST", "/api/steps/kept/delete", {})
        assert status == 400 and "- pipeline pk (local)" in err["error"]
        status, err = request(i, "POST", "/api/steps/user-validation/delete/dry-run", {})
        assert status == 400 and "Built-in steps cannot be deleted" in err["error"]
    finally:
        inited.factory("server", "stop", check=False)


def test_editor_page_has_delete_flow(inited):
    from conftest import SF
    page = (SF / "lib" / "factory" / "web" / "editor.html").read_text()
    for text in ("/delete/dry-run", "Confirm delete", "function commitBox", 'd.level !== "builtin"'):
        assert text in page
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run --with pytest --with pyyaml pytest -q tests/test_step_delete.py -k "api or editor"`
Expected: FAIL (404 on the route, page text missing).

- [ ] **Step 3: Implement the routes**

In `api.py`, after the `GET /api/steps/<id>` route:

```python
@route("POST", "/api/steps/([a-z][a-z0-9_-]*)/delete/dry-run")
def step_delete_dry_run(server, sid, query, body):
    from . import step_delete
    return step_delete.plan(server.ctx, sid, body.get("level"))


@route("POST", "/api/steps/([a-z][a-z0-9_-]*)/delete")
def step_delete_run(server, sid, query, body):
    from . import step_delete
    return step_delete.delete(server.ctx, sid, body.get("level"))
```

- [ ] **Step 4: Implement the editor changes in `editor.html`**

Replace the commit part of `renderSave` and the function `commitLibrary` with one shared `commitBox`:

```js
function commitBox(offer, done) {
  const box = el("div", {}, el("div", {}, "The library is a git repository. Files:"));
  for (const p of offer.paths) box.append(el("div", { class: "muted" }, p));
  box.append(el("div", {}, offer.message),
    el("button", { type: "button", onclick: guard(async () => {
      await api("/api/library/commit", { message: offer.message, paths: offer.paths });
      done();
    }) }, "Commit to library"));
  return box;
}
```

In `renderSave`, replace the `if (state.commit) { ... }` block with:

```js
  if (state.commit) {
    box.append(commitBox(state.commit, () => {
      state.commit = null;
      state.savedPath = state.savedPath + " (committed to the library)";
      renderSave();
    }));
  }
```

Delete the old `async function commitLibrary() { ... }`.

At the end of `showDetail`, after the body `pre`, add:

```js
  if (d.level !== "builtin") {
    box.append(el("div", { class: "row" },
      el("button", { type: "button", onclick: guard(async () => {
        const plan = await api("/api/steps/" + encodeURIComponent(d.id) + "/delete/dry-run", { level: d.level });
        box.append(deletePlanBlock(d, plan));
      }) }, "Delete")));
  }
```

Add after `showDetail`:

```js
function userText(u) {
  if (u.kind === "task") return "task " + u.id;
  return (u.kind === "pipeline" ? "pipeline " : "composite step ") + u.id + " (" + u.level + ")";
}
function deletePlanBlock(d, plan) {
  const block = el("div", { class: "card" }, el("div", {}, "Delete the " + plan.level + " step " + plan.id + ". Files:"));
  for (const f of plan.files) block.append(el("div", { class: "muted" }, f));
  if (plan.replaced_by) block.append(el("div", {}, "After the delete, the " + plan.replaced_by + " step " + plan.id + " is used."));
  if (plan.in_use_stays) block.append(el("div", {}, "The " + plan.in_use_stays + " step " + plan.id + " stays in use."));
  for (const w of plan.warnings) block.append(el("div", { class: "problem warning" }, "Warning: " + w));
  if (plan.blocked) {
    block.append(el("div", { class: "problem error" }, "The step is still used. Remove it from these first:"));
    for (const u of plan.users) block.append(el("div", { class: "problem error" }, userText(u)));
    return block;
  }
  block.append(el("div", { class: "row" },
    el("button", { type: "button", class: "primary", onclick: guard(() => deleteStep(d)) }, "Confirm delete"),
    el("button", { type: "button", onclick: () => block.remove() }, "Cancel")));
  return block;
}
async function deleteStep(d) {
  const result = await api("/api/steps/" + encodeURIComponent(d.id) + "/delete", { level: d.level });
  const box = clear(byId("detail"));
  box.append(el("div", {}, "Deleted the " + result.level + " step " + result.id + "."));
  for (const f of result.removed) box.append(el("div", { class: "muted" }, f));
  if (result.library_commit) {
    box.append(commitBox(result.library_commit, () => box.append(el("div", { class: "muted" }, "Committed to the library."))));
  }
  await loadSteps();
  if (state.model) await runCheck();
}
```

Check the page syntax:

```bash
python3 - <<'EOF' > "${TMPDIR:-/tmp}/editor-check.js"
import re, pathlib
text = pathlib.Path("software-factory/lib/factory/web/editor.html").read_text()
print(re.search(r"<script>(.*)</script>", text, re.S).group(1))
EOF
node --check "${TMPDIR:-/tmp}/editor-check.js"
```

Expected: no output, exit 0.

- [ ] **Step 5: Run the tests**

Run: `uv run --with pytest --with pyyaml pytest -q tests/test_step_delete.py tests/test_editor_api.py`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add software-factory/lib/factory/api.py software-factory/lib/factory/web/editor.html software-factory/tests/test_step_delete.py
git commit -m "editor: delete a step from the detail panel; api: delete dry run and delete routes"
```

## Task 5: Menu, SKILL.md, README, milestone 1 close

**Files:**
- Modify: `software-factory/lib/factory/menu.py`
- Modify: `software-factory/skills/software-factory/SKILL.md`
- Modify: `software-factory/README.md`
- Test: `software-factory/tests/test_step_delete.py` (append)

- [ ] **Step 1: Write the failing tests**

```python
def test_menu_has_delete_step_after_new_step(inited):
    actions = [a for g in inited.factory.json("menu")["groups"] for a in g["actions"]]
    keys = [a["key"] for a in actions]
    assert keys[keys.index("new-step") + 1] == "step-delete"
    assert actions[keys.index("step-delete")]["label"] == "Delete a step"


def test_docs_describe_delete():
    from conftest import SF
    readme = (SF / "README.md").read_text()
    skill = (SF / "skills" / "software-factory" / "SKILL.md").read_text()
    assert "**Delete a step**" in readme and "`factory step delete <id> [--level local|generic] [--dry-run]`" in readme
    assert "### Pipeline editor" in readme
    assert "(`step-delete`)" in skill and "factory step delete <id> --level <level> --dry-run --json" in skill
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run --with pytest --with pyyaml pytest -q tests/test_step_delete.py -k "menu or docs"`
Expected: FAIL.

- [ ] **Step 3: Implement**

`menu.py`, in `ACTIONS`, after the `new-step` line:

```python
    ("Pipelines and steps", "step-delete", "Delete a step", None),
```

`SKILL.md`, in Actions, after the "Create a new step" bullet:

```markdown
- **Delete a step** (`step-delete`):
  1. Run `factory step list --json`. List the local and generic steps with their level and category. Do not list built-in steps.
  2. Ask which one. Run `factory step delete <id> --level <level> --dry-run --json`. Show the files, the step that replaces it, the users and the warnings.
  3. If `blocked` is true, show the users and tell the user to remove the step from them first. Stop.
  4. Delete only after the user confirms: `factory step delete <id> --level <level> --json`.
  5. If `library_commit` is set, offer the library commit (Library commits below) with its message and paths.
```

`SKILL.md`, Library commits, first line becomes:

```markdown
After a write to the library (generic step, generic pipeline, catalog install to the library, migration, delete of a generic step):
```

`README.md`, Menu actions, after "Create a new step":

```markdown
- **Delete a step**: delete a local or generic step. It first shows what the delete does, then asks you to confirm.
```

`README.md`, Commands, after `factory step show <id>`:

```markdown
- `factory step delete <id> [--level local|generic] [--dry-run]`: delete a step. `--dry-run` only shows the files it removes, the step that replaces it and the users that block it. Built-in steps cannot be deleted.
```

`README.md`, new section before `### Dashboard`:

```markdown
### Pipeline editor

`factory pipeline edit [<id>]` opens the editor in the browser.

- Left: the available steps. Filter them by category or by text. "Reload steps" reads the step files again.
- Middle: the pipeline. Drag steps into it and reorder them. The checks run while you edit. You can save with warnings, never with errors.
- Right: the step detail. Click a step to see its manifest, its level, its file and its body.
- Delete: the detail of a local or generic step has a "Delete" button.
  - It first shows what the delete does: the files it removes, the step that replaces it, and the pipelines, composite steps and tasks that still use it.
  - A step that is still used cannot be deleted. Remove it from its users first.
  - "Confirm delete" removes the files. The list of steps reloads.
  - For a generic step, the editor offers the library commit.
```

- [ ] **Step 4: Run the full suite**

Run: `uv run --with pytest --with pyyaml pytest -q tests`
Expected: all PASS (`tests/test_docs.py` included).

- [ ] **Step 5: Commit the milestone**

```bash
git add software-factory/lib/factory/menu.py software-factory/skills/software-factory/SKILL.md software-factory/README.md software-factory/tests/test_step_delete.py
git commit -m "menu: Delete a step; docs: step delete in SKILL and README"
```

# Milestone 2: Hide a step

## Task 6: Hide and unhide, step list and show

**Files:**
- Modify: `software-factory/lib/factory/hidden.py`
- Modify: `software-factory/lib/factory/pipeline_store.py` (`step_summary`, `step_detail`)
- Modify: `software-factory/lib/factory/commands.py` (parser, `step list`, `step show`, new `step hide`, `step unhide`)
- Test: `software-factory/tests/test_step_hide.py` (new)

**Interfaces:**
- Consumes: `hidden.KEY`, `hidden.remove`, `Registry.variants`.
- Produces:
  - `hidden.hide(ctx, sid) -> str`, `hidden.unhide(ctx, sid) -> str`.
  - `pipeline_store.step_summary(step, hidden_ids=()) -> dict` with `hidden: bool`.
  - `pipeline_store.step_detail(reg, step, hidden_ids=()) -> dict` with `hidden: bool`.
  - `factory step list [--all]`, `factory step hide <id>`, `factory step unhide <id>`.

- [ ] **Step 1: Write the failing tests**

Create `software-factory/tests/test_step_hide.py`:

```python
import pytest
import yaml

from conftest import task_json, write_pipeline, write_step
from factory import hidden, repo


@pytest.fixture
def ctx(inited):
    return repo.load_ctx(cwd=inited.repo)


def set_hidden(inited, ids):
    p = inited.fdir / "factory.yaml"
    data = yaml.safe_load(p.read_text())
    data["hidden_steps"] = ids
    p.write_text(yaml.safe_dump(data, sort_keys=False))


def factory_yaml(inited):
    return yaml.safe_load((inited.fdir / "factory.yaml").read_text())


def test_hide_and_unhide(inited, ctx):
    write_step(inited.fdir, "quiet", {})
    assert inited.factory("step", "hide", "quiet").stdout.strip() == "Step quiet is hidden."
    assert hidden.ids(ctx) == ["quiet"]
    assert inited.factory("step", "hide", "quiet").stdout.strip() == "Step quiet is already hidden."
    assert hidden.ids(ctx) == ["quiet"]
    assert inited.factory("step", "unhide", "quiet").stdout.strip() == "Step quiet is visible again."
    assert hidden.ids(ctx) == []
    assert inited.factory("step", "unhide", "quiet").stdout.strip() == "Step quiet is not hidden."


def test_hide_unknown_refused_unhide_stale_allowed(inited, ctx):
    r = inited.factory("step", "hide", "ghost", check=False)
    assert r.returncode == 1 and "The step `ghost` does not exist." in r.stderr
    assert hidden.ids(ctx) == []
    set_hidden(inited, ["ghost"])
    assert inited.factory("step", "unhide", "ghost").stdout.strip() == "Step ghost is visible again."
    assert hidden.ids(ctx) == []


def test_hide_any_level(inited, ctx):
    write_step(inited.library, "gen", {})
    write_step(inited.fdir, "loc", {})
    for sid in ("user-validation", "gen", "loc"):
        inited.factory("step", "hide", sid)
    assert hidden.ids(ctx) == ["user-validation", "gen", "loc"]


def test_step_list_and_show(inited):
    write_step(inited.fdir, "quiet", {})
    write_step(inited.fdir, "loud", {})
    inited.factory("step", "hide", "quiet")
    rows = {r["id"]: r for r in inited.factory.json("step", "list")}
    assert "quiet" not in rows and rows["loud"]["hidden"] is False
    rows = {r["id"]: r for r in inited.factory.json("step", "list", "--all")}
    assert rows["quiet"]["hidden"] is True and rows["loud"]["hidden"] is False
    lines = inited.factory("step", "list", "--all").stdout.splitlines()
    assert [l for l in lines if l.startswith("quiet ")][0].endswith("hidden): Step quiet")
    assert "quiet " not in inited.factory("step", "list").stdout
    assert inited.factory.json("step", "show", "quiet")["hidden"] is True
    assert inited.factory("step", "show", "quiet").stdout.splitlines()[0].endswith("(hidden)")


def test_data_without_hidden_steps(inited, ctx):
    assert "hidden_steps" not in factory_yaml(inited)
    assert hidden.ids(ctx) == []
    version = factory_yaml(inited)["version"]
    report = inited.factory.json("version", "check")
    inited.factory("step", "hide", "user-validation")
    inited.factory("step", "unhide", "user-validation")
    assert "hidden_steps" not in factory_yaml(inited)
    assert factory_yaml(inited)["version"] == version
    assert inited.factory.json("version", "check") == report
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run --with pytest --with pyyaml pytest -q tests/test_step_hide.py`
Expected: FAIL (`invalid choice: 'hide'`).

- [ ] **Step 3: Implement**

`hidden.py`, add (and `from .errors import FactoryError`, `from .registry import Registry` at the top):

```python
def hide(ctx, sid):
    if sid not in Registry.load(ctx).variants:
        raise FactoryError(f"The step `{sid}` does not exist.")

    def add(data):
        current = list(data.get(KEY) or [])
        if sid in current:
            return False
        data[KEY] = current + [sid]
        return True

    if sid in ids(ctx) or not fsio.update_yaml(path(ctx), add):
        return f"Step {sid} is already hidden."
    return f"Step {sid} is hidden."


def unhide(ctx, sid):
    if sid not in ids(ctx) or not fsio.update_yaml(path(ctx), lambda data: remove(data, sid)):
        return f"Step {sid} is not hidden."
    return f"Step {sid} is visible again."
```

`pipeline_store.py`:

```python
def step_summary(step, hidden_ids=()):
    return {"id": step.id, "description": step.description, "category": step.category, "type": step.type,
            "level": step.level, "run_in": step.run_in, "path": str(step.path), "hidden": step.id in hidden_ids}


def step_detail(reg, step, hidden_ids=()):
    reads, writes = reg.io(step.id)
    return {**step_summary(step, hidden_ids), "manifest": step.manifest, "body": step.body,
            "reads": reads, "writes": writes, "children": step.children}
```

`commands.py` `register`: replace `sts.add_parser("list", parents=[common])` with:

```python
    sl = sts.add_parser("list", parents=[common]); sl.add_argument("--all", action="store_true")
    sts.add_parser("hide", parents=[common]).add_argument("id")
    sts.add_parser("unhide", parents=[common]).add_argument("id")
```

Replace `step_list_cmd` and `step_show_cmd`, add the two new commands:

```python
@cli.command("step list")
def step_list_cmd(args):
    from . import hidden, pipeline_store
    from .registry import Registry
    ctx = ctx_of(args)
    hidden_ids = set(hidden.ids(ctx))
    steps = sorted(Registry.load(ctx).steps.values(), key=lambda s: s.id)
    rows = [pipeline_store.step_summary(s, hidden_ids) for s in steps if args.all or s.id not in hidden_ids]
    if args.json:
        cli.emit(rows, True)
        return
    for r in rows:
        mark = ", hidden" if r["hidden"] else ""
        print(f"{r['id']} [{r['category']}] ({r['level']}, {r['run_in']}{mark}): {r['description']}")


@cli.command("step show")
def step_show_cmd(args):
    from . import hidden, pipeline_store
    from .registry import Registry
    ctx = ctx_of(args)
    reg = Registry.load(ctx)
    detail = pipeline_store.step_detail(reg, reg.step(args.id), set(hidden.ids(ctx)))
    if args.json:
        cli.emit(detail, True)
    else:
        print(f"{detail['path']}{' (hidden)' if detail['hidden'] else ''}\n\n{detail['body']}")


@cli.command("step hide")
def step_hide_cmd(args):
    from . import hidden
    print(hidden.hide(ctx_of(args), args.id))


@cli.command("step unhide")
def step_unhide_cmd(args):
    from . import hidden
    print(hidden.unhide(ctx_of(args), args.id))
```

- [ ] **Step 4: Run the tests**

Run: `uv run --with pytest --with pyyaml pytest -q tests/test_step_hide.py tests/test_step_delete.py tests/test_editor_api.py`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add software-factory/lib/factory/hidden.py software-factory/lib/factory/pipeline_store.py software-factory/lib/factory/commands.py software-factory/tests/test_step_hide.py
git commit -m "step hide: hide, unhide, step list --all and hidden marks"
```

## Task 7: Pipeline check warning, API, runtime

**Files:**
- Modify: `software-factory/lib/factory/pipeline_check.py`
- Modify: `software-factory/lib/factory/pipeline_store.py` (`check`)
- Modify: `software-factory/lib/factory/commands.py` (`pipeline check`)
- Modify: `software-factory/lib/factory/api.py` (steps routes, new hide and unhide routes)
- Test: `software-factory/tests/test_step_hide.py` (append)

**Interfaces:**
- Consumes: `hidden.ids`, `hidden.hide`, `hidden.unhide`, `pipeline_store.step_summary(step, hidden_ids)`.
- Produces:
  - `pipeline_check.check(reg, data, columns, save_level=None, hidden=())`.
  - `POST /api/steps/<id>/hide` and `POST /api/steps/<id>/unhide` → `{"message": str}`.
  - `GET /api/steps` and `GET /api/steps/<id>` rows carry `hidden`.

- [ ] **Step 1: Write the failing tests**

Put the import at the top of the file, the tests at the end.

```python
from serverutil import info, request


def hidden_pipeline(inited):
    write_step(inited.fdir, "quiet", {})
    write_pipeline(inited.fdir, {"id": "hp", "steps": ["quiet", "quiet"]})
    inited.factory("step", "hide", "quiet")


def test_pipeline_check_warns_hidden_once(inited):
    hidden_pipeline(inited)
    r = inited.factory("pipeline", "check", "hp")
    assert r.returncode == 0
    assert r.stdout.count("WARNING: A hidden step is used: `quiet`.") == 1


def test_pipeline_with_hidden_step_runs_to_end(inited):
    hidden_pipeline(inited)
    task = inited.factory.json("launch", "hp", "--description", "Hidden run")
    tid = task["id"]
    for _ in range(2):
        inited.factory("next", "--task", tid)
        inited.factory("done", "--task", tid)
    assert task_json(inited.fdir, tid)["status"] == "finished"


def test_api_hide_unhide_list_check(inited, ctx):
    write_step(inited.fdir, "quiet", {})
    inited.factory("pipeline", "edit")
    i = info(inited.fdir)
    try:
        assert request(i, "POST", "/api/steps/quiet/hide", {}, token=False)[0] == 401
        assert hidden.ids(ctx) == []
        status, out = request(i, "POST", "/api/steps/quiet/hide", {})
        assert status == 200 and out == {"message": "Step quiet is hidden."} and hidden.ids(ctx) == ["quiet"]
        status, steps = request(i, "GET", "/api/steps")
        by_id = {s["id"]: s for s in steps}
        assert by_id["quiet"]["hidden"] is True and by_id["user-validation"]["hidden"] is False
        assert request(i, "GET", "/api/steps/quiet")[1]["hidden"] is True
        status, problems = request(i, "POST", "/api/pipelines/check", {"data": {"id": "x", "steps": ["quiet"]}, "level": "local"})
        assert {"level": "warning", "message": "A hidden step is used: `quiet`."} in problems
        status, err = request(i, "POST", "/api/steps/ghost/hide", {})
        assert status == 400 and "does not exist" in err["error"]
        assert request(i, "POST", "/api/steps/quiet/unhide", {}, token=False)[0] == 401
        status, out = request(i, "POST", "/api/steps/quiet/unhide", {})
        assert status == 200 and out == {"message": "Step quiet is visible again."} and hidden.ids(ctx) == []
    finally:
        inited.factory("server", "stop", check=False)
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run --with pytest --with pyyaml pytest -q tests/test_step_hide.py`
Expected: the check and API tests FAIL. The run test may already pass.

- [ ] **Step 3: Implement**

`pipeline_check.py`: change the signature and add the warning inside the entry loop, right after `step = reg.steps[sid]`:

```python
def check(reg, data, columns, save_level=None, hidden=()):
    problems = []
    hidden = set(hidden)
    warned_hidden = set()
```

```python
        step = reg.steps[sid]
        if sid in hidden and sid not in warned_hidden:
            warned_hidden.add(sid)
            warning(f"A hidden step is used: `{sid}`.")
```

`pipeline_store.check`:

```python
def check(ctx, data, level):
    from . import hidden
    reg = Registry.load(ctx)
    return [p.to_dict() for p in pipeline_check.check(reg, data, ctx.columns(), level, hidden.ids(ctx))]
```

`commands.py` `pipeline_check_cmd`: import `hidden` and pass it:

```python
    from . import hidden, pipeline_check, repo
```

```python
    problems = pipeline_check.check(reg, pipeline.data, ctx.columns(), pipeline.level, hidden.ids(ctx))
```

`api.py`: replace the two GET step routes and add the hide routes:

```python
@route("GET", "/api/steps")
def steps(server, query, body):
    from . import hidden, pipeline_store
    hidden_ids = set(hidden.ids(server.ctx))
    return [pipeline_store.step_summary(s, hidden_ids) for s in sorted(registry(server).steps.values(), key=lambda s: s.id)]


@route("GET", "/api/steps/([a-z][a-z0-9_-]*)")
def step(server, sid, query, body):
    from . import hidden, pipeline_store
    reg = registry(server)
    return pipeline_store.step_detail(reg, reg.step(sid), set(hidden.ids(server.ctx)))


@route("POST", "/api/steps/([a-z][a-z0-9_-]*)/hide")
def step_hide(server, sid, query, body):
    from . import hidden
    return {"message": hidden.hide(server.ctx, sid)}


@route("POST", "/api/steps/([a-z][a-z0-9_-]*)/unhide")
def step_unhide(server, sid, query, body):
    from . import hidden
    return {"message": hidden.unhide(server.ctx, sid)}
```

`launch.py` keeps calling `pipeline_check.check` without `hidden`: a hidden step never blocks a launch.

- [ ] **Step 4: Run the tests**

Run: `uv run --with pytest --with pyyaml pytest -q tests/test_step_hide.py tests/test_pipeline_check.py tests/test_editor_api.py tests/test_launch.py`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add software-factory/lib/factory/pipeline_check.py software-factory/lib/factory/pipeline_store.py software-factory/lib/factory/commands.py software-factory/lib/factory/api.py software-factory/tests/test_step_hide.py
git commit -m "step hide: check warning, api routes and hidden field"
```

## Task 8: Editor hide UI, step assistant, SKILL.md, README, milestone 2 close

**Files:**
- Modify: `software-factory/lib/factory/web/editor.html`
- Modify: `software-factory/builtin/steps/new-step.md`
- Modify: `software-factory/skills/software-factory/SKILL.md`
- Modify: `software-factory/README.md`
- Test: `software-factory/tests/test_step_hide.py` (append)

- [ ] **Step 1: Write the failing tests**

```python
def test_editor_page_has_hide_ui():
    from conftest import SF
    page = (SF / "lib" / "factory" / "web" / "editor.html").read_text()
    for text in ("Show hidden steps", '"Unhide"', '"Hide"', "localStorage", '"/hide"', '"/unhide"', '"hidden"'):
        assert text in page


def test_docs_describe_hide():
    from conftest import SF
    readme = (SF / "README.md").read_text()
    skill = (SF / "skills" / "software-factory" / "SKILL.md").read_text()
    assistant = (SF / "builtin" / "steps" / "new-step.md").read_text()
    for text in ("`factory step hide <id>`", "`factory step unhide <id>`", "`factory step list [--all]`",
                 "Show hidden steps", "`hidden_steps`"):
        assert text in readme
    assert "factory step list --all --json" in skill
    assert "factory step list --all" in assistant
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run --with pytest --with pyyaml pytest -q tests/test_step_hide.py -k "editor or docs"`
Expected: FAIL.

- [ ] **Step 3: Implement the editor**

CSS, add to the style block:

```css
.dim { opacity: 0.5; }
```

Constants and state, after `const CHECK_DELAY_MS = 300;`:

```js
const SHOW_HIDDEN_KEY = "factory-editor-show-hidden";
function readShowHidden() { try { return localStorage.getItem(SHOW_HIDDEN_KEY) === "1"; } catch (e) { return false; } }
function saveShowHidden(value) { try { localStorage.setItem(SHOW_HIDDEN_KEY, value ? "1" : "0"); } catch (e) {} }
```

Add `showHidden: readShowHidden()` to the `state` object.

In `renderFilters`, add the toggle after the "Reload steps" button:

```js
  const toggle = el("input", { type: "checkbox" });
  toggle.checked = state.showHidden;
  toggle.addEventListener("change", () => { state.showHidden = toggle.checked; saveShowHidden(toggle.checked); renderAvailable(); });
  f.append(el("label", {}, toggle, " Show hidden steps"));
```

In `renderAvailable`, at the top of the loop:

```js
    if (s.hidden && !state.showHidden) continue;
```

Build the card with the dim class and the button:

```js
    const card = el("div", { class: "card clickable" + (s.hidden ? " dim" : ""), draggable: "true", onclick: () => showDetail(s.id) },
      el("strong", {}, s.id), " ",
      el("span", { class: "tag" }, s.category || "no category"),
      el("span", { class: "tag" }, s.level),
      el("span", { class: "tag" }, s.run_in),
      el("button", { type: "button", onclick: (e) => { e.stopPropagation(); guard(() => setHidden(s.id, !s.hidden))(); } }, s.hidden ? "Unhide" : "Hide"),
      el("div", { class: "muted" }, s.description));
```

Add after `renderAvailable`:

```js
async function setHidden(id, hide) {
  await api("/api/steps/" + encodeURIComponent(id) + (hide ? "/hide" : "/unhide"), {});
  await loadSteps();
  if (state.model) await runCheck();
}
```

In `loadSteps`, after `renderAvailable();`:

```js
  if (state.model) renderPipeline();
```

In `pipelineRow`, after the id span, add the mark:

```js
  const info = state.steps.find((x) => x.id === s.id);
  const mark = info && info.hidden ? el("span", { class: "tag" }, "hidden") : "";
```

and put `mark` in the `head` children right after the id span.

Check the page syntax with the same `node --check` command as Task 4. Expected: exit 0.

- [ ] **Step 4: Implement the docs**

`new-step.md`, "Before writing", first bullet becomes:

```markdown
- Run `factory step list --all`. Hidden steps count too. If a similar generic or local step exists, show it with `factory step show <id>` and propose to reuse or update it. The id must not be used by any step, hidden or not.
```

(Item 3, the composite choice, keeps `factory step list`, which leaves hidden steps out.)

`SKILL.md`, "Delete a step" item 1 becomes:

```markdown
  1. Run `factory step list --all --json`. List the local and generic steps with their level and category. Mark hidden steps `hidden`. Do not list built-in steps.
```

`README.md`, Commands, replace `- \`factory step list\`: list the steps.` with:

```markdown
- `factory step list [--all]`: list the steps. Hidden steps are left out. `--all` lists them too, marked `hidden`.
- `factory step hide <id>`: hide a step from the pipeline editor and from `factory step list`. Pipelines that use it still run it.
- `factory step unhide <id>`: show a hidden step again.
```

`README.md`, Pipeline editor section, add at the end:

```markdown
- Hide: each available step has a "Hide" button. A hidden step is not in the list. Pipelines that use it still run it. The choice is saved in `.factory/factory.yaml` and is never committed.
  - "Show hidden steps" shows the hidden steps, greyed, each with an "Unhide" button. The browser remembers this choice.
  - A hidden step in the pipeline has a `hidden` mark. The checks warn: "A hidden step is used". It does not block the save.
  - Built-in steps cannot be deleted. Hide them instead.
```

`README.md`, `.factory/factory.yaml` fields line becomes:

```markdown
`version`, `library`, `terminal`, `columns`, `poll_minutes`, `ticket_url`, `hidden_steps` (optional: the ids of hidden steps).
```

- [ ] **Step 5: Run the full suite**

Run: `uv run --with pytest --with pyyaml pytest -q tests`
Expected: all PASS.

- [ ] **Step 6: Commit the milestone**

```bash
git add software-factory/lib/factory/web/editor.html software-factory/builtin/steps/new-step.md software-factory/skills/software-factory/SKILL.md software-factory/README.md software-factory/tests/test_step_hide.py
git commit -m "editor: hide, unhide and show hidden steps; docs: step hide"
```

## Task 9: Verification artifacts

**Files:**
- Create: `software-factory/tests/report_step_delete_hide.py`
- Create: `verification/software-factory/step-delete-hide-manual-check.md`
- Generate: `verification/software-factory/step-delete-hide-junit.xml`, `verification/software-factory/step-delete-hide-report.md`

- [ ] **Step 1: Write the report script**

```python
import sys
from datetime import datetime

from report import VERIF, cases, table

MILESTONES = {"1. Delete a step": ["test_step_delete"], "2. Hide a step": ["test_step_hide"]}
JUNIT = VERIF / "step-delete-hide-junit.xml"
REPORT = VERIF / "step-delete-hide-report.md"


def main():
    rows = cases(JUNIT)
    lines = ["# Step delete and hide verification report", "", f"Date: {datetime.now():%Y-%m-%d %H:%M}", ""]
    for title, modules in MILESTONES.items():
        mine = [r for r in rows if r["module"] in modules]
        passed = sum(r["status"] == "PASS" for r in mine)
        lines += [f"## Milestone {title}", "", f"{passed} of {len(mine)} tests pass.", ""] + table(mine) + [""]
    passed = sum(r["status"] == "PASS" for r in rows)
    failed = [r for r in rows if r["status"] != "PASS"]
    lines += ["## Full test suite", "", f"{passed} of {len(rows)} tests pass.", ""]
    if failed:
        lines += table(failed) + [""]
    REPORT.write_text("\n".join(lines) + "\n")
    return 0 if rows and passed == len(rows) else 1


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Write the manual check list**

`verification/software-factory/step-delete-hide-manual-check.md`:

```markdown
# Step delete and hide: manual browser check

Setup: a test repository with the factory initialized and a test library in its own git repository. Never a real library.
Create a local step `m-local`, a generic step `m-generic` (commit it in the test library), and a pipeline `m-pipe` that uses `m-local`.
Open the editor with `factory pipeline edit`.

## Delete

1. Click `m-generic`. The detail has a "Delete" button.
2. Click "Delete". The panel shows the file, the warning "Other repositories that use this library are not checked." and "Confirm delete".
3. Click "Cancel". Nothing changes.
4. Click "Delete", then "Confirm delete". The step leaves the list. The panel shows "Commit to library" with `Factory library: delete step m-generic`.
5. Click "Commit to library". The test library has a new commit with only the removed file.
6. Click `m-local`, then "Delete". The panel lists `pipeline m-pipe (local)` and has no "Confirm delete".
7. Click `user-validation`. The detail has no "Delete" button.

## Hide

8. Click "Hide" on `m-local`. It leaves the list. The pipeline row of `m-local` in `m-pipe` shows a `hidden` mark. The checks show "Warning: A hidden step is used: `m-local`.". Save still works.
9. Tick "Show hidden steps". `m-local` is back, greyed, with "Unhide".
10. Reload the page. The toggle is still ticked.
11. Click `m-local` in the list. The detail has a "Delete" button.
12. Click "Unhide". The step is no longer greyed. The `hidden` mark and the warning disappear.

## Orchestrator

13. In the orchestrator, choose "Delete a step". The list has the local and generic steps with level and category, and hidden ones marked `hidden`. No built-in step.
14. Choose a step. The orchestrator shows the dry run and waits for your confirmation.
15. Confirm. The step is deleted. For a generic step, the orchestrator offers the library commit.

| Item | Result | Notes |
|---|---|---|
| 1-7 Delete | | |
| 8-12 Hide | | |
| 13-15 Orchestrator | | |
```

- [ ] **Step 3: Generate the report**

```bash
cd software-factory
uv run --with pytest --with pyyaml pytest -q tests --junitxml=../verification/software-factory/step-delete-hide-junit.xml
uv run --with pyyaml python3 tests/report_step_delete_hide.py
```

Expected: the suite passes, the script exits 0, the report has 3 sections.

- [ ] **Step 4: Commit**

```bash
git add software-factory/tests/report_step_delete_hide.py verification/software-factory/step-delete-hide-manual-check.md verification/software-factory/step-delete-hide-junit.xml verification/software-factory/step-delete-hide-report.md
git commit -m "verification: step delete and hide report and manual check list"
```
