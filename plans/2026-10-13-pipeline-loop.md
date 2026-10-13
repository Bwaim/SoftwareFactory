# Pipeline Loops Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A pipeline entry can repeat a range of steps while a task key is set, at most `max` times. The factory makes the jump in `factory done`.

**Architecture:** A new module `lib/factory/loops.py` holds the loop logic: the snapshot at launch, the set test, the count reset, the current loop and the pipeline checks. `engine.py` calls it in `factory done`, `end_wait`, `goto`, the footer and `factory status`. The editor, the dashboard, the authoring skill and the README follow in milestone 2.

**Tech Stack:** Python 3.12, pytest, pyyaml, uv, plain HTML and JavaScript, node (only for one editor test, skipped without node).

**Spec:** `specs/2026-10-13-pipeline-loop-design.md`

## Global Constraints

- All code is under `software-factory/`. Verification files are under `verification/software-factory/`.
- Work on the branch `pipeline-loop`, created from `master`. `master` stays unchanged.
- No new step type. No data version change. A task without `loops` in its snapshot runs as today.
- Messages, exactly:
  - "Loop <n> of <max>: back to `<step>`. Run `factory next`."
  - "Loop limit reached on `<entry>`: `<key>` is still set"
  - "This step controls a loop. Set `<key>` to `none` when nothing is left."
  - `factory status` and the card: "loop <n> of <max>".
- Events: `loop_back` with `entry`, `to`, `round`, `max`. `loop_limit` with `entry`, `key`.
- Tests use the fixtures of `tests/conftest.py`: a test repository, a test library, the fake adapter. Never a real library or a real `.factory/`.
- No code comments. Commit messages have no co-author line.
- Simple English and short sentences in the skill and the README.
- Run tests from `software-factory/`: `uv run --with pytest --with pyyaml pytest -q tests/<file>`. The full suite takes about 4 minutes.
- Every patch in this plan was applied in order to a copy of `master` at `04fd876`, and the tests of each task passed at its own stage.

## Review Focus

1. A loop step that is the last step of a group entry, with `back_to` the group itself. Expected: the jump goes to the first child, and the target is shown as `group > child`. Test: `test_group_loop_back_to_itself` (Task 3).
2. A task launched before this change has no `loops` key. Expected: `factory done` and `factory status` work as today. Test: `test_old_task_without_loops` (Task 3).
3. A key used inside a loop before the step that outputs it, for example `{{findings}}` in `write-spec`. Expected: no "no earlier source" warning inside the range, still a warning outside it. Test: `test_key_set_later_in_the_loop_is_available_inside_the_range` (Task 2).
4. The editor loads a pipeline whose `loop` is wrong (an unknown field, or not a map). Expected: saving without touching the loop keeps it unchanged, so the check still shows the error. Test: `test_editor_model_keeps_loop_on_load_and_save` (Task 6).
5. A `wait_external` step at the end of a loop entry. Expected: the loop decision runs when the wait ends, and the session gets the loop message. Test: `test_wait_step_loop_jumps_on_external_done` (Task 3).

---

## Milestone 1: Loop runtime

### Task 0: Branch (controller)

- [ ] **Step 1: Create the branch and commit the spec and the plan**

```bash
cd /Users/fabienboismoreau/Documents/Projects/SoftwareFactory/SoftwareFactory
git switch -c pipeline-loop master
git add specs/2026-10-13-pipeline-loop-design.md plans/2026-10-13-pipeline-loop.md
git commit -m "pipeline loop: spec and plan"
```

### Task 1: Loop snapshot

**Files:**
- Create: `software-factory/lib/factory/loops.py` (first part: `is_set`, `back_index`, `run_entries`, `snapshot`, `task_loops`, `loop_ending_at`, `reset_counts`, `holds`, `current_loop`, `controlled_keys`)
- Modify: `software-factory/lib/factory/launch.py` (`new_task` saves `loops`)
- Modify: `software-factory/tests/conftest.py` (`task_from_pipeline` saves `loops`)
- Test: `software-factory/tests/test_loops.py` (create)

**Interfaces:**
- Produces, in `factory.loops`:
  - `is_set(value) -> bool`
  - `snapshot(reg, pipeline) -> list[dict]`, each `{"entry", "back_to", "first", "last", "while", "max", "jumps": 0}`
  - `loop_ending_at(task, position) -> dict | None`
  - `reset_counts(task, target, jumping=None) -> None`
  - `current_loop(task) -> {"n", "max", "entry"} | None`
  - `controlled_keys(task, step) -> list[str]`
- `task["loops"]` is the list from `snapshot`. Old tasks have no key: always read it with `loops.task_loops(task)`.

- [ ] **Step 1: Write the failing tests**

Create `software-factory/tests/test_loops.py` with exactly this content:

````python
import json

import pytest

from conftest import events, fake_calls, task_from_pipeline, task_json, write_pipeline, write_step
from factory import loops, repo
from factory.registry import Registry

LIMIT = "Loop limit reached on `review`: `findings` is still set"


def runner(inited, tid="t1"):
    return lambda *a, check=True: inited.factory(*a, "--task", tid, check=check)


def loop(back_to, key, limit):
    return {"back_to": back_to, "while": key, "max": limit}


def review_pipeline(inited, limit=2, after=True):
    write_step(inited.fdir, "write", {})
    write_step(inited.fdir, "review", {"outputs": {"findings": {"type": "long-text", "description": "Findings"}}})
    write_step(inited.fdir, "after", {})
    steps = ["write", {"id": "review", "loop": loop("write", "findings", limit)}]
    if after:
        steps.append("after")
    write_pipeline(inited.fdir, {"id": "rl", "steps": steps})
    task_from_pipeline(inited, "rl")
    return runner(inited)


def review_round(run, value):
    run("next")
    run("done")
    run("next")
    run("state", "set", "findings", value)
    return run("done", check=False)


def current_id(inited, tid="t1"):
    t = task_json(inited.fdir, tid)
    return t["steps"][t["position"]]["id"] if t["position"] < len(t["steps"]) else None


def of_type(inited, kind, tid="t1"):
    return [e for e in events(inited.fdir, tid) if e["type"] == kind]


def test_is_set():
    for value in (None, "", "  ", "none", "None", " None ", "NONE"):
        assert loops.is_set(value) is False
    for value in ("x", "nonesuch", "0", 0):
        assert loops.is_set(value) is True


def test_snapshot_positions(inited):
    write_step(inited.fdir, "a", {})
    write_step(inited.fdir, "b", {})
    write_step(inited.fdir, "g", {"type": "group", "steps": ["a", "b"]}, body="")
    write_pipeline(inited.fdir, {"id": "s1", "steps": ["a", {"id": "g", "loop": loop("a", "k", 3)}, "b"]})
    write_pipeline(inited.fdir, {"id": "s2", "steps": [{"id": "create-worktree", "with": {"base_ref": "main"}}, "a",
                                                         {"id": "g", "loop": loop("g", "k", 3)}]})
    reg = Registry.load(repo.load_ctx(cwd=inited.repo))
    assert loops.snapshot(reg, reg.pipeline("s1")) == [
        {"entry": "g", "back_to": "a", "first": 1, "last": 3, "while": "k", "max": 3, "jumps": 0}]
    assert loops.snapshot(reg, reg.pipeline("s2")) == [
        {"entry": "g", "back_to": "g", "first": 2, "last": 3, "while": "k", "max": 3, "jumps": 0}]
````

- [ ] **Step 2: Run the tests to see them fail**

Run: `cd software-factory && uv run --with pytest --with pyyaml pytest -q tests/test_loops.py`
Expected: collection error `ImportError: cannot import name 'loops' from 'factory'`.

- [ ] **Step 3: Apply the implementation patch**

Save the block below (between the `<!-- patch: task-1 -->` marker and its closing four-backtick line) to a file, for example with this script, then apply it from the repository root:

```bash
cd /Users/fabienboismoreau/Documents/Projects/SoftwareFactory/SoftwareFactory
python3 - <<'PY'
import re, pathlib
brief = pathlib.Path("<path of your task brief>").read_text()
body = re.search(r"<!-- patch: task-1 -->\n````diff\n(.*?)^````$", brief, re.S | re.M).group(1)
pathlib.Path("/tmp/task-1.diff").write_text(body)
PY
git apply --check /tmp/task-1.diff && git apply /tmp/task-1.diff
```

<!-- patch: task-1 -->
````diff
diff --git a/software-factory/lib/factory/launch.py b/software-factory/lib/factory/launch.py
index cc69ea3..ffeb38a 100644
--- a/software-factory/lib/factory/launch.py
+++ b/software-factory/lib/factory/launch.py
@@ -4,7 +4,7 @@ import sys
 import unicodedata
 from pathlib import Path
 
-from . import adapters, config, events, keys, pipeline_check, repo, session, state
+from . import adapters, config, events, keys, loops, pipeline_check, repo, session, state
 from .errors import FactoryError
 from .registry import CREATE_WORKTREE, Registry
 
@@ -220,7 +220,7 @@ def new_task(ctx, reg, report, inputs):
         "column": pipeline.start_column or columns[0],
         "worktree": report["worktree"], "base_ref": report["base_ref"],
         "session_id": session.new_session_id(), "terminal_handle": None,
-        "goto_counts": {}, "approval": None, "claude": pipeline.claude,
+        "goto_counts": {}, "loops": loops.snapshot(reg, pipeline), "approval": None, "claude": pipeline.claude,
         "state": task_state, "created_at": now, "updated_at": now,
     }
 
diff --git a/software-factory/lib/factory/loops.py b/software-factory/lib/factory/loops.py
new file mode 100644
index 0000000..cd820e9
--- /dev/null
+++ b/software-factory/lib/factory/loops.py
@@ -0,0 +1,83 @@
+from . import keys
+from .registry import CREATE_WORKTREE, normalize_entry
+
+LOOP_FIELDS = ("back_to", "while", "max")
+MAX_JUMPS = 20
+EMPTY_VALUES = ("", "none")
+
+
+def is_set(value):
+    return value is not None and str(value).strip().lower() not in EMPTY_VALUES
+
+
+def back_index(entries, i, back_to):
+    for j in range(i, -1, -1):
+        if entries[j].get("id") == back_to:
+            return j
+    return None
+
+
+def run_entries(data):
+    entries = [normalize_entry(e) for e in data.get("steps") or []]
+    if not entries or entries[0].get("id") != CREATE_WORKTREE:
+        entries = [{"id": CREATE_WORKTREE}] + entries
+    return entries
+
+
+def snapshot(reg, pipeline):
+    entries = run_entries(pipeline.data)
+    starts, ends, position = [], [], 0
+    for entry in entries:
+        starts.append(position)
+        position += len(reg.leaves(entry["id"]))
+        ends.append(position - 1)
+    out = []
+    for i, entry in enumerate(entries):
+        loop = entry.get("loop")
+        if not isinstance(loop, dict):
+            continue
+        j = back_index(entries, i, loop.get("back_to"))
+        if j is None:
+            continue
+        out.append({"entry": entry["id"], "back_to": loop["back_to"], "first": starts[j], "last": ends[i],
+                    "while": loop.get("while"), "max": loop.get("max"), "jumps": 0})
+    return out
+
+
+def task_loops(task):
+    return task.get("loops") or []
+
+
+def loop_ending_at(task, position):
+    return next((loop for loop in task_loops(task) if loop["last"] == position), None)
+
+
+def reset_counts(task, target, jumping=None):
+    for loop in task_loops(task):
+        if loop is jumping:
+            continue
+        inside = jumping is not None and loop["first"] >= jumping["first"] and loop["last"] <= jumping["last"]
+        if loop["first"] > target or inside:
+            loop["jumps"] = 0
+
+
+def holds(loop, position):
+    return loop["first"] <= position <= loop["last"]
+
+
+def current_loop(task):
+    position = task["position"]
+    active = [loop for loop in task_loops(task) if holds(loop, position) and loop["jumps"] >= 1]
+    if not active:
+        return None
+    loop = min(active, key=lambda l: l["last"] - l["first"])
+    return {"n": loop["jumps"], "max": loop["max"], "entry": loop["entry"]}
+
+
+def controlled_keys(task, step):
+    outputs = keys.outputs_of(step)
+    found = []
+    for loop in task_loops(task):
+        if holds(loop, task["position"]) and loop["while"] in outputs and loop["while"] not in found:
+            found.append(loop["while"])
+    return found
diff --git a/software-factory/tests/conftest.py b/software-factory/tests/conftest.py
index 541bfc0..db93589 100644
--- a/software-factory/tests/conftest.py
+++ b/software-factory/tests/conftest.py
@@ -185,6 +185,9 @@ def task_from_pipeline(inited, pid, tid="t1", worktree=None, **fields):
     from factory.registry import Registry
     ctx = repo.load_ctx(cwd=inited.repo)
     reg = Registry.load(ctx)
