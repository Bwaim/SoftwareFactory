# Factory Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix six daily-use problems of the software factory: Herdr name limit, squash-merge clean, artifact viewer, poll countdown and "Check now", focus to front, names from the ticket.

**Architecture:** Small changes in the existing modules of `software-factory/lib/factory/`. One new module, `rename.py`, holds the rename after launch. Two new helpers: `adapters.base.herdr_name` (name rule) and `fsio.try_locked` (non-blocking cross-process lock). No data format version change: new task fields are optional.

**Tech Stack:** Python 3 (stdlib + PyYAML), pytest, plain HTML/JS dashboard, git 2.55, Herdr 0.9.3 (stubbed in tests).

**Spec:** `specs/2026-10-16-factory-fixes-design.md`

## Global Constraints

- All paths below are relative to `software-factory/` unless they start with `specs/`, `plans/` or `verification/`.
- Test command (full suite): `cd software-factory && uv run --with pytest --with pyyaml pytest -q tests`. Baseline: 416 passed.
- Work only on the branch `factory-fixes`. Never commit to `master`. Never push.
- Never add a `Co-Authored-By` line to a commit message.
- Never start, rename or close a real Herdr workspace, tab or agent. Tests use the fake adapter (`FACTORY_TERMINAL=fake`) or the stub `tests/fake_herdr.py` on `PATH`.
- Never run the real `open -a`. Tests that set `terminal_app` put a stub `open` first on `PATH`.
- Never delete a real task, worktree or branch. Tests use the temp repos of `tests/conftest.py`.
- Do not write code comments.
- Herdr name rule: `^[a-z][a-z0-9_-]{0,31}$`.
- Jira key rule: `[A-Z][A-Z0-9]+-[0-9]+`, first match, lowercased.
- Squash text: `The branch is merged into origin/<base_ref> (squash merge). Its commits are not lost.` Clean reason: `merged (squash)`.
- Check busy text: `A check is already running.`
- No data format version change. New optional task fields: `display_name`, `rename_error` (terminal rename), `claude_rename_error` (Claude rename), `claude_rename_pending`, `last_check`.
- Run the full suite after each milestone, fix failures, then commit before the next milestone.

## Review Focus

1. A click that starts inside the artifact text (text selection) and ends on the backdrop must not close the viewer. Task 4 tracks the `mousedown` target.
2. A check whose task folder was archived while the check waited must not recreate `.factory/tasks/<id>/`. Task 5: `try_locked` never creates folders, `check_task` loads the task before the lock.
3. A ticket key longer than 29 characters must still give a valid task id. Task 8 cuts the base at `ID_BASE_MAX`.
4. A pending Claude rename that keeps failing (for example the adapter has no `send_prompt`) must not log `rename_failed` on every poll. Task 9 logs only when the reason changes.
5. A tab or workspace rename that fails after the agent rename succeeded must still save the new agent name in the handle, or every later call targets a name that no longer exists. Task 9 tests it with the fake adapter returning problems.

---

### Task 0: Branch and spec commit

**Files:** none changed in code.

- [ ] **Step 1: Save the master commit, then create the branch**

```bash
cd /Users/fabienboismoreau/Documents/Projects/SoftwareFactory/SoftwareFactory
git rev-parse master | tee verification/software-factory/factory-fixes-master-before.txt
git switch -c factory-fixes master
```

Expected: `5c3b44e779c0bab597e3cfe3a4f7e235d5bd3da7`. Task 10 compares `master` with this saved value.

Expected: `Switched to a new branch 'factory-fixes'`. The uncommitted `prompts/factory_skill_creation.md` change and `prompts/factory_fixes.md` move with the working tree. Do not commit them.

- [ ] **Step 2: Commit the spec and the plan**

```bash
git add specs/2026-10-16-factory-fixes-design.md plans/2026-10-16-factory-fixes.md verification/software-factory/factory-fixes-master-before.txt
git commit -m "factory fixes: spec and plan"
```

---

### Task 1: Herdr name limit (milestone 1)

**Files:**
- Modify: `lib/factory/adapters/base.py`
- Modify: `lib/factory/adapters/herdr.py` (`start_session`)
- Modify: `lib/factory/adapters/fake.py` (`start_session`)
- Create: `tests/test_herdr_names.py`
- Modify: `README.md` (Commands: `factory terminal start-session` line)

**Interfaces:**
- Produces: `factory.adapters.base.herdr_name(name: str) -> str`, `HERDR_NAME_RE`. Task 7 uses `herdr_name`.

- [ ] **Step 1: Write the failing tests**

`tests/test_herdr_names.py`:

```python
import json
import os
import stat

import pytest

from conftest import SF, fake_calls
from factory import repo
from factory.adapters.base import HERDR_NAME_RE, herdr_name
from factory.adapters.fake import FakeAdapter
from factory.adapters.herdr import HerdrAdapter

LONG = "library-following-opening-the-review-mr"


def test_long_name_is_valid_and_short():
    name = herdr_name(LONG)
    assert HERDR_NAME_RE.fullmatch(name) and len(name) <= 32
    assert name.startswith("library-following-opening")


def test_names_that_differ_after_32_characters_stay_different():
    a = "a" * 32 + "-first"
    b = "a" * 32 + "-second"
    assert herdr_name(a) != herdr_name(b)
    assert len(herdr_name(a)) <= 32 and len(herdr_name(b)) <= 32


@pytest.mark.parametrize("raw, expected", [
    ("HT-4549 Fix", "ht-4549-fix"),
    ("4549", "t-4549"),
    ("ht-4549", "ht-4549"),
    ("", "t"),
    ("Été!!", "t"),
])
def test_rule(raw, expected):
    assert herdr_name(raw) == expected


def test_fake_adapter_returns_the_real_name(inited):
    adapter = FakeAdapter(repo.load_ctx(cwd=inited.repo))
    handle = adapter.start_session(LONG, inited.repo, "p", [])
    assert handle["agent"] == herdr_name(LONG)
    call = [c for c in fake_calls(inited.fdir) if c["op"] == "start_session"][-1]
    assert call["name"] == LONG and call["herdr_name"] == herdr_name(LONG)


def test_herdr_adapter_starts_with_the_real_name(tmp_path, monkeypatch, origin_repo):
    bindir = tmp_path / "bin"
    bindir.mkdir()
    exe = bindir / "herdr"
    exe.write_text(f"#!/bin/sh\nexec python3 {SF / 'tests' / 'fake_herdr.py'} \"$@\"\n")
    exe.chmod(exe.stat().st_mode | stat.S_IEXEC)
    log = tmp_path / "herdr.log"
    monkeypatch.setenv("PATH", f"{bindir}:{os.environ['PATH']}")
    monkeypatch.setenv("FAKE_HERDR_LOG", str(log))
    monkeypatch.setenv("FAKE_HERDR_MAIN", str(origin_repo))
    adapter = HerdrAdapter(repo.load_ctx(cwd=origin_repo))
    handle = adapter.start_session(LONG, origin_repo / "wt", "p", [])
    real = herdr_name(LONG)
    assert handle["agent"] == real
    calls = [json.loads(line) for line in log.read_text().splitlines()]
    assert any(c[:3] == ["agent", "start", real] for c in calls)
    opened = [c for c in calls if c[:2] == ["worktree", "open"]][0]
    assert opened[opened.index("--label") + 1] == real
    assert not any(LONG in c for c in calls)
```

- [ ] **Step 2: Run the tests, expect failure**

Run: `cd software-factory && uv run --with pytest --with pyyaml pytest -q tests/test_herdr_names.py`
Expected: FAIL, `ImportError: cannot import name 'HERDR_NAME_RE'`.

- [ ] **Step 3: Implement**

`lib/factory/adapters/base.py`, add at the top and after `OPTIONAL`:

```python
import hashlib
import re

from ..errors import FactoryError

OPTIONAL = ("send_prompt", "focus", "state", "wait_idle", "notify")
HERDR_NAME_RE = re.compile(r"[a-z][a-z0-9_-]{0,31}")
HERDR_NAME_MAX = 32
HASH_CHARS = 4


def herdr_name(name):
    if HERDR_NAME_RE.fullmatch(name):
        return name
    text = re.sub(r"[^a-z0-9_-]+", "-", name.lower()).strip("-")
    if not text[:1].isalpha():
        text = f"t-{text}" if text else "t"
    if len(text) <= HERDR_NAME_MAX:
        return text
    digest = hashlib.sha1(name.encode()).hexdigest()[:HASH_CHARS]
    start = text[:HERDR_NAME_MAX - HASH_CHARS - 1].rstrip("-_")
    return f"{start}-{digest}"
```

`lib/factory/adapters/herdr.py`, import and first line of `start_session`:

```python
from .base import OPTIONAL, Adapter, AdapterError, herdr_name
```

```python
    def start_session(self, name, cwd, prompt, claude_args):
        name = herdr_name(name)
        if self.find_agent(name) is not None:
```

The rest of the method already uses `name` and `handle["agent"]`.

`lib/factory/adapters/fake.py`:

```python
from .base import OPTIONAL, Adapter, AdapterError, herdr_name
```

```python
    def start_session(self, name, cwd, prompt, claude_args):
        real = herdr_name(name)
        self.record("start_session", name=name, herdr_name=real, cwd=str(cwd), prompt=prompt, args=list(claude_args))
        if self.cfg().get("fail_start"):
            raise AdapterError("The fake adapter failed to start the session.")
        return {"agent": real, "fake": True}
```

- [ ] **Step 4: Run the new tests, expect pass**

Run: `uv run --with pytest --with pyyaml pytest -q tests/test_herdr_names.py`
Expected: all pass.

- [ ] **Step 5: README**

In `README.md`, replace the line of `factory terminal start-session` with:

```markdown
- `factory terminal start-session <name> <cwd> <prompt> -- <claude args>`: start a Claude session in the terminal. Prints the session handle as JSON. Herdr accepts names that match `^[a-z][a-z0-9_-]{0,31}$`, so the adapter turns any name into a valid one: lowercase, other characters become `-`, the prefix `t-` when it does not start with a letter, and a name longer than 32 characters ends with `-` and 4 characters of a hash. The `agent` field of the handle is the real Herdr name. Later calls use the handle.
```

- [ ] **Step 6: Full suite, then commit**

Run: `uv run --with pytest --with pyyaml pytest -q tests`
Expected: all pass (416 + new). Fix any test that compared the fake `start_session` record exactly.

