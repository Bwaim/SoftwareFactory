from . import session, state
from .errors import FactoryError
from .registry import Registry

PRIORITY = {"blocked": 0, "awaiting_approval": 1}


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


def task_row(ctx, task, reg=None):
    reg = reg or Registry.load(ctx)
    step = current_step(reg, task)
    waiting = task["status"] == "waiting_external"
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
        "mr_url": task["state"].get("mr_url"),
        "artifacts": artifact_names(ctx, task["id"]),
        "approval": approval_info(task),
        "wait_has_check": bool(step and step.done_check) if waiting else None,
    }


def task_rows(ctx):
    reg = Registry.load(ctx)
    tasks = sorted(state.list_tasks(ctx), key=lambda t: (PRIORITY.get(t["status"], len(PRIORITY)), t["created_at"]))
    return [task_row(ctx, t, reg) for t in tasks]


def render_rows(rows):
    if not rows:
        return "No task."
    lines = []
    for r in rows:
        reason = f" ({r['status_reason']})" if r["status_reason"] else ""
        lines.append(f"{r['id']}: {r['description']}")
        lines.append(f"    {r['pipeline']} > {r['step']}")
        lines.append(f"    status: {r['status']}{reason}. session: {r['session_state']}")
    return "\n".join(lines)