-    snapshot = reg.expand(reg.pipeline(pid))
+    from factory import loops
+    pipeline = reg.pipeline(pid)
+    snapshot = reg.expand(pipeline)
     position = 1 if snapshot and snapshot[0]["id"] == "create-worktree" else 0
+    fields.setdefault("loops", loops.snapshot(reg, pipeline))
     return make_task(ctx, tid=tid, worktree=worktree, steps=snapshot, position=position, pipeline=pid, **fields)
````

- [ ] **Step 4: Run the tests to see them pass**

Run: `cd software-factory && uv run --with pytest --with pyyaml pytest -q tests/test_loops.py tests/test_launch.py`
Expected: all pass (2 tests in `test_loops.py`).

- [ ] **Step 5: Commit**

```bash
cd /Users/fabienboismoreau/Documents/Projects/SoftwareFactory/SoftwareFactory
git add software-factory/lib/factory/loops.py software-factory/lib/factory/launch.py software-factory/tests/conftest.py software-factory/tests/test_loops.py
git commit -m "pipeline loop: loop snapshot"
```

### Task 2: Pipeline check for loops

**Files:**
- Modify: `software-factory/lib/factory/loops.py` (append `loop_range`, `keys_in_ranges`, `range_outputs`, `check_one`, `overlaps`, `check`)
- Modify: `software-factory/lib/factory/pipeline_check.py` (calls `loops.check`, and counts loop keys as available inside the range)
- Test: `software-factory/tests/test_loops.py` (append)

**Interfaces:**
- Consumes: `loops.back_index`, `loops.run_entries` from Task 1.
- Produces: `loops.check(reg, data) -> list[tuple[level, message]]` and `loops.keys_in_ranges(reg, entries) -> dict[int, set[str]]`.

- [ ] **Step 1: Write the failing tests**

Append this block to the end of `software-factory/tests/test_loops.py`:

````python


def check_messages(inited, pid, steps):
    write_pipeline(inited.fdir, {"id": pid, "steps": steps})
    r = inited.factory("pipeline", "check", pid, "--json", check=False)
    return [(p["level"], p["message"]) for p in json.loads(r.stdout)]


def test_check_errors_and_warnings(inited):
    out_k = {"outputs": {"k": {"type": "text", "description": "K"}}}
    write_step(inited.fdir, "a", {})
    write_step(inited.fdir, "b", out_k)
    write_step(inited.fdir, "opt", {"outputs": {"k": {"type": "text", "description": "K", "optional": True}}})
    cases = {
        "not-map": (["a", {"id": "b", "loop": "a"}, "a"], ("error", "Step `b`: `loop` must be a map with `back_to`, `while` and `max`.")),
        "unknown": (["a", {"id": "b", "loop": {**loop("a", "k", 2), "until": 1}}, "a"], ("error", "Step `b`: `loop` has an unknown field `until`.")),
        "later": (["a", {"id": "b", "loop": loop("c", "k", 2)}, "a"], ("error", "Step `b`: `loop.back_to` must be this step or an earlier step of the pipeline.")),
        "worktree": (["create-worktree", "a", {"id": "b", "loop": loop("create-worktree", "k", 2)}, "a"],
                     ("error", "Step `b`: `loop.back_to` cannot be `create-worktree`. It cannot run again.")),
        "max-zero": (["a", {"id": "b", "loop": loop("a", "k", 0)}, "a"], ("error", "Step `b`: `loop.max` must be an integer from 1 to 20.")),
        "max-big": (["a", {"id": "b", "loop": loop("a", "k", 21)}, "a"], ("error", "Step `b`: `loop.max` must be an integer from 1 to 20.")),
        "max-text": (["a", {"id": "b", "loop": loop("a", "k", "2")}, "a"], ("error", "Step `b`: `loop.max` must be an integer from 1 to 20.")),
        "max-bool": (["a", {"id": "b", "loop": loop("a", "k", True)}, "a"], ("error", "Step `b`: `loop.max` must be an integer from 1 to 20.")),
        "bad-key": (["a", {"id": "b", "loop": loop("a", "Bad-Key", 2)}, "a"],
                    ("error", "Step `b`: `loop.while` must be a key name: lowercase letters, digits and `_`, starting with a letter.")),
        "no-output": (["a", {"id": "a", "loop": loop("a", "k", 2)}, "b"], ("warning", "Step `a`: no step inside the loop outputs `k`. The loop never ends early.")),
        "optional": (["a", {"id": "opt", "loop": loop("a", "k", 2)}, "a"], ("warning", "Step `opt`: `k` is optional in every step that outputs it inside the loop.")),
        "last": (["a", {"id": "b", "loop": loop("a", "k", 2)}],
                 ("warning", "Step `b`: the loop is on the last step. At the limit, the task finishes without asking the user. Add a step after it, for example `user-validation`.")),
    }
    for pid, (steps, expected) in cases.items():
        assert expected in check_messages(inited, pid, steps), pid


def test_overlap_names_both_loops_and_nested_is_fine(inited):
    out_k = {"outputs": {"k": {"type": "text", "description": "K"}}}
    for sid in ("a", "b", "c", "d"):
        write_step(inited.fdir, sid, out_k)
    overlap = check_messages(inited, "ov", ["a", "b", {"id": "c", "loop": loop("a", "k", 2)}, {"id": "d", "loop": loop("b", "k", 2)}, "a"])
    assert ("error", "The loops of `c` and `d` overlap. One loop must be inside the other.") in overlap
    nested = check_messages(inited, "ok", ["a", {"id": "b", "loop": loop("b", "k", 2)}, {"id": "c", "loop": loop("a", "k", 2)}, "d"])
    assert nested == []


def test_back_to_uses_the_nearest_earlier_entry(inited):
    for sid in ("a", "b"):
        write_step(inited.fdir, sid, {"outputs": {"k": {"type": "text", "description": "K"}}})
    write_pipeline(inited.fdir, {"id": "near", "steps": ["a", "b", "a", {"id": "b", "loop": loop("a", "k", 2)}, "b"]})
    reg = Registry.load(repo.load_ctx(cwd=inited.repo))
    assert [(l["first"], l["last"]) for l in loops.snapshot(reg, reg.pipeline("near"))] == [(3, 4)]
    assert check_messages(inited, "near", ["a", "b", "a", {"id": "b", "loop": loop("a", "k", 2)}, "b"]) == []


def test_key_set_later_in_the_loop_is_available_inside_the_range(inited):
    write_step(inited.fdir, "write", {}, body="Fix {{findings}}.\n")
    write_step(inited.fdir, "review", {"outputs": {"findings": {"type": "long-text", "description": "Findings"}}})
    write_step(inited.fdir, "after", {}, body="Read {{findings}}.\n")
    write_step(inited.fdir, "before", {}, body="Read {{findings}}.\n")
    messages = check_messages(inited, "lk", ["before", "write", {"id": "review", "loop": loop("write", "findings", 2)}, "after"])
    assert messages == [("warning", "Step `before` uses `findings`, which no input, earlier step or factory key sets.")]
````

- [ ] **Step 2: Run the tests to see them fail**

Run: `cd software-factory && uv run --with pytest --with pyyaml pytest -q tests/test_loops.py`
Expected: the 4 new tests fail (the check reports no loop problem). The 2 tests of Task 1 pass.

- [ ] **Step 3: Apply the implementation patch**

Save the block below (between the `<!-- patch: task-2 -->` marker and its closing four-backtick line) to a file, for example with this script, then apply it from the repository root:

```bash
cd /Users/fabienboismoreau/Documents/Projects/SoftwareFactory/SoftwareFactory
python3 - <<'PY'
import re, pathlib
brief = pathlib.Path("<path of your task brief>").read_text()
body = re.search(r"<!-- patch: task-2 -->\n````diff\n(.*?)^````$", brief, re.S | re.M).group(1)
pathlib.Path("/tmp/task-2.diff").write_text(body)
PY
git apply --check /tmp/task-2.diff && git apply /tmp/task-2.diff
```

<!-- patch: task-2 -->
````diff
diff --git a/software-factory/lib/factory/loops.py b/software-factory/lib/factory/loops.py
index cd820e9..8a8a71b 100644
--- a/software-factory/lib/factory/loops.py
+++ b/software-factory/lib/factory/loops.py
@@ -81,3 +81,91 @@ def controlled_keys(task, step):
         if holds(loop, task["position"]) and loop["while"] in outputs and loop["while"] not in found:
             found.append(loop["while"])
     return found
+
+
+def loop_range(entries, i):
+    loop = entries[i].get("loop")
+    if not isinstance(loop, dict) or not isinstance(loop.get("back_to"), str) or loop["back_to"] == CREATE_WORKTREE:
+        return None
+    j = back_index(entries, i, loop["back_to"])
+    return None if j is None else (j, i)
+
+
+def keys_in_ranges(reg, entries):
+    found = {i: set() for i in range(len(entries))}
+    for i in range(len(entries)):
+        span = loop_range(entries, i)
+        if span is None:
+            continue
+        names = {name for entry in entries[span[0]:i + 1] for leaf in keys.entry_leaves(reg, entry) for name in keys.outputs_of(leaf)}
+        for k in range(span[0], i + 1):
+            found[k] |= names
+    return found
+
+
+def range_outputs(reg, entries, j, i, key):
+    found = []
+    for entry in entries[j:i + 1]:
+        for leaf in keys.entry_leaves(reg, entry):
+            out = keys.outputs_of(leaf).get(key)
+            if out:
+                found.append(out)
+    return found
+
+
+def check_one(reg, entries, i, problems, ranges):
+    entry = entries[i]
+    sid = entry.get("id")
+    error = lambda m: problems.append(("error", m))
+    warning = lambda m: problems.append(("warning", m))
+    loop = entry["loop"]
+    if not isinstance(loop, dict):
+        error(f"Step `{sid}`: `loop` must be a map with `back_to`, `while` and `max`.")
+        return
+    for name in loop:
+        if name not in LOOP_FIELDS:
+            error(f"Step `{sid}`: `loop` has an unknown field `{name}`.")
+    back_to = loop.get("back_to")
+    j = back_index(entries, i, back_to) if isinstance(back_to, str) else None
+    if back_to == CREATE_WORKTREE:
+        error(f"Step `{sid}`: `loop.back_to` cannot be `create-worktree`. It cannot run again.")
+        j = None
+    elif j is None:
+        error(f"Step `{sid}`: `loop.back_to` must be this step or an earlier step of the pipeline.")
+    limit = loop.get("max")
+    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= MAX_JUMPS:
+        error(f"Step `{sid}`: `loop.max` must be an integer from 1 to {MAX_JUMPS}.")
+    key = loop.get("while")
+    if not keys.is_key(key):
+        error(f"Step `{sid}`: `loop.while` must be a key name: lowercase letters, digits and `_`, starting with a letter.")
+    if j is not None:
+        ranges.append((j, i, sid))
+        if keys.is_key(key):
+            outputs = range_outputs(reg, entries, j, i, key)
+            if not outputs:
+                warning(f"Step `{sid}`: no step inside the loop outputs `{key}`. The loop never ends early.")
+            elif all(out["optional"] for out in outputs):
+                warning(f"Step `{sid}`: `{key}` is optional in every step that outputs it inside the loop.")
+    if i == len(entries) - 1:
+        warning(f"Step `{sid}`: the loop is on the last step. At the limit, the task finishes without asking the user. "
+                "Add a step after it, for example `user-validation`.")
+
+
+def overlaps(a, b):
+    (s1, e1, _), (s2, e2, _) = a, b
+    share = s1 <= e2 and s2 <= e1
+    nested = (s1 <= s2 and e2 <= e1) or (s2 <= s1 and e1 <= e2)
+    return share and not nested
+
+
+def check(reg, data):
+    entries = [normalize_entry(e) for e in data.get("steps") or []]
+    problems, ranges = [], []
+    for i, entry in enumerate(entries):
+        if "loop" in entry:
+            check_one(reg, entries, i, problems, ranges)
+    for a in range(len(ranges)):
+        for b in range(a + 1, len(ranges)):
+            if overlaps(ranges[a], ranges[b]):
+                problems.append(("error", f"The loops of `{ranges[a][2]}` and `{ranges[b][2]}` overlap. One loop must be inside the other."))
+    return problems
diff --git a/software-factory/lib/factory/pipeline_check.py b/software-factory/lib/factory/pipeline_check.py
index 3c32776..0ea0eb8 100644
--- a/software-factory/lib/factory/pipeline_check.py
+++ b/software-factory/lib/factory/pipeline_check.py
@@ -1,6 +1,6 @@
 from dataclasses import dataclass
 
