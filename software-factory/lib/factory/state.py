import re
from datetime import datetime, timezone

from . import fsio
from .errors import FactoryError

STATUSES = ("active", "blocked", "awaiting_approval", "waiting_external", "paused", "finished")
ARTIFACT_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def tasks_dir(ctx):
    return ctx.fdir / "tasks"


def task_dir(ctx, tid):
    return tasks_dir(ctx) / tid


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

    def change(task):
        fn(task)
        task["updated_at"] = now()
        return task

    return fsio.update_json(task_file(ctx, tid), change)


def create(ctx, task):
    d = task_dir(ctx, task["id"])
    (d / "artifacts").mkdir(parents=True, exist_ok=True)
    fsio.write_json(task_file(ctx, task["id"]), task)


def list_tasks(ctx):
    return [fsio.read_json(p) for p in sorted(tasks_dir(ctx).glob("*/task.json"))]


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


def artifact_path(ctx, tid, name):
    if not ARTIFACT_NAME_RE.match(name):
        raise FactoryError("The artifact name must be a simple file name, for example `plan.md`.")
    d = task_dir(ctx, tid) / "artifacts"
    d.mkdir(parents=True, exist_ok=True)
    return (d / name).resolve()
