from dataclasses import dataclass

from . import keys, loops
from .errors import FactoryError
from .registry import CREATE_WORKTREE, is_valid_id, normalize_entry


@dataclass
class Problem:
    level: str
    message: str

    def to_dict(self):
        return {"level": self.level, "message": self.message}


def errors(problems):
    return [p for p in problems if p.level == "error"]


def check(reg, data, columns, save_level=None, hidden=()):
    problems = []
    hidden = set(hidden)
    warned_hidden = set()
    error = lambda m: problems.append(Problem("error", m))
    warning = lambda m: problems.append(Problem("warning", m))
    pid = data.get("id") or ""
    if not is_valid_id(pid):
        error(f"The pipeline id `{pid}` must be lowercase: letters, digits, `-` or `_`, starting with a letter.")
    entries = [normalize_entry(e) for e in data.get("steps") or []]
    if not entries:
        error("The pipeline has no step.")
    start = data.get("start_column")
    if start and start not in columns:
        error(f"The start column `{start}` is not in the board columns.")
    for name, spec in (data.get("inputs") or {}).items():
        if not keys.is_key(name):
            error(f"The input `{name}` must use lowercase letters, digits and `_`, and start with a letter.")
        elif keys.key_type(spec) not in keys.KEY_TYPES:
            error(f"The input `{name}` has an unknown type `{keys.key_type(spec)}`. Use text, long-text or file.")
    rows = keys.start_rows(data)
    first_type = {name: (r["type"], r["source"]) for name, r in rows.items() if r["source"] == "input"}
    warned_types = set()
    loop_keys = loops.keys_in_ranges(reg, entries)
    for i, entry in enumerate(entries):
        sid = entry.get("id")
        if sid == CREATE_WORKTREE and i != 0:
            error("`create-worktree` is listed, but not as the first step.")
        if sid not in reg.steps:
            error(f"The step `{sid}` does not exist.")
            continue
        step = reg.steps[sid]
        if sid in hidden and sid not in warned_hidden:
            warned_hidden.add(sid)
            warning(f"A hidden step is used: `{sid}`.")
        if entry.get("column") and entry["column"] not in columns:
            error(f"Step `{sid}` uses the column `{entry['column']}`, which is not in the board columns.")
        if (save_level or data.get("_level")) == "generic" and step.level == "local":
            warning(f"This generic pipeline uses the local step `{sid}`.")
        try:
            leaves = reg.leaves(sid)
        except FactoryError as e:
            error(str(e))
            continue
        for path in leaves:
            leaf = reg.steps.get(path[-1])
            if leaf is None:
                error(f"The step `{path[-1]}` does not exist.")
                continue
            if leaf.column and leaf.column not in columns:
                error(f"Step `{leaf.id}` uses the column `{leaf.column}`, which is not in the board columns.")
            if (entry.get("model") or entry.get("effort")) and leaf.run_in == "session":
                warning(f"Step `{leaf.id}` runs in the session. Its `model` and `effort` have no effect.")
            own_outputs = set(keys.outputs_of(leaf))
            for key in keys.leaf_uses(leaf):
                if key not in rows and key not in own_outputs and key not in loop_keys[i]:
                    warning(f"Step `{leaf.id}` uses `{key}`, which no input, earlier step or factory key sets.")
            for name, out in keys.outputs_of(leaf).items():
                seen = first_type.setdefault(name, (out["type"], f"step {leaf.id}"))
                if seen[0] != out["type"] and name not in warned_types:
                    warned_types.add(name)
                    warning(f"The key `{name}` is set with two types: {seen[0]} ({seen[1]}) and {out['type']} (step {leaf.id}).")
            keys.add_outputs(rows, leaf)
    for level, message in loops.check(reg, data):
        problems.append(Problem(level, message))
    return problems