-from . import keys
+from . import keys, loops
 from .errors import FactoryError
 from .registry import CREATE_WORKTREE, is_valid_id, normalize_entry
 
@@ -41,6 +41,7 @@ def check(reg, data, columns, save_level=None, hidden=()):
     rows = keys.start_rows(data)
     first_type = {name: (r["type"], r["source"]) for name, r in rows.items() if r["source"] == "input"}
     warned_types = set()
+    loop_keys = loops.keys_in_ranges(reg, entries)
     for i, entry in enumerate(entries):
         sid = entry.get("id")
         if sid == CREATE_WORKTREE and i != 0:
@@ -72,7 +73,7 @@ def check(reg, data, columns, save_level=None, hidden=()):
                 warning(f"Step `{leaf.id}` runs in the session. Its `model` and `effort` have no effect.")
             own_outputs = set(keys.outputs_of(leaf))
             for key in keys.leaf_uses(leaf):
-                if key not in rows and key not in own_outputs:
+                if key not in rows and key not in own_outputs and key not in loop_keys[i]:
                     warning(f"Step `{leaf.id}` uses `{key}`, which no input, earlier step or factory key sets.")
             for name, out in keys.outputs_of(leaf).items():
                 seen = first_type.setdefault(name, (out["type"], f"step {leaf.id}"))
@@ -80,4 +81,6 @@ def check(reg, data, columns, save_level=None, hidden=()):
                     warned_types.add(name)
                     warning(f"The key `{name}` is set with two types: {seen[0]} ({seen[1]}) and {out['type']} (step {leaf.id}).")
             keys.add_outputs(rows, leaf)
+    for level, message in loops.check(reg, data):
+        problems.append(Problem(level, message))
     return problems
````

- [ ] **Step 4: Run the tests to see them pass**

Run: `cd software-factory && uv run --with pytest --with pyyaml pytest -q tests/test_loops.py tests/test_pipeline_check.py tests/test_pipeline_keys.py`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
cd /Users/fabienboismoreau/Documents/Projects/SoftwareFactory/SoftwareFactory
git add software-factory/lib/factory/loops.py software-factory/lib/factory/pipeline_check.py software-factory/tests/test_loops.py
git commit -m "pipeline loop: pipeline check"
```

### Task 3: Loop jump in `factory done`

**Files:**
- Modify: `software-factory/lib/factory/engine.py` (`done` calls `settle`; new `settle`, `loop_back`, `loop_limit`; `goto` resets loop counts; `end_wait` uses `settle`)
- Test: `software-factory/tests/test_loops.py` (append)

**Interfaces:**
- Consumes: `loops.loop_ending_at`, `loops.is_set`, `loops.reset_counts` from Task 1.
- Produces: `engine.settle(ctx, tid, position, statuses=ADVANCE_STATUSES, first_event=None) -> tuple[kind, text]`, with `kind` in `"step"`, `"loop"`, `"limit"`.

- [ ] **Step 1: Write the failing tests**

Append this block to the end of `software-factory/tests/test_loops.py`:

````python


def test_review_loop_jumps_twice_then_moves_on(inited):
    run = review_pipeline(inited)
    outs = [review_round(run, v).stdout.strip() for v in ("two bugs", "one bug", "none")]
    assert outs == ["Loop 1 of 2: back to `write`. Run `factory next`.",
                    "Loop 2 of 2: back to `write`. Run `factory next`.",
                    "Step done. Run `factory next`."]
    assert current_id(inited) == "after" and task_json(inited.fdir, "t1")["status"] == "active"
    backs = of_type(inited, "loop_back")
    assert [(e["entry"], e["to"], e["round"], e["max"]) for e in backs] == [("review", "write", 1, 2), ("review", "write", 2, 2)]


def test_limit_moves_on_and_blocks(inited):
    run = review_pipeline(inited)
    review_round(run, "a")
    review_round(run, "b")
    out = review_round(run, "c").stdout
    assert LIMIT in out and "The task is blocked." in out and 'factory goto "write"' in out
    t = task_json(inited.fdir, "t1")
    assert current_id(inited) == "after" and t["status"] == "blocked" and t["status_reason"] == LIMIT
    limit = of_type(inited, "loop_limit")
    assert [(e["entry"], e["key"]) for e in limit] == [("review", "findings")]
    assert of_type(inited, "task_blocked")[-1]["reason"] == LIMIT


def test_goto_after_limit_gives_one_more_round(inited):
    run = review_pipeline(inited)
    for value in ("a", "b", "c"):
        review_round(run, value)
    run("goto", "write", "--reason", "one more round")
    assert LIMIT in review_round(run, "d").stdout
    assert task_json(inited.fdir, "t1")["status"] == "blocked"


def test_limit_on_last_entry_finishes(inited):
    run = review_pipeline(inited, limit=1, after=False)
    review_round(run, "a")
    out = review_round(run, "b").stdout
    assert "The pipeline is finished, but the loop limit was reached on `review`: `findings` is still set." in out
    assert task_json(inited.fdir, "t1")["status"] == "finished"
    assert [(e["entry"], e["key"]) for e in of_type(inited, "loop_limit")] == [("review", "findings")]


def test_group_loop_back_to_itself(inited):
    write_step(inited.fdir, "split", {})
    write_step(inited.fdir, "pick", {"outputs": {"remaining": {"type": "long-text", "description": "Left"}}})
    write_step(inited.fdir, "build", {})
    write_step(inited.fdir, "round", {"type": "group", "steps": ["pick", "build"]}, body="")
    write_pipeline(inited.fdir, {"id": "tl", "steps": ["split", {"id": "round", "loop": loop("round", "remaining", 20)}]})
    task_from_pipeline(inited, "tl")
    run = runner(inited)
    run("next")
    run("done")
    outs = []
    for left in ("b\nc", "c", "none"):
        run("next")
        run("state", "set", "remaining", left)
        run("done")
        run("next")
        outs.append(run("done").stdout.strip())
    assert outs == ["Loop 1 of 20: back to `round > pick`. Run `factory next`.",
                    "Loop 2 of 20: back to `round > pick`. Run `factory next`.",
                    "The pipeline is finished. Tell the user that the task is finished."]
    t = task_json(inited.fdir, "t1")
    assert t["goto_counts"] == {} and t["status"] == "finished"


def nested_pipeline(inited):
    write_step(inited.fdir, "a", {})
    write_step(inited.fdir, "b", {"outputs": {"inner": {"type": "text", "description": "Inner"}}})
    write_step(inited.fdir, "c", {"outputs": {"outer": {"type": "text", "description": "Outer"}}})
    write_step(inited.fdir, "end", {})
    write_pipeline(inited.fdir, {"id": "nest", "steps": [
        "a", {"id": "b", "loop": loop("b", "inner", 1)}, {"id": "c", "loop": loop("a", "outer", 2)}, "end"]})
    task_from_pipeline(inited, "nest")
    return runner(inited)


def step_with(run, key=None, value=None):
    run("next")
    if key:
        run("state", "set", key, value)
    return run("done").stdout.strip()


def test_nested_inner_loop_resets_after_outer_jump(inited):
    run = nested_pipeline(inited)
    step_with(run)
    assert step_with(run, "inner", "x") == "Loop 1 of 1: back to `b`. Run `factory next`."
    assert "Loop limit reached on `b`" in step_with(run, "inner", "x")
    run("unblock")
    assert step_with(run, "outer", "y") == "Loop 1 of 2: back to `a`. Run `factory next`."
    step_with(run)
    assert step_with(run, "inner", "x") == "Loop 1 of 1: back to `b`. Run `factory next`."


def test_goto_resets_only_before_the_range(inited):
    run = nested_pipeline(inited)
    step_with(run)
    step_with(run, "inner", "x")
    step_with(run, "inner", "x")
    run("unblock")
    run("goto", "b", "--reason", "again")
    assert "Loop limit reached on `b`" in step_with(run, "inner", "x")
    run("unblock")
    run("goto", "a", "--reason", "from the start")
    step_with(run)
    assert step_with(run, "inner", "x") == "Loop 1 of 1: back to `b`. Run `factory next`."


def test_not_set_values_move_on(inited):
    run = review_pipeline(inited)
    assert review_round(run, " None ").stdout.strip() == "Step done. Run `factory next`."
    write_step(inited.fdir, "solo", {})
    write_step(inited.fdir, "end", {})
    write_pipeline(inited.fdir, {"id": "never", "steps": [{"id": "solo", "loop": loop("solo", "unset_key", 2)}, "end"]})
    task_from_pipeline(inited, "never", tid="t2")
    run2 = runner(inited, "t2")
    run2("next")
    assert run2("done").stdout.strip() == "Step done. Run `factory next`."
    assert of_type(inited, "loop_back") == [] and of_type(inited, "loop_back", "t2") == []


def test_skipped_loop_step_does_not_jump(inited):
    run = review_pipeline(inited)
    run("next")
    run("done")
    run("next")
    run("state", "set", "findings", "bugs")
    run("skip")
    assert current_id(inited) == "after" and of_type(inited, "loop_back") == []


def test_three_loop_rounds_do_not_block_like_goto(inited):
    run = review_pipeline(inited, limit=5)
    for value in ("a", "b", "c"):
        review_round(run, value)
    t = task_json(inited.fdir, "t1")
    assert t["goto_counts"] == {} and t["status"] == "active" and current_id(inited) == "write"


def test_jump_resets_fields_and_keeps_keys(inited):
    write_step(inited.fdir, "chk", {"type": "command", "outputs": {"k": {"type": "text", "description": "K"}}},
               body="factory state set k again\n")
    write_step(inited.fdir, "end", {})
    write_pipeline(inited.fdir, {"id": "cl", "steps": [{"id": "chk", "loop": loop("chk", "k", 2)}, "end"]})
    task_from_pipeline(inited, "cl", state={"keep": "me"})
    run = runner(inited)
    run("next")
    run("run-command")
    path = inited.fdir / "tasks" / "t1" / "task.json"
    data = json.loads(path.read_text())
    data["approval"] = {"position": 1, "approved": True, "target": "worktree", "artifact_key": None}
    path.write_text(json.dumps(data))
    assert run("done").stdout.startswith("Loop 1 of 2")
    t = task_json(inited.fdir, "t1")
    assert t["command_result"] is None and t["approval"] is None and t["started"] is None
    assert t["state"] == {"keep": "me", "k": "again"}


def test_wait_step_loop_jumps_on_external_done(inited):
    write_step(inited.fdir, "w", {"wait_external": True, "done_when": "QA is done.",
                                  "outputs": {"bugs": {"type": "text", "description": "Bugs"}}})
    write_step(inited.fdir, "end", {})
    write_pipeline(inited.fdir, {"id": "wl", "steps": [{"id": "w", "loop": loop("w", "bugs", 2)}, "end"]})
    task_from_pipeline(inited, "wl", terminal_handle={"agent": "t1"})
    run = runner(inited)
    run("next")
    run("state", "set", "bugs", "two")
    run("wait")
    inited.factory("external-done", "t1")
    assert current_id(inited) == "w" and task_json(inited.fdir, "t1")["status"] == "active"
    texts = [c.get("text", "") for c in fake_calls(inited.fdir)]
    assert "The external event happened: QA is done. Loop 1 of 2: back to `w`. Run `factory next`." in texts


def test_old_task_without_loops(inited):
    write_step(inited.fdir, "a", {})
    write_pipeline(inited.fdir, {"id": "old", "steps": ["a"]})
    task_from_pipeline(inited, "old")
    path = inited.fdir / "tasks" / "t1" / "task.json"
    data = json.loads(path.read_text())
    del data["loops"]
    path.write_text(json.dumps(data))
    run = runner(inited)
    run("next")
    assert "The pipeline is finished" in run("done").stdout
    assert ", loop" not in run("status").stdout
````

- [ ] **Step 2: Run the tests to see them fail**

Run: `cd software-factory && uv run --with pytest --with pyyaml pytest -q tests/test_loops.py`
Expected: the loop runtime tests fail (no jump: "Step done. Run `factory next`." where a loop message is expected). `test_skipped_loop_step_does_not_jump`, `test_not_set_values_move_on` and `test_old_task_without_loops` may already pass.

- [ ] **Step 3: Apply the implementation patch**

Save the block below (between the `<!-- patch: task-3 -->` marker and its closing four-backtick line) to a file, for example with this script, then apply it from the repository root:

```bash
cd /Users/fabienboismoreau/Documents/Projects/SoftwareFactory/SoftwareFactory
python3 - <<'PY'
import re, pathlib
brief = pathlib.Path("<path of your task brief>").read_text()
body = re.search(r"<!-- patch: task-3 -->\n````diff\n(.*?)^````$", brief, re.S | re.M).group(1)
pathlib.Path("/tmp/task-3.diff").write_text(body)
PY
git apply --check /tmp/task-3.diff && git apply /tmp/task-3.diff
```

<!-- patch: task-3 -->
````diff
diff --git a/software-factory/lib/factory/engine.py b/software-factory/lib/factory/engine.py
index 208aa71..6dcee33 100644
--- a/software-factory/lib/factory/engine.py
+++ b/software-factory/lib/factory/engine.py
@@ -3,7 +3,7 @@ import shlex
 import subprocess
 from pathlib import Path
 
-from . import config, events, keys, render, repo, session, state
+from . import config, events, keys, loops, render, repo, session, state
 from .errors import FactoryError
 from .registry import CREATE_WORKTREE, Registry
 
@@ -270,7 +270,57 @@ def done(ctx, tid):
         if not ok:
             events.log(ctx, tid, "done_check_failed", state.step_path_str(task), output=output)
             raise FactoryError(f"The done check failed. The step is not done.\nCheck: {step.done_check}\n{output}")
-    return advance(ctx, tid, "step_done", task["position"])
+    return settle(ctx, tid, task["position"])[1]
+
+
+def settle(ctx, tid, position, statuses=ADVANCE_STATUSES, first_event=None):
+    task = state.load(ctx, tid)
+    loop = loops.loop_ending_at(task, position)
+    if loop is None or not loops.is_set((task.get("state") or {}).get(loop["while"])):
+        return "step", advance(ctx, tid, "step_done", position, statuses, first_event)
+    if loop["jumps"] < loop["max"]:
+        return "loop", loop_back(ctx, tid, position, statuses, first_event)
+    return "limit", loop_limit(ctx, tid, position, statuses, first_event)
+
+
+def loop_back(ctx, tid, position, statuses, first_event):
+    info = {}
+
+    def change(t):
+        require_unchanged(t, position, statuses)
+        loop = loops.loop_ending_at(t, position)
+        info["from"] = state.step_path_str(t)
+        if first_event:
+            first_event()
+        events.log(ctx, tid, "step_done", info["from"])
+        loop["jumps"] += 1
+        loops.reset_counts(t, loop["first"], loop)
+        t["position"] = loop["first"]
+        t["started"] = None
+        t["command_result"] = None
+        t["approval"] = None
+        state.set_status(t, "active")
+        info.update(entry=loop["entry"], n=loop["jumps"], max=loop["max"], to=state.step_path_str(t))
+
+    task = state.update(ctx, tid, change)
+    events.log(ctx, tid, "loop_back", info["from"], entry=info["entry"], to=info["to"], round=info["n"], max=info["max"])
+    return f"Loop {info['n']} of {info['max']}: back to `{info['to']}`. Run `{cmd(task, 'next')}`."
+
+
+def loop_limit(ctx, tid, position, statuses, first_event):
+    task = state.load(ctx, tid)
+    loop = loops.loop_ending_at(task, position)
+    path = state.step_path_str(task)
+    target = state.step_path_str(task, loop["first"])
+    reason = f"Loop limit reached on `{loop['entry']}`: `{loop['while']}` is still set"
+    advance(ctx, tid, "step_done", position, statuses, first_event)
+    events.log(ctx, tid, "loop_limit", path, entry=loop["entry"], key=loop["while"])
+    if state.load(ctx, tid)["status"] == "finished":
+        session.notify(ctx, f"Task {tid} finished, but the loop limit was reached on `{loop['entry']}`: `{loop['while']}` is still set.")
+        return f"The pipeline is finished, but the loop limit was reached on `{loop['entry']}`: `{loop['while']}` is still set. Tell the user."
+    block(ctx, tid, reason)
+    return (f"{reason}. The task is blocked. Ask the user what to do. To go on, the user runs `factory unblock`. "
+            f"For one more round, after the user approves, run `factory goto \"{target}\" --reason \"<why>\"`.")
 
 
 def skip(ctx, tid):
