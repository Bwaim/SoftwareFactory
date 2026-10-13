from . import keys
from .registry import CREATE_WORKTREE, normalize_entry

LOOP_FIELDS = ("back_to", "while", "max")
MAX_JUMPS = 20
EMPTY_VALUES = ("", "none")


def is_set(value):
    return value is not None and str(value).strip().lower() not in EMPTY_VALUES


def back_index(entries, i, back_to):
    for j in range(i, -1, -1):
        if entries[j].get("id") == back_to:
            return j
    return None


def run_entries(data):
    entries = [normalize_entry(e) for e in data.get("steps") or []]
    if not entries or entries[0].get("id") != CREATE_WORKTREE:
        entries = [{"id": CREATE_WORKTREE}] + entries
    return entries


def snapshot(reg, pipeline):
    entries = run_entries(pipeline.data)
    starts, ends, position = [], [], 0
    for entry in entries:
        starts.append(position)
        position += len(reg.leaves(entry["id"]))
        ends.append(position - 1)
    out = []
    for i, entry in enumerate(entries):
        loop = entry.get("loop")
        if not isinstance(loop, dict):
            continue
        j = back_index(entries, i, loop.get("back_to"))
        if j is None:
            continue
        out.append({"entry": entry["id"], "back_to": loop["back_to"], "first": starts[j], "last": ends[i],
                    "while": loop.get("while"), "max": loop.get("max"), "jumps": 0})
    return out


def task_loops(task):
    return task.get("loops") or []


def loop_ending_at(task, position):
    return next((loop for loop in task_loops(task) if loop["last"] == position), None)


def reset_counts(task, target, jumping=None):
    for loop in task_loops(task):
        if loop is jumping:
            continue
        inside = jumping is not None and loop["first"] >= jumping["first"] and loop["last"] <= jumping["last"]
        if loop["first"] > target or inside:
            loop["jumps"] = 0


def holds(loop, position):
    return loop["first"] <= position <= loop["last"]


def current_loop(task):
    position = task["position"]
    active = [loop for loop in task_loops(task) if holds(loop, position) and loop["jumps"] >= 1]
    if not active:
        return None
    loop = min(active, key=lambda l: l["last"] - l["first"])
    return {"n": loop["jumps"], "max": loop["max"], "entry": loop["entry"]}


def controlled_keys(task, step):
    outputs = keys.outputs_of(step)
    found = []
    for loop in task_loops(task):
        if holds(loop, task["position"]) and loop["while"] in outputs and loop["while"] not in found:
            found.append(loop["while"])
    return found
