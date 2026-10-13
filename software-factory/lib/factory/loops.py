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


def loop_range(entries, i):
    loop = entries[i].get("loop")
    if not isinstance(loop, dict) or not isinstance(loop.get("back_to"), str) or loop["back_to"] == CREATE_WORKTREE:
        return None
    j = back_index(entries, i, loop["back_to"])
    return None if j is None else (j, i)


def keys_in_ranges(reg, entries):
    found = {i: set() for i in range(len(entries))}
    for i in range(len(entries)):
        span = loop_range(entries, i)
        if span is None:
            continue
        names = {name for entry in entries[span[0]:i + 1] for leaf in keys.entry_leaves(reg, entry) for name in keys.outputs_of(leaf)}
        for k in range(span[0], i + 1):
            found[k] |= names
    return found


def range_outputs(reg, entries, j, i, key):
    found = []
    for entry in entries[j:i + 1]:
        for leaf in keys.entry_leaves(reg, entry):
            out = keys.outputs_of(leaf).get(key)
            if out:
                found.append(out)
    return found


def check_one(reg, entries, i, problems, ranges):
    entry = entries[i]
    sid = entry.get("id")
    error = lambda m: problems.append(("error", m))
    warning = lambda m: problems.append(("warning", m))
    loop = entry["loop"]
    if not isinstance(loop, dict):
        error(f"Step `{sid}`: `loop` must be a map with `back_to`, `while` and `max`.")
        return
    for name in loop:
        if name not in LOOP_FIELDS:
            error(f"Step `{sid}`: `loop` has an unknown field `{name}`.")
    back_to = loop.get("back_to")
    j = back_index(entries, i, back_to) if isinstance(back_to, str) else None
    if back_to == CREATE_WORKTREE:
        error(f"Step `{sid}`: `loop.back_to` cannot be `create-worktree`. It cannot run again.")
        j = None
    elif j is None:
        error(f"Step `{sid}`: `loop.back_to` must be this step or an earlier step of the pipeline.")
    limit = loop.get("max")
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= MAX_JUMPS:
        error(f"Step `{sid}`: `loop.max` must be an integer from 1 to {MAX_JUMPS}.")
    key = loop.get("while")
    if not keys.is_key(key):
        error(f"Step `{sid}`: `loop.while` must be a key name: lowercase letters, digits and `_`, starting with a letter.")
    if j is not None:
        ranges.append((j, i, sid))
        if keys.is_key(key):
            outputs = range_outputs(reg, entries, j, i, key)
            if not outputs:
                warning(f"Step `{sid}`: no step inside the loop outputs `{key}`. The loop never ends early.")
            elif all(out["optional"] for out in outputs):
                warning(f"Step `{sid}`: `{key}` is optional in every step that outputs it inside the loop.")
    if i == len(entries) - 1:
        warning(f"Step `{sid}`: the loop is on the last step. At the limit, the task finishes without asking the user. "
                "Add a step after it, for example `user-validation`.")


def overlaps(a, b):
    (s1, e1, _), (s2, e2, _) = a, b
    share = s1 <= e2 and s2 <= e1
    nested = (s1 <= s2 and e2 <= e1) or (s2 <= s1 and e1 <= e2)
    return share and not nested


def check(reg, data):
    entries = [normalize_entry(e) for e in data.get("steps") or []]
    problems, ranges = [], []
    for i, entry in enumerate(entries):
        if "loop" in entry:
            check_one(reg, entries, i, problems, ranges)
    for a in range(len(ranges)):
        for b in range(a + 1, len(ranges)):
            if overlaps(ranges[a], ranges[b]):
                problems.append(("error", f"The loops of `{ranges[a][2]}` and `{ranges[b][2]}` overlap. One loop must be inside the other."))
    return problems