@@ -313,6 +363,7 @@ def goto(ctx, tid, target, reason):
         t["started"] = None
         t["command_result"] = None
         t["approval"] = None
+        loops.reset_counts(t, index)
         if t["goto_counts"][key] >= MAX_JUMPS:
             state.set_status(t, "blocked", f"loop on {to_path}")
         else:
@@ -345,14 +396,15 @@ def end_wait(ctx, tid, how):
         raise FactoryError(f"Task {tid} is not waiting for an external event.")
     entry, step = load_step(ctx, task)
     path = state.step_path_str(task)
-    advance(ctx, tid, "step_done", task["position"], ("waiting_external",),
-            lambda: events.log(ctx, tid, "external_event", path, how=how))
+    kind, text = settle(ctx, tid, task["position"], ("waiting_external",),
+                        lambda: events.log(ctx, tid, "external_event", path, how=how))
     task = state.load(ctx, tid)
     happened = (step.done_when or "An external event.").removesuffix(".")
     session.notify(ctx, f"Task {tid}: {step.done_when or 'the external event happened'}")
     if task["status"] == "finished":
         return
-    session.deliver(ctx, tid, f"The external event happened: {happened}. Run `{cmd(task, 'next')}`.")
+    then = f"Run `{cmd(task, 'next')}`." if kind == "step" else text
+    session.deliver(ctx, tid, f"The external event happened: {happened}. {then}")
 
 
 def poll_task(ctx, task):
````

- [ ] **Step 4: Run the tests to see them pass**

