import os
import shlex
import subprocess
import sys
from pathlib import Path

from . import config, events, exclusive, fsio, keys, loops, render, repo, session, state
from .errors import FactoryError
from .registry import CREATE_WORKTREE, Registry

DONE_CHECK_TIMEOUT = 300
POLL_CHECK_TIMEOUT = 60
APPROVAL_STEP = "user-validation"
MAX_JUMPS = 3
CHECK_BUSY = "A check is already running."
NOT_WAITING = "The task does not wait on a done check."
CHECK_OUTPUT_CHARS = 500
EXCLUSIVE_WAIT = ("The step `{id}` needs `{name}`, now used by task `{holder}`. "
                  "The factory starts this task when it is free. End your turn.")
WAITS_FOR = "The step waits for `{name}`. End your turn. The factory sends you a message when it is free."
NOT_EXTERNAL = ("Task {id} waits for `{name}`, not for an external event. "
                "Release it with `factory exclusive release {name} --force` if the holder is stuck.")


def cmd(task, text):
    return f"factory {text}"


def task_cwd(ctx, task):
    return Path(task["worktree"]) if task.get("worktree") else ctx.main


def artifacts_dir(ctx, task):
    return (state.task_dir(ctx, task["id"]) / "artifacts").resolve()


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


def load_step(ctx, task):
    entry = state.current_entry(task)
    if entry is None:
        raise FactoryError("The pipeline is finished.")
    return entry, Registry.load(ctx).step(entry["id"])


def settings(entry, step):
    return entry.get("model") or step.model, entry.get("effort") or step.effort


def require_running(task):
    if task["status"] == "paused":
        raise FactoryError("The task is paused. Resume it first.")


def on_start(ctx, task, entry, step):
    pending = []
    column = entry.get("column") or step.column
    if column and column != task["column"]:
        pending.append(("column_changed", {"from": task["column"], "to": column}))
        task["column"] = column
    if step.id == APPROVAL_STEP:
        values, _ = config.resolve(ctx, step, entry.get("with"))
        target = values.get("target") or "worktree"
        task["approval"] = {"position": task["position"], "approved": False, "target": target, "artifact_key": values.get("artifact_key") or None}
        state.set_status(task, "awaiting_approval")
        pending.append(("approval_requested", {"target": target}))
    return pending


def start(ctx, tid, entry, step):
    pending = []

    def change(t):
        t["started"] = t["position"]
        pending.extend(on_start(ctx, t, entry, step))

    task = state.update(ctx, tid, change)
    path = state.step_path_str(task)
    model, effort = settings(entry, step)
    events.log(ctx, tid, "step_started", path, run_in=step.run_in, model=model, effort=effort)
    for event_type, details in pending:
        events.log(ctx, tid, event_type, path, **details)
    return task


def key_values(task):
    return {**(task.get("state") or {}), "task_id": task["id"], "description": task.get("description") or ""}


def step_line(task):
    return f"Step {task['position'] + 1} of {len(task['steps'])}: {state.step_path_str(task)}"


def render_step(task, entry, step, values):
    prompt = render.fill(step.body, key_values(task), values) if step.type == "ai" else ""
    model, effort = settings(entry, step)
    return render.step_text(step, prompt, step_line(task), keys.outputs_of(step), model, effort, loops.controlled_keys(task, step),
                            exclusive=step.exclusive)


def render_missing(task, step, missing):
    lines = [step_line(task), "", "Some config values are missing. Ask the user for each one, then save it:"]
    for key in missing:
        desc = step.config_spec[key].get("description", "")
        lines.append(f"- `{key}`: {desc} Save it with `factory config set {step.id} {key} <value>`.")
    lines.append("Then run `factory next` again.")
    return "\n".join(lines)