```bash
git add software-factory/lib/factory/adapters software-factory/tests/test_herdr_names.py software-factory/README.md
git commit -m "herdr: turn any session name into a valid Herdr name"
```

---

### Task 2: Clean after a squash merge (milestone 2)

**Files:**
- Modify: `lib/factory/delete.py`
- Create: `tests/test_squash_merge.py`
- Modify: `README.md` (Clean dialog, Menu "Clean finished tasks")

**Interfaces:**
- Produces: `delete.content_merged(ctx, rev: str, base_ref: str) -> bool`. Plan field `squash_merged: bool`. Clean reason `"merged (squash)"`.

- [ ] **Step 1: Write the failing tests**

`tests/test_squash_merge.py`:

```python
import shutil

import pytest

from conftest import commit_all, git, write_pipeline, write_step
from factory import delete, launch, repo, state

SQUASH_TEXT = "The branch is merged into origin/main (squash merge). Its commits are not lost."


@pytest.fixture
def env(inited):
    write_step(inited.fdir, "w", {})
    write_pipeline(inited.fdir, {"id": "b", "inputs": {"branch": {"description": "b"}}, "steps": ["w"]})
    write_pipeline(inited.fdir, {"id": "nb", "steps": ["w"]})
    ctx = repo.load_ctx(cwd=inited.repo)
    other = inited.work / "other"
    git("clone", str(inited.work / "origin.git"), str(other), cwd=inited.work)
    git("config", "user.name", "Test", cwd=other)
    git("config", "user.email", "test@example.com", cwd=other)
    return inited, ctx, other


def task_with_commit(inited, ctx, branch, name="f.txt", text="one\n"):
    task = launch.launch(ctx, "b", f"Task {branch}", {"branch": branch})
    wt = inited.worktrees / task["id"]
    (wt / name).write_text(text)
    commit_all(wt, f"change {name}")
    git("push", "-u", "origin", branch, cwd=wt)
    return task, wt


def squash_into_main(other, branch, delete_remote=True):
    git("fetch", "origin", cwd=other)
    git("checkout", "main", cwd=other)
    git("pull", "origin", "main", cwd=other)
    git("merge", "--squash", f"origin/{branch}", cwd=other)
    git("commit", "-m", f"squash {branch}", cwd=other)
    git("push", "origin", "main", cwd=other)
    if delete_remote:
        git("push", "origin", "--delete", branch, cwd=other)


def finish(ctx, tid):
    state.update(ctx, tid, lambda t: state.set_status(t, "finished"))


def test_squash_merged_branch_loses_nothing_and_is_deleted(env):
    inited, ctx, other = env
    task, _ = task_with_commit(inited, ctx, "feat/sq")
    squash_into_main(other, "feat/sq")
    plan = delete.plan_delete(ctx, task["id"])
    assert plan["squash_merged"] and plan["unpushed"] == [] and plan["delete_branch"] and not plan["needs_confirm"]
    assert SQUASH_TEXT in delete.render_plan(plan)
    delete.delete(ctx, task["id"])
    assert git("branch", "--list", "feat/sq", cwd=inited.repo) == ""


def test_local_commit_after_squash_is_listed(env):
    inited, ctx, other = env
    task, wt = task_with_commit(inited, ctx, "feat/late")
    squash_into_main(other, "feat/late")
    (wt / "late.txt").write_text("late\n")
    commit_all(wt, "late work")
    plan = delete.plan_delete(ctx, task["id"])
    assert not plan["squash_merged"] and plan["needs_confirm"]
    assert any("late work" in line for line in plan["unpushed"])
    assert not plan["delete_branch"]


def test_merge_commit_is_unchanged(env):
    inited, ctx, other = env
    task, _ = task_with_commit(inited, ctx, "feat/mc")
    git("fetch", "origin", cwd=other)
    git("merge", "--no-ff", "-m", "merge", "origin/feat/mc", cwd=other)
    git("push", "origin", "main", cwd=other)
    plan = delete.plan_delete(ctx, task["id"])
    assert plan["unpushed"] == [] and plan["delete_branch"] and not plan["squash_merged"]


def test_never_pushed_branch_is_unchanged(env):
    inited, ctx, _ = env
    task = launch.launch(ctx, "b", "Local only", {"branch": "feat/local"})
    wt = inited.worktrees / task["id"]
    (wt / "l.txt").write_text("l\n")
    commit_all(wt, "local work")
    plan = delete.plan_delete(ctx, task["id"])
    assert plan["needs_confirm"] and not plan["delete_branch"] and not plan["squash_merged"]
    assert any("local work" in line for line in plan["unpushed"])


def test_clean_reports_squash_when_worktree_is_gone(env):
    inited, ctx, other = env
    task, wt = task_with_commit(inited, ctx, "feat/gone")
    squash_into_main(other, "feat/gone")
    git("worktree", "remove", "--force", str(wt), cwd=inited.repo)
    finish(ctx, task["id"])
    rows = {r["id"]: r for r in inited.factory.json("clean")}
    assert rows[task["id"]]["merged"] and rows[task["id"]]["reason"] == "merged (squash)"


def test_later_change_of_same_lines_is_not_merged(env):
    inited, ctx, other = env
    task, _ = task_with_commit(inited, ctx, "feat/conf", name="README.md", text="branch\n")
    squash_into_main(other, "feat/conf", delete_remote=False)
    (other / "README.md").write_text("main later\n")
    commit_all(other, "main later")
    git("push", "origin", "main", cwd=other)
    finish(ctx, task["id"])
    rows = {r["id"]: r for r in inited.factory.json("clean")}
    assert not rows[task["id"]]["merged"] and rows[task["id"]]["reason"] == "not merged"
```

- [ ] **Step 2: Run, expect failure**

Run: `uv run --with pytest --with pyyaml pytest -q tests/test_squash_merge.py`
Expected: FAIL with `KeyError: 'squash_merged'` and a wrong clean reason.

- [ ] **Step 3: Implement in `lib/factory/delete.py`**

Add after `is_ancestor`:

```python
def content_merged(ctx, rev, base_ref):
    base = f"refs/remotes/origin/{base_ref}"
    if not ref_exists(ctx.main, base):
        return False
    r = repo.git(["merge-tree", "--write-tree", base, rev], ctx.main, check=False)
    if r.returncode != 0 or not r.stdout.strip():
        return False
    base_tree = repo.git(["rev-parse", f"{base}^{{tree}}"], ctx.main, check=False).stdout.strip()
    return r.stdout.splitlines()[0].strip() == base_tree


def head_commit(worktree):
    return repo.git(["rev-parse", "HEAD"], worktree, check=False).stdout.strip()
```

In `merge_state`, right after the `is_ancestor` check and before the `tracks_own_branch` check:

```python
    if ref_exists(ctx.main, local) and content_merged(ctx, local, base_ref):
        return True, "merged (squash)"
```

The order matters. A squash-merged branch was usually pushed with `-u` and its remote branch deleted, so the `tracks_own_branch` check would also match. The squash check must come first so the reason is "merged (squash)".

The test of a later change on `main` keeps the remote branch (`delete_remote=False`). With the remote branch deleted, the existing rule "pushed, and its remote branch was deleted" counts it as merged, as today.

Replace `plan_delete` with:

```python
def plan_delete(ctx, tid):
    task = state.load(ctx, tid)
    worktree = task.get("worktree")
    base_ref = task.get("base_ref") or "main"
    plan = {
        "task_id": tid, "session_id": task.get("session_id"), "terminal_handle": task.get("terminal_handle"),
        "worktree": worktree, "branch": None, "base_ref": base_ref, "uncommitted": [], "unpushed": [],
        "squash_merged": False, "delete_branch": False, "needs_confirm": False, "check_errors": [],
    }
    errors = plan["check_errors"]
    if worktree and Path(worktree).exists():
        repo.git(["fetch", "origin", base_ref], ctx.main, check=False)
        plan["uncommitted"] = git_lines(["status", "--porcelain"], worktree, "Cannot check uncommitted changes", errors)
        branch = current_branch(worktree)
        plan["branch"] = branch
        upstream = f"origin/{branch}" if branch and ref_exists(worktree, f"refs/remotes/origin/{branch}") else f"origin/{base_ref}"
        plan["unpushed"] = git_lines(["log", "--oneline", f"{upstream}..HEAD"], worktree, "Cannot check unpushed commits", errors)
        if plan["unpushed"] and not errors:
            rev = f"refs/heads/{branch}" if branch else head_commit(worktree)
            if rev and content_merged(ctx, rev, base_ref):
                plan["squash_merged"] = True
                plan["unpushed"] = []
        if branch:
            merged = plan["squash_merged"] or branch_merged_or_pushed(ctx, branch, base_ref)
            plan["delete_branch"] = not errors and not plan["unpushed"] and merged
    plan["needs_confirm"] = bool(plan["uncommitted"] or plan["unpushed"] or errors)
    return plan
```

In `render_plan`, after the `- The task folder moves ...` line:

```python
    if plan.get("squash_merged"):
        lines.append(f"The branch is merged into origin/{plan['base_ref']} (squash merge). Its commits are not lost.")
```

- [ ] **Step 4: Run new tests, expect pass**

Run: `uv run --with pytest --with pyyaml pytest -q tests/test_squash_merge.py tests/test_delete.py tests/test_clean.py`
Expected: all pass.

- [ ] **Step 5: README**

Under "Clean dialog", after step 2, add:

```markdown
A branch merged with a squash merge counts as merged when its content is already in `origin/<base_ref>`: `git merge-tree --write-tree` gives the tree of `origin/<base_ref>`. Its commits are not listed as lost, the reason is "merged (squash)", and the delete removes the local branch. When `origin/<base_ref>` later changed the same lines, the task counts as not merged, and the delete asks for `--confirm-unpushed`.
```

In "Menu actions", "Clean finished tasks" line, append: ` A squash-merged branch counts as merged.`

- [ ] **Step 6: Full suite, then commit**

Run: `uv run --with pytest --with pyyaml pytest -q tests`. Expected: all pass.

```bash
git add software-factory/lib/factory/delete.py software-factory/tests/test_squash_merge.py software-factory/README.md
git commit -m "clean: a squash-merged branch counts as merged"
```

---

### Task 3: Artifact viewer CSS and modal structure (milestone 3, part 1)

**Files:**
- Modify: `lib/factory/web/dashboard.html`
- Create: `tests/test_dashboard_page.py`