Run: `cd software-factory && uv run --with pytest --with pyyaml pytest -q tests/test_loops.py tests/test_engine.py tests/test_goto.py tests/test_waiting.py tests/test_approval.py tests/test_runtime_v2.py`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
cd /Users/fabienboismoreau/Documents/Projects/SoftwareFactory/SoftwareFactory
git add software-factory/lib/factory/engine.py software-factory/tests/test_loops.py
git commit -m "pipeline loop: loop jump in factory done"
```

### Task 4: Footer line and `factory status`

**Files:**
- Modify: `software-factory/lib/factory/render.py` (`loop_lines`; `footer`, `prompt_with_footer`, `subagent_text`, `command_text`, `step_text` take the loop lines)
- Modify: `software-factory/lib/factory/engine.py` (`render_step` passes `loops.controlled_keys`; `loop_suffix`; `status_text`)
- Test: `software-factory/tests/test_loops.py` (append)

**Interfaces:**
- Consumes: `loops.controlled_keys`, `loops.current_loop` from Task 1.
- Produces: `render.step_text(step, prompt, step_line, outputs, model=None, effort=None, loop_keys=())`.

- [ ] **Step 1: Write the failing tests**

Append this block to the end of `software-factory/tests/test_loops.py`:

````python


FOOTER = "This step controls a loop. Set `k` to `none` when nothing is left."


def test_footer_line_only_on_the_controlling_step(inited):
    out_k = {"outputs": {"k": {"type": "text", "description": "K"}}}
    write_step(inited.fdir, "pre", out_k)
    write_step(inited.fdir, "a", {})
    write_step(inited.fdir, "b", out_k)
    write_step(inited.fdir, "post", out_k)
    write_pipeline(inited.fdir, {"id": "ft", "steps": ["pre", "a", {"id": "b", "loop": loop("a", "k", 2)}, "post"]})
    task_from_pipeline(inited, "ft")
    run = runner(inited)
    seen = {}
    for sid in ("pre", "a", "b", "post"):
        out = run("next").stdout
        seen[sid] = FOOTER in out
        if sid != "a":
            run("state", "set", "k", "none")
        run("done")
    assert seen == {"pre": False, "a": False, "b": True, "post": False}


def test_footer_line_for_subagent_and_command(inited):
    write_step(inited.fdir, "sub", {"run_in": "subagent", "outputs": {"k": {"type": "text", "description": "K"}}})
    write_step(inited.fdir, "cmd", {"type": "command", "outputs": {"k": {"type": "text", "description": "K"}}},
               body="factory state set k none\n")
    write_step(inited.fdir, "end", {})
    write_pipeline(inited.fdir, {"id": "sc", "steps": [{"id": "sub", "loop": loop("sub", "k", 2)},
                                                        {"id": "cmd", "loop": loop("cmd", "k", 2)}, "end"]})
    task_from_pipeline(inited, "sc")
    run = runner(inited)
    sub = run("next").stdout
    assert FOOTER in sub.split("<<<", 1)[1].split(">>>", 1)[0]
    run("state", "set", "k", "none")
    run("done")
    cmd = run("next").stdout
    assert "This step controls a loop. The command sets `k` to `none` when nothing is left." in cmd
    assert "factory state set" not in cmd


def test_status_shows_loop_count(inited):
    run = review_pipeline(inited)
    assert ", loop" not in run("status").stdout
    review_round(run, "bugs")
    assert "Step: write (2 of 4), loop 1 of 2" in run("status").stdout


def test_status_shows_the_innermost_loop(inited):
    run = nested_pipeline(inited)
    step_with(run)
    step_with(run, "inner", "x")
    step_with(run, "inner", "x")
    run("unblock")
    step_with(run, "outer", "y")
    assert "Step: a (2 of 5), loop 1 of 2" in run("status").stdout
    step_with(run)
    step_with(run, "inner", "x")
    assert "Step: b (3 of 5), loop 1 of 1" in run("status").stdout
````

- [ ] **Step 2: Run the tests to see them fail**

Run: `cd software-factory && uv run --with pytest --with pyyaml pytest -q tests/test_loops.py`
Expected: the 4 new tests fail (no footer line, no "loop <n> of <max>" in the status).

- [ ] **Step 3: Apply the implementation patch**

Save the block below (between the `<!-- patch: task-4 -->` marker and its closing four-backtick line) to a file, for example with this script, then apply it from the repository root:

```bash
cd /Users/fabienboismoreau/Documents/Projects/SoftwareFactory/SoftwareFactory
python3 - <<'PY'
import re, pathlib
brief = pathlib.Path("<path of your task brief>").read_text()
body = re.search(r"<!-- patch: task-4 -->\n````diff\n(.*?)^````$", brief, re.S | re.M).group(1)
pathlib.Path("/tmp/task-4.diff").write_text(body)
PY
git apply --check /tmp/task-4.diff && git apply /tmp/task-4.diff
```

<!-- patch: task-4 -->
````diff
diff --git a/software-factory/lib/factory/engine.py b/software-factory/lib/factory/engine.py
index 6dcee33..c3bcefb 100644
--- a/software-factory/lib/factory/engine.py
+++ b/software-factory/lib/factory/engine.py
@@ -95,7 +95,7 @@ def step_line(task):
 def render_step(task, entry, step, values):
     prompt = render.fill(step.body, key_values(task), values) if step.type == "ai" else ""
     model, effort = settings(entry, step)
-    return render.step_text(step, prompt, step_line(task), keys.outputs_of(step), model, effort)
+    return render.step_text(step, prompt, step_line(task), keys.outputs_of(step), model, effort, loops.controlled_keys(task, step))
 
 
 def render_missing(task, step, missing):
@@ -515,13 +515,18 @@ def set_state(ctx, tid, key, value):
     return value
 
 
+def loop_suffix(task):
+    loop = loops.current_loop(task)
+    return f", loop {loop['n']} of {loop['max']}" if loop else ""
+
+
 def status_text(ctx, tid):
     task = state.load(ctx, tid)
     lines = [
         f"Task: {task['id']}",
         f"Description: {task['description']}",
         f"Pipeline: {task['pipeline']}",
-        f"Step: {state.step_path_str(task)} ({min(task['position'] + 1, len(task['steps']))} of {len(task['steps'])})",
+        f"Step: {state.step_path_str(task)} ({min(task['position'] + 1, len(task['steps']))} of {len(task['steps'])})" + loop_suffix(task),
         f"Status: {task['status']}" + (f" ({task['status_reason']})" if task.get("status_reason") else ""),
     ]
     return "\n".join(lines)
diff --git a/software-factory/lib/factory/render.py b/software-factory/lib/factory/render.py
index 23ca35e..10d3d00 100644
--- a/software-factory/lib/factory/render.py
+++ b/software-factory/lib/factory/render.py
@@ -54,8 +54,14 @@ def end_line(step):
     return WAIT_END if step.wait_external else SESSION_END
 
 
-def footer(step_line, step, outputs, last, help_lines):
-    lines = [SEPARATOR, step_line] + output_lines(outputs, "Outputs to set:")
+def loop_lines(step, loop_keys):
+    if step.type == "command":
+        return [f"This step controls a loop. The command sets `{key}` to `none` when nothing is left." for key in loop_keys]
+    return [f"This step controls a loop. Set `{key}` to `none` when nothing is left." for key in loop_keys]
+
+
+def footer(step_line, step, outputs, last, help_lines, extra=()):
+    lines = [SEPARATOR, step_line] + output_lines(outputs, "Outputs to set:") + list(extra)
     if step.done_when:
         lines.append(f"Done when: {step.done_when}")
     if help_lines:
@@ -63,29 +69,31 @@ def footer(step_line, step, outputs, last, help_lines):
     return lines + [last]
 
 
-def prompt_with_footer(prompt, step_line, step, outputs, last, help_lines):
-    return "\n".join([prompt.rstrip("\n"), ""] + footer(step_line, step, outputs, last, help_lines))
+def prompt_with_footer(prompt, step_line, step, outputs, last, help_lines, extra=()):
+    return "\n".join([prompt.rstrip("\n"), ""] + footer(step_line, step, outputs, last, help_lines, extra))
 
 
-def subagent_text(prompt, step_line, step, outputs, model, effort):
-    inner = prompt_with_footer(prompt, step_line, step, outputs, SUBAGENT_END, False)
+def subagent_text(prompt, step_line, step, outputs, model, effort, extra=()):
+    inner = prompt_with_footer(prompt, step_line, step, outputs, SUBAGENT_END, False, extra)
     return "\n".join([step_line, "Run this step in a subagent. Call the Agent tool with:",
                       f"- model: {model or 'inherit'}", f"- effort: {effort or 'inherit'}",
                       "- prompt:", "<<<", inner, ">>>", WAIT_END if step.wait_external else SUBAGENT_AFTER])
 
 
-def command_text(step_line, step, outputs):
+def command_text(step_line, step, outputs, extra=()):
     lines = [step_line, COMMAND_RUN]
     if outputs:
         lines += [COMMAND_OUTPUTS] + [output_name_line(name, out) for name, out in outputs.items()]
+    lines += list(extra)
     if step.done_when:
         lines.append(f"Done when: {step.done_when}")
     return "\n".join(lines + [COMMAND_RETRY] + IF_NEEDED + [end_line(step)])
 
 
-def step_text(step, prompt, step_line, outputs, model=None, effort=None):
+def step_text(step, prompt, step_line, outputs, model=None, effort=None, loop_keys=()):
+    extra = loop_lines(step, loop_keys)
     if step.type == "command":
-        return command_text(step_line, step, outputs)
+        return command_text(step_line, step, outputs, extra)
     if step.run_in == "subagent":
-        return subagent_text(prompt, step_line, step, outputs, model, effort)
-    return prompt_with_footer(prompt, step_line, step, outputs, end_line(step), True)
+        return subagent_text(prompt, step_line, step, outputs, model, effort, extra)
+    return prompt_with_footer(prompt, step_line, step, outputs, end_line(step), True, extra)
````

- [ ] **Step 4: Run the tests to see them pass**

Run: `cd software-factory && uv run --with pytest --with pyyaml pytest -q tests/test_loops.py tests/test_runtime_v2.py tests/test_engine.py`
Expected: all pass (23 tests in `test_loops.py`).

- [ ] **Step 5: Commit**

```bash
cd /Users/fabienboismoreau/Documents/Projects/SoftwareFactory/SoftwareFactory
git add software-factory/lib/factory/render.py software-factory/lib/factory/engine.py software-factory/tests/test_loops.py
git commit -m "pipeline loop: footer line and status"
```

### Task 5: Close milestone 1 (controller)

- [ ] **Step 1: Run the full suite**

```bash
cd /Users/fabienboismoreau/Documents/Projects/SoftwareFactory/SoftwareFactory/software-factory
uv run --with pytest --with pyyaml pytest -q tests
```

Expected: every test passes. If a test fails, fix it before milestone 2. List any changed existing test in `verification/software-factory/pipeline-loop-updated-tests.md` (Task 8 writes the file).

- [ ] **Step 2: Commit the milestone**

The tasks already committed their work. Make an empty milestone commit only if nothing is left to commit:

```bash
cd /Users/fabienboismoreau/Documents/Projects/SoftwareFactory/SoftwareFactory
git commit --allow-empty -m "pipeline loop: milestone 1, loop runtime"
```

---

## Milestone 2: Loop authoring

### Task 6: Pipeline editor and dashboard card

**Files:**
- Modify: `software-factory/lib/factory/web/editor.html` (constants `DEFAULT_LOOP_MAX`, `LOOP_MAX_LIMIT`; `isMap`, `loopOf`, `loopData`; `entryOf` and `dataOf` keep `loop`; `nearestIndex`, `loopMarkText`, `loopMark`, `loopBlock`; the row mark and the loop block in the entry form)
- Modify: `software-factory/lib/factory/web/dashboard.html` (`loopText` on the card)
- Modify: `software-factory/lib/factory/board.py` (`task_row` gets `loop`)
- Test: `software-factory/tests/test_loop_authoring.py` (create)

**Interfaces:**
- Consumes: `loops.current_loop` from Task 1, `/api/pipelines/keys` and `/api/pipelines/check` (existing).
- Produces: `board.task_row(...)["loop"]`: `{"n", "max", "entry"}` or `None`.
- The editor keeps a loop it does not edit exactly as loaded (`loopData` returns the raw value until the user changes a loop field).

- [ ] **Step 1: Write the failing tests**

Create `software-factory/tests/test_loop_authoring.py` with exactly this content:

````python
import json
import shutil
import subprocess

import pytest

from conftest import SF, task_from_pipeline, write_pipeline, write_step
from factory import board, repo, state
from serverutil import info, request

LOOP = {"back_to": "write", "while": "findings", "max": 2}
EDITOR = SF / "lib" / "factory" / "web" / "editor.html"
ROUND_TRIP = ["emptyModel", "isMap", "loopOf", "loopData", "entryOf", "modelOf", "parseValue", "dataOf"]


@pytest.fixture
def ed(inited):
    write_step(inited.fdir, "write", {})
    write_step(inited.fdir, "review", {"outputs": {"findings": {"type": "long-text", "description": "Findings"}}})
    write_step(inited.fdir, "after", {})
    inited.factory("pipeline", "edit")
    yield inited, info(inited.fdir)
    inited.factory("server", "stop", check=False)


def test_editor_api_saves_and_loads_loop_unchanged(ed):
    inited, i = ed
    data = {"id": "rl", "description": "Review loop", "steps": ["write", {"id": "review", "loop": LOOP}, "after"]}
    status, saved = request(i, "POST", "/api/pipelines/save", {"data": data, "level": "local"})
    assert status == 200, saved
    status, loaded = request(i, "GET", "/api/pipelines/rl")
    assert loaded["data"]["steps"] == ["write", {"id": "review", "loop": LOOP}, "after"]
    status, problems = request(i, "POST", "/api/pipelines/check", {"data": {**data, "steps": ["write", {"id": "review", "loop": {**LOOP, "max": 0}}, "after"]}, "level": "local"})
    assert {"level": "error", "message": "Step `review`: `loop.max` must be an integer from 1 to 20."} in problems


def test_editor_page_has_loop_controls(ed):
    inited, i = ed
    status, page = request(i, "GET", "/editor")
    for text in ("(no loop)", "↺ ${s.loop.back_to} ×${s.loop.max}", "datalist", "keysAt(i + 2)", "loopBlock(s, i, loopTag)"):
        assert text in page, text


def extract(source, name):
    start = source.index(f"function {name}(")
    end = source.index("\n}\n", start) + 2
    return source[start:end]


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_editor_model_keeps_loop_on_load_and_save(work):
    source = EDITOR.read_text()
    consts = "const DEFAULT_LOOP_MAX = 2;\nconst LOOP_MAX_LIMIT = 20;\n"
    functions = "\n".join(extract(source, n) for n in ROUND_TRIP)
    data = {"id": "rl", "description": "d", "steps": [
        "write", {"id": "review", "loop": LOOP}, {"id": "odd", "loop": {"back_to": "write", "until": 1}}, {"id": "bad", "loop": "write"}]}
    script = consts + functions + f"\nconst m = modelOf({json.dumps(data)});\nconsole.log(JSON.stringify(dataOf(m).steps.map((s) => s.loop)));\n"
    path = work / "roundtrip.js"
    path.write_text(script)
    out = subprocess.run(["node", str(path)], capture_output=True, text=True, check=True).stdout
    assert json.loads(out) == [None, LOOP, {"back_to": "write", "until": 1}, "write"]


def test_task_row_shows_loop_count(inited):
    write_step(inited.fdir, "write", {})
    write_step(inited.fdir, "review", {"outputs": {"findings": {"type": "long-text", "description": "Findings"}}})
    write_step(inited.fdir, "after", {})
    write_pipeline(inited.fdir, {"id": "rl", "steps": ["write", {"id": "review", "loop": LOOP}, "after"]})
    task_from_pipeline(inited, "rl")
    ctx = repo.load_ctx(cwd=inited.repo)
    assert board.task_row(ctx, state.load(ctx, "t1"))["loop"] is None
    run = lambda *a: inited.factory(*a, "--task", "t1")
    run("next"); run("done"); run("next")
    run("state", "set", "findings", "bugs")
    run("done")
    assert board.task_row(ctx, state.load(ctx, "t1"))["loop"] == {"n": 1, "max": 2, "entry": "review"}
    page = (SF / "lib" / "factory" / "web" / "dashboard.html").read_text()
    assert "` · loop ${t.loop.n} of ${t.loop.max}`" in page
````

- [ ] **Step 2: Run the tests to see them fail**

Run: `cd software-factory && uv run --with pytest --with pyyaml pytest -q tests/test_loop_authoring.py`
Expected: `test_editor_page_has_loop_controls`, `test_editor_model_keeps_loop_on_load_and_save` and `test_task_row_shows_loop_count` fail. `test_editor_api_saves_and_loads_loop_unchanged` passes already: the server keeps `loop`.

- [ ] **Step 3: Apply the implementation patch**

Save the block below (between the `<!-- patch: task-6 -->` marker and its closing four-backtick line) to a file, for example with this script, then apply it from the repository root:

```bash
cd /Users/fabienboismoreau/Documents/Projects/SoftwareFactory/SoftwareFactory
python3 - <<'PY'
import re, pathlib
brief = pathlib.Path("<path of your task brief>").read_text()
body = re.search(r"<!-- patch: task-6 -->\n````diff\n(.*?)^````$", brief, re.S | re.M).group(1)
pathlib.Path("/tmp/task-6.diff").write_text(body)
PY
git apply --check /tmp/task-6.diff && git apply /tmp/task-6.diff
```

<!-- patch: task-6 -->
````diff
diff --git a/software-factory/lib/factory/board.py b/software-factory/lib/factory/board.py
index 04ffbba..e29ac4d 100644
--- a/software-factory/lib/factory/board.py
+++ b/software-factory/lib/factory/board.py
@@ -1,4 +1,4 @@
-from . import session, state
+from . import loops, session, state
 from .errors import FactoryError
 from .registry import Registry
 
@@ -51,6 +51,7 @@ def task_row(ctx, task, reg=None):
         "artifacts": artifact_names(ctx, task["id"]),
         "approval": approval_info(task),
         "wait_has_check": bool(step and step.done_check) if waiting else None,
+        "loop": loops.current_loop(task),
     }
 
 
diff --git a/software-factory/lib/factory/web/dashboard.html b/software-factory/lib/factory/web/dashboard.html
index 4974a03..016378d 100644
--- a/software-factory/lib/factory/web/dashboard.html
+++ b/software-factory/lib/factory/web/dashboard.html
@@ -227,13 +227,14 @@ function approvalArtifact(t) {
   const base = a.artifact ? String(a.artifact).split("/").pop() : "";
   return [base, a.artifact_key, a.artifact_key + ".md"].find((n) => n && t.artifacts.includes(n)) || null;
 }
+function loopText(t) { return t.loop ? ` · loop ${t.loop.n} of ${t.loop.max}` : ""; }
 function taskCard(t) {
   const card = el("div", { class: "card s-" + t.status });
   const top = el("div", { class: "row" });
   const ticket = ticketNode(t);
   if (ticket) top.append(ticket);
   top.append(el("span", { class: "muted" }, t.id));
-  card.append(top, el("div", { class: "title" }, t.description), el("div", { class: "muted" }, `${t.pipeline} › ${t.step}`));
+  card.append(top, el("div", { class: "title" }, t.description), el("div", { class: "muted" }, `${t.pipeline} › ${t.step}${loopText(t)}`));
   const since = ago(t.status_since);
   const label = t.status.replace("_", " ");
   card.append(el("div", { class: "status" }, `${ICONS[t.status] || ""} ${label}${since && t.status !== "finished" ? " for " + since : ""}`));
diff --git a/software-factory/lib/factory/web/editor.html b/software-factory/lib/factory/web/editor.html
index 0108360..7a8e1bd 100644
--- a/software-factory/lib/factory/web/editor.html
+++ b/software-factory/lib/factory/web/editor.html
@@ -75,6 +75,8 @@ const TOKEN = params.get("token");
 const CHECK_DELAY_MS = 300;
 const SHOW_HIDDEN_KEY = "factory-editor-show-hidden";
 const KEY_TYPES = ["text", "long-text", "file"];
+const DEFAULT_LOOP_MAX = 2;
+const LOOP_MAX_LIMIT = 20;
 function readShowHidden() { try { return localStorage.getItem(SHOW_HIDDEN_KEY) === "1"; } catch (e) { return false; } }
 function saveShowHidden(value) { try { localStorage.setItem(SHOW_HIDDEN_KEY, value ? "1" : "0"); } catch (e) {} }
 const state = { steps: [], columns: [], pipelines: [], loadedLevel: null, saveLevel: "local", model: null, checkTimer: null, checkCount: 0, hasError: true, commit: null, savedPath: null, original: null, confirmReplace: false, showHidden: readShowHidden() };
@@ -104,10 +106,21 @@ function guard(fn) { return (...a) => fn(...a).catch(() => {}); }
 function emptyModel() {
   return { id: "", description: "", model: "", effort: "", start_column: "", inputs: [], steps: [], extra: {} };
 }
+function isMap(v) { return !!v && typeof v === "object" && !Array.isArray(v); }
+function loopOf(raw) {
+  if (raw === undefined) return null;
+  const m = isMap(raw) ? raw : {};
+  return { raw, edited: false, back_to: m.back_to ?? "", while: m.while ?? "", max: m.max ?? DEFAULT_LOOP_MAX };
+}
+function loopData(l) {
+  if (!l.edited) return l.raw;
+  return { ...(isMap(l.raw) ? l.raw : {}), back_to: l.back_to, while: l.while, max: l.max };
+}
 function entryOf(raw) {
   const e = typeof raw === "string" ? { id: raw } : raw || {};
   return { id: e.id || "", model: e.model || "", effort: e.effort || "", column: e.column || "",
-    with: Object.entries(e.with || {}).map(([key, value]) => ({ key, value: typeof value === "string" ? value : JSON.stringify(value) })), open: false };
+    with: Object.entries(e.with || {}).map(([key, value]) => ({ key, value: typeof value === "string" ? value : JSON.stringify(value) })),
+    loop: loopOf(e.loop), open: false };
 }
 function modelOf(data) {
   const claude = data.claude || {};
@@ -129,7 +142,9 @@ function dataOf(m) {
   for (const s of m.steps) {
     const w = {};
     for (const r of s.with) if (r.key) w[r.key] = parseValue(r.value);
-    data.steps.push({ id: s.id, with: w, model: s.model, effort: s.effort, column: s.column });
+    const entry = { id: s.id, with: w, model: s.model, effort: s.effort, column: s.column };
+    if (s.loop) entry.loop = loopData(s.loop);
+    data.steps.push(entry);
   }
   return data;
 }
@@ -190,6 +205,49 @@ function renderForm() {
     field("inputs", inputRows(m.inputs)));
 }
 
+function nearestIndex(i, id) {
+  for (let j = i; j >= 0; j--) if (state.model.steps[j].id === id) return j;
+  return -1;
+}
+function loopMarkText(s) { return s.loop ? `↺ ${s.loop.back_to} ×${s.loop.max}` : ""; }
+function loopMark(s) {
+  const tag = el("span", { class: "tag" }, loopMarkText(s));
+  if (!s.loop) tag.style.display = "none";
+  return tag;
+}
+function loopBlock(s, i, tag) {
+  const editLoop = (fn) => { fn(s.loop); s.loop.edited = true; tag.textContent = loopMarkText(s); changed(); };
+  const target = el("select");
+  target.append(el("option", { value: "" }, "(no loop)"));
+  state.model.steps.slice(0, i + 1).forEach((e, j) => target.append(el("option", { value: String(j) }, `${j + 1}. ${e.id}`)));
+  target.value = s.loop ? String(nearestIndex(i, s.loop.back_to)) : "";
+  target.addEventListener("change", () => {
+    if (target.value === "") s.loop = null;
+    else {
+      s.loop = s.loop || loopOf({ back_to: "", while: "", max: DEFAULT_LOOP_MAX });
+      s.loop.back_to = state.model.steps[Number(target.value)].id;
+      s.loop.edited = true;
+    }
+    renderPipeline();
+    changed();
+  });
+  const box = el("div", { class: "loop" }, el("div", { class: "muted" }, "loop"), field("back_to", target));
+  if (!s.loop) return box;
+  const listId = `loop-keys-${i}`;
+  const keyList = el("datalist", { id: listId });
+  const whileInput = el("input", { type: "text", list: listId });
+  whileInput.value = s.loop.while;
+  whileInput.addEventListener("input", () => editLoop((l) => { l.while = whileInput.value; }));
+  guard(async () => { for (const r of await keysAt(i + 2)) keyList.append(el("option", { value: r.name })); })();
+  const maxInput = el("input", { type: "number", min: "1", max: String(LOOP_MAX_LIMIT) });
+  maxInput.value = String(s.loop.max);
+  maxInput.addEventListener("input", () => editLoop((l) => {
+    const n = Number(maxInput.value);
+    l.max = maxInput.value.trim() !== "" && Number.isInteger(n) ? n : maxInput.value;
+  }));
+  box.append(field("while", whileInput), keyList, field("max", maxInput));
+  return box;
+}
 function renderPipeline() {
   const box = clear(byId("pipeline"));
   if (!state.model.steps.length) box.append(el("div", { class: "muted" }, "Drag steps here."));
@@ -197,10 +255,12 @@ function renderPipeline() {
 }
 function pipelineRow(s, i) {
   const info = state.steps.find((x) => x.id === s.id);
+  const loopTag = loopMark(s);
   const mark = info && info.hidden ? el("span", { class: "tag" }, "hidden") : "";
   const head = el("div", { class: "head", draggable: "true" },
     el("span", { class: "muted" }, String(i + 1)),
     el("span", { class: "link grow", onclick: guard(() => showDetail(s.id, i + 1)) }, s.id),
+    loopTag,
     mark,
     el("button", { type: "button", onclick: () => { s.open = !s.open; renderPipeline(); } }, s.open ? "Close" : "Edit"),
     el("button", { type: "button", onclick: () => { state.model.steps.splice(i, 1); renderPipeline(); changed(); } }, "Remove"));
@@ -212,7 +272,8 @@ function pipelineRow(s, i) {
       pairRows(s.with, "key", "value", "key", "value"),
       field("model", textInput(s.model, (v) => { s.model = v; changed(); })),
       field("effort", textInput(s.effort, (v) => { s.effort = v; changed(); })),
-      field("column", selectInput(["", ...state.columns], s.column, (v) => { s.column = v; changed(); })));
+      field("column", selectInput(["", ...state.columns], s.column, (v) => { s.column = v; changed(); })),
+      loopBlock(s, i, loopTag));
   }
   return card;
 }
````

- [ ] **Step 4: Run the tests to see them pass**

Run: `cd software-factory && uv run --with pytest --with pyyaml pytest -q tests/test_loop_authoring.py tests/test_editor_api.py tests/test_dashboard_api.py tests/test_board.py`
Expected: all pass. Also run a syntax check of the editor script:

```bash
cd /Users/fabienboismoreau/Documents/Projects/SoftwareFactory/SoftwareFactory/software-factory
python3 -c "import re,sys;s=open('lib/factory/web/editor.html').read();open('/tmp/editor.js','w').write(chr(10).join(re.findall(r'<script>(.*?)</script>',s,re.S)))"
node --check /tmp/editor.js
```

- [ ] **Step 5: Commit**

```bash
cd /Users/fabienboismoreau/Documents/Projects/SoftwareFactory/SoftwareFactory
git add software-factory/lib/factory/web/editor.html software-factory/lib/factory/web/dashboard.html software-factory/lib/factory/board.py software-factory/tests/test_loop_authoring.py
git commit -m "pipeline loop: editor and dashboard"
```

### Task 7: Authoring skill and README

**Files:**
- Modify: `software-factory/skills/factory-authoring/SKILL.md` (`loop` in the entry fields, a "Loops" section before "Examples", a "Loop examples" section at the end)
- Modify: `software-factory/README.md` (`loop` in "Pipeline fields" with the review example, a "Loop" line in "Pipeline editor", new sections "Loops" and "Events")
- Modify: `software-factory/tests/test_authoring_skill.py` (the examples test checks the two new pipelines; new `test_skill_documents_loops`)
- Test: `software-factory/tests/test_loop_authoring.py` (append `test_readme_documents_loops`)

**Interfaces:**
- Consumes: the runtime messages of Tasks 3 and 4, word for word.
- The example files are `.factory/steps/write-spec.md`, `review-spec.md`, `split-tickets.md`, `pick-ticket.md`, `build-ticket.md`, `ticket-round.md` and `.factory/pipelines/spec-review.yaml`, `ticket-loop.yaml`, each under a `####` heading with one fenced block, so `test_authoring_skill` copies them.

