# Factory improvement: exclusive steps and "May wait for you" — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** One task at a time runs a step with the same `exclusive` name, and a task session that ends its turn while `active` shows "May wait for you" and notifies the user once.

**Architecture:** New module `lib/factory/exclusive.py` keeps one JSON file per resource in `.factory/exclusive/<name>.json`, always changed under its `flock` lock, and is called by the engine after each move. New module `lib/factory/attention.py` implements `factory hook stop|prompt|notify-later`, called by Claude Code hooks that `init.ensure_settings` writes into `.factory/claude-settings.json`.

**Tech Stack:** Python 3 (stdlib + PyYAML), pytest, plain HTML/JS dashboard, Herdr 0.9.3, Claude Code 2.1.301.

**Spec:** `specs/2026-10-16-factory-improvement-design.md` (read it with this plan).

## Global Constraints

- All work in `software-factory/` on branch `factory-improvement`, created from `master`. Spec and plan stay in `specs/` and `plans/`. Verification artifacts go to `verification/software-factory/`.
- Before the branch: `git rev-parse master > verification/software-factory/factory-improvement-master-before.txt`. At the end, `master` must still have that hash. Never push.
- Never change a real `.factory/`, the user's library, or a real Herdr workspace, tab or agent. Tests use the `inited` fixture (temp repos under `verification/software-factory/work/`) and `FACTORY_TERMINAL=fake`.
- No code comments (user rule). Match the existing style: small functions, `FactoryError` for user errors, `state.update` for task changes, `events.log` for events.
- Data format version stays 2. No migration.
- Full suite: `cd software-factory && uv run --with pytest --with pyyaml pytest -q -p no:cacheprovider tests`. Baseline: 478 passed (about 6 minutes). Run it after each milestone.
- Resource name rule: `[a-z][a-z0-9_-]*`.
- Lock order: resource lock first, then task lock. Never take a resource lock inside a `state.update` callback.
- Exact texts (copy verbatim):
  - Wait reason: `Waiting for <name>, used by <holder>`
  - `factory next` wait: ``The step `<id>` needs `<name>`, now used by task `<holder>`. The factory starts this task when it is free. End your turn.``
  - Handover, mode `next`: `` `<name>` is yours now. Run `factory next`. ``
  - Handover, mode `acquire`: `` `<name>` is yours now. Continue the step. ``
  - Acquire wait: `` `<name>` is used by task `<holder>`. The factory sends you a message when it is free. End your turn. ``
  - Footer line: ``This step uses `<name>`. Only one task at a time runs it. Before a long wait for the user, free it with `factory exclusive release <name>`. Take it again with `factory exclusive acquire <name>`.``
  - Released line: ``You released `<name>`. Run `factory exclusive acquire <name>` before you use it again.``
  - external-done refusal: ``Task <id> waits for `<name>`, not for an external event. Release it with `factory exclusive release <name> --force` if the holder is stuck.``
  - Notification: `<display name> may wait for you: <first line>`, or `<display name> may wait for you.` without a message.

## Review Focus

1. A waiting task whose step has a `done_check`: `factory poll` must not run that check and end the step. Test in Task 3 (`test_poll_ignores_exclusive_wait`).
2. A holder deleted while others wait: the next waiting task must start. Test in Task 3 (`test_delete_holder_hands_over`).
3. A second `factory next` from a waiting session must not add a second queue entry. Test in Task 2 (`test_claim_twice_queues_once`).
4. A hook run outside any factory repository, or with another data version: exit 0, no output. Test in Task 7 (`test_hook_outside_factory_is_silent`).
5. Two Stop hooks within one second: the first `notify-later` must not notify for the second turn end. `attention.at` uses microseconds. Test in Task 7 (`test_attention_at_is_unique`).

---

## Milestone 1: Exclusive steps

### Task 0: Branch

- [ ] **Step 1:** `cd <PROJECT_ROOT> && git rev-parse master > verification/software-factory/factory-improvement-master-before.txt`
- [ ] **Step 2:** `git switch -c factory-improvement master`. The working tree has unrelated changes in `prompts/` (do not commit them). Expected: on branch `factory-improvement`.

### Task 1: Manifest field `exclusive`

**Files:**
- Modify: `software-factory/lib/factory/step_format.py` (FIELD_ORDER, validate)
- Modify: `software-factory/lib/factory/registry.py` (Step property)
- Modify: `software-factory/lib/factory/render.py` (footer line)
- Modify: `software-factory/lib/factory/web/editor.html` (form field, FORM_KEYS, detail panel)
- Test: `software-factory/tests/test_exclusive_format.py`

**Interfaces:**
- Produces: `Step.exclusive -> str | None`; `step_format.EXCLUSIVE_RE = re.compile(r"[a-z][a-z0-9_-]*")`; `render.exclusive_line(name) -> str` (footer line text); `render.released_line(name) -> str`.