**Interfaces:**
- Produces in the page: `showModal({ title, content, dismissable, headButtons })`, `openModal(title, ...content)` (unchanged signature, calls `showModal`), `#modal .bar`, `#modal .content`. Task 4 uses them.

- [ ] **Step 1: Write the failing page test**

`tests/test_dashboard_page.py`:

```python
from conftest import SF

PAGE = (SF / "lib" / "factory" / "web" / "dashboard.html").read_text()


def test_modal_has_fixed_bar_and_scrolling_content():
    assert "#modal .bar" in PAGE and "#modal .content" in PAGE
    assert "max-height: calc(100vh - 2rem)" in PAGE


def test_artifact_viewer_is_dismissable():
    assert "dismissable: true" in PAGE
    assert 'e.key !== "Escape"' in PAGE
    assert "Discard the typed text?" in PAGE
    assert "pressedOnBackdrop" in PAGE
```

- [ ] **Step 2: Run, expect failure**

Run: `uv run --with pytest --with pyyaml pytest -q tests/test_dashboard_page.py`. Expected: FAIL.

- [ ] **Step 3: CSS**

Replace the two lines `#modal .box {...}` and `#modal h3 {...}` with:

```css
#modal .box { background: var(--bg); border: 1px solid var(--line); border-radius: 10px; width: min(720px, 92vw); max-height: calc(100vh - 2rem); display: flex; flex-direction: column; overflow: hidden; box-sizing: border-box; }
#modal .bar { flex: none; display: flex; gap: 8px; align-items: center; justify-content: space-between; padding: 12px 16px; border-bottom: 1px solid var(--line); }
#modal .bar h3 { margin: 0; overflow-wrap: anywhere; }
#modal .content { flex: 1 1 auto; min-height: 0; overflow: auto; padding: 12px 16px 16px; }
#modal .discard { display: flex; gap: 8px; align-items: center; justify-content: flex-end; padding: 8px 16px; border-bottom: 1px solid var(--line); background: var(--awaiting_approval); }
```

- [ ] **Step 4: Modal functions**

Replace `closeModal` and `openModal` with:

```js
function closeModal() { const m = byId("modal"); m.hidden = true; clear(m); m.dataset.dismissable = ""; state.lastKey = null; state.modalStart = new WeakMap(); }
function textFields(m) { return [...m.querySelectorAll("textarea, input:not([type]), input[type=text]")]; }
function showModal({ title, content, dismissable = false, headButtons = [] }) {
  const m = clear(byId("modal"));
  m.append(el("div", { class: "box" }, el("div", { class: "bar" }, el("h3", {}, title), ...headButtons), el("div", { class: "content" }, ...content)));
  m.dataset.dismissable = dismissable ? "1" : "";
  m.hidden = false;
  state.modalStart = new WeakMap(textFields(m).map((n) => [n, n.value]));
  return m;
}
function openModal(title, ...content) { return showModal({ title, content }); }
```

Add `modalStart: new WeakMap()` to the `state` object literal.

- [ ] **Step 5: Run the page test**

Run: `uv run --with pytest --with pyyaml pytest -q tests/test_dashboard_page.py::test_modal_has_fixed_bar_and_scrolling_content`. Expected: PASS. The other test still fails until Task 4.

No commit yet: Task 4 finishes the milestone.

---

### Task 4: Artifact viewer close behavior (milestone 3, part 2)

**Files:**
- Modify: `lib/factory/web/dashboard.html`
- Create: `verification/software-factory/factory-fixes-artifact-viewer.md`
- Modify: `README.md` (Dashboard card list, artifacts line)

**Interfaces:**
- Consumes: `showModal`, `textFields`, `state.modalStart` from Task 3.

- [ ] **Step 1: Viewer and handlers**

Replace `openArtifact` with:

```js
async function openArtifact(tid, name) {
  const data = await api(`/api/tasks/${tid}/artifacts/${encodeURIComponent(name)}`);
  showModal({ title: `${tid} / ${name}`, content: [el("pre", {}, data.text)], dismissable: true, headButtons: [closeButton()] });
}
```

Add after `closeButton`:

```js
function typedText() {
  const m = byId("modal");
  return textFields(m).some((n) => n.value !== (state.modalStart.has(n) ? state.modalStart.get(n) : n.defaultValue));
}
function askDiscard() {
  const box = byId("modal").querySelector(".box");
  if (!box || box.querySelector(".discard")) return;
  const row = el("div", { class: "discard" }, el("span", {}, "Discard the typed text?"),
    el("button", { class: "danger", onclick: closeModal }, "Discard"),
    el("button", { onclick: () => row.remove() }, "Keep editing"));
  box.querySelector(".bar").after(row);
}
let pressedOnBackdrop = false;
byId("modal").addEventListener("mousedown", (e) => { pressedOnBackdrop = e.target === byId("modal"); });
byId("modal").addEventListener("click", (e) => {
  const m = byId("modal");
  if (e.target === m && pressedOnBackdrop && m.dataset.dismissable) closeModal();
  pressedOnBackdrop = false;
});
document.addEventListener("keydown", (e) => {
  if (e.key !== "Escape" || !modalOpen()) return;
  e.preventDefault();
  const m = byId("modal");
  const discard = m.querySelector(".discard");
  if (discard) { discard.remove(); return; }
  if (m.dataset.dismissable || !typedText()) closeModal(); else askDiscard();
});
```

These lines must come after `const byId = ...` and after the `<div id="modal">` exists. The script tag is at the end of `<body>`, so `byId("modal")` exists.

- [ ] **Step 2: Run the page tests**

Run: `uv run --with pytest --with pyyaml pytest -q tests/test_dashboard_page.py`. Expected: PASS.

- [ ] **Step 3: Browser check setup**

Make a throwaway repo in the scratchpad, never in a real repo:

```bash
S=/private/tmp/claude-501/-Users-fabienboismoreau-Documents-Projects-SoftwareFactory-SoftwareFactory/d460c30b-f6d9-416d-9a33-9f63cde0150d/scratchpad/viewer
rm -rf "$S" && mkdir -p "$S" && cd "$S"
git init -q --bare -b main origin.git && git clone -q origin.git repo && cd repo
git -c user.name=T -c user.email=t@e commit -q --allow-empty -m init && git push -q origin HEAD:main
export FACTORY_TERMINAL=fake FACTORY_NO_OPEN=1
F=/Users/fabienboismoreau/Documents/Projects/SoftwareFactory/SoftwareFactory/software-factory/bin/factory
python3 $F init --library "$S/lib" --create-library
python3 - <<'EOF'
import sys
sys.path.insert(0, "/Users/fabienboismoreau/Documents/Projects/SoftwareFactory/SoftwareFactory/software-factory/lib")
sys.path.insert(0, "/Users/fabienboismoreau/Documents/Projects/SoftwareFactory/SoftwareFactory/software-factory/tests")
from conftest import make_task
from factory import repo, state
ctx = repo.load_ctx()
make_task(ctx, tid="t1", worktree=str(ctx.main), terminal_handle={"agent": "t1"}, status="awaiting_approval")
state.artifact_path(ctx, "t1", "short.md").write_text("line 1\nline 2\nline 3\n")
state.artifact_path(ctx, "t1", "long.md").write_text("".join(f"line {i}\n" for i in range(1, 2001)))
EOF
python3 $F dashboard
```

Expected: a URL `http://127.0.0.1:<port>/dashboard?token=...`.

- [ ] **Step 4: Browser check**

Use the `claude-in-chrome` skill. Open the URL in a new tab. For `short.md` and for `long.md`:
1. Click the name. The viewer opens. The title bar with "Close" is visible at the top. For `long.md`, scroll inside the text: the bar stays visible.
2. Press Escape: the viewer closes.
3. Open again. Click the dark area outside the box: it closes.
4. Open again. Click "Close": it closes.
5. Open again. Select text inside the viewer by dragging, release the mouse on the dark area: the viewer stays open.

Then "Request changes" on t1 (status `awaiting_approval`):
6. Type "abc". Click outside: the form stays open.
7. Press Escape: "Discard the typed text?" appears. Click "Keep editing": the text is still there. Escape again, then "Discard": it closes.
8. Open again with no text, press Escape: it closes at once.

Then stop the server: `python3 $F server stop` (in `$S/repo`).

- [ ] **Step 5: Write the result file**

`verification/software-factory/factory-fixes-artifact-viewer.md`: the setup commands of Step 3, the 8 checks of Step 4, and for each one the observed result (PASS or FAIL and what happened). Fix and recheck any FAIL.

- [ ] **Step 6: README**

In "Dashboard > Tasks view", replace `- The artifacts of the task. Click a name to read it.` with:

```markdown
- The artifacts of the task. Click a name to read it. The viewer closes with Escape, a click outside it, or its Close button. Its title bar stays visible, and the text scrolls inside it. A form, for example "Request changes", never closes on a click outside. Escape on a form with typed text asks "Discard the typed text?".
```

- [ ] **Step 7: Full suite, then commit**

Run: `uv run --with pytest --with pyyaml pytest -q tests`. Expected: all pass.

```bash
git add software-factory/lib/factory/web/dashboard.html software-factory/tests/test_dashboard_page.py software-factory/README.md verification/software-factory/factory-fixes-artifact-viewer.md
git commit -m "dashboard: artifact viewer closes with Escape and a click outside"
```

---

### Task 5: One-task check with a cross-process lock (milestone 4, part 1)

**Files:**
- Modify: `lib/factory/fsio.py` (add `try_locked`)
- Modify: `lib/factory/engine.py` (`check_task`, `poll`, remove `poll_task`)
- Modify: `lib/factory/commands.py` (`poll_cmd`)
- Create: `tests/test_check_now.py` (CLI and lock tests)

**Interfaces:**
- Produces: `fsio.try_locked(path) -> contextmanager[bool]` (lock file `<path>.lock`, never creates folders). `engine.check_task(ctx, tid) -> dict` with keys `id`, `ended`, `output`, `error`, `busy`. `engine.CHECK_BUSY`, `engine.NOT_WAITING`. Task field `last_check = {"at": iso, "ended": bool, "output": str}`. Task 6 and Task 7 use `try_locked`. Task 6 uses `check_task`.

- [ ] **Step 1: Write the failing tests**

`tests/test_check_now.py`:

```python
import subprocess
import sys
import threading

import pytest

from conftest import BIN, events, task_from_pipeline, task_json, write_pipeline, write_step
from factory import engine, repo


@pytest.fixture
def waits(inited, monkeypatch):
    for key, value in inited.factory.env.items():
        monkeypatch.setenv(key, value)
    flag = inited.work / "ok.flag"
    write_step(inited.fdir, "wait-review", {"wait_external": True, "done_when": "Approved.",
                                            "done_check": f"echo 'CodeRabbit review pending'; sleep ${{CHECK_SLEEP:-0}}; test -f {flag}"})
    write_step(inited.fdir, "after", {})
    write_pipeline(inited.fdir, {"id": "w", "steps": ["wait-review", "after"]})
    return inited, flag


def waiting_task(inited, tid="t1"):
    task_from_pipeline(inited, "w", tid=tid, worktree=str(inited.repo), terminal_handle={"agent": tid},
                       status="waiting_external", started=0)
    return tid


def ended_count(fdir, tid):
    return sum(1 for e in events(fdir, tid) if e["type"] == "external_event")


def sent_count(fdir, tid):
    return sum(1 for e in events(fdir, tid) if e["type"] == "prompt_sent")


def test_poll_task_failing_check_saves_result(waits):
    inited, _ = waits
    waiting_task(inited)
    rows = inited.factory.json("poll", "--task", "t1")
    assert rows[0]["ended"] is False
    last = task_json(inited.fdir, "t1")["last_check"]
    assert last["ended"] is False and "CodeRabbit review pending" in last["output"] and last["at"]
    assert task_json(inited.fdir, "t1")["status"] == "waiting_external"


def test_poll_task_passing_check_ends_wait(waits):
    inited, flag = waits
    waiting_task(inited)
    flag.write_text("ok")
    rows = inited.factory.json("poll", "--task", "t1")
    assert rows[0]["ended"] is True
    assert task_json(inited.fdir, "t1")["last_check"]["ended"] is True
    assert task_json(inited.fdir, "t1")["status"] != "waiting_external"


def test_poll_task_not_waiting_runs_nothing(waits):
    inited, _ = waits
    task_from_pipeline(inited, "w", tid="t2", worktree=str(inited.repo))
    rows = inited.factory.json("poll", "--task", "t2")
    assert rows[0]["error"] == engine.NOT_WAITING
    assert "last_check" not in task_json(inited.fdir, "t2")


def test_two_threads_end_the_wait_once(waits, monkeypatch):
    inited, flag = waits
    waiting_task(inited)
    flag.write_text("ok")
    monkeypatch.setenv("CHECK_SLEEP", "1")
    ctx = repo.load_ctx(cwd=inited.repo)
    results = []
    threads = [threading.Thread(target=lambda: results.append(engine.check_task(ctx, "t1"))) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(r["ended"] for r in results) == [False, True]
    assert any(r["error"] in (engine.CHECK_BUSY, engine.NOT_WAITING) for r in results)
    assert ended_count(inited.fdir, "t1") == 1
    assert sent_count(inited.fdir, "t1") == 1


def test_cli_and_in_process_check_end_the_wait_once(waits, monkeypatch):
    inited, flag = waits
    waiting_task(inited)
    flag.write_text("ok")
    monkeypatch.setenv("CHECK_SLEEP", "1")
    env = {**inited.factory.env, "CHECK_SLEEP": "1"}
    cli = subprocess.Popen([sys.executable, str(BIN), "poll", "--task", "t1"], cwd=inited.repo, env=env,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    ctx = repo.load_ctx(cwd=inited.repo)
    engine.check_task(ctx, "t1")
    cli.wait(timeout=60)
    assert ended_count(inited.fdir, "t1") == 1
    assert sent_count(inited.fdir, "t1") == 1
```

- [ ] **Step 2: Run, expect failure**

Run: `uv run --with pytest --with pyyaml pytest -q tests/test_check_now.py`
Expected: FAIL, `factory poll` does not accept a task, `engine.check_task` missing.

Note: `--task` is already a common option, so `factory poll --task t1` parses. Today it is ignored.

- [ ] **Step 3: `try_locked` in `lib/factory/fsio.py`**

After `locked`:

```python
@contextmanager
def try_locked(path):
    path = Path(path)
    lock = path.with_name(path.name + ".lock")
    with open(lock, "a") as f:
        try:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            yield False
            return
        try:
            yield True
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)
```

- [ ] **Step 4: `check_task` in `lib/factory/engine.py`**

Add `fsio` to the import line: `from . import config, events, fsio, keys, loops, render, repo, session, state`.

Add constants after `MAX_JUMPS`:

```python
CHECK_BUSY = "A check is already running."
NOT_WAITING = "The task does not wait on a done check."
CHECK_OUTPUT_CHARS = 500
```

Replace `poll_task` and `poll` with:

```python
def check_result(tid, ended=False, output=None, error=None, busy=False):
    return {"id": tid, "ended": ended, "output": output, "error": error, "busy": busy}


def waiting_step(ctx, task):
    if task["status"] != "waiting_external":
        return None
    entry, step = load_step(ctx, task)
    return (entry, step) if step.done_check else None


def check_task(ctx, tid):
    state.load(ctx, tid)
    with fsio.try_locked(state.task_dir(ctx, tid) / "check") as got:
        if not got:
            return check_result(tid, error=CHECK_BUSY, busy=True)
        task = state.load(ctx, tid)
        found = waiting_step(ctx, task)
        if found is None:
            return check_result(tid, error=NOT_WAITING)
        entry, step = found
        values, _ = config.resolve(ctx, step, entry.get("with"))
        ok, output = run_check(ctx, task, step, step.done_check, POLL_CHECK_TIMEOUT, values)
        tail = output[-CHECK_OUTPUT_CHARS:]
        record = {"at": state.now(), "ended": ok, "output": tail}
        state.update(ctx, tid, lambda t: t.__setitem__("last_check", record))
        if ok:
            end_wait(ctx, tid, "check")
        return check_result(tid, ended=ok, output=None if ok else tail)


def poll(ctx):
    results = []
    for task in state.list_tasks(ctx):
        try:
            if waiting_step(ctx, task) is None:
                continue
            results.append(check_task(ctx, task["id"]))
        except Exception as e:
            results.append(check_result(task["id"], error=str(e)))
    return results
```

`grep -rn poll_task lib tests` must return nothing after this change. If a test imports `poll_task`, change it to `check_task`.

- [ ] **Step 5: CLI in `lib/factory/commands.py`**

Replace `poll_cmd`:

```python
@cli.command("poll")
def poll_cmd(args):
    from . import engine
    ctx = ctx_of(args)
    results = [engine.check_task(ctx, args.task)] if args.task else engine.poll(ctx)
    if args.json:
        cli.emit(results, True)
        return
    if not results:
        print("No task waits on a done check.")
    for r in results:
        print(f"{r['id']}: " + ("the wait ended." if r["ended"] else "still waiting.") + (f" Error: {r['error']}" if r["error"] else ""))
```

- [ ] **Step 6: Run, expect pass**

Run: `uv run --with pytest --with pyyaml pytest -q tests/test_check_now.py tests/test_waiting.py tests/test_background_poll.py`
Expected: all pass.

No commit yet: Task 6 finishes milestone 4.

---

### Task 6: Countdown, API and "Check now" (milestone 4, part 2)

**Files:**
- Modify: `lib/factory/server.py` (`next_poll`)
- Modify: `lib/factory/board.py` (`task_row`, `task_rows`)
- Modify: `lib/factory/api.py` (`tasks`, new `check` route)
- Modify: `lib/factory/web/dashboard.html`
- Modify: `tests/test_check_now.py` (API tests)
- Modify: `README.md`, `skills/software-factory/SKILL.md`

**Interfaces:**
- Consumes: `engine.check_task` from Task 5.
- Produces: `board.task_rows(ctx, next_poll=None)`, `board.task_row(ctx, task, reg=None, next_poll=None)`. Row fields `next_check_at` (ISO or None) and `last_check` (dict or None). Route `POST /api/tasks/<id>/check -> {"job": id}`. Task 7 adds fields to the same row.

- [ ] **Step 1: Write the failing API tests**

Append to `tests/test_check_now.py`:

```python
import time

from serverutil import info, request


@pytest.fixture
def served(waits):
    inited, flag = waits
    inited.factory("dashboard", env={"FACTORY_POLL_SECONDS": "600", "CHECK_SLEEP": "5"})
    yield inited, flag, info(inited.fdir)
    inited.factory("server", "stop", check=False)


def test_api_returns_next_check_time(served):
    inited, _, i = served
    waiting_task(inited)
    end = time.time() + 5
    row = None
    while time.time() < end:
        row = request(i, "GET", "/api/tasks")[1][0]
        if row["next_check_at"]:
            break
        time.sleep(0.2)
    assert row["next_check_at"]
    assert row["last_check"] is None


def test_check_now_answers_at_once_with_a_job(served):
    inited, flag, i = served
    waiting_task(inited)
    flag.write_text("ok")
    start = time.time()
    status, res = request(i, "POST", "/api/tasks/t1/check", {})
    assert status == 200 and res["job"] and time.time() - start < 1
    start = time.time()
    assert request(i, "GET", "/api/tasks")[0] == 200 and time.time() - start < 2
    end = time.time() + 30
    job = None
    while time.time() < end:
        job = request(i, "GET", f"/api/jobs/{res['job']}")[1]
        if job["status"] != "running":
            break
        time.sleep(0.3)
    assert job["status"] == "done" and job["result"]["ended"] is True
    assert ended_count(inited.fdir, "t1") == 1


def test_paused_task_has_no_countdown(served):
    inited, _, i = served
    task_from_pipeline(inited, "w", tid="t3", worktree=str(inited.repo), status="paused")
    row = request(i, "GET", "/api/tasks")[1][0]
    assert row["next_check_at"] is None
```

- [ ] **Step 2: Run, expect failure**

Run: `uv run --with pytest --with pyyaml pytest -q tests/test_check_now.py -k "api or check_now or paused"`
Expected: FAIL, `KeyError: 'next_check_at'`.

- [ ] **Step 3: Server**

In `Server.__init__`, after `self.jobs = {}`: `self.next_poll = None`.

Replace `poll_loop`:

```python
    def poll_loop(self):
        from . import engine
        while True:
            interval = self.poll_interval()
            self.next_poll = time.time() + interval
            time.sleep(interval)
            try:
                engine.poll(self.ctx)
            except Exception as e:
                print(f"poll failed: {e}", file=sys.stderr, flush=True)
```

