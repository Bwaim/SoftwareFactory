import os
import re
import shlex
import subprocess
from pathlib import Path

from . import config, events, repo, session, state
from .errors import FactoryError
from .registry import CREATE_WORKTREE, Registry

DONE_CHECK_TIMEOUT = 300
POLL_CHECK_TIMEOUT = 60
APPROVAL_STEP = "user-validation"
FACTORY_SPAN_RE = re.compile(r"`(factory [^`]*)`")
MAX_JUMPS = 3


def cmd(task, text):
    return f"factory {text}{repo.task_flag(task)}"


def with_task_flag(text, tid):
    def add(m):
        inner = m.group(1)
        return m.group(0) if "--task" in inner else f"`{inner} --task {tid}`"
    return FACTORY_SPAN_RE.sub(add, text)


def task_cwd(ctx, task):
    return Path(task["worktree"]) if task.get("worktree") else ctx.main


def artifacts_dir(ctx, task):
    return (state.task_dir(ctx, task["id"]) / "artifacts").resolve()


def run_check(ctx, task, command, timeout, values=None):
    env = script_env(ctx, task, values or {})
    try:
        r = subprocess.run(command, shell=True, cwd=task_cwd(ctx, task), env=env,
                           capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return False, f"Timed out after {timeout} s."
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


def header(task, step):
    lines = [
        f"Task `{task['id']}`, step {task['position'] + 1} of {len(task['steps'])}: {state.step_path_str(task)}",
        f"Type: {step.type}. Runs in: {step.run_in}.",
    ]
    if step.done_when:
        lines.append(f"Done when: {step.done_when}")
    return lines


def context_lines(ctx, task, step, values):
    lines = []
    if values:
        lines += ["", "Config:"] + [f"- {k}: {v}" for k, v in values.items()]
    reads = step.get("reads") or []
    if reads:
        lines += ["", "Task state:"] + [f"- {k}: {task['state'].get(k, '(not set)')}" for k in reads]
    writes = step.get("writes") or []
    if writes:
        lines += ["", f"Save these task state keys with `factory state set <key> <value>`: {', '.join(writes)}."]
    lines += ["", f"Artifacts folder: {artifacts_dir(ctx, task)}"]
    return lines


def subagent_block(ctx, task, entry, step, values):
    model, effort = settings(entry, step)
    prompt = [
        f"You run one step of the factory task `{task['id']}`: {state.step_path_str(task)}.",
        f"Working folder: {task_cwd(ctx, task)}",
        *context_lines(ctx, task, step, values),
        "",
        "Instructions:",
        step.body.strip(),
        "",
        "Write your outputs with `factory state set <key> <value>`.",
        "End with a short report. If you need an answer from the user, say so in the report and stop.",
    ]
    return [
        "Run this step in a subagent. Call the Agent tool with:",
        f"- model: {model or 'inherit'}",
        f"- effort: {effort or 'inherit'}",
        "- prompt:",
        "<<<",
        with_task_flag("\n".join(prompt), task["id"]),
        ">>>",
    ]


def end_line(step):
    if step.wait_external:
        return "When the actions of this step are done, run `factory wait`. The factory tells you when the external event happens."
    if step.run_in == "subagent":
        return "When the subagent ends, read its report. If it needs the user, ask the user, then run `factory next` again. Otherwise run `factory done`."
    return "When the step is done, run `factory done`."


def render(ctx, task, entry, step, values):
    lines = header(task, step)
    if step.run_in == "subagent" and step.type in ("prompt", "skill"):
        lines += [""] + subagent_block(ctx, task, entry, step, values)
    else:
        lines += context_lines(ctx, task, step, values)
        if step.type == "script":
            lines += ["", "Run the step script with `factory run-script`. It prints the script output and its exit code."]
        else:
            lines += ["", "Instructions:", step.body.strip()]
    lines += ["", end_line(step)]
    text = "\n".join(lines)
    return with_task_flag(text, task["id"]) if not task.get("worktree") else text


def render_missing(task, step, missing):
    lines = header(task, step) + ["", "Some config values are missing. Ask the user for each one, then save it:"]
    for key in missing:
        desc = step.config_spec[key].get("description", "")
        lines.append(f"- `{key}`: {desc} Save it with `factory config set {step.id} {key} <value>`.")
    lines.append("Then run `factory next` again.")
    text = "\n".join(lines)
    return with_task_flag(text, task["id"]) if not task.get("worktree") else text


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
        task = start(ctx, tid, entry, step)
    return render(ctx, task, entry, step, values)


def block(ctx, tid, reason):
    task = state.update(ctx, tid, lambda t: state.set_status(t, "blocked", reason))
    events.log(ctx, tid, "task_blocked", state.step_path_str(task), reason=reason)
    session.notify(ctx, f"Task {tid} is blocked: {reason}")
    return f"Task {tid} is blocked. Ask the user, then run `{cmd(task, 'unblock')}` when the user has answered."


def unblock(ctx, tid):
    if state.load(ctx, tid)["status"] != "blocked":
        raise FactoryError(f"Task {tid} is not blocked.")
    task = state.update(ctx, tid, lambda t: state.set_status(t, "active"))
    events.log(ctx, tid, "task_unblocked", state.step_path_str(task))
    return f"Task {tid} is active again."


def require_awaiting(task):
    if task["status"] != "awaiting_approval" or not task.get("approval"):
        raise FactoryError(f"Task {task['id']} is not waiting for an approval.")


def approve(ctx, tid, send=False):
    require_awaiting(state.load(ctx, tid))

    def change(t):
        t["approval"]["approved"] = True
        state.set_status(t, "active")

    task = state.update(ctx, tid, change)
    events.log(ctx, tid, "approved", state.step_path_str(task))
    if send:
        session.deliver(ctx, tid, f"The user approved. Run `{cmd(task, 'done')}`.")
    return f"Approved. Run `{cmd(task, 'done')}`."


def request_changes(ctx, tid, text, send=False):
    require_awaiting(state.load(ctx, tid))

    def change(t):
        t["approval"] = None
        t["started"] = None
        state.set_status(t, "active")

    task = state.update(ctx, tid, change)
    events.log(ctx, tid, "changes_requested", state.step_path_str(task), text=text)
    if send:
        session.deliver(ctx, tid, f"The user requested changes: {text}\nMake the changes, then run `{cmd(task, 'next')}`.")
    return f"Changes requested. Make them, then run `{cmd(task, 'next')}`."


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


def advance(ctx, tid, event_type):
    before = state.load(ctx, tid)
    events.log(ctx, tid, event_type, state.step_path_str(before))

    def change(t):
        t["position"] += 1
        t["started"] = None
        t["approval"] = None
        if t["position"] >= len(t["steps"]):
            state.set_status(t, "finished")
            t["column"] = repo.DONE_COLUMN
        elif t["status"] != "active":
            state.set_status(t, "active")

    task = state.update(ctx, tid, change)
    if task["status"] != "finished":
        return f"Step done. Run `{cmd(task, 'next')}`."
    if before["column"] != repo.DONE_COLUMN:
        events.log(ctx, tid, "column_changed", None, **{"from": before["column"], "to": repo.DONE_COLUMN})
    events.log(ctx, tid, "task_finished")
    session.notify(ctx, f"Task {tid} is finished.")
    return "The pipeline is finished. Tell the user that the task is finished."


def done(ctx, tid):
    task = state.load(ctx, tid)
    if task["status"] == "finished":
        return "The pipeline is finished."
    require_running(task)
    entry, step = load_step(ctx, task)
    if step.done_check:
        values, _ = config.resolve(ctx, step, entry.get("with"))
        ok, output = run_check(ctx, task, step.done_check, DONE_CHECK_TIMEOUT, values)
        if not ok:
            events.log(ctx, tid, "done_check_failed", state.step_path_str(task), output=output)
            raise FactoryError(f"The done check failed. The step is not done.\nCheck: {step.done_check}\n{output}")
    return advance(ctx, tid, "step_done")


def skip(ctx, tid):
    task = state.load(ctx, tid)
    require_running(task)
    entry, step = load_step(ctx, task)
    if step.required:
        raise FactoryError(f"The step `{step.id}` is required. It cannot be skipped.")
    return advance(ctx, tid, "step_skipped")


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
    require_running(task)
    index = find_target(task, target)
    from_path, to_path = state.step_path_str(task), state.step_path_str(task, index)

    def change(t):
        key = str(index)
        t["goto_counts"][key] = t["goto_counts"].get(key, 0) + 1
        t["position"] = index
        t["started"] = None
        t["approval"] = None
        if t["goto_counts"][key] >= MAX_JUMPS:
            state.set_status(t, "blocked", f"loop on {to_path}")
        else:
            state.set_status(t, "active")

    task = state.update(ctx, tid, change)
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
    events.log(ctx, tid, "external_event", state.step_path_str(task), how=how)
    advance(ctx, tid, "step_done")
    task = state.load(ctx, tid)
    happened = (step.done_when or "An external event.").removesuffix(".")
    session.notify(ctx, f"Task {tid}: {step.done_when or 'the external event happened'}")
    session.deliver(ctx, tid, f"The external event happened: {happened}. Run `{cmd(task, 'next')}`.")


def poll(ctx):
    results = []
    for task in state.list_tasks(ctx):
        if task["status"] != "waiting_external":
            continue
        entry, step = load_step(ctx, task)
        if not step.done_check:
            continue
        values, _ = config.resolve(ctx, step, entry.get("with"))
        ok, output = run_check(ctx, task, step.done_check, POLL_CHECK_TIMEOUT, values)
        row = {"id": task["id"], "ended": ok, "output": None if ok else output[-500:], "error": None}
        if ok:
            try:
                end_wait(ctx, task["id"], "check")
            except FactoryError as e:
                row["error"] = str(e)
        results.append(row)
    return results


def external_done(ctx, tid):
    task = state.load(ctx, tid)
    if task["status"] != "waiting_external":
        raise FactoryError(f"Task {tid} is not waiting for an external event.")
    entry, step = load_step(ctx, task)
    if step.done_check:
        raise FactoryError("This step has a done check. The wait ends when the check passes. Run `factory poll`.")
    end_wait(ctx, tid, "manual")


def script_env(ctx, task, values):
    env = {**os.environ, "FACTORY_TASK": task["id"]}
    for key, value in values.items():
        env["FACTORY_CONFIG_" + key.upper().replace("-", "_")] = str(value)
    return env


def run_script(ctx, tid):
    task = state.load(ctx, tid)
    require_running(task)
    entry, step = load_step(ctx, task)
    if step.type != "script":
        raise FactoryError(f"The step `{step.id}` is not a script step.")
    first_line = step.body.strip().splitlines()[0].strip() if step.body.strip() else ""
    script = (step.path.parent / first_line).resolve()
    if not first_line or not script.is_file():
        raise FactoryError(f"The script of step `{step.id}` does not exist: {script}")
    values, _ = config.resolve(ctx, step, entry.get("with"))
    r = subprocess.run(["bash", str(script)], cwd=task_cwd(ctx, task), env=script_env(ctx, task, values))
    print(f"Script exit code: {r.returncode}")
    return r.returncode


def status_text(ctx, tid):
    task = state.load(ctx, tid)
    lines = [
        f"Task: {task['id']}",
        f"Description: {task['description']}",
        f"Pipeline: {task['pipeline']}",
        f"Step: {state.step_path_str(task)} ({min(task['position'] + 1, len(task['steps']))} of {len(task['steps'])})",
        f"Status: {task['status']}" + (f" ({task['status_reason']})" if task.get("status_reason") else ""),
    ]
    return "\n".join(lines)
