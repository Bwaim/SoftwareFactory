import sys
from contextlib import ExitStack

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
    with ExitStack() as stack:
        try:
            got = stack.enter_context(fsio.try_locked(state.task_dir(ctx, tid) / "rename"))
        except FileNotFoundError:
            return False
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
        if not task.get("claude_rename_pending") or task["status"] == "finished":
            continue
        if session.live_state(ctx, task) == "gone":
            continue
        try:
            apply_pending(ctx, task)
        except Exception as e:
            print(f"rename of {task['id']} failed: {e}", file=sys.stderr, flush=True)