- [ ] **Step 1: Write the failing tests**

```python
def test_valid_exclusive_name():
    errors, _ = step_format.validate({"id": "s", "type": "ai", "description": "d", "exclusive": "android-emulator"}, "Do it.")
    assert errors == []

@pytest.mark.parametrize("bad", ["Android", "1emu", "emu lator", ""])
def test_bad_exclusive_name(bad):
    errors, _ = step_format.validate({"id": "s", "type": "ai", "description": "d", "exclusive": bad}, "Do it.")
    assert any("exclusive" in e for e in errors)

def test_exclusive_on_group_is_error():
    errors, _ = step_format.validate({"id": "g", "type": "group", "description": "d", "steps": ["a"], "exclusive": "emu"}, "")
    assert "`exclusive` applies only to `ai` and `command` steps. Set it on the child steps." in errors

def test_footer_names_resource(inited):
    write_step(inited.fdir, "emu", {"exclusive": "android-emulator"})
    write_pipeline(inited.fdir, {"id": "p", "steps": ["emu"]})
    task_from_pipeline(inited, "p", worktree=str(inited.repo))
    out = inited.factory("next", "--task", "t1").stdout
    assert "This step uses `android-emulator`. Only one task at a time runs it." in out
    assert "`factory exclusive release android-emulator`" in out

def test_pipeline_check_accepts_exclusive(inited):
    write_step(inited.fdir, "emu", {"exclusive": "android-emulator"})
    write_pipeline(inited.fdir, {"id": "p", "steps": ["emu"]})
    assert "no problem" in inited.factory("pipeline", "check", "p").stdout

def test_step_api_saves_exclusive(inited):
    ...  # use serverutil like tests/test_step_editor_api.py: POST /api/steps/save mode new with manifest exclusive "emu",
         # then GET /api/steps/<id>: manifest["exclusive"] == "emu", and the file has "exclusive: emu" after "wait_external" order
```

Also add to `tests/test_dashboard_page.py` style (editor page): `assert 'field("exclusive"' in EDITOR_PAGE`.

- [ ] **Step 2:** Run `uv run --with pytest --with pyyaml pytest -q tests/test_exclusive_format.py`. Expected: FAIL.
- [ ] **Step 3: Implement.** `validate` adds errors: bad name → ``The exclusive name `<v>` must match [a-z][a-z0-9_-]*.``; group → the exact text above. `exclusive` goes in FIELD_ORDER after `wait_external`. `render.step_text` gets a new keyword `exclusive=None`; when set, add `exclusive_line(name)` to the `extra` lines (both session, subagent and command footers). `engine.render_step` and `step_store.preview` pass `step.exclusive`. Editor: text input `exclusive` in the form (placeholder `android-emulator`), included in FORM_KEYS and in the saved manifest, empty means absent; the detail panel lists it like `wait_external`.
- [ ] **Step 4:** Run the test file. Expected: PASS.
- [ ] **Step 5:** Commit `exclusive: manifest field, check and footer`.

### Task 2: Resource store and handover (`exclusive.py`)

**Files:**
- Create: `software-factory/lib/factory/exclusive.py`
- Test: `software-factory/tests/test_exclusive_store.py`

**Interfaces:**
- Consumes: `Step.exclusive`, `state.load/update/list_tasks/current_entry/set_status`, `fsio.update_json/read_json`, `events.log`, `engine.deliver_quietly` (import inside functions to avoid cycles).
- Produces (all `ctx` first):
  - `resource_dir(ctx) -> Path` (`ctx.fdir / "exclusive"`), `read(ctx, name) -> {"holder", "since", "queue"}`
  - `step_name(ctx, task) -> str | None`: the `exclusive` of the current step, None when finished or the step is unknown.
  - `claim(ctx, tid, name, mode) -> (bool, str | None)`: True when the task holds it now; else False and the holder id. When it must wait: joins the queue once, sets the task `waiting_external` with the wait reason and `exclusive_wait = {"name", "mode"}`, logs `exclusive_wait` (`name`, `holder`) only on the first join.
  - `release(ctx, tid, name, event=None) -> bool`: frees it when `tid` is the holder; logs `event` when given; then `handover`.
  - `handover(ctx, name) -> str | None`: the task that got it.
  - `force_release(ctx, name, by=None) -> str`: the old holder; raises ``FactoryError("`<name>` is free.")`` when there is no holder.
  - `sync(ctx, tid) -> None`: release and leave queues for names that are not the current step name (C1 rule).
  - `forget(ctx, tid) -> None`: leave every queue and release everything (task deleted).
  - `recheck(ctx) -> list[str]`: drop invalid holders and queue entries, then handover each resource; returns names handed over.
  - `holder_text(ctx, task) -> str | None`: the line for `factory status`.
  - `task_info(ctx, task) -> dict | None`: `{"name", "holder", "holds", "waiting", "released", "paused"}`.
  - `status_rows(ctx) -> list[dict]`: `{"name", "holder", "holder_status", "queue": [{"task", "status", "since", "mode"}]}` for every name used by a step or present on disk.

