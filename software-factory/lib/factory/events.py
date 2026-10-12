import json

from . import fsio
from .state import now, task_dir


def log(ctx, tid, type, step=None, **details):
    line = json.dumps({"ts": now(), "type": type, "step": step, **details}, ensure_ascii=False)
    fsio.append_line(task_dir(ctx, tid) / "events.jsonl", line)


def read(ctx, tid):
    p = task_dir(ctx, tid) / "events.jsonl"
    if not p.exists():
        return []
    return [json.loads(l) for l in p.read_text().splitlines() if l.strip()]
