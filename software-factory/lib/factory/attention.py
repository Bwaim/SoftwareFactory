import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from . import adapters, events, fsio, repo, state, version

def read_delay():
    try:
        return float(os.environ.get("FACTORY_ATTENTION_DELAY", "60"))
    except ValueError:
        return 60.0


DELAY_SECONDS = read_delay()
MESSAGE_LINES = 12
MESSAGE_CHARS = 2000


def now_precise():
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def find_task(ctx, session_id):
    if not isinstance(session_id, str) or not session_id:
        return None
    return next((t for t in state.list_tasks(ctx) if t.get("session_id") == session_id), None)


def entry_text(entry):
    if not isinstance(entry, dict) or entry.get("type") != "assistant":
        return None
    content = (entry.get("message") or {}).get("content")
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return None
    texts = [b["text"] for b in content if isinstance(b, dict) and b.get("type") == "text" and isinstance(b.get("text"), str)]
    return "\n".join(texts)


def transcript_message(path):
    found = None
    for line in Path(path).read_text().splitlines():
        try:
            text = entry_text(json.loads(line))
        except ValueError:
            continue
        if text and text.strip():
            found = text
    return found


def last_message(data):
    try:
        text = data.get("last_assistant_message")
        if isinstance(text, str) and text.strip():
            return text
        return transcript_message(data["transcript_path"])
    except Exception:
        return None


def trim(text):
    if not text or not text.strip():
        return None
    return "\n".join(text.strip().splitlines()[-MESSAGE_LINES:])[-MESSAGE_CHARS:].strip() or None


def first_line(message):
    return message.splitlines()[0] if message else None


def notice(task, message):
    name = state.display_name(task)
    line = first_line(message)
    return f"{name} may wait for you: {line}" if line else f"{name} may wait for you."


def background_work(data):
    tasks = data.get("background_tasks")
    return isinstance(tasks, list) and len(tasks) > 0


def not_focused(adapter, handle):
    if not handle or "focused" not in adapter.capabilities():
        return False
    try:
        return adapter.focused(handle) is False
    except Exception:
        return False


def spawn_later(ctx, tid, at):
    subprocess.Popen(
        [sys.executable, str(repo.PLUGIN_ROOT / "bin" / "factory"), "hook", "notify-later", tid, at],
        cwd=ctx.main, start_new_session=True,
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )


def alert(ctx, task, at):
    adapter = adapters.get_adapter(ctx)
    if "notify" not in adapter.capabilities():
        return
    if not_focused(adapter, task.get("terminal_handle")):
        adapter.notify(notice(task, task["attention"]["message"]))
    else:
        spawn_later(ctx, task["id"], at)


def on_stop(ctx, data):
    task = find_task(ctx, data.get("session_id"))
    if task is None or task.get("status") != "active" or background_work(data):
        return
    tid = task["id"]
    at = now_precise()
    message = trim(last_message(data))

    def mark(t):
        if t.get("status") == "active":
            t["attention"] = {"at": at, "message": message}

    task = state.update(ctx, tid, mark)
    if (task.get("attention") or {}).get("at") != at:
        return
    events.log(ctx, tid, "attention", message=first_line(message))
    alert(ctx, task, at)


def on_prompt(ctx, data):
    task = find_task(ctx, data.get("session_id"))
    if task is not None:
        clear(ctx, task["id"], "prompt")


def clear(ctx, tid, reason):
    if state.load(ctx, tid).get("attention") is None:
        return False
    found = []

    def drop(t):
        if t.get("attention") is not None:
            found.append(t.pop("attention"))

    state.update(ctx, tid, drop)
    if found:
        events.log(ctx, tid, "attention_cleared", reason=reason)
    return bool(found)


def notify_later(ctx, tid, at):
    from . import session
    time.sleep(DELAY_SECONDS)
    task = fsio.read_json(state.task_file(ctx, tid))
    if not task:
        return
    attention = task.get("attention") or {}
    if attention.get("at") == at:
        session.notify(ctx, notice(task, attention.get("message")))


def ready_ctx(cwd):
    ctx = repo.load_ctx(cwd=cwd)
    if not ctx.initialized() or version.repo_version(ctx) != version.DATA_VERSION:
        return None
    return ctx


def report_failure(ctx, kind, tid, error):
    try:
        if tid and repo.task_exists(ctx, tid):
            events.log(ctx, tid, "hook_failed", hook=kind, error=str(error) or type(error).__name__)
    except Exception:
        pass


HOOKS = {"stop": on_stop, "prompt": on_prompt}


def run_hook(kind, stdin_text, cwd):
    try:
        ctx = ready_ctx(cwd)
        data = json.loads(stdin_text) if stdin_text.strip() else None
    except Exception:
        return
    if ctx is None or not isinstance(data, dict):
        return
    tid = None
    try:
        task = find_task(ctx, data.get("session_id"))
        tid = task and task["id"]
        HOOKS[kind](ctx, data)
    except Exception as e:
        report_failure(ctx, kind, tid, e)


def run_notify_later(tid, at, cwd):
    try:
        ctx = ready_ctx(cwd)
        if ctx is None:
            return
        state.check_task_id(tid)
    except Exception:
        return
    try:
        notify_later(ctx, tid, at)
    except Exception as e:
        report_failure(ctx, "notify-later", tid, e)
