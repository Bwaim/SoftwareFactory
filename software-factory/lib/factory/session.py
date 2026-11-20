import subprocess
import sys
import uuid

from . import adapters, config, events, exclusive, fsio, init, state
from .adapters.base import AdapterError
from .errors import FactoryError

TERMINAL_SECTION = "terminal"
TERMINAL_APP_KEY = "terminal_app"
OPEN_TIMEOUT = 10
ASK_TERMINAL_APP = (
    "Ask the user which terminal app shows Herdr, for example Ghostty or iTerm, then run "
    "`factory config set terminal terminal_app '<app>'`. An empty value means never ask again."
)
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


def first_prompt(task):
    return FIRST_PROMPT.format(id=task["id"], next="factory next", done="factory done")


def resume_prompt(task, extra=None):
    text = RESUME_PROMPT.format(status="factory status", next="factory next")
    return f"{text}\n\n{extra}" if extra else text


def new_session_id():
    return str(uuid.uuid4())


def task_settings_path(ctx, task):
    return state.task_dir(ctx, task["id"]) / "claude-settings.json"


def shared_settings(ctx):
    path = ctx.fdir / "claude-settings.json"
    settings = init.read_settings(path) if path.exists() else {}
    if not isinstance(settings.get("env", {}), dict):
        raise FactoryError(f"{path}: `env` must be a JSON object. Fix or remove it, then run again.")
    return settings


def write_task_settings(ctx, task):
    settings = shared_settings(ctx)
    settings["env"] = {**settings.get("env", {}), "FACTORY_TASK": task["id"]}
    path = task_settings_path(ctx, task)
    fsio.write_json(path, settings)
    return path


def claude_args(ctx, task, resume=False):
    args = ["--name", state.display_name(task)]
    args += ["--resume", task["session_id"]] if resume else ["--session-id", task["session_id"]]
    args += ["--settings", str(task_settings_path(ctx, task))]
    args += ["--add-dir", str(state.task_dir(ctx, task["id"]) / "artifacts")]
    claude = task.get("claude") or {}
    if claude.get("model"):
        args += ["--model", str(claude["model"])]
    if claude.get("effort"):
        args += ["--effort", str(claude["effort"])]
    return args


def start(ctx, task, prompt, resume=False):
    from .engine import task_cwd

    write_task_settings(ctx, task)
    cwd = task_cwd(ctx, task)
    if task.get("worktree") and not cwd.exists():
        raise FactoryError(f"The worktree {cwd} of task {task['id']} does not exist.")
    return adapters.get_adapter(ctx).start_session(state.display_name(task), str(cwd), prompt, claude_args(ctx, task, resume))


def notify(ctx, text):
    try:
        adapter = adapters.get_adapter(ctx)
        if "notify" not in adapter.capabilities():
            return
        adapter.notify(text)
    except AdapterError:
        pass


def close_quietly(ctx, handle):
    try:
        adapters.get_adapter(ctx).close(handle)
    except (AdapterError, FactoryError):
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
        t.pop("claude_rename_pending", None)
        t.pop("rename_error", None)
        t.pop("claude_rename_error", None)
        t["terminal_handle"] = handle
        if t["status"] == "paused":
            saved = t.get("saved_status") or {"status": "active", "reason": None}
            state.set_status(t, saved["status"], saved.get("reason"))
            t["saved_status"] = None

    try:
        task = state.update(ctx, tid, change)
    except FactoryError:
        if not state.task_file(ctx, tid).exists():
            close_quietly(ctx, handle)
        raise
    events.log(ctx, tid, "task_resumed", state.step_path_str(task))
    if task.get("exclusive_wait"):
        exclusive.handover(ctx, task["exclusive_wait"]["name"])
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
    from . import attention
    try:
        attention.clear(ctx, task["id"], "prompt")
    except FactoryError:
        pass
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
