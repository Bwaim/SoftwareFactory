import re
from datetime import datetime, timezone

from . import fsio
from .errors import FactoryError

STATUSES = ("active", "blocked", "awaiting_approval", "waiting_external", "paused", "finished")
ARTIFACT_NAME_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")
TASK_ID_RE = re.compile(r"[a-z][a-z0-9_-]{0,31}")


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def tasks_dir(ctx):
    return ctx.fdir / "tasks"


def check_task_id(tid):
    if not isinstance(tid, str) or not TASK_ID_RE.fullmatch(tid):
        raise FactoryError(f"Invalid task id `{tid}`.")
    return tid


def display_name(task):
    return task.get("display_name") or task["id"]


def task_dir(ctx, tid):
    return tasks_dir(ctx) / check_task_id(tid)


def task_file(ctx, tid):
    return task_dir(ctx, tid) / "task.json"


def load(ctx, tid):
    data = fsio.read_json(task_file(ctx, tid))
    if not data:
        raise FactoryError(f"Unknown task {tid}.")
    return data


def update(ctx, tid, fn):
    if not task_file(ctx, tid).exists():
        raise FactoryError(f"Unknown task {tid}.")

    dropped = []

    def change(task):
        before = task.get("status")
        fn(task)
        if task.get("status") != before and task.get("attention") is not None:
            task.pop("attention")
            dropped.append(True)
        task["updated_at"] = now()
        return task

    result = fsio.update_json(task_file(ctx, tid), change)
    if dropped:
        from . import events
        events.log(ctx, tid, "attention_cleared", step_path_str(result), reason="status")
    return result


def create(ctx, task):
    d = task_dir(ctx, task["id"])
    try:
        d.mkdir(parents=True)
    except FileExistsError:
        raise FactoryError(f"A task with the id `{task['id']}` already exists.")
    (d / "artifacts").mkdir()
    fsio.write_json(task_file(ctx, task["id"]), task)


def list_tasks(ctx):
    tasks = (fsio.read_json(p) for p in sorted(tasks_dir(ctx).glob("*/task.json")))
    return [t for t in tasks if t is not None]


def current_entry(task):
    pos = task["position"]
    return task["steps"][pos] if pos < len(task["steps"]) else None


def step_path_str(task, pos=None):
    pos = task["position"] if pos is None else pos
    if pos >= len(task["steps"]):
        return "(finished)"
    return " > ".join(task["steps"][pos]["path"])


def set_status(task, status, reason=None):
    task["status"] = status
    task["status_reason"] = reason
    task["status_since"] = now()


def get_key(ctx, tid, key):
    data = load(ctx, tid)["state"]
    if key not in data:
        raise FactoryError(f"The task state key `{key}` is not set.")
    return data[key]


def set_key(ctx, tid, key, value):
    update(ctx, tid, lambda t: t["state"].__setitem__(key, value))


def artifact_file(ctx, tid, name):
    if not isinstance(name, str) or not ARTIFACT_NAME_RE.fullmatch(name):
        raise FactoryError("The artifact name must be a simple file name, for example `plan.md`.")
    folder = (task_dir(ctx, tid) / "artifacts").resolve()
    path = (folder / name).resolve()
    if path.parent != folder:
        raise FactoryError("The artifact must stay inside the task artifacts folder.")
    return path


def artifact_path(ctx, tid, name):
    path = artifact_file(ctx, tid, name)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path