Rules (from spec 3.2–3.4): a queued task that is paused never gets the resource and keeps its place; `claim` takes a free resource when no queued task is unpaused; `handover` drops queue entries whose task is missing, finished, or whose current step name differs; the picked task becomes holder and leaves the queue inside the lock, and gets `status active`, `exclusive_wait` removed, and for mode `acquire` `exclusive_released` removed; after the lock, log `exclusive_start` (`name`, `mode`) and deliver the handover text with `engine.deliver_quietly`. `force_release` sets `exclusive_released = name` on the old holder and logs `exclusive_forced` (`name`, `holder`, `by`) on the holder and on `by` when given.

- [ ] **Step 1: Write the failing tests** (use `make_task`/`task_from_pipeline` with a pipeline whose step has `exclusive: emu`, tasks t1, t2, t3, each `started` set to its position where needed)

```python
def test_claim_free_resource(ctx3):
    assert exclusive.claim(ctx3, "t1", "emu", "next") == (True, None)
    assert exclusive.read(ctx3, "emu")["holder"] == "t1"

def test_claim_busy_waits(ctx3):
    exclusive.claim(ctx3, "t1", "emu", "next")
    assert exclusive.claim(ctx3, "t2", "emu", "next") == (False, "t1")
    t = task_json(ctx3.fdir, "t2")
    assert t["status"] == "waiting_external" and t["status_reason"] == "Waiting for emu, used by t1"
    assert t["exclusive_wait"] == {"name": "emu", "mode": "next"}

def test_claim_twice_queues_once(ctx3):
    exclusive.claim(ctx3, "t1", "emu", "next"); exclusive.claim(ctx3, "t2", "emu", "next"); exclusive.claim(ctx3, "t2", "emu", "next")
    assert [q["task"] for q in exclusive.read(ctx3, "emu")["queue"]] == ["t2"]
    assert len([e for e in events(ctx3.fdir, "t2") if e["type"] == "exclusive_wait"]) == 1

def test_release_hands_over_in_order(ctx3):
    for tid in ("t1", "t2", "t3"): exclusive.claim(ctx3, tid, "emu", "next")
    exclusive.release(ctx3, "t1", "emu")
    assert exclusive.read(ctx3, "emu")["holder"] == "t2"
    assert task_json(ctx3.fdir, "t2")["status"] == "active"
    texts = [c["text"] for c in fake_calls(ctx3.fdir) if c["op"] == "send_prompt"]
    assert texts == ["`emu` is yours now. Run `factory next`."]

def test_paused_waiter_is_skipped_and_keeps_place(ctx3): ...
    # t1 holds, t2 then t3 wait, t2 paused (session.pause), release t1 -> holder t3; queue == ["t2"]

def test_free_resource_not_blocked_by_paused_waiter(ctx3): ...
    # t1 holds, t2 waits and is paused, release t1 -> holder None; claim t3 -> (True, None)

def test_acquire_mode_message(ctx3): ...
    # t2 waits with mode "acquire"; release -> text "`emu` is yours now. Continue the step."

def test_force_release_logs_both(ctx3): ...
    # t1 holds and is blocked, t2 waits; force_release(ctx3, "emu", by="t2") == "t1"
    # exclusive_forced in events of t1 and t2; t1 has exclusive_released == "emu"; holder t2

def test_force_release_free_resource_errors(ctx3): ...  # FactoryError "`emu` is free."

def test_names_do_not_block_each_other(ctx3): ...  # claim "emu" and "printer" by t1 and t2: both True

def test_recheck_drops_missing_holder(ctx3): ...
    # t1 holds, t2 waits; remove tasks/t1 folder; recheck -> holder t2

def test_two_processes_claim_once(inited):
    # two subprocesses run `factory next --task t1` and `--task t2` at the same moment
    # (start both with Popen, then wait); exactly one task has started its step and
    # read(...)["holder"] is that task; the other is waiting_external
```

- [ ] **Step 2:** Run `pytest -q tests/test_exclusive_store.py`. Expected: FAIL (no module).
- [ ] **Step 3:** Implement `exclusive.py` with the interfaces above. Resource file changes go through `fsio.update_json(resource_dir(ctx) / f"{name}.json", fn, default_factory=lambda: {"holder": None, "since": None, "queue": []})`. Deliveries and `events.log` of `exclusive_start` run after `update_json` returns.
- [ ] **Step 4:** Run the test file. Expected: PASS (the two-process test passes once Task 3 wires `next`; mark it to run in Task 3 if needed).
- [ ] **Step 5:** Commit `exclusive: resource store, queue and handover`.