- [ ] **Step 1: Write the failing tests**

Apply this test patch to `software-factory/tests/test_authoring_skill.py` (same method as Step 3, marker `test-task-7`):

<!-- patch: test-task-7 -->
````diff
diff --git a/software-factory/tests/test_authoring_skill.py b/software-factory/tests/test_authoring_skill.py
index d8936ea..f71a9a7 100644
--- a/software-factory/tests/test_authoring_skill.py
+++ b/software-factory/tests/test_authoring_skill.py
@@ -65,7 +65,8 @@ def test_examples_load_and_check_clean(inited):
     from factory import repo
     reg = registry.Registry.load(repo.load_ctx(cwd=inited.repo))
     assert {reg.steps[sid].type for sid in example_step_ids(text)} == {"ai", "command", "group"}
-    assert inited.factory.json("pipeline", "check", "crash-fix") == []
+    for pid in ("crash-fix", "spec-review", "ticket-loop"):
+        assert inited.factory.json("pipeline", "check", pid) == [], pid
     rows = {r["name"]: r for r in inited.factory.json("pipeline", "keys", "crash-fix", "--at", "2")}
     assert rows["crash_log"]["source"] == "input"
     assert rows["crash_report"]["source"] == "step collect-crash"
@@ -127,3 +128,15 @@ def test_skill_covers_review_findings():
                    "A step file that does not load stops the check", "no factory command works",
                    "does not see a `with` key", "`{{ key }}` with spaces", "Every input is required at launch"):
         assert needle in text, needle
