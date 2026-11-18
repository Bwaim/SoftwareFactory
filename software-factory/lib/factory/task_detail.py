from . import board, events, state

EVENT_LIMIT = 200


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