### Task 3: Engine, session and delete integration

**Files:**
- Modify: `software-factory/lib/factory/engine.py` (`next_step`, `clear_step`, `done`/`skip`/`goto`/`settle` callers, `waiting_step`, `is_waiting_check`, `external_done`, `poll`, `status_text`)
- Modify: `software-factory/lib/factory/session.py` (`resume`)
- Modify: `software-factory/lib/factory/delete.py` (`delete`)
- Test: `software-factory/tests/test_exclusive_flow.py`

**Interfaces:**
- Consumes: Task 2 functions.
- Produces: no new public names. Behavior:
  - `next_step`: when `step.exclusive` and the step is not started → `claim(..., "next")`; not got → return the `factory next` wait text. When started and the task is not the holder → render the step and append `render.released_line(name)`.
  - `clear_step` also pops `exclusive_wait` and `exclusive_released`.
  - After `settle` (done, external wait end), `advance` (skip) and `goto` return from their task update, call `exclusive.sync(ctx, tid)`.
  - `waiting_step` and `is_waiting_check` return None / False when `task.get("exclusive_wait")`.
  - `external_done` raises the refusal text when `exclusive_wait` is set.
  - `done` and `run_command` raise ``FactoryError("The step waits for `<name>`. End your turn. The factory sends you a message when it is free.")`` when `exclusive_wait` is set, so a waiting step is never ended without running.
  - `poll` calls `exclusive.recheck(ctx)` first; an exception there is caught so polling continues.
  - `status_text` adds `exclusive.holder_text(ctx, task)` when not None.
  - `session.resume`: after the update, when the task has `exclusive_wait`, call `exclusive.handover(ctx, name)`.
  - `delete.delete`: after the folder move, call `exclusive.forget(ctx, tid)`.

- [ ] **Step 1: Write the failing tests** (CLI level, `inited`, pipeline `steps: [emu, after]` with `emu` having `exclusive: emu`; tasks t1, t2, t3 via `task_from_pipeline(..., worktree=str(inited.repo), terminal_handle={"agent": "<tid>"})`)

```python
def test_second_task_waits_then_starts_after_done(flow):
    run(flow, "t1", "next"); out = run(flow, "t2", "next").stdout
    assert "The step `emu` needs `emu`, now used by task `t1`." in out and "End your turn." in out
    run(flow, "t1", "done")
    assert task_json(flow.fdir, "t2")["status"] == "active"
    assert prompts_to(flow, "t2") == ["`emu` is yours now. Run `factory next`."]
    assert "Do the step." in run(flow, "t2", "next").stdout

def test_three_tasks_in_wait_order(flow): ...
def test_third_task_cannot_jump_queue(flow): ...
    # t1 holds, t2 waits; t1 done -> holder t2 (not yet run next); t3 next -> waits; holder still t2
def test_acquire_waiter_continues_step(flow): ...
    # t1 holds; t2 started (holder via release order) ... t2 `exclusive acquire emu` while t1 holds -> waits;
    # t1 done -> prompt "`emu` is yours now. Continue the step."
def test_paused_waiter_then_resume(flow): ...
    # t1 holds; t2, t3 wait; pause t2; t1 done -> t3 holds; resume t2; t3 done -> t2 holds
def test_resume_gets_free_resource_at_once(flow): ...
def test_deleted_waiter_leaves_queue(flow): ...
def test_delete_holder_hands_over(flow): ...
@pytest.mark.parametrize("move", ["skip", "goto", "loop"])
def test_moves_release(flow, move): ...
    # skip: `factory skip`; goto: pipeline [before, emu] goto before; loop: pipeline [emu, check(loop back_to emu while k)]
    # where the loop target step has no exclusive -> after the move t1 is not holder and t2 holds
def test_next_step_with_same_name_keeps_resource(flow): ...  # pipeline [emu, emu2] both exclusive emu (C1)
def test_paused_holder_keeps(flow): ...
def test_finish_releases(flow): ...
def test_release_mid_step_then_acquire_waits(flow): ...
    # t1 `exclusive release emu` -> t2 holds, t1 position unchanged; t1 next shows released line;
    # t1 `exclusive acquire emu` -> waits; t2 done -> t1 gets "Continue the step."
def test_force_release_blocked_holder(flow): ...
    # t1 holds then `block`; t2 waits; `exclusive release emu --force --task t2`;
    # exclusive_forced in both logs; t2 active and got the prompt
def test_external_done_refused_while_waiting(flow): ...
def test_done_and_run_command_refused_while_waiting(flow): ...  # t2 waits: `factory done` and `factory run-command` exit 1, position same
def test_poll_ignores_exclusive_wait(flow): ...  # emu has done_check "true"; t2 waits; `factory poll` -> t2 still waiting, position same
def test_poll_recovers_missed_handover(flow): ...  # write the resource file with holder None and t2 queued, then `factory poll` -> t2 holds
def test_status_shows_holder(flow): ...  # "Exclusive: waiting for `emu`, used by `t1`" in `factory status --task t2`
def test_step_without_exclusive_unchanged(flow): ...  # `after` step: no exclusive file is written
```