+
+
+def test_skill_documents_loops():
+    text = skill_text()
+    loops_section = text.split("### Loops\n", 1)[1].split("\n## ", 1)[0]
+    for needle in ("`back_to`", "`while`", "`max`", "from 1 to 20", "Loop <n> of <max>: back to `<step>`",
+                   "Loop limit reached on `<entry>`: `<key>` is still set",
+                   "This step controls a loop. Set `<key>` to `none` when nothing is left.",
+                   "Each step that outputs the `while` key must set it to `none` when nothing is left."):
+        assert needle in loops_section, needle
+    review = dict(examples(text))[".factory/steps/review-spec.md"]
+    assert "run_in: subagent" in review and "set `findings` to `none`" in review
````

Append this block to the end of `software-factory/tests/test_loop_authoring.py`:

````python


def test_readme_documents_loops():
    text = (SF / "README.md").read_text()
    fields = text.split("### Pipeline fields\n", 1)[1].split("\n### ", 1)[0]
    for needle in ("`loop`", "`back_to`", "`while`", "`max`", "back_to: write-spec", "while: findings"):
        assert needle in fields, needle
    for needle in ("### Loops", "Loop <n> of <max>: back to `<step>`", "`loop_back`", "`loop_limit`", "↺ write-spec ×2"):
        assert needle in text, needle
````

- [ ] **Step 2: Run the tests to see them fail**

Run: `cd software-factory && uv run --with pytest --with pyyaml pytest -q tests/test_authoring_skill.py tests/test_loop_authoring.py`
Expected: `test_examples_load_and_check_clean` fails (`spec-review` does not exist), `test_skill_documents_loops` and `test_readme_documents_loops` fail.

- [ ] **Step 3: Apply the implementation patch**

Save the block below (between the `<!-- patch: task-7 -->` marker and its closing four-backtick line) to a file, for example with this script, then apply it from the repository root:

```bash
cd /Users/fabienboismoreau/Documents/Projects/SoftwareFactory/SoftwareFactory
python3 - <<'PY'
import re, pathlib
brief = pathlib.Path("<path of your task brief>").read_text()
body = re.search(r"<!-- patch: task-7 -->\n````diff\n(.*?)^````$", brief, re.S | re.M).group(1)
pathlib.Path("/tmp/task-7.diff").write_text(body)
PY
git apply --check /tmp/task-7.diff && git apply /tmp/task-7.diff
```

<!-- patch: task-7 -->
````diff
diff --git a/software-factory/README.md b/software-factory/README.md
index b97fd5c..1705691 100644
--- a/software-factory/README.md
+++ b/software-factory/README.md
@@ -221,6 +221,7 @@ Local server:
 - Middle: the pipeline. Drag steps into it and reorder them. The checks run while you edit. You can save with warnings, never with errors.
 - Right: the step detail. Click a step to see its manifest, its level, its file and its body.
 - Keys: click a step in the pipeline to see the keys available at its position.
+- Loop: "Edit" on a pipeline step shows the loop fields. Pick `back_to` from this step and the earlier steps, `while` from the keys available after the step, and `max`. A step with a loop shows a mark, for example "↺ write-spec ×2".
 - Step form: "New step" above the available steps opens it. The start screen of the editor has a "New step" button too. In the step detail, "Edit" changes a local or generic step, "Copy to local" copies a generic or built-in step to a local step with the same id, and "Duplicate" copies any step under a new id.
   - The form shows the fields of the manifest, a table for config keys, a table for outputs, and the prompt or the command. A `group` step shows a list of child steps. Drag them to change the order.
   - Next to the body, click a key to insert `{{<key>}}` in a prompt or `$FACTORY_KEY_<KEY>` in a command.
@@ -382,10 +383,47 @@ Only `http` and `https` URLs are used.
 
 - `id`, `description`
 - `inputs`: values asked at launch, each with a `type` and a `description`. A relative `file` path is resolved from the main repository.
-- `steps`: a list of entries with `id`, `with`, `model`, `effort` and `column`.
+- `steps`: a list of entries with `id`, `with`, `model`, `effort`, `column` and `loop`.
+- `loop`: repeat a range of steps while a task key is set.
+  - `back_to`: this entry or an earlier entry. The loop range goes from there to this entry.
+  - `while`: a task key name.
+  - `max`: the most jumps back, from 1 to 20.
+
+  A review loop:
+
+  ```yaml
+  steps:
+    - write-spec
+    - id: review-spec
+      loop:
+        back_to: write-spec
+        while: findings
+        max: 2
+    - next-step
+  ```
 - `claude`: `model` and `effort` of the task session.
 - `start_column`: the board column of a new task.
 
+### Loops
+
+- When `factory done` succeeds on the last step of a loop entry, the factory reads the `while` key.
+- The key is not set when it is missing, empty or `none`, ignoring case and spaces around it.
+- Set, with fewer than `max` jumps: the task goes back to the first step of `back_to`. `factory done` prints "Loop <n> of <max>: back to `<step>`. Run `factory next`."
+- Set, after `max` jumps: the task moves to the next step and is blocked. The user unblocks to go on, or approves one more round with `factory goto`.
+- Not set: the task moves on. A skipped step never makes its loop jump.
+- At the limit on the last entry, the task finishes. The check warns about a loop on the last entry.
+- The jump keeps the task keys. Session steps run again in the same session, with the conversation of the earlier rounds.
+- A loop's count goes back to 0 when the task jumps to a step before its range. An inner loop gets its full `max` in each round of an outer loop.
+- A step inside the range that outputs the `while` key gets a footer line: "This step controls a loop. Set `<key>` to `none` when nothing is left." A clean round must reset the key, because task keys keep their values.
+- `factory status` and the dashboard card show "loop <n> of <max>".
+
+### Events
+
+Each task logs its events in `.factory/tasks/<id>/events.jsonl`, one JSON object per line. Loops add two events:
+
+- `loop_back`: the loop jumped back. It has `entry`, `to` (the target step), `round` (the jump number) and `max`.
+- `loop_limit`: the loop reached `max` with the key still set. It has `entry` and `key`.
+
 ### `.factory/factory.yaml` fields
 
 `version`, `library`, `terminal`, `columns`, `poll_minutes`, `ticket_url`, `hidden_steps` (optional: the ids of hidden steps).
diff --git a/software-factory/skills/factory-authoring/SKILL.md b/software-factory/skills/factory-authoring/SKILL.md
index 5e736d7..5738fa1 100644
--- a/software-factory/skills/factory-authoring/SKILL.md
+++ b/software-factory/skills/factory-authoring/SKILL.md
@@ -188,10 +188,49 @@ A step file is YAML frontmatter between two `---` lines, then the body.
   - `with`: config values for this entry,
   - `model` and `effort`: for a step that runs in a subagent,
   - `column`: the board column when this entry starts.
+  - `loop`: repeat a range of steps while a key is set. See Loops.
 - `claude`: `model` and `effort` of the task session.
 - `start_column`: the board column of a new task.
 - `create-worktree`: the factory adds the built-in step `create-worktree` as the first step. List it only to set its `with` values, and then only as the first step.
 
+### Loops
+
+A pipeline entry can repeat a range of steps while a task key is set.
+
+```yaml
+steps:
+  - write-spec
+  - id: review-spec
+    loop:
+      back_to: write-spec
+      while: findings
+      max: 2
+  - user-validation
+```
+
+- `loop` has three fields:
+  - `back_to`: the id of this entry or of an earlier entry. When the id appears more than once, the nearest one at or before this entry is used. It cannot be `create-worktree`.
+  - `while`: a task key name.
+  - `max`: an integer from 1 to 20. It is the most jumps back for this loop.
+- The entry can be a normal step or a group step. `back_to` can be the entry itself, to repeat one round.
+- The loop range is the steps from the `back_to` entry to the loop entry.
+- When `factory done` succeeds on the last step of the loop entry, the factory reads the `while` key:
+  - The key is not set when it is missing, empty or `none`, ignoring case and spaces around it.
+  - Set, with fewer than `max` jumps: the task goes back to the first step of `back_to`. `factory done` prints "Loop <n> of <max>: back to `<step>`. Run `factory next`."
+  - Set, after `max` jumps: the task moves to the next step and is blocked: "Loop limit reached on `<entry>`: `<key>` is still set". The user unblocks to go on, or approves one more round with `factory goto`.
+  - Not set: the task moves on.
+- At the limit on the last entry of the pipeline, the task finishes without asking the user. So put a step after a loop, for example `user-validation`.
+- A skipped step never makes its loop jump.
+- The factory makes the jump. The session never runs `factory goto` for a loop.
+- The jump keeps the task keys. It runs in the same task session, so a `session` step keeps the conversation of the earlier rounds. A `subagent` step starts a new agent each time.
+- A loop's count goes back to 0 when the task jumps to a step before its range. So an inner loop gets its full `max` in each round of an outer loop.
+- `factory status` and the dashboard card show "loop <n> of <max>".
+- A step inside the range that outputs the `while` key gets this footer line: "This step controls a loop. Set `<key>` to `none` when nothing is left."
+- Each step that outputs the `while` key must set it to `none` when nothing is left. Task keys keep their values, so a clean round must reset the key. Say this in the step prompt.
+- In a `command` step, the command sets the key itself, also to `none`.
+- Inside the range, a step can use a key that a later step of the range outputs. It is `(not set)` in the first round.
+- `factory pipeline check` refuses a bad `loop` and two loops that overlap without one being inside the other. It warns when no step in the range outputs the key, when the key is optional in every step that outputs it, and when the loop is on the last entry.
+
 ## Examples
 
 One flow: collect a crash report with a command, fix the crash with the agent, then ask the user to validate with the built-in step `user-validation`.
@@ -288,3 +327,176 @@ What the example shows:
 - The input `crash_log` is used by the script as `"$FACTORY_KEY_CRASH_LOG"`.
 - The output `crash_report` of `collect-crash` is used by `fix-crash` as `{{crash_report}}`.
 - The config value `lines` is set with `with` on the group entry. `test_hint` uses its default.
