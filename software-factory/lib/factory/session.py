import uuid

from . import adapters, events, state
from .adapters.base import AdapterError
from .errors import FactoryError

NO_WORKTREE_PIPELINES = frozenset()

ASK_IN_TEXT = (
    "Ask the user in plain text, never with the AskUserQuestion tool, then end your turn. "
    "The answer can come from this tab, the orchestrator or the dashboard."
)
FIRST_PROMPT = (
    "You run factory task `{id}`. Run `{next}` and follow its instructions. "
    "When the step is done, run `{done}`. Repeat until `{next}` says the pipeline is finished. "
    "When you need an answer from the user: " + ASK_IN_TEXT
)
PAUSE_WAIT_SECONDS = 3600
RESUME_PROMPT = "The factory resumed this task. Run `{status}`, then continue with `{next}`."
QUESTION_BOX = "The session shows a question box. Answer it in the task tab: factory terminal focus {id}."


def factory_cmd(task, sub):
    return f"factory {sub}" + ("" if task.get("worktree") else f" --task {task['id']}")


def first_prompt(task):
    return FIRST_PROMPT.format(id=task["id"], next=factory_cmd(task, "next"), done=factory_cmd(task, "done"))


def resume_prompt(task, extra=None):
    text = RESUME_PROMPT.format(status=factory_cmd(task, "status"), next=factory_cmd(task, "next"))
    return f"{text}\n\n{extra}" if extra else text


def new_session_id():
    return str(uuid.uuid4())


def claude_args(ctx, task, resume=False):
    args = ["--name", task["id"]]
    args += ["--resume", task["session_id"]] if resume else ["--session-id", task["session_id"]]
    args += ["--settings", str(ctx.fdir / "claude-settings.json")]
    args += ["--add-dir", str(state.task_dir(ctx, task["id"]) / "artifacts")]
    if task["pipeline"] in NO_WORKTREE_PIPELINES and ctx.library():
        args += ["--add-dir", str(ctx.library())]
    claude = task.get("claude") or {}
    if claude.get("model"):
        args += ["--model", str(claude["model"])]
    if claude.get("effort"):
        args += ["--effort", str(claude["effort"])]
    return args


def start(ctx, task, prompt, resume=False):
    cwd = task["worktree"] or str(ctx.main)
    return adapters.get_adapter(ctx).start_session(
        task["id"], cwd, prompt, claude_args(ctx, task, resume), bool(task.get("worktree"))
    )


def notify(ctx, text):
    try:
        adapter = adapters.get_adapter(ctx)
        if "notify" not in adapter.capabilities():
            return
        adapter.notify(text)
    except AdapterError:
        pass


def live_state(ctx, task):
    handle = task.get("terminal_handle")
    if not handle:
        return "gone"
    try:
        adapter = adapters.get_adapter(ctx)
        if "state" not in adapter.capabilities():
            return "unknown"
        return adapter.state(handle)
    except AdapterError:
        return "unknown"


def adapter_of(ctx):
    return adapters.get_adapter(ctx)


def pause(ctx, tid, wait=False, timeout_s=PAUSE_WAIT_SECONDS):
    task = state.load(ctx, tid)
    if task["status"] in ("paused", "finished"):
        raise FactoryError(f"Task {tid} is already {task['status']}.")
    adapter = adapter_of(ctx)
    handle = task.get("terminal_handle")
    if handle:
        if wait and "wait_idle" in adapter.capabilities():
            adapter.wait_idle(handle, timeout_s)
        try:
            adapter.close(handle)
        except AdapterError:
            pass

    def change(t):
        t["saved_status"] = {"status": t["status"], "reason": t.get("status_reason")}
        state.set_status(t, "paused")
        t["terminal_handle"] = None

    task = state.update(ctx, tid, change)
    events.log(ctx, tid, "task_paused", state.step_path_str(task))


def pause_all(ctx, wait=False):
    ids = [t["id"] for t in state.list_tasks(ctx) if t["status"] not in ("paused", "finished")]
    for tid in ids:
        pause(ctx, tid, wait)
    return ids


def resume(ctx, tid, extra=None):
    task = state.load(ctx, tid)
    if task["status"] == "finished":
        raise FactoryError(f"Task {tid} is finished.")
    if task["status"] != "paused":
        live = live_state(ctx, task)
        if live not in ("gone", "unknown"):
            raise FactoryError(f"The session of task {tid} is still running ({live}).")
    handle = start(ctx, task, resume_prompt(task, extra), resume=True)

    def change(t):
        t["terminal_handle"] = handle
        if t["status"] == "paused":
            saved = t.get("saved_status") or {"status": "active", "reason": None}
            state.set_status(t, saved["status"], saved.get("reason"))
            t["saved_status"] = None

    task = state.update(ctx, tid, change)
    events.log(ctx, tid, "task_resumed", state.step_path_str(task))
    return task


def require_handle(task):
    if not task.get("terminal_handle"):
        raise FactoryError(f"Task {task['id']} has no live session. Resume it first.")
    return task["terminal_handle"]


def type_prompt(adapter, task, handle, text):
    if adapter.question_box(handle):
        raise FactoryError(QUESTION_BOX.format(id=task["id"]))
    adapter.send_prompt(handle, text)


def logged_delivery(ctx, task, text, send):
    try:
        result = send()
    except FactoryError as e:
        events.log(ctx, task["id"], "prompt_failed", state.step_path_str(task), text=text, reason=str(e))
        raise
    events.log(ctx, task["id"], "prompt_sent", state.step_path_str(task), text=text)
    return result


def deliver(ctx, tid, text):
    task = state.load(ctx, tid)

    def send():
        if task["status"] == "paused" or live_state(ctx, task) == "gone":
            resume(ctx, tid, text)
            return "resumed"
        type_prompt(adapter_of(ctx), task, require_handle(task), text)
        return "sent"

    return logged_delivery(ctx, task, text, send)


def live_handle(ctx, tid):
    task = state.load(ctx, tid)
    return task, require_handle(task)


def send_prompt(ctx, tid, text, wait=False):
    task = state.load(ctx, tid)

    def send():
        handle = require_handle(task)
        adapter = adapter_of(ctx)
        if wait and "wait_idle" in adapter.capabilities():
            adapter.wait_idle(handle, PAUSE_WAIT_SECONDS)
        type_prompt(adapter, task, handle, text)

    logged_delivery(ctx, task, text, send)


def focus(ctx, tid):
    _, handle = live_handle(ctx, tid)
    adapter_of(ctx).focus(handle)