- [ ] **Step 2:** Run `pytest -q tests/test_exclusive_flow.py`. Expected: FAIL.
- [ ] **Step 3:** Implement the behavior listed in Interfaces. The `factory exclusive` CLI is needed by some tests: add it here in `commands.py` (`exclusive status`, `exclusive release <name> [--force]`, `exclusive acquire <name>`, all with `common`). `release` without `--force` uses `task_of(args)`. With `--force`, `by` is `args.task`, or the task of the current worktree when one is found, else None. `acquire` checks that the current step has that name and has started, else ``FactoryError("The current step does not use `<name>`.")`` / ``"Run `factory next` first."``; logs `exclusive_acquire` when got; prints the texts from Global Constraints. `release` (own) prints ``Released `<name>`.`` and logs `exclusive_release`.
- [ ] **Step 4:** Run `pytest -q tests/test_exclusive_flow.py tests/test_exclusive_store.py`. Expected: PASS.
- [ ] **Step 5:** Commit `exclusive: engine, resume, delete and poll integration`.

### Task 4: Display, menu and docs

**Files:**
- Modify: `software-factory/lib/factory/board.py` (row `exclusive`, `wait_has_check` None when waiting for a resource)
- Modify: `software-factory/lib/factory/api.py` (route `POST /api/exclusive/([a-z][a-z0-9_-]*)/release`, body `{task}` → `{"holder": force_release(...)}`)
- Modify: `software-factory/lib/factory/web/dashboard.html` (card lines and Release button)
- Modify: `software-factory/lib/factory/menu.py` (action `("Tasks", "exclusive-release", "Release a shared resource", None)` after `clean`)
- Modify: `software-factory/skills/software-factory/SKILL.md` (the action, spec 5.2)
- Modify: `software-factory/skills/factory-authoring/SKILL.md` (`exclusive` field, example, release/acquire)
- Modify: `software-factory/README.md` (field list, commands, card, menu action, events)
- Test: `software-factory/tests/test_exclusive_display.py`, plus existing `tests/test_docs.py`, `tests/test_authoring_skill.py` must stay green

**Interfaces:**
- Consumes: `exclusive.task_info`, `exclusive.force_release`, `exclusive.status_rows`.

- [ ] **Step 1: Write the failing tests**

```python
def test_row_for_waiting_task(flow):
    run(flow, "t1", "next"); run(flow, "t2", "next")
    rows = {r["id"]: r for r in flow.factory.json("tasks")}
    assert rows["t2"]["exclusive"] == {"name": "emu", "holder": "t1", "holds": False, "waiting": True, "released": False, "paused": False}
    assert rows["t2"]["wait_has_check"] is None
    assert rows["t1"]["exclusive"]["holds"] is True

def test_api_release_route(flow_server): ...  # POST /api/exclusive/emu/release {"task": "t2"} -> holder "t1"; t2 now holds
def test_status_command_lists_queue(flow): ...  # `factory exclusive status --json` -> [{"name": "emu", "holder": "t1", "queue": [{"task": "t2", ...}]}]
def test_menu_has_release_action(inited): ...  # "Release a shared resource" in `factory menu` output
def test_dashboard_page_has_release(): assert "Release" in PAGE and "Keeps " in PAGE and "/api/exclusive/" in PAGE and "t.exclusive" in PAGE
def test_skill_documents_exclusive(): assert "exclusive:" in AUTHORING and "factory exclusive acquire" in AUTHORING
```

- [ ] **Step 2:** Run. Expected: FAIL.
- [ ] **Step 3: Implement.** Card: when `t.exclusive.waiting`: line `Waiting for <name>, used by <holder>` and a "Release" button. It opens a confirmation in the page's own modal (never `window.confirm`, it blocks browser automation) with the text `Release <name> from task <holder>? Its session loses the resource.`, then calls the route with `{task: t.id}`. When `t.exclusive.holds`: `Uses <name>`, or `Keeps <name> while paused` when paused. `Mark done` and `Check now` stay hidden because `wait_has_check` is None. README: add `exclusive` to "Step manifest fields", the three `factory exclusive` commands under "Task life", the card line and "Release" button, the menu action, and an "Exclusive steps" subsection (hold, release, handover, force, per repository). Authoring skill: field reference row and a short example step with `exclusive: android-emulator`.
- [ ] **Step 4:** Run `pytest -q tests/test_exclusive_display.py tests/test_docs.py tests/test_authoring_skill.py tests/test_dashboard_page.py tests/test_init_menu.py`. Expected: PASS.
- [ ] **Step 5:** Commit `exclusive: dashboard, menu, skills and README`.