- [ ] **Step 4: Board rows**

In `lib/factory/board.py`, add `from datetime import datetime, timezone` at the top, and:

```python
def iso_time(epoch):
    return datetime.fromtimestamp(epoch, timezone.utc).isoformat(timespec="seconds") if epoch else None
```

Change `task_row(ctx, task, reg=None)` to `task_row(ctx, task, reg=None, next_poll=None)`. Before the `return`, add `has_check = bool(waiting and step and step.done_check)`. Replace the `wait_has_check` entry and add two fields:

```python
        "wait_has_check": bool(step and step.done_check) if waiting else None,
        "next_check_at": iso_time(next_poll) if has_check else None,
        "last_check": task.get("last_check") if has_check else None,
```

Change `task_rows`:

```python
def task_rows(ctx, next_poll=None):
    reg = Registry.load(ctx)
    tasks = sorted(state.list_tasks(ctx), key=lambda t: (PRIORITY.get(t["status"], len(PRIORITY)), t["created_at"]))
    return [task_row(ctx, t, reg, next_poll) for t in tasks]
```

- [ ] **Step 5: API**

In `lib/factory/api.py`, change `tasks`:

```python
@route("GET", "/api/tasks")
def tasks(server, query, body):
    from . import board
    return board.task_rows(server.ctx, server.next_poll)
```

Add after `external_done`:

```python
@route("POST", f"/api/tasks/{TASK}/check")
def check_now(server, tid, query, body):
    from . import engine, state
    state.load(server.ctx, tid)
    return {"job": server.start_job(lambda: engine.check_task(server.ctx, tid))}
```

- [ ] **Step 6: Run API tests, expect pass**

Run: `uv run --with pytest --with pyyaml pytest -q tests/test_check_now.py tests/test_dashboard_api.py tests/test_board.py`
Expected: all pass.

- [ ] **Step 7: Dashboard card**

Add `checking: new Set()` to the `state` literal.

Add after `loopText`:

```js
function countdownText(iso) {
  const s = Math.round((Date.parse(iso) - Date.now()) / 1000);
  if (isNaN(s)) return "";
  if (s <= 0) return "Next check soon";
  return `Next check in ${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}
function lastCheckText(c) {
  if (c.ended) return "the wait ended";
  const line = (c.output || "").trim().split("\n").pop();
  return line ? `still waiting: ${line}` : "still waiting";
}
function checkBlock(t) {
  const box = el("div", { class: "check" });
  if (t.next_check_at) box.append(el("div", { "data-next-check": t.next_check_at }, countdownText(t.next_check_at)));
  if (t.last_check) box.append(el("div", { class: "muted" }, `Last check: ${new Date(t.last_check.at).toLocaleTimeString()}, ${lastCheckText(t.last_check)}`));
  return box;
}
async function checkNow(t) {
  state.checking.add(t.id);
  render();
  try {
    const res = await api(`/api/tasks/${t.id}/check`, {});
    const job = await waitJob(res.job);
    if (job.status === "done" && job.result.error) showError(job.result.error);
  } finally {
    state.checking.delete(t.id);
    state.lastKey = null;
    await refresh(true);
  }
}
```

In `taskCard`, before `card.append(taskButtons(t));`:

```js
  if (t.status === "waiting_external" && t.wait_has_check) card.append(checkBlock(t));
```

In `taskButtons`, after the "Mark done" line:

```js
  if (t.status === "waiting_external" && t.wait_has_check) {
    row.append(state.checking.has(t.id) ? button("Checking…", () => {}, { disabled: true }) : button("Check now", () => checkNow(t)));
  }
```

At the end of the script, after `setInterval(refresh, REFRESH_MS);`:

```js
setInterval(() => { for (const n of document.querySelectorAll("[data-next-check]")) n.textContent = countdownText(n.dataset.nextCheck); }, 1000);
```

Add to `tests/test_dashboard_page.py`:

```python
def test_card_has_countdown_and_check_now():
    assert "data-next-check" in PAGE and "Next check in" in PAGE
    assert "Check now" in PAGE and "Checking…" in PAGE
    assert "/check`" in PAGE
```

- [ ] **Step 8: Browser check of the card**

Reuse the Task 4 scratchpad repo. Add a step file with a 5-second check and a waiting task:

```bash
cd "$S/repo"
mkdir -p .factory/steps .factory/pipelines
printf -- '---\nid: wait-review\ndescription: Wait\ncategory: test\ntype: ai\nwait_external: true\ndone_when: Approved.\ndone_check: "echo CodeRabbit review pending; sleep 5; false"\n---\n\nWait.\n' > .factory/steps/wait-review.md
printf 'id: w\ndescription: W\nsteps:\n  - wait-review\n' > .factory/pipelines/w.yaml
python3 - <<'EOF'
import sys
sys.path.insert(0, "/Users/fabienboismoreau/Documents/Projects/SoftwareFactory/SoftwareFactory/software-factory/lib")
sys.path.insert(0, "/Users/fabienboismoreau/Documents/Projects/SoftwareFactory/SoftwareFactory/software-factory/tests")
from conftest import make_task
from factory import repo
ctx = repo.load_ctx()
make_task(ctx, tid="t2", worktree=str(ctx.main), terminal_handle={"agent": "t2"}, pipeline="w", status="waiting_external", started=0,
          steps=[{"id": "wait-review", "path": ["wait-review"], "with": {}, "column": None, "model": None, "effort": None}])
EOF
python3 $F server stop; FACTORY_POLL_SECONDS=120 python3 $F dashboard
```

In the browser: the t2 card shows "Next check in 1:59" and it counts down each second. Click "Check now": it shows "Checking…" and is disabled for about 5 seconds, while the page still scrolls and other buttons work. Then the card shows "Last check: <time>, still waiting: CodeRabbit review pending". Append the steps and the results to `verification/software-factory/factory-fixes-artifact-viewer.md` under a heading "Poll countdown and Check now". Stop the server.

- [ ] **Step 9: README and skill**

`README.md`, Commands: replace `- \`factory poll\`: check the waiting tasks.` with:

```markdown
- `factory poll [--task <id>]`: run the done check of every waiting task, or of one task. Only one check of a task runs at a time, across processes (lock file `.factory/tasks/<id>/check.lock`). A second check returns "A check is already running." After each check, the task saves `last_check`: the time, whether the wait ended, and the end of the output.
```

`README.md`, Dashboard card list, after the status lines:

```markdown
- For a task that is `waiting_external` on a step with a `done_check`: "Next check in m:ss", counted down in the page, and the last check with its time and result.
```

Card buttons list, after "Mark done":

```markdown
- **Check now**: shown when the status is `waiting_external` and the wait has a done check. It runs `factory poll --task <id>` as a background job. The button shows "Checking…" until the result.
```

`skills/software-factory/SKILL.md` line 42: replace `run \`factory poll\`.` with `run \`factory poll\` (\`factory poll --task <id>\` checks one task).`

- [ ] **Step 10: Full suite, then commit**

Run: `uv run --with pytest --with pyyaml pytest -q tests`. Expected: all pass.

```bash
git add software-factory/lib/factory software-factory/tests software-factory/README.md software-factory/skills verification/software-factory/factory-fixes-artifact-viewer.md
git commit -m "poll: countdown, Check now and one check per task at a time"
```

---

### Task 7: Focus brings the terminal app to the front (milestone 5)

**Files:**
- Modify: `lib/factory/session.py` (`focus`, new `bring_to_front`, `front_text`)
- Modify: `lib/factory/commands.py` (`focus_cmd`)
- Modify: `lib/factory/api.py` (`focus` returns the result)
- Modify: `lib/factory/web/dashboard.html` (Focus button)
- Modify: `skills/software-factory/SKILL.md` (Focus line)
- Create: `tests/test_focus_front.py`
- Modify: `README.md`

**Interfaces:**
- Produces: `session.focus(ctx, tid) -> {"front": "ok"|"off"|"ask"|"failed", "app"?: str, "message"?: str}`, `session.is_macos() -> bool`, `session.front_text(result) -> str`. Config: section `terminal`, key `terminal_app`.

- [ ] **Step 1: Write the failing tests**

`tests/test_focus_front.py`:

```python
import os
import stat

import pytest

from conftest import fake_calls, make_task
from factory import config, repo, session


@pytest.fixture
def focus_env(inited, monkeypatch, tmp_path):
    for key, value in inited.factory.env.items():
        monkeypatch.setenv(key, value)
    bindir = tmp_path / "bin"
    bindir.mkdir()
    log = tmp_path / "open.log"
    stub = bindir / "open"
    stub.write_text(f"#!/bin/sh\necho \"$@\" >> {log}\nexit ${{OPEN_EXIT:-0}}\n")
    stub.chmod(stub.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("PATH", f"{bindir}:{os.environ['PATH']}")
    monkeypatch.setattr(session, "is_macos", lambda: True)
    ctx = repo.load_ctx(cwd=inited.repo)
    make_task(ctx, tid="t1", worktree=str(inited.repo), terminal_handle={"agent": "t1"})
    return inited, ctx, log


def opened(log):
    return log.read_text().splitlines() if log.exists() else []


def test_open_runs_after_the_herdr_focus(focus_env):
    inited, ctx, log = focus_env
    config.set_value(ctx, "terminal", "terminal_app", "Ghostty")
    assert session.focus(ctx, "t1") == {"front": "ok", "app": "Ghostty"}
    assert fake_calls(inited.fdir)[-1]["op"] == "focus"
    assert opened(log) == ["-a Ghostty"]


def test_empty_app_skips_open(focus_env):
    inited, ctx, log = focus_env
    config.set_value(ctx, "terminal", "terminal_app", "")
    assert session.focus(ctx, "t1") == {"front": "off"}
    assert opened(log) == []
    assert fake_calls(inited.fdir)[-1]["op"] == "focus"


def test_missing_app_asks(focus_env):
    _, ctx, log = focus_env
    assert session.focus(ctx, "t1") == {"front": "ask"}
    assert opened(log) == []


def test_failed_open_keeps_the_focus(focus_env, monkeypatch):
    inited, ctx, log = focus_env
    config.set_value(ctx, "terminal", "terminal_app", "Nope")
    monkeypatch.setenv("OPEN_EXIT", "1")
    result = session.focus(ctx, "t1")
    assert result["front"] == "failed" and result["app"] == "Nope"
    assert fake_calls(inited.fdir)[-1]["op"] == "focus"


def test_not_macos_reports_failure(focus_env, monkeypatch):
    _, ctx, log = focus_env
    config.set_value(ctx, "terminal", "terminal_app", "Ghostty")
    monkeypatch.setattr(session, "is_macos", lambda: False)
    assert session.focus(ctx, "t1")["front"] == "failed"
    assert opened(log) == []
```

