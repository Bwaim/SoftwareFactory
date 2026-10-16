from datetime import datetime, timezone

from . import exclusive, loops, session, state
from .errors import FactoryError
from .registry import Registry

PRIORITY = {"blocked": 0, "awaiting_approval": 1}


def priority(task):
    if task.get("attention"):
        return PRIORITY["blocked"]
    return PRIORITY.get(task["status"], len(PRIORITY))


def iso_time(epoch):
    return datetime.fromtimestamp(epoch, timezone.utc).isoformat(timespec="seconds") if epoch else None


def current_step(reg, task):
    entry = state.current_entry(task)
    if entry is None:
        return None
    try:
        return reg.step(entry["id"])
    except FactoryError:
        return None


def approval_info(task):
    approval = task.get("approval")
    if not approval or task["status"] != "awaiting_approval":
        return None
    target = approval.get("target", "worktree")
    key = approval.get("artifact_key")
    artifact = task["state"].get(key) if target == "artifact" and key else None
    return {"target": target, "artifact_key": key, "artifact": artifact}


def artifact_names(ctx, tid):
    folder = state.task_dir(ctx, tid) / "artifacts"
    return sorted(p.name for p in folder.iterdir()) if folder.exists() else []


def task_row(ctx, task, reg=None, next_poll=None):
    reg = reg or Registry.load(ctx)
    step = current_step(reg, task)
    waiting = task["status"] == "waiting_external"
    info = exclusive.task_info(ctx, task, reg)
    has_check = bool(waiting and step and step.done_check and not (info and info["waiting"]))
    return {
        "id": task["id"],
        "description": task["description"],
        "pipeline": task["pipeline"],
        "step": state.step_path_str(task),
        "status": task["status"],
        "status_reason": task.get("status_reason"),
        "status_since": task.get("status_since"),
        "column": task.get("column"),
        "session_state": session.live_state(ctx, task),
        "worktree": task.get("worktree"),
        "branch": task["state"].get("branch"),
        "ticket": task["state"].get("ticket"),
        "display_name": state.display_name(task),
        "rename_error": "; ".join(e for e in (task.get("rename_error"), task.get("claude_rename_error")) if e) or None,
        "mr_url": task["state"].get("mr_url"),
        "artifacts": artifact_names(ctx, task["id"]),
        "approval": approval_info(task),
        "exclusive": info,
        "wait_has_check": (None if info and info["waiting"] else bool(step and step.done_check)) if waiting else None,
        "next_check_at": iso_time(next_poll) if has_check else None,
        "last_check": task.get("last_check") if has_check else None,
        "loop": loops.current_loop(task),
        "attention": task.get("attention"),
    }


def task_rows(ctx, next_poll=None):
    reg = Registry.load(ctx)
    tasks = sorted(state.list_tasks(ctx), key=lambda t: (priority(t), t["created_at"]))
    return [task_row(ctx, t, reg, next_poll) for t in tasks]


def may_wait(row):
    attention = row.get("attention")
    if not attention:
        return ""
    message = attention.get("message")
    return f", may wait for you: {message.splitlines()[0]}" if message else ", may wait for you"


def render_rows(rows):
    if not rows:
        return "No task."
    lines = []
    for r in rows:
        reason = f" ({r['status_reason']})" if r["status_reason"] else ""
        name = r["display_name"] if r["display_name"] == r["id"] else f"{r['display_name']} ({r['id']})"
        lines.append(f"{name}: {r['description']}")
        lines.append(f"    {r['pipeline']} > {r['step']}")
        lines.append(f"    status: {r['status']}{reason}. session: {r['session_state']}{may_wait(r)}")
    return "\n".join(lines)