### Task 5: Milestone 1 gate

- [ ] **Step 1:** Run the full suite. Expected: 478 old tests plus the new ones, all PASS. Fix failures (use superpowers:systematic-debugging).
- [ ] **Step 2:** Commit any fixes: `exclusive: milestone fixes`.

## Milestone 2: "May wait for you"

### Task 6: Hooks in `claude-settings.json`

**Files:**
- Modify: `software-factory/lib/factory/init.py`
- Modify: `software-factory/lib/factory/commands.py` (`version check`)
- Test: `software-factory/tests/test_hook_settings.py`

**Interfaces:**
- Produces: `init.HOOK_EVENTS = {"Stop": "hook stop", "UserPromptSubmit": "hook prompt"}`; `init.hook_command(sub) -> str` (`shlex.quote(str(link_dir() / "factory")) + " " + sub`); `init.ensure_settings(ctx) -> bool` (True when it wrote).
- Handler shape: `{"type": "command", "command": hook_command(sub), "timeout": 10}` in `{"hooks": [handler]}`.

- [ ] **Step 1: Write the failing tests**

```python
def test_init_writes_hooks(inited):
    s = json.loads((inited.fdir / "claude-settings.json").read_text())
    assert s["permissions"]["allow"] == ["Bash(factory:*)", "Bash(factory *)"]
    assert s["hooks"]["Stop"][0]["hooks"][0]["command"].endswith("factory hook stop")
    assert s["hooks"]["UserPromptSubmit"][0]["hooks"][0]["command"].endswith("factory hook prompt")

def test_existing_settings_keep_rules_and_get_hooks_once(factory, origin_repo, library_path):
    f = origin_repo / ".factory"; f.mkdir()
    (f / "claude-settings.json").write_text(json.dumps({"permissions": {"allow": ["Bash(ls:*)"]}, "hooks": {"Stop": [{"hooks": [{"type": "command", "command": "other"}]}]}}))
    factory("init", "--library", library_path, "--create-library"); factory("init", "--library", library_path)
    s = json.loads((f / "claude-settings.json").read_text())
    assert "Bash(ls:*)" in s["permissions"]["allow"] and "Bash(factory *)" in s["permissions"]["allow"]
    commands = [h["command"] for g in s["hooks"]["Stop"] for h in g["hooks"]]
    assert "other" in commands and sum(c.endswith("factory hook stop") for c in commands) == 1

def test_version_check_adds_missing_hooks(inited): ...
    # write settings without hooks; `factory version check --json` -> settings_updated True, hooks present;
    # second run -> settings_updated False
```

- [ ] **Step 2:** Run. Expected: FAIL.
- [ ] **Step 3:** Implement `ensure_settings` with `fsio.update_json` (keeps unknown keys). `init.init` calls it instead of `write_new` for this file and reports the path in `created` or `kept`. `version check` adds `settings_updated` to the report when `initialized` and `repo_state == "same"`.
- [ ] **Step 4:** Run. Expected: PASS. Also run `tests/test_init_menu.py tests/test_repo_version.py`.
- [ ] **Step 5:** Commit `attention: hooks in claude-settings.json`.

### Task 7: `factory hook` commands and adapter focus

**Files:**
- Create: `software-factory/lib/factory/attention.py`
- Modify: `software-factory/lib/factory/commands.py`, `software-factory/lib/factory/cli.py` (`hook` in `NO_VERSION_CHECK`)
- Modify: `software-factory/lib/factory/adapters/base.py` (`"focused"` in OPTIONAL, `focused(handle)`), `adapters/fake.py` (cfg `focused`: bool, default False, records nothing), `adapters/herdr.py` (`bool(self.require_owned(handle).get("focused"))`)
- Test: `software-factory/tests/test_attention_hooks.py`, plus a Herdr unit test in `tests/test_herdr_adapter.py` style using `tests/fake_herdr.py`