+
+## Loop examples
+
+### Review loop
+
+Write a spec in the session, review it in a subagent, and fix it until the review is clean, at most 2 times.
+
+#### .factory/steps/write-spec.md
+
+```markdown
+---
+id: write-spec
+description: Write the spec, or fix it from the review findings
+category: planning
+type: ai
+outputs:
+  spec:
+    type: file
+    description: The spec file
+done_when: The spec file is written and its path is saved.
+---
+
+Write a spec for: {{description}}.
+Save it at the path printed by `factory artifact path spec.md`.
+
+Findings of the last review: {{findings}}.
+In the first round, there is no review yet. In a later round, fix each finding in the spec.
+```
+
+#### .factory/steps/review-spec.md
+
+```markdown
+---
+id: review-spec
+description: Review the spec and list the real problems
+category: planning
+type: ai
+outputs:
+  findings:
+    type: long-text
+    description: The real problems of the spec, one per line, or none
+done_when: The findings are saved.
+run_in: subagent
+model: opus
+effort: high
+---
+
+Review the spec at {{spec}} for: {{description}}.
+List only real problems: a missing case, a contradiction, a vague rule. Skip style comments.
+Set `findings` to the list, one problem per line.
+When you find no real problem, set `findings` to `none`.
+```
+
+#### .factory/pipelines/spec-review.yaml
+
+```yaml
+id: spec-review
+description: Write a spec, review it, and fix it until the review is clean
+steps:
+  - write-spec
+  - id: review-spec
+    loop:
+      back_to: write-spec
+      while: findings
+      max: 2
+  - id: user-validation
+    with:
+      target: artifact
+      artifact_key: spec
+```
+
+### Ticket loop
+
+Split the work into tickets, then run one round of steps per ticket, for any number of tickets.
+
+#### .factory/steps/split-tickets.md
+
+```markdown
+---
+id: split-tickets
+description: Split the work into small tickets
+category: planning
+type: ai
+outputs:
+  remaining:
+    type: long-text
+    description: The tickets left, one per line, or none
+done_when: The tickets are saved.
+---
+
+Split this work into small tickets: {{description}}.
+Each ticket is one line. Each ticket can be built and tested alone.
+Set `remaining` to the tickets, one per line.
+When there is no ticket, set `remaining` to `none`.
+```
+
+#### .factory/steps/pick-ticket.md
+
+```markdown
+---
+id: pick-ticket
+description: Take the next ticket from the list
+category: planning
+type: ai
+outputs:
+  ticket:
+    type: text
+    description: The ticket of this round, or none
+  remaining:
+    type: long-text
+    description: The tickets left after this one, one per line, or none
+done_when: The ticket and the tickets left are saved.
+---
+
+The tickets left: {{remaining}}.
+
+- When this is `none`, set `ticket` to `none` and `remaining` to `none`.
+- Otherwise, set `ticket` to the first line.
+- Set `remaining` to the other lines. When no line is left, set it to `none`.
+```
+
+#### .factory/steps/build-ticket.md
+
+```markdown
+---
+id: build-ticket
+description: Build one ticket and commit it
+category: build
+type: ai
+done_when: The ticket is built, tested and committed.
+---
+
+The ticket of this round: {{ticket}}.
+
+When it is `none`, do nothing and run `factory done`.
+Otherwise, build the ticket, run the tests and commit the change.
+```
+
+#### .factory/steps/ticket-round.md
+
+```markdown
+---
+id: ticket-round
+description: Take the next ticket and build it
+category: build
+type: group
+steps:
+  - pick-ticket
+  - build-ticket
+---
+```
+
+#### .factory/pipelines/ticket-loop.yaml
+
+```yaml
+id: ticket-loop
+description: Split the work into tickets and build them one by one
+steps:
+  - split-tickets
+  - id: ticket-round
+    loop:
+      back_to: ticket-round
+      while: remaining
+      max: 20
+  - user-validation
+```
+
+What the examples show:
+- `review-spec` runs in a subagent and sets `findings` to `none` when the review is clean.
+- `write-spec` uses `{{findings}}`, an output of a later step of its loop. It is `(not set)` in the first round.
+- `ticket-round` loops back to itself. `pick-ticket` controls the loop: it sets `remaining` to `none` after the last ticket.
+- With zero tickets, `pick-ticket` sets `ticket` to `none`, and `build-ticket` does nothing.
+- Each loop has a step after it, so the user decides at the limit.
````

- [ ] **Step 4: Run the tests to see them pass**

Run: `cd software-factory && uv run --with pytest --with pyyaml pytest -q tests/test_authoring_skill.py tests/test_loop_authoring.py tests/test_docs.py tests/test_skill.py`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
cd /Users/fabienboismoreau/Documents/Projects/SoftwareFactory/SoftwareFactory
git add software-factory/skills/factory-authoring/SKILL.md software-factory/README.md software-factory/tests/test_authoring_skill.py software-factory/tests/test_loop_authoring.py
git commit -m "pipeline loop: authoring skill and README"
```

### Task 8: Verification report and manual check list

**Files:**
- Create: `software-factory/tests/report_pipeline_loop.py`
- Create: `verification/software-factory/pipeline-loop-updated-tests.md`
- Create: `verification/software-factory/pipeline-loop-dod.md`
- Create: `verification/software-factory/pipeline-loop-manual-check.md`
- Generated: `verification/software-factory/pipeline-loop-junit.xml`, `verification/software-factory/pipeline-loop-report.md`

**Interfaces:**
- Consumes: `tests/report.py` (`VERIF`, `cases`, `table`).

- [ ] **Step 1: Write the report script**

Create `software-factory/tests/report_pipeline_loop.py`:

````python
import sys
from datetime import datetime

from report import VERIF, cases, table

MILESTONES = {
    "1. Loop runtime": ["test_loops"],
    "2. Loop authoring": ["test_loop_authoring", "test_authoring_skill", "test_docs"],
}
JUNIT = VERIF / "pipeline-loop-junit.xml"
REPORT = VERIF / "pipeline-loop-report.md"
UPDATED = VERIF / "pipeline-loop-updated-tests.md"
DOD = VERIF / "pipeline-loop-dod.md"


def main():
    rows = cases(JUNIT)
    lines = ["# Pipeline loop verification report", "", f"Date: {datetime.now():%Y-%m-%d %H:%M}", ""]
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
    updated = UPDATED.read_text().splitlines() if UPDATED.exists() else []
    updated = [line for line in updated if line.strip() and line != "# Updated tests"]
    lines += updated or ["None."]
    if DOD.exists():
        lines += [""] + DOD.read_text().splitlines()
    REPORT.write_text("\n".join(lines) + "\n")
    return 0 if rows and passed == len(rows) else 1


if __name__ == "__main__":
    sys.exit(main())
````

- [ ] **Step 2: Write the updated-tests file**

Create `verification/software-factory/pipeline-loop-updated-tests.md`:

````markdown
# Updated tests

- tests/test_authoring_skill.py::test_examples_load_and_check_clean: the skill has two new example pipelines, `spec-review` and `ticket-loop`. The test now checks all three example pipelines.
- tests/conftest.py `task_from_pipeline` (a helper, not a test): it now saves the loops of the pipeline in the task snapshot, as `factory launch` does.
````

Add a line for any other existing test that a task changed, with the reason.

- [ ] **Step 3: Write the DoD mapping**

Create `verification/software-factory/pipeline-loop-dod.md`:

````markdown
## Definition Of Done

### Workflow Complete

- The plan is `plans/2026-10-13-pipeline-loop.md`. It was committed in the first commit of the branch, before the implementation.
- The work is on the branch `pipeline-loop`. `master` is unchanged.
- Every existing test still passes: see "Full test suite". Updated tests: see "Updated tests".

### Loop field

- `back_to`, `while`, `max`, the nearest `back_to`, a loop back to the entry itself, a group entry: covered by `test_loops::test_snapshot_positions`, `test_back_to_uses_the_nearest_earlier_entry`, `test_group_loop_back_to_itself`.

### Runtime

- Snapshot of each loop: `test_snapshot_positions`. A changed file does not change a running loop: the loop is read from `task.json` only, see `test_old_task_without_loops` for a task without loops.
- Jump, "Loop <n> of <max>" and `loop_back`: `test_review_loop_jumps_twice_then_moves_on`.
- Limit, block, reason and `loop_limit`: `test_limit_moves_on_and_blocks`. One more round with `factory goto`: `test_goto_after_limit_gives_one_more_round`.
- Limit on the last entry: `test_limit_on_last_entry_finishes`.
- Not set values: `test_is_set`, `test_not_set_values_move_on`.
- Skip: `test_skipped_loop_step_does_not_jump`.
- Reset of `started`, `command_result`, `approval`, task keys kept: `test_jump_resets_fields_and_keeps_keys`.
- Counts apart from `goto_counts`, no `goto` block: `test_three_loop_rounds_do_not_block_like_goto`, `test_group_loop_back_to_itself`.
- Count reset by an outer loop and by `factory goto`: `test_nested_inner_loop_resets_after_outer_jump`, `test_goto_resets_only_before_the_range`.
- Wait steps: `test_wait_step_loop_jumps_on_external_done`.
- Same session for session steps, new agent for subagent steps: the jump only moves the position. Real sessions: manual check 1.
- `factory status`: `test_status_shows_loop_count`, `test_status_shows_the_innermost_loop`.

### Footer

- `test_footer_line_only_on_the_controlling_step`, `test_footer_line_for_subagent_and_command`.

### Pipeline check

- Every error and warning: `test_check_errors_and_warnings`, `test_overlap_names_both_loops_and_nested_is_fine`.
- A key output later in the loop is available inside the range: `test_key_set_later_in_the_loop_is_available_inside_the_range`.

### Pipeline editor and dashboard

- Save and load with `loop` unchanged: `test_loop_authoring::test_editor_api_saves_and_loads_loop_unchanged` (server) and `test_editor_model_keeps_loop_on_load_and_save` (editor model, run with node).
- Entry form controls and row mark: `test_editor_page_has_loop_controls`. Browser look: manual check 3.
- Live checks: the editor calls `/api/pipelines/check`, see `test_editor_api_saves_and_loads_loop_unchanged`.
- Dashboard card: `test_task_row_shows_loop_count`. Browser look: manual check 4.

### Authoring skill and documentation

- Skill loop section, footer line, the rule to set the key to `none`, the two examples with a subagent review step: `test_authoring_skill::test_skill_documents_loops`, `test_examples_load_and_check_clean`.
- README: `test_loop_authoring::test_readme_documents_loops`.
- Every `factory` command in the README and the skills exists: `test_docs::test_readme_commands_exist`, `test_authoring_skill::test_skill_commands_exist`.

### Verification

- This report, and the manual check list `pipeline-loop-manual-check.md`.
````

- [ ] **Step 4: Write the manual check list**

Create `verification/software-factory/pipeline-loop-manual-check.md`:

````markdown
# Pipeline loops: manual checks

Use a test repository with the factory initialized and a test library in its own git repository. Never a real library or a real `.factory/`.

## Setup

1. Install the plugin from the branch `pipeline-loop`, or start Claude with `--plugin-dir <path to software-factory>`.
2. Copy the examples of the "Loop examples" section of `skills/factory-authoring/SKILL.md` into `.factory/steps/` and `.factory/pipelines/` of the test repository.
3. Run `factory pipeline check spec-review` and `factory pipeline check ticket-loop`. Expected: no problem.

## Checks

1. **Review loop with a real session.**
   - Launch `spec-review` with a description that has gaps, for example "Add a login page".
   - Expected: `review-spec` runs in a subagent and sets `findings`. `factory done` prints "Loop 1 of 2: back to `write-spec`."
   - Expected: `write-spec` runs again in the same session, with the findings in its prompt.
   - Expected: after the second jump, if findings remain, the task moves to `user-validation` and is blocked with "Loop limit reached on `review-spec`: `findings` is still set".
2. **Ticket loop with three tickets.**
   - Launch `ticket-loop` with a description of three small changes.
   - Expected: `pick-ticket` and `build-ticket` run three times. "Loop 1 of 20" and "Loop 2 of 20" appear. After the third ticket, `remaining` is `none` and the task moves to `user-validation`.
3. **Pipeline editor.**
   - Run `factory pipeline edit spec-review`.
   - Expected: the row `review-spec` shows "↺ write-spec ×2".
   - Click "Edit" on `review-spec`. Change `max` to 0. Expected: the live checks show "Step `review-spec`: `loop.max` must be an integer from 1 to 20." Set it back to 2.
   - Pick a `while` key from the list. Save. Expected: the saved file keeps `loop`.
4. **Dashboard card.**
   - Run `factory dashboard` while the review loop of check 1 runs.
   - Expected: after the first jump, the card shows "loop 1 of 2" after the step.

Write the result of each check: pass or fail, with what you saw.
````

- [ ] **Step 5: Run the full suite and write the report**

```bash
cd /Users/fabienboismoreau/Documents/Projects/SoftwareFactory/SoftwareFactory/software-factory
uv run --with pytest --with pyyaml pytest -q tests --junitxml=../verification/software-factory/pipeline-loop-junit.xml
cd tests && uv run --with pyyaml python report_pipeline_loop.py
```

Expected: every test passes, the script exits 0, and the report has "Milestone 1. Loop runtime", "Milestone 2. Loop authoring" and "Full test suite" with all tests passing.

- [ ] **Step 6: Commit**

```bash
cd /Users/fabienboismoreau/Documents/Projects/SoftwareFactory/SoftwareFactory
git add software-factory/tests/report_pipeline_loop.py verification/software-factory/pipeline-loop-*
git commit -m "pipeline loop: verification report and manual check list"
```
