from dataclasses import dataclass

from .errors import FactoryError
from .registry import CREATE_WORKTREE, is_valid_id, normalize_entry

ALWAYS_AVAILABLE = {"summary", "branch", "ticket"}


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
    available = set((data.get("inputs") or {}).keys()) | ALWAYS_AVAILABLE
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
            for key in leaf.get("reads") or []:
                if key not in available:
                    warning(f"Step `{leaf.id}` reads `{key}`, which is not a pipeline input and is not written by an earlier step.")
            available |= set(leaf.get("writes") or [])
            if (entry.get("model") or entry.get("effort")) and leaf.run_in == "session":
                warning(f"Step `{leaf.id}` runs in the session. Its `model` and `effort` have no effect.")
    return problems