**Interfaces:**
- Produces:
  - `attention.DELAY_SECONDS` from env `FACTORY_ATTENTION_DELAY`, default 60. `MESSAGE_LINES = 12`, `MESSAGE_CHARS = 2000`.
  - `attention.now_precise() -> str` (UTC ISO with microseconds).
  - `attention.find_task(ctx, session_id) -> dict | None`
  - `attention.last_message(data) -> str | None` (`last_assistant_message`, else last assistant text in `transcript_path` JSONL: entries with `type == "assistant"`, `message.content` text blocks; any error → None)
  - `attention.on_stop(ctx, data) -> None`, `attention.on_prompt(ctx, data) -> None`, `attention.notify_later(ctx, tid, at) -> None`
  - `attention.clear(ctx, tid, reason) -> bool` (removes `attention`, logs `attention_cleared` with `reason`; False when not set)
  - `attention.run_hook(kind, stdin_text, cwd) -> None` (never raises; loads ctx, checks initialized and `version.repo_version == DATA_VERSION`, dispatches; an error with a known task logs `hook_failed` (`hook`, `error`))
  - CLI: `factory hook stop`, `factory hook prompt`, `factory hook notify-later <id> <at>`. Each returns 0 and prints nothing, whatever happens.

`on_stop` rules (spec 4.3 with user decision N1): only `status == "active"`; skip when `background_tasks` is a non-empty list; set `attention = {"at": now_precise(), "message": trimmed or None}`; log `attention` (`message`: first line); then, when the adapter supports `notify`: focused capability and `focused(handle)` is False → notify now; otherwise (focused, no capability, check error, no handle) → `subprocess.Popen([sys.executable, str(repo.PLUGIN_ROOT / "bin" / "factory"), "hook", "notify-later", tid, at], cwd=ctx.main, start_new_session=True, stdin/stdout/stderr=DEVNULL)`. `notify_later` sleeps `DELAY_SECONDS`, reloads, notifies only when `attention.at == at`.

- [ ] **Step 1: Write the failing tests** (task t1 `active`, `session_id` "sid-1", `terminal_handle {"agent": "t1"}`; `hook(inited, kind, payload)` runs `factory hook <kind>` with `input=json.dumps(payload)` and env `FACTORY_ATTENTION_DELAY`)

```python
def test_stop_on_active_sets_attention_and_notifies(att):
    r = hook(att, "stop", {"session_id": "sid-1", "last_assistant_message": "Which API?\nA or B"})
    assert r.returncode == 0 and r.stdout == "" and r.stderr == ""
    a = task_json(att.fdir, "t1")["attention"]
    assert a["message"] == "Which API?\nA or B"
    assert [c["text"] for c in fake_calls(att.fdir) if c["op"] == "notify"] == ["t1 may wait for you: Which API?"]
    assert any(e["type"] == "attention" for e in events(att.fdir, "t1"))

@pytest.mark.parametrize("status", ["blocked", "waiting_external", "awaiting_approval", "paused", "finished"])
def test_stop_other_status_changes_nothing(att, status): ...

def test_stop_with_background_tasks_changes_nothing(att): ...  # payload "background_tasks": [{"id": "x"}]

def test_prompt_clears(att): ...  # stop then prompt -> no attention, attention_cleared reason "prompt"

@pytest.mark.parametrize("stdin", ["", "not json", json.dumps({"session_id": "unknown"})])
def test_bad_input_is_silent(att, stdin): ...  # returncode 0, stdout == stderr == "", task unchanged

def test_hook_outside_factory_is_silent(tmp_path): ...  # cwd a plain temp dir (not git): returncode 0, no output

def test_focused_uses_delay(att):
    fake_config(att.fdir, focused=True)
    start = time.time(); hook(att, "stop", {"session_id": "sid-1", "last_assistant_message": "Q?"}, delay="1")
    assert time.time() - start < 1 and notifies(att) == []
    wait_until(lambda: notifies(att) == ["t1 may wait for you: Q?"], timeout=10)

def test_focused_prompt_during_delay_no_notify(att): ...  # delay "2", prompt hook right after, sleep 4 -> no notify

def test_no_focus_capability_uses_delay(att): ...  # fake_config capabilities without "focused"; attention cleared during delay -> none; still set -> one

def test_attention_at_is_unique(att): ...  # two stops in a row -> two different `at` values

def test_transcript_fallback(att, tmp_path): ...  # no last_assistant_message, transcript_path with one assistant entry -> message from it

def test_herdr_focused_reads_agent_get(): ...  # fake_herdr returns agent with "focused": true and owned tab -> True
```

- [ ] **Step 2:** Run. Expected: FAIL.
- [ ] **Step 3:** Implement as in Interfaces. `commands.py` hook commands call `attention.run_hook(kind, sys.stdin.read(), os.getcwd())` inside `try/except BaseException: pass` and return 0; `notify-later` calls `attention.notify_later` the same way.
- [ ] **Step 4:** Run `pytest -q tests/test_attention_hooks.py tests/test_herdr_adapter.py tests/test_adapters.py`. Expected: PASS.
- [ ] **Step 5:** Commit `attention: hook commands and adapter focus`.

### Task 8: Clearing, display and docs

