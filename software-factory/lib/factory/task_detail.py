from . import adapters, board, events, state
from .adapters.base import AdapterError

EVENT_LIMIT = 200
SCREEN_LINES = 80


def step_rows(task):
    """Every step of the task's pipeline with done, current or todo, from the position in task.json."""
    pos = task["position"]
    finished = task["status"] == "finished"
    rows = []
    for i, entry in enumerate(task["steps"]):
        if i < pos or finished:
            where = "done"
        elif i == pos:
            where = "current"
        else:
            where = "todo"
        rows.append({"index": i, "id": entry["id"], "path": entry["path"], "state": where})
    return rows


def detail(ctx, tid, next_poll=None):
    task = state.load(ctx, tid)
    return {
        "row": board.task_row(ctx, task, next_poll=next_poll),
        "steps": step_rows(task),
        "info": {
            "branch": task["state"].get("branch"),
            "worktree": task.get("worktree"),
            "base_ref": task.get("base_ref"),
            "created_at": task.get("created_at"),
            "updated_at": task.get("updated_at"),
        },
        "values": task["state"],
        "events": events.read(ctx, tid)[-EVENT_LIMIT:],
    }


def screen(ctx, tid):
    """The last lines of the task's terminal session, or why they cannot be read."""
    task = state.load(ctx, tid)
    handle = task.get("terminal_handle")
    if not handle:
        return {"available": False, "reason": "The task has no live session."}
    try:
        adapter = adapters.get_adapter(ctx)
        if "read_screen" not in adapter.capabilities():
            return {"available": False, "reason": f"The {adapter.name} terminal adapter cannot read the session."}
        return {"available": True, "text": adapter.read_screen(handle, SCREEN_LINES)}
    except AdapterError as e:
        return {"available": False, "reason": str(e)}