- [ ] **Step 2: Run, expect failure**

Run: `uv run --with pytest --with pyyaml pytest -q tests/test_focus_front.py`
Expected: FAIL, `session` has no `is_macos`.

- [ ] **Step 3: Implement in `lib/factory/session.py`**

Imports: `import subprocess`, `import sys`, `import uuid`, and `from . import adapters, config, events, state`.

Constants:

```python
TERMINAL_SECTION = "terminal"
TERMINAL_APP_KEY = "terminal_app"
OPEN_TIMEOUT = 10
ASK_TERMINAL_APP = (
    "Ask the user which terminal app shows Herdr, for example Ghostty or iTerm, then run "
    "`factory config set terminal terminal_app '<app>'`. An empty value means never ask again."
)
```

Replace `focus`:

```python
def is_macos():
    return sys.platform == "darwin"


def front_failed(app, message):
    return {"front": "failed", "app": app, "message": message}


def bring_to_front(ctx):
    app = config.get_value(ctx, TERMINAL_SECTION, TERMINAL_APP_KEY)
    if app is None:
        return {"front": "ask"}
    app = str(app).strip()
    if not app:
        return {"front": "off"}
    if not is_macos():
        return front_failed(app, "Bringing the app to the front works only on macOS.")
    try:
        r = subprocess.run(["open", "-a", app], capture_output=True, text=True, timeout=OPEN_TIMEOUT)
    except (OSError, subprocess.TimeoutExpired) as e:
        return front_failed(app, str(e))
    if r.returncode != 0:
        return front_failed(app, (r.stderr or r.stdout).strip() or f"open exited with {r.returncode}.")
    return {"front": "ok", "app": app}


def front_text(result):
    if result["front"] == "ok":
        return f"Focused. {result['app']} is in front."
    if result["front"] == "ask":
        return "Focused in the terminal. " + ASK_TERMINAL_APP
    if result["front"] == "failed":
        return f"Focused in the terminal. Could not bring {result['app']} to the front: {result['message']}"
    return "Focused in the terminal."


def focus(ctx, tid):
    _, handle = live_handle(ctx, tid)
    adapter_of(ctx).focus(handle)
    return bring_to_front(ctx)
```

- [ ] **Step 4: CLI and API**

`commands.py`:

```python
@cli.command("terminal focus")
def focus_cmd(args):
    from . import session
    result = session.focus(ctx_of(args), args.id)
    cli.emit(result, True) if args.json else print(session.front_text(result))
```

`api.py`:

```python
@route("POST", f"/api/tasks/{TASK}/focus")
def focus(server, tid, query, body):
    from . import session
    return {"ok": True, **session.focus(server.ctx, tid)}
```

- [ ] **Step 5: Dashboard**

Replace the Focus line in `taskButtons`:

```js
  if (live && can("focus") && !finished) row.append(button("Focus", () => focusTask(t)));
```

Add after `taskButtons`:

```js
async function focusTask(t) {
  const res = await api(`/api/tasks/${t.id}/focus`, {});
  if (res.front === "ask") openTerminalApp(t);
  if (res.front === "failed") { state.deliveryErrors.set(t.id, `Focused in Herdr. Could not bring ${res.app} to the front: ${res.message}`); state.lastKey = null; render(); }
}
function openTerminalApp(t) {
  const name = el("input", { placeholder: "Ghostty" });
  openModal("Terminal app", el("p", {}, "Which terminal app shows Herdr? Leave it empty to never ask again."), name,
    el("div", { class: "footer" }, closeButton("Cancel"), button("Save", async () => {
      await api("/api/config/set", { step: "terminal", key: "terminal_app", value: name.value.trim() });
      closeModal();
      await focusTask(t);
    }, { cls: "primary" })));
}
```

Add to `tests/test_dashboard_page.py`:

```python
def test_focus_asks_terminal_app():
    assert "terminal_app" in PAGE and "Which terminal app shows Herdr?" in PAGE
```

- [ ] **Step 6: Skill and README**

`skills/software-factory/SKILL.md` line 43, append: ` When it prints "Ask the user which terminal app shows Herdr", ask the user, run the \`factory config set terminal terminal_app '<app>'\` command it shows (an empty answer saves an empty value), then run \`factory terminal focus <id>\` again. When it says the app could not be brought to the front, tell the user.`

`README.md`:
- Menu "Focus a task": append ` Then it brings the terminal app that shows Herdr to the front, with \`open -a <terminal_app>\` on macOS.`
- Commands, `factory terminal focus <id>` line: append `. Then it runs \`open -a <terminal_app>\`. \`terminal_app\` is asked on first use: \`factory config set terminal terminal_app Ghostty\`. An empty value means only the focus inside Herdr.`
- Card buttons, **Focus**: append ` Then it brings the terminal app to the front. The first time, it asks for the app name. When it fails, the card says so.`
- Bash allowlist, Herdr adapter list: add `- \`open -a <terminal app>\``.

- [ ] **Step 7: Full suite, then commit**

Run: `uv run --with pytest --with pyyaml pytest -q tests`. Expected: all pass. `test_dashboard_api.test_actions_call_cli_functions` still passes: no `terminal_app` gives `ask`, no `open` runs.

```bash
git add software-factory/lib/factory software-factory/tests software-factory/README.md software-factory/skills
git commit -m "focus: bring the terminal app to the front"
```

---

### Task 8: Task id from the ticket at launch (milestone 6, part 1)

**Files:**
- Modify: `lib/factory/launch.py`
- Create: `tests/test_ticket_names.py` (launch tests)

**Interfaces:**
- Produces: `launch.ticket_key(value: str|None) -> str|None` (first Jira key, lowercase, cut at `ID_BASE_MAX`). Task 9 uses it.

- [ ] **Step 1: Write the failing tests**

`tests/test_ticket_names.py`:

```python
import pytest

from conftest import write_pipeline, write_step
from factory import launch


@pytest.fixture
def tp(inited):
    write_step(inited.fdir, "w", {})
    write_pipeline(inited.fdir, {"id": "tp", "inputs": {"ticket": {"description": "Jira ticket"}}, "steps": ["w"]})
    return inited


def launched_id(inited, ticket, description="Fix the list"):
    return inited.factory.json("launch", "tp", "--description", description, "--input", f"ticket={ticket}")["id"]


@pytest.mark.parametrize("value, key", [
    ("HT-4549", "ht-4549"),
    ("https://x.atlassian.net/browse/HT-4549", "ht-4549"),
    ("HT-4549 Fix the list", "ht-4549"),
    ("none yet", None),
    ("", None),
    (None, None),
])
def test_ticket_key(value, key):
    assert launch.ticket_key(value) == key


def test_long_key_is_cut():
    assert len(launch.ticket_key("ABCDEFGHIJKLMNOPQRSTUVWXYZ-1234567")) <= launch.ID_BASE_MAX


def test_launch_ids_from_ticket(tp):
    assert launched_id(tp, "HT-4549") == "ht-4549"
    assert launched_id(tp, "HT-4549") == "ht-4549-2"
    assert launched_id(tp, "https://x.atlassian.net/browse/HT-77") == "ht-77"


def test_launch_without_key_uses_the_slug(tp):
    assert launched_id(tp, "none yet") == "fix-the-list"


def test_dry_run_shows_the_id(tp):
    out = tp.factory("launch", "tp", "--description", "Fix", "--input", "ticket=HT-9", "--dry-run").stdout
    assert "Task id: ht-9" in out
```

- [ ] **Step 2: Run, expect failure**

Run: `uv run --with pytest --with pyyaml pytest -q tests/test_ticket_names.py`. Expected: FAIL, no `ticket_key`.

- [ ] **Step 3: Implement**

`lib/factory/launch.py`, after `ID_BASE_MAX = 29`:

```python
TICKET_KEY_RE = re.compile(r"[A-Z][A-Z0-9]+-[0-9]+")


def ticket_key(value):
    match = TICKET_KEY_RE.search(value or "")
    return match.group(0).lower()[:ID_BASE_MAX].rstrip("-") if match else None
```

In `plan_launch`, replace the `else:` branch of the id:

```python
    else:
        base = ticket_key(str(inputs.get("ticket", ""))) or slugify(report["description"] or "task")
        report["task_id"] = unique_id(ctx, base)
```

- [ ] **Step 4: Run, expect pass**

Run: `uv run --with pytest --with pyyaml pytest -q tests/test_ticket_names.py tests/test_launch.py`. Expected: all pass.

No commit yet: Task 9 finishes milestone 6.

---

### Task 9: Rename after launch (milestone 6, part 2)

**Files:**
- Modify: `lib/factory/state.py` (`display_name`)
- Modify: `lib/factory/adapters/base.py` (`OPTIONAL`, `rename`)
- Modify: `lib/factory/adapters/herdr.py` (`rename`)
- Modify: `lib/factory/adapters/fake.py` (`rename`)
- Create: `lib/factory/rename.py`
- Modify: `lib/factory/engine.py` (`set_state`)
- Modify: `lib/factory/commands.py` (`state_set`)
- Modify: `lib/factory/session.py` (`claude_args`, `start`, `resume`)
- Modify: `lib/factory/server.py` (`poll_loop`)
- Modify: `lib/factory/api.py` (`tasks`)
- Modify: `lib/factory/board.py` (row fields, `render_rows`)
- Modify: `lib/factory/web/dashboard.html` (card name, rename error)
- Modify: `tests/test_ticket_names.py`
- Modify: `README.md`

**Interfaces:**
- Consumes: `herdr_name` (Task 1), `fsio.try_locked` (Task 5), `launch.ticket_key` (Task 8), `board.task_rows(ctx, next_poll)` (Task 6).
- Produces:
  - `state.display_name(task) -> str`.
  - `Adapter.rename(handle, name) -> (new_handle: dict, problems: list[str])`. Raises `AdapterError` only when the agent rename itself fails.
  - `rename.on_ticket_set(ctx, tid, old, new) -> str|None` (the problem text, or None).
  - `rename.apply_pending(ctx, task) -> bool`, `rename.apply_all_pending(ctx) -> None`.
  - Events: `task_renamed {name}`, `rename_failed {name, reason}`, `claude_renamed {name}`.
  - Row fields: `display_name`, `rename_error`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_ticket_names.py`:

```python
import json
import os
import stat