def next_step(ctx, tid):
    task = state.load(ctx, tid)
    if task["status"] == "finished":
        return "The pipeline is finished."
    require_running(task)
    entry, step = load_step(ctx, task)
    values, missing = config.resolve(ctx, step, entry.get("with"))
    if missing:
        for key in missing:
            events.log(ctx, tid, "config_asked", state.step_path_str(task), key=key)
        return render_missing(task, step, missing)
    if task.get("started") != task["position"]:
        if step.exclusive:
            got, holder = exclusive.claim(ctx, tid, step.exclusive, "next")
            if not got:
                holder = holder or exclusive.read(ctx, step.exclusive)["holder"] or "another task"
                return EXCLUSIVE_WAIT.format(id=step.id, name=step.exclusive, holder=holder)
        task = start(ctx, tid, entry, step)
    elif step.exclusive and exclusive.read(ctx, step.exclusive)["holder"] != tid:
        return render_step(task, entry, step, values) + "\n\n" + render.released_line(step.exclusive)
    return render_step(task, entry, step, values)


def require_not_queued(task):
    wait = task.get("exclusive_wait")
    if wait:
        raise FactoryError(WAITS_FOR.format(name=wait["name"]))


def require_open(task):
    if task["status"] in ("finished", "paused"):
        raise FactoryError(f"Task {task['id']} is {task['status']}.")


def block(ctx, tid, reason):
    def change(t):
        require_open(t)
        state.set_status(t, "blocked", reason)

    task = state.update(ctx, tid, change)
    events.log(ctx, tid, "task_blocked", state.step_path_str(task), reason=reason)
    session.notify(ctx, f"Task {tid} is blocked: {reason}")
    return f"Task {tid} is blocked. {session.ASK_IN_TEXT} When the user has answered, run `{cmd(task, 'unblock')}`."


def unblock(ctx, tid):
    def change(t):
        if t["status"] != "blocked":
            raise FactoryError(f"Task {tid} is not blocked.")
        state.set_status(t, "active")

    task = state.update(ctx, tid, change)
    events.log(ctx, tid, "task_unblocked", state.step_path_str(task))
    return f"Task {tid} is active again."


def require_unchanged(task, position, statuses):
    if task["position"] != position or task["status"] not in statuses:
        raise FactoryError(f"Task {task['id']} changed while this command ran. Check its state and try again.")


def require_awaiting(task):
    if task["status"] != "awaiting_approval" or not task.get("approval"):
        raise FactoryError(f"Task {task['id']} is not waiting for an approval.")


def deliver_quietly(ctx, tid, text):
    try:
        session.deliver(ctx, tid, text)
    except FactoryError as e:
        return str(e)
    return None


def approve(ctx, tid, send=False):
    def change(t):
        require_awaiting(t)
        t["approval"]["approved"] = True
        state.set_status(t, "active")

    task = state.update(ctx, tid, change)
    events.log(ctx, tid, "approved", state.step_path_str(task))
    delivery_error = deliver_quietly(ctx, tid, f"The user approved. Run `{cmd(task, 'done')}`.") if send else None
    return f"Approved. Run `{cmd(task, 'done')}`.", delivery_error


def request_changes(ctx, tid, text, send=False):
    def change(t):
        require_awaiting(t)
        t["approval"] = None
        t["started"] = None
        state.set_status(t, "active")

    task = state.update(ctx, tid, change)
    events.log(ctx, tid, "changes_requested", state.step_path_str(task), text=text)
    delivery_error = None
    if send:
        delivery_error = deliver_quietly(ctx, tid, f"The user requested changes: {text}\nMake the changes, then run `{cmd(task, 'next')}`.")
    return f"Changes requested. Make them, then run `{cmd(task, 'next')}`.", delivery_error


def approval_check(ctx, tid):
    task = state.load(ctx, tid)
    approval = task.get("approval")
    return bool(approval and approval.get("position") == task["position"] and approval.get("approved"))