**Files:**
- Modify: `software-factory/lib/factory/state.py` (`update`: clear on status change)
- Modify: `software-factory/lib/factory/session.py` (`logged_delivery`: clear on success)
- Modify: `software-factory/lib/factory/board.py` (row `attention`, sort, `render_rows`)
- Modify: `software-factory/lib/factory/web/dashboard.html` (card)
- Modify: `software-factory/skills/software-factory/SKILL.md` (Show tasks and need-the-user lists include `attention`)
- Modify: `software-factory/README.md` ("May wait for you" section, hooks, events `attention`, `attention_cleared`, `hook_failed`, `factory hook` commands, card line, sort)
- Test: `software-factory/tests/test_attention_display.py`

**Interfaces:**
- Consumes: `attention.clear`.
- `state.update(ctx, tid, fn)` keeps its signature (tests monkeypatch it). Inside `change`, it compares the status before and after `fn`; when it changed and `attention` is set, it pops it; after the write, it logs `attention_cleared` (`reason: "status"`) with a local import of `events`.
- Board row: `"attention": task.get("attention")`; sort key: 0 for `blocked` or `attention`, 1 for `awaiting_approval`, else 2; `render_rows` status line gets `, may wait for you: <first line>`.

- [ ] **Step 1: Write the failing tests**

```python
def test_block_clears_attention(att): ...  # stop hook, then `factory block "q"` -> no attention; attention_cleared reason "status"
def test_dashboard_send_prompt_clears(att_server): ...  # POST /api/tasks/t1/send-prompt -> no attention, reason "prompt"
def test_tasks_sort_attention_with_blocked(att): ...  # t1 active+attention, t2 awaiting_approval, t3 active -> order t1, t2, t3
def test_row_has_attention(att): ...  # row["attention"]["message"] == "Q?"
def test_text_list_says_may_wait(att): ...  # "may wait for you: Q?" in `factory tasks`
def test_cleared_logged_once(att): ...  # only one attention_cleared after block + unblock
def test_dashboard_page_has_attention(): assert "May wait for you" in PAGE and "t.attention" in PAGE
```

- [ ] **Step 2:** Run. Expected: FAIL.
- [ ] **Step 3:** Implement. Card: when `t.attention`, the card class is `card s-blocked`, and a block shows `May wait for you · <ago(t.attention.at)> ago` and the message in a `pre` (plain text, `white-space: pre-wrap`).
- [ ] **Step 4:** Run `pytest -q tests/test_attention_display.py tests/test_races.py tests/test_board.py tests/test_docs.py tests/test_dashboard_page.py`. Expected: PASS.
- [ ] **Step 5:** Commit `attention: clearing, card, task list and docs`.

### Task 9: Real check and milestone 2 gate

**Files:**
- Create: `verification/software-factory/real_attention_check.py` (and its output `verification/software-factory/real-attention-check.md`)

- [ ] **Step 1:** Write the script. It creates a temp dir under `verification/software-factory/work/`, a bare origin and a clone (like `conftest.origin_repo`), a temp library, sets `FACTORY_TERMINAL=fake`, `FACTORY_LINK_DIR=<tmp>/bin` (with the link to `bin/factory`), and PATH with that dir first. It runs `factory init`, writes a one-step `ai` pipeline, `factory launch` (fake adapter records the claude args), reads `session_id` from `task.json`, then runs the real Claude binary (`shutil.which("claude")` resolves the binary, not the zsh function) in the worktree: `claude -p "Ask me which color I prefer, in plain text. Do not use any tool. Then stop." --session-id <id> --settings <repo>/.factory/claude-settings.json`. Then it checks `task.json` has `attention` with a message, writes the result (pass or fail, the message, the events) to `real-attention-check.md`, and removes the temp dir.
- [ ] **Step 2:** Run `uv run --with pyyaml python verification/software-factory/real_attention_check.py`. Expected: the report says PASS.
- [ ] **Step 3:** Run the full suite. Expected: all PASS.
- [ ] **Step 4:** Commit `attention: real check and milestone fixes` (include the script and its report).

## Final verification

- [ ] Run the full suite with `--junitxml verification/software-factory/factory-improvement-junit.xml`. Write `verification/software-factory/factory-improvement-report.md` with one section per milestone (tests and results) and `factory-improvement-dod.md` with every Definition Of Done bullet of `prompts/factory_improvment.md` and its evidence.
- [ ] Check `git rev-parse master` equals the saved hash. Check `git status` shows no change outside `software-factory/`, `specs/`, `plans/`, `verification/software-factory/` (the earlier `prompts/` changes stay uncommitted).
- [ ] Recheck the Facts of the prompt (hook input fields, Herdr `focused`, `write_new` replaced) and note them in the DoD file.
- [ ] Commit `factory improvement: verification`.