import yaml

from conftest import SF, events, fake_calls, fake_config, make_task, task_json
from factory import board, engine, rename, repo, session


def ticket_task(inited, tid="fix-the-list", **fields):
    ctx = repo.load_ctx(cwd=inited.repo)
    make_task(ctx, tid=tid, worktree=str(inited.repo), terminal_handle={"agent": tid, "fake": True}, **fields)
    return ctx, tid


def set_ticket(inited, tid, value, check=True):
    return inited.factory("state", "set", "ticket", value, "--task", tid, check=check)


def test_state_set_ticket_renames_and_keeps_the_id(tp):
    ctx, tid = ticket_task(tp)
    r = set_ticket(tp, tid, "HT-4549")
    assert r.returncode == 0
    task = task_json(tp.fdir, tid)
    assert task["id"] == tid and task["worktree"] == str(tp.repo)
    assert task["display_name"] == "ht-4549" and task["claude_rename_pending"] == "ht-4549"
    assert task["terminal_handle"]["agent"] == "ht-4549"
    assert [c for c in fake_calls(tp.fdir) if c["op"] == "rename"][-1]["name"] == "ht-4549"
    assert any(e["type"] == "task_renamed" for e in events(tp.fdir, tid))
    assert (tp.fdir / "tasks" / tid).exists()


def test_old_value_without_key_still_renames(tp):
    ctx, tid = ticket_task(tp, state={"ticket": "none yet"})
    set_ticket(tp, tid, "HT-4549")
    assert task_json(tp.fdir, tid)["display_name"] == "ht-4549"


def test_second_ticket_does_not_rename_again(tp):
    ctx, tid = ticket_task(tp)
    set_ticket(tp, tid, "HT-4549")
    set_ticket(tp, tid, "HT-1")
    assert task_json(tp.fdir, tid)["display_name"] == "ht-4549"
    assert len([c for c in fake_calls(tp.fdir) if c["op"] == "rename"]) == 1


def test_display_name_is_unique(tp):
    ticket_task(tp, tid="ht-4549")
    ctx, tid = ticket_task(tp, tid="other")
    set_ticket(tp, tid, "HT-4549")
    assert task_json(tp.fdir, tid)["display_name"] == "ht-4549-2"


def test_working_session_gets_rename_later(tp, monkeypatch):
    for key, value in tp.factory.env.items():
        monkeypatch.setenv(key, value)
    ctx, tid = ticket_task(tp)
    fake_config(tp.fdir, states={"ht-4549": "working"})
    set_ticket(tp, tid, "HT-4549")
    assert not [c for c in fake_calls(tp.fdir) if c["op"] == "send_prompt"]
    assert rename.apply_pending(ctx, task_json(tp.fdir, tid)) is False
    assert task_json(tp.fdir, tid)["claude_rename_pending"] == "ht-4549"
    fake_config(tp.fdir, states={"ht-4549": "idle"})
    assert rename.apply_pending(ctx, task_json(tp.fdir, tid)) is True
    assert rename.apply_pending(ctx, task_json(tp.fdir, tid)) is False
    prompts = [c["text"] for c in fake_calls(tp.fdir) if c["op"] == "send_prompt"]
    assert prompts == ["/rename ht-4549"]
    assert "claude_rename_pending" not in task_json(tp.fdir, tid)


def test_question_box_blocks_the_live_rename(tp, monkeypatch):
    for key, value in tp.factory.env.items():
        monkeypatch.setenv(key, value)
    ctx, tid = ticket_task(tp)
    set_ticket(tp, tid, "HT-4549")
    fake_config(tp.fdir, question_box=True)
    assert rename.apply_pending(ctx, task_json(tp.fdir, tid)) is False
    assert task_json(tp.fdir, tid)["claude_rename_pending"] == "ht-4549"


def test_resume_applies_the_name(tp):
    ctx, tid = ticket_task(tp)
    fake_config(tp.fdir, states={"ht-4549": "working"})
    set_ticket(tp, tid, "HT-4549")
    tp.factory("pause", tid)
    tp.factory("resume", tid)
    start = [c for c in fake_calls(tp.fdir) if c["op"] == "start_session"][-1]
    assert start["name"] == "ht-4549"
    assert start["args"][start["args"].index("--name") + 1] == "ht-4549"
    assert "claude_rename_pending" not in task_json(tp.fdir, tid)


def test_failed_rename_does_not_fail_state_set(tp):
    ctx, tid = ticket_task(tp)
    fake_config(tp.fdir, fail_rename=True)
    r = set_ticket(tp, tid, "HT-4549")
    assert r.returncode == 0 and "rename failed" in r.stdout
    assert task_json(tp.fdir, tid)["state"]["ticket"] == "HT-4549"
    assert any(e["type"] == "rename_failed" for e in events(tp.fdir, tid))
    row = [r for r in tp.factory.json("tasks") if r["id"] == tid][0]
    assert row["rename_error"]


def test_partial_rename_keeps_the_new_agent_name(tp):
    ctx, tid = ticket_task(tp)
    fake_config(tp.fdir, rename_problems=["herdr tab rename failed: no tab"])
    set_ticket(tp, tid, "HT-4549")
    task = task_json(tp.fdir, tid)
    assert task["terminal_handle"]["agent"] == "ht-4549" and "tab rename" in task["rename_error"]


def test_claude_rename_keeps_the_tab_error(tp, monkeypatch):
    for key, value in tp.factory.env.items():
        monkeypatch.setenv(key, value)
    ctx, tid = ticket_task(tp)
    fake_config(tp.fdir, rename_problems=["herdr tab rename failed: no tab"])
    set_ticket(tp, tid, "HT-4549")
    assert rename.apply_pending(ctx, task_json(tp.fdir, tid)) is True
    task = task_json(tp.fdir, tid)
    assert "claude_rename_pending" not in task
    assert "tab rename" in task["rename_error"]
    row = [r for r in tp.factory.json("tasks") if r["id"] == tid][0]
    assert "tab rename" in row["rename_error"]


def test_failed_claude_rename_is_cleared_by_a_later_success(tp, monkeypatch):
    for key, value in tp.factory.env.items():
        monkeypatch.setenv(key, value)
    ctx, tid = ticket_task(tp)
    set_ticket(tp, tid, "HT-4549")
    fake_config(tp.fdir, send_prompt_fails=True)
    assert rename.apply_pending(ctx, task_json(tp.fdir, tid)) is False
    assert rename.apply_pending(ctx, task_json(tp.fdir, tid)) is False
    assert sum(1 for e in events(tp.fdir, tid) if e["type"] == "rename_failed") == 1
    assert task_json(tp.fdir, tid)["claude_rename_error"]
    assert task_json(tp.fdir, tid)["claude_rename_pending"] == "ht-4549"
    fake_config(tp.fdir)
    assert rename.apply_pending(ctx, task_json(tp.fdir, tid)) is True
    assert "claude_rename_error" not in task_json(tp.fdir, tid)


def test_rows_and_task_list_show_display_name(tp):
    ctx, tid = ticket_task(tp)
    set_ticket(tp, tid, "HT-4549")
    row = [r for r in tp.factory.json("tasks") if r["id"] == tid][0]
    assert row["display_name"] == "ht-4549"
    assert "ht-4549 (fix-the-list)" in tp.factory("tasks").stdout


def test_herdr_names_are_renamed_with_the_stub(tp, monkeypatch, tmp_path):
    for key, value in tp.factory.env.items():
        monkeypatch.setenv(key, value)
    yaml_path = tp.fdir / "factory.yaml"
    data = yaml.safe_load(yaml_path.read_text())
    data["terminal"] = "herdr"
    yaml_path.write_text(yaml.safe_dump(data))
    bindir = tmp_path / "bin"
    bindir.mkdir()
    exe = bindir / "herdr"
    exe.write_text(f"#!/bin/sh\nexec python3 {SF / 'tests' / 'fake_herdr.py'} \"$@\"\n")
    exe.chmod(exe.stat().st_mode | stat.S_IEXEC)
    log = tmp_path / "herdr.log"
    monkeypatch.setenv("PATH", f"{bindir}:{os.environ['PATH']}")
    monkeypatch.setenv("FAKE_HERDR_LOG", str(log))
    monkeypatch.setenv("FAKE_HERDR_MAIN", str(tp.repo))
    monkeypatch.setenv("FAKE_HERDR_PRESENT", "1")
    ctx = repo.load_ctx(cwd=tp.repo)
    tid = "fix-the-list"
    make_task(ctx, tid=tid, worktree=str(tp.repo), terminal_handle={"agent": tid, "workspace": "w9", "tab": "w9:t1"})
    engine.set_state(ctx, tid, "ticket", "HT-4549")
    calls = [json.loads(line) for line in log.read_text().splitlines()]
    assert ["agent", "rename", tid, "ht-4549"] in calls
    assert ["tab", "rename", "w9:t1", "ht-4549"] in calls
    assert ["workspace", "rename", "w9", "ht-4549"] in calls
    task = task_json(tp.fdir, tid)
    assert task["id"] == tid and task["worktree"] == str(tp.repo) and task["terminal_handle"]["agent"] == "ht-4549"
    assert "rename_error" not in task or task["rename_error"] is None
```

- [ ] **Step 2: Run, expect failure**

Run: `uv run --with pytest --with pyyaml pytest -q tests/test_ticket_names.py`. Expected: the new tests FAIL (no `rename` module).

- [ ] **Step 3: `state.display_name`**

`lib/factory/state.py`, after `check_task_id`:

```python
def display_name(task):
    return task.get("display_name") or task["id"]
```

- [ ] **Step 4: Adapters**

`adapters/base.py`: `OPTIONAL = ("send_prompt", "focus", "state", "wait_idle", "notify", "rename")`, and in `Adapter`:

```python
    def rename(self, handle, name):
        self.unsupported("rename")
```

`adapters/herdr.py`, in `HerdrAdapter`, after `focus`:

```python
    def rename(self, handle, name):
        self.require_owned(handle)
        run(["agent", "rename", handle["agent"], name])
        handle = {**handle, "agent": name}
        problems = []
        for kind in ("tab", "workspace"):
            if handle.get(kind):
                try:
                    run([kind, "rename", handle[kind], name])
                except AdapterError as e:
                    problems.append(str(e))
        return handle, problems