def open_ide(ctx, tid):
    command = config.get_value(ctx, APPROVAL_STEP, "ide_command")
    if not command:
        raise FactoryError(
            "The IDE command is not set. Ask the user, then run "
            "`factory config set user-validation ide_command '<command with {path}>'`, for example `code {path}`."
        )
    path = str(task_cwd(ctx, state.load(ctx, tid)))
    try:
        argv = [part.replace("{path}", path) for part in shlex.split(command)]
    except ValueError as e:
        raise FactoryError(f"The IDE command is not valid: {e}. Fix it with `factory config set user-validation ide_command '<command>'`.")
    if not argv:
        raise FactoryError("The IDE command is empty. Set it with `factory config set user-validation ide_command '<command>'`.")
    try:
        subprocess.Popen(argv, start_new_session=True, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError as e:
        raise FactoryError(f"Cannot start the IDE command `{argv[0]}`: {e.strerror or e}.")
    return argv


ADVANCE_STATUSES = ("active", "blocked", "awaiting_approval", "waiting_external")


def clear_step(t):
    t["started"] = None
    t["command_result"] = None
    t["approval"] = None
    t.pop("exclusive_wait", None)
    t.pop("exclusive_released", None)


def forward(t, reason=None):
    t["position"] += 1
    clear_step(t)
    if t["position"] >= len(t["steps"]):
        state.set_status(t, "finished")
        t["column"] = repo.DONE_COLUMN
    elif reason:
        state.set_status(t, "blocked", reason)
    elif t["status"] != "active":
        state.set_status(t, "active")


def move(ctx, tid, event_type, position, statuses, first_event, decide=None):
    info = {}

    def change(t):
        require_unchanged(t, position, statuses)
        info.clear()
        info.update(kind="step", column=t["column"], path=state.step_path_str(t))
        if first_event:
            first_event()
        events.log(ctx, tid, event_type, info["path"])
        if decide:
            decide(t, info)
        if info["kind"] != "loop":
            forward(t, info.get("reason"))

    task = state.update(ctx, tid, change)
    exclusive.sync(ctx, tid)
    return task, info


def log_finished(ctx, tid, info):
    if info["column"] != repo.DONE_COLUMN:
        events.log(ctx, tid, "column_changed", None, **{"from": info["column"], "to": repo.DONE_COLUMN})
    events.log(ctx, tid, "task_finished")


def stepped(ctx, tid, task, info):
    if task["status"] != "finished":
        return f"Step done. Run `{cmd(task, 'next')}`."
    log_finished(ctx, tid, info)
    session.notify(ctx, f"Task {tid} is finished.")
    return "The pipeline is finished. Tell the user that the task is finished."


def advance(ctx, tid, event_type, position, statuses=ADVANCE_STATUSES, first_event=None):
    task, info = move(ctx, tid, event_type, position, statuses, first_event)
    return stepped(ctx, tid, task, info)


def done(ctx, tid):
    task = state.load(ctx, tid)
    if task["status"] == "finished":
        return "The pipeline is finished."
    require_running(task)
    require_not_queued(task)
    entry, step = load_step(ctx, task)
    problem = output_problem(task, step)
    if problem:
        events.log(ctx, tid, "done_check_failed", state.step_path_str(task), output=problem)
        raise FactoryError(f"The step is not done. {problem}")
    if step.done_check:
        values, _ = config.resolve(ctx, step, entry.get("with"))
        ok, output = run_check(ctx, task, step, step.done_check, DONE_CHECK_TIMEOUT, values)
        if not ok:
            events.log(ctx, tid, "done_check_failed", state.step_path_str(task), output=output)
            raise FactoryError(f"The done check failed. The step is not done.\nCheck: {step.done_check}\n{output}")
    return settle(ctx, tid, task["position"])[1]


def settle(ctx, tid, position, statuses=ADVANCE_STATUSES, first_event=None):
    task, info = move(ctx, tid, "step_done", position, statuses, first_event, decide_loop)
    if info["kind"] == "loop":
        return "loop", looped(ctx, tid, task, info)
    if info["kind"] == "limit":
        return "limit", limit_reached(ctx, tid, task, info)
    return "step", stepped(ctx, tid, task, info)


def decide_loop(t, info):
    loop = loops.loop_ending_at(t, t["position"])
    if loop is None or not loops.is_set((t.get("state") or {}).get(loop["while"])):
        return
    info.update(entry=loop["entry"], key=loop["while"], max=loop["max"], target=state.step_path_str(t, loop["first"]))
    if loop["jumps"] >= loop["max"]:
        info.update(kind="limit", reason=f"Loop limit reached on `{loop['entry']}`: `{loop['while']}` is still set")
        return
    loop["jumps"] += 1
    loops.reset_counts(t, loop["first"], loop)
    t["position"] = loop["first"]
    clear_step(t)
    state.set_status(t, "active")
    info.update(kind="loop", n=loop["jumps"])


def looped(ctx, tid, task, info):
    events.log(ctx, tid, "loop_back", info["path"], entry=info["entry"], to=info["target"], round=info["n"], max=info["max"])
    return f"Loop {info['n']} of {info['max']}: back to `{info['target']}`. Run `{cmd(task, 'next')}`."


def limit_reached(ctx, tid, task, info):
    events.log(ctx, tid, "loop_limit", info["path"], entry=info["entry"], key=info["key"])
    if task["status"] == "finished":
        log_finished(ctx, tid, info)
        session.notify(ctx, f"Task {tid} finished, but the loop limit was reached on `{info['entry']}`: `{info['key']}` is still set.")
        return f"The pipeline is finished, but the loop limit was reached on `{info['entry']}`: `{info['key']}` is still set. Tell the user."
    events.log(ctx, tid, "task_blocked", state.step_path_str(task), reason=info["reason"])
    session.notify(ctx, f"Task {tid} is blocked: {info['reason']}")
    return (f"{info['reason']}. The task is blocked. Ask the user what to do. When the user says to go on, run `{cmd(task, 'unblock')}`. "
            f"For one more round, after the user approves, run `factory goto \"{info['target']}\" --reason \"<why>\"`.")


def skip(ctx, tid):
    task = state.load(ctx, tid)
    require_running(task)
    entry, step = load_step(ctx, task)
    if step.required:
        raise FactoryError(f"The step `{step.id}` is required. It cannot be skipped.")
    return advance(ctx, tid, "step_skipped", task["position"])


def find_target(task, target):
    parts = [p.strip() for p in target.split(">") if p.strip()]

    def matches(i):
        path = task["steps"][i]["path"]
        return path == parts or (len(parts) == 1 and path[-1] == parts[0])

    if parts and parts[-1] == CREATE_WORKTREE:
        raise FactoryError("`create-worktree` cannot run again.")
    earlier = [i for i in range(task["position"]) if matches(i)]
    if earlier:
        return earlier[-1]
    if any(matches(i) for i in range(task["position"], len(task["steps"]))):
        raise FactoryError("This step is not before the current step. To move forward, skip steps with `factory skip`, after user approval.")
    raise FactoryError(f"This task has no step `{target}`.")


def goto(ctx, tid, target, reason):
    task = state.load(ctx, tid)
    require_open(task)
    index = find_target(task, target)
    from_path, to_path = state.step_path_str(task), state.step_path_str(task, index)

    def change(t):
        require_unchanged(t, task["position"], ADVANCE_STATUSES)
        key = str(index)
        t["goto_counts"][key] = t["goto_counts"].get(key, 0) + 1
        t["position"] = index
        clear_step(t)
        loops.reset_counts(t, index)
        if t["goto_counts"][key] >= MAX_JUMPS:
            state.set_status(t, "blocked", f"loop on {to_path}")
        else:
            state.set_status(t, "active")

    task = state.update(ctx, tid, change)
    exclusive.sync(ctx, tid)
    events.log(ctx, tid, "step_goto", to_path, **{"from": from_path, "to": to_path, "reason": reason})
    if task["status"] == "blocked":
        events.log(ctx, tid, "task_blocked", to_path, reason=task["status_reason"])
        session.notify(ctx, f"Task {tid} is blocked: {task['status_reason']}")
        return f"The task is blocked: {task['status_reason']}. Ask the user what to do."
    return f"Moved back to {to_path}. Run `{cmd(task, 'next')}`."


def wait(ctx, tid):
    task = state.load(ctx, tid)
    require_running(task)
    entry, step = load_step(ctx, task)
    if not step.wait_external:
        raise FactoryError(f"The step `{step.id}` does not wait for an external event.")
    reason = step.done_when or "An external event."
    task = state.update(ctx, tid, lambda t: state.set_status(t, "waiting_external", reason))
    events.log(ctx, tid, "waiting_started", state.step_path_str(task), reason=reason)
    return "The task now waits for the external event. Stop here. The factory sends you a message when it happens."


def end_wait(ctx, tid, how):
    task = state.load(ctx, tid)
    if task["status"] != "waiting_external":
        raise FactoryError(f"Task {tid} is not waiting for an external event.")
    entry, step = load_step(ctx, task)
    path = state.step_path_str(task)
    kind, text = settle(ctx, tid, task["position"], ("waiting_external",),
                        lambda: events.log(ctx, tid, "external_event", path, how=how))
    task = state.load(ctx, tid)
    happened = (step.done_when or "An external event.").removesuffix(".")
    session.notify(ctx, f"Task {tid}: {step.done_when or 'the external event happened'}")
    if task["status"] == "finished":
        return
    then = f"Run `{cmd(task, 'next')}`." if kind == "step" else text
    session.deliver(ctx, tid, f"The external event happened: {happened}. {then}")


def check_result(tid, ended=False, output=None, error=None, busy=False):
    return {"id": tid, "ended": ended, "output": output, "error": error, "busy": busy}


def waiting_step(ctx, task):
    if task["status"] != "waiting_external" or task.get("exclusive_wait"):
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
    try:
        exclusive.recheck(ctx)
    except Exception as e:
        print(f"exclusive recheck failed: {e}", file=sys.stderr, flush=True)
    results = []
    for task in state.list_tasks(ctx):
        try:
            if waiting_step(ctx, task) is None:
                continue
            results.append(check_task(ctx, task["id"]))
        except Exception as e:
            results.append(check_result(task["id"], error=str(e)))
    return results


def is_waiting_check(reg, task):
    if task["status"] != "waiting_external" or task.get("exclusive_wait"):
        return False
    entry = state.current_entry(task)
    return entry is not None and bool(reg.step(entry["id"]).done_check)


def waiting_checks(ctx):
    try:
        reg = Registry.load(ctx)
        tasks = state.list_tasks(ctx)
    except Exception:
        return []
    ids = []
    for task in tasks:
        try:
            if is_waiting_check(reg, task):
                ids.append(task["id"])
        except Exception:
            continue
    return ids


def external_done(ctx, tid):
    task = state.load(ctx, tid)
    if task["status"] != "waiting_external":
        raise FactoryError(f"Task {tid} is not waiting for an external event.")
    if task.get("exclusive_wait"):
        raise FactoryError(NOT_EXTERNAL.format(id=tid, name=task["exclusive_wait"]["name"]))
    entry, step = load_step(ctx, task)
    if step.done_check:
        raise FactoryError("This step has a done check. The wait ends when the check passes. Run `factory poll`.")
    end_wait(ctx, tid, "manual")


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
    require_not_queued(task)
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
    for key in missing_outputs(state.load(ctx, tid), step):
        print(f"The command did not set the output `{key}`.", flush=True)
    return r.returncode


def missing_outputs(task, step):
    values = task.get("state") or {}
    return [key for key, out in keys.outputs_of(step).items()
            if not out["optional"] and (values.get(key) is None or str(values.get(key)).strip() == "")]


def output_problem(task, step):
    values = task.get("state") or {}
    outputs = keys.outputs_of(step)
    missing = missing_outputs(task, step)
    if missing and step.type == "command":
        return f"The step command did not set the output `{missing[0]}`. Run `factory block` and tell the user."
    if missing:
        return f"The output `{missing[0]}` is not set. Set it with `factory state set {missing[0]} <value>`."
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
            try:
                task = state.update(ctx, tid, lambda t: t.__setitem__("rename_error", problem))
                events.log(ctx, tid, "rename_failed", state.step_path_str(task), reason=problem)
            except Exception:
                pass
    return value, problem


def loop_suffix(task):
    loop = loops.current_loop(task)
    return f", loop {loop['n']} of {loop['max']}" if loop else ""


def status_text(ctx, tid):
    task = state.load(ctx, tid)
    lines = [
        f"Task: {task['id']}",
        f"Description: {task['description']}",
        f"Pipeline: {task['pipeline']}",
        f"Step: {state.step_path_str(task)} ({min(task['position'] + 1, len(task['steps']))} of {len(task['steps'])})" + loop_suffix(task),
        f"Status: {task['status']}" + (f" ({task['status_reason']})" if task.get("status_reason") else ""),
    ]
    held = exclusive.holder_text(ctx, task)
    if held:
        lines.append(held)
    return "\n".join(lines)