```

`adapters/fake.py`, in `FakeAdapter`:

```python
    def rename(self, handle, name):
        self.require("rename")
        self.record("rename", handle=handle, name=name)
        cfg = self.cfg()
        if cfg.get("fail_rename"):
            raise AdapterError("The fake adapter failed to rename.")
        return {**handle, "agent": name}, list(cfg.get("rename_problems", []))
```

Also in `FakeAdapter.send_prompt`, after `self.require("send_prompt")`:

```python
        if self.cfg().get("send_prompt_fails"):
            raise AdapterError("The fake adapter failed to send the prompt.")
```

- [ ] **Step 5: `lib/factory/rename.py`**

```python
import sys

from . import adapters, events, fsio, launch, session, state
from .adapters.base import AdapterError, herdr_name

RENAME_PROMPT = "/rename {name}"


def used_names(ctx, tid):
    names = set()
    for task in state.list_tasks(ctx):
        if task["id"] != tid:
            names.update({task["id"], state.display_name(task)})
    return names


def unique_name(ctx, tid, key):
    taken = used_names(ctx, tid)
    name, n = herdr_name(key), 2
    while name in taken:
        name = herdr_name(f"{key}-{n}")
        n += 1
    return name


def on_ticket_set(ctx, tid, old, new):
    key = launch.ticket_key(new)
    if not key or launch.ticket_key(old) or state.load(ctx, tid).get("display_name"):
        return None
    name = unique_name(ctx, tid, key)
    if name == tid:
        return None
    return rename(ctx, tid, name)


def rename_terminal(ctx, handle, name):
    try:
        adapter = adapters.get_adapter(ctx)
        if "rename" not in adapter.capabilities():
            return handle, []
        return adapter.rename(handle, name)
    except AdapterError as e:
        return handle, [str(e)]


def rename(ctx, tid, name):
    task = state.load(ctx, tid)
    handle, problems = task.get("terminal_handle"), []
    if handle:
        handle, problems = rename_terminal(ctx, handle, name)
    error = "; ".join(problems) or None

    def change(t):
        t["display_name"] = name
        t["claude_rename_pending"] = name
        t["terminal_handle"] = handle
        t["rename_error"] = error

    task = state.update(ctx, tid, change)
    path = state.step_path_str(task)
    events.log(ctx, tid, "task_renamed", path, name=name)
    if error:
        events.log(ctx, tid, "rename_failed", path, name=name, reason=error)
    return error


def note_failure(ctx, task, name, reason):
    if task.get("claude_rename_error") == reason:
        return
    state.update(ctx, task["id"], lambda t: t.__setitem__("claude_rename_error", reason))
    events.log(ctx, task["id"], "rename_failed", state.step_path_str(task), name=name, reason=reason)


def ready_for_prompt(ctx, adapter, task, handle):
    caps = adapter.capabilities()
    if "send_prompt" not in caps or session.live_state(ctx, task) != "idle":
        return False
    return not adapter.question_box(handle)


def clear_pending(t):
    t.pop("claude_rename_pending", None)
    t.pop("claude_rename_error", None)


def apply_pending(ctx, task):
    if not task.get("claude_rename_pending") or not task.get("terminal_handle"):
        return False
    tid = task["id"]
    with fsio.try_locked(state.task_dir(ctx, tid) / "rename") as got:
        if not got:
            return False
        task = state.load(ctx, tid)
        name, handle = task.get("claude_rename_pending"), task.get("terminal_handle")
        if not name or not handle:
            return False
        try:
            adapter = adapters.get_adapter(ctx)
            if not ready_for_prompt(ctx, adapter, task, handle):
                return False
            adapter.send_prompt(handle, RENAME_PROMPT.format(name=name))
        except AdapterError as e:
            note_failure(ctx, task, name, str(e))
            return False
        task = state.update(ctx, tid, clear_pending)
        events.log(ctx, tid, "claude_renamed", state.step_path_str(task), name=name)
        return True


def apply_all_pending(ctx):
    for task in state.list_tasks(ctx):
        if not task.get("claude_rename_pending"):
            continue
        try:
            apply_pending(ctx, task)
        except Exception as e:
            print(f"rename of {task['id']} failed: {e}", file=sys.stderr, flush=True)
```

`rename_error` holds only the terminal rename problems, written by `rename`. `claude_rename_error` holds only the last failed Claude rename, written by `note_failure`. `clear_pending` clears only `claude_rename_error`, so a successful Claude rename never erases a Herdr rename error.

- [ ] **Step 6: Call sites**

`engine.py`, `set_state` returns the value and the rename problem:

```python
def set_state(ctx, tid, key, value):
    from . import rename
    task = state.load(ctx, tid)
    old = task["state"].get(key)
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
    problem = None
    if key == "ticket":
        try:
            problem = rename.on_ticket_set(ctx, tid, old, value)
        except Exception as e:
            problem = str(e)
            events.log(ctx, tid, "rename_failed", state.step_path_str(state.load(ctx, tid)), reason=problem)
    return value, problem
```

`commands.py`, `state_set`:

```python
@cli.command("state set")
def state_set(args):
    from . import engine
    ctx, tid = task_of(args)
    _, problem = engine.set_state(ctx, tid, args.key, args.value)
    print(f"Saved `{args.key}`.")
    if problem:
        print(f"Warning: the rename failed: {problem}")
```

`grep -rn "set_state(" lib tests`: update any other caller to unpack the tuple.

`session.py`:
- `claude_args`: `args = ["--name", state.display_name(task)]`.
- `start`: `adapters.get_adapter(ctx).start_session(state.display_name(task), task["worktree"], prompt, claude_args(ctx, task, resume))`.
- `resume`, inside `change(t)`, first line: `t.pop("claude_rename_pending", None)`.

`server.py`, `poll_loop` body after `engine.poll(self.ctx)`, inside the same `try`:

```python
            try:
                engine.poll(self.ctx)
                rename.apply_all_pending(self.ctx)
            except Exception as e:
```

with `from . import engine, rename` at the top of `poll_loop`.

`api.py`, `tasks`:

```python
@route("GET", "/api/tasks")
def tasks(server, query, body):
    from . import board, rename
    rename.apply_all_pending(server.ctx)
    return board.task_rows(server.ctx, server.next_poll)
```

`board.py`, in `task_row` add:

```python
        "display_name": state.display_name(task),
        "rename_error": "; ".join(e for e in (task.get("rename_error"), task.get("claude_rename_error")) if e) or None,
```

and in `render_rows` replace the first line:

```python
        name = r["display_name"] if r["display_name"] == r["id"] else f"{r['display_name']} ({r['id']})"
        lines.append(f"{name}: {r['description']}")
```

- [ ] **Step 7: Dashboard card**

CSS: `.rename-error { color: var(--err); font-size: 12px; margin: 2px 0; }`

In `taskCard`, replace `top.append(el("span", { class: "muted" }, t.id));` with:

```js
  top.append(el("strong", {}, t.display_name));
  if (t.display_name !== t.id) top.append(el("span", { class: "muted" }, t.id));
```

After the "Session gone" line:

```js
  if (t.rename_error) card.append(el("div", { class: "rename-error" }, `Rename failed: ${t.rename_error}`));
```

Add to `tests/test_dashboard_page.py`:

```python
def test_card_shows_display_name_and_rename_error():
    assert "t.display_name" in PAGE and "Rename failed" in PAGE
```

- [ ] **Step 8: Run, expect pass**

Run: `uv run --with pytest --with pyyaml pytest -q tests/test_ticket_names.py tests/test_session.py tests/test_dashboard_page.py`. Expected: all pass.

- [ ] **Step 9: README**

- Concepts, after **Task**: `- **Display name**: the ticket key of a task, when the ticket is known only after the launch. Without it, the display name is the id.`
- Commands, `factory launch` line: append `. When the pipeline input \`ticket\` holds a Jira key (\`HT-4549\`, a URL or a text), the task id is that key in lowercase, for example \`ht-4549\`, plus \`-2\` when taken.`
- Commands, `factory state set` line: append `. The first time \`ticket\` gets a Jira key after the launch, the task gets a display name. The Herdr agent, tab and workspace are renamed. The Claude session is renamed with \`/rename\` when it is idle with no question box, or at the next resume with \`--name\`. The id and the worktree folder do not change. A failed rename only prints a warning.`
- Dashboard card list, first bullet: `- The ticket, then the display name, then the id when it differs. A failed rename is shown in red.`
- Events section: add `task_renamed` (`name`), `rename_failed` (`name`, `reason`) and `claude_renamed` (`name`).
- Bash allowlist, Herdr adapter: add `- \`herdr workspace rename\`, \`herdr tab rename\`, \`herdr agent rename\``.

- [ ] **Step 10: Full suite, then commit**

Run: `uv run --with pytest --with pyyaml pytest -q tests`. Expected: all pass.

```bash
git add software-factory/lib/factory software-factory/tests software-factory/README.md
git commit -m "names: task id from the ticket, rename after launch"
```

---

### Task 10: Final verification

**Files:**
- Create: `verification/software-factory/factory-fixes-dod.md`
- Create: `verification/software-factory/factory-fixes-junit.xml`

- [ ] **Step 1: Full suite with a report**

```bash
cd software-factory && uv run --with pytest --with pyyaml pytest -q tests --junitxml=../verification/software-factory/factory-fixes-junit.xml
```

Expected: all pass, count above 416.

- [ ] **Step 2: Facts check**

Run and paste the output in the DoD file: `herdr --version`, `herdr workspace rename --help`, `herdr tab rename --help`, `herdr agent rename --help`, `git --version`, `claude --version`.

- [ ] **Step 3: Branch check**

```bash
git -C .. log --oneline master..factory-fixes
test "$(git -C .. rev-parse master)" = "$(cat ../verification/software-factory/factory-fixes-master-before.txt)" && echo "master unchanged"
```

Expected: the milestone commits are only on `factory-fixes`, and `master unchanged`.

- [ ] **Step 4: DoD file**

`verification/software-factory/factory-fixes-dod.md`: one line per Definition Of Done bullet of `prompts/factory_fixes.md`, each with PASS or FAIL and the evidence (test name, commit, file, or browser check result). Fix any FAIL, rerun the affected tests, update the line.

- [ ] **Step 5: Commit**

```bash
git add verification/software-factory/factory-fixes-dod.md verification/software-factory/factory-fixes-junit.xml
git commit -m "factory fixes: verification"
```
