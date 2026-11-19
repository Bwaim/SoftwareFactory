from pathlib import Path

from . import adapters, board, config, events, fsio, hidden, init, repo, state
from .errors import DetailedError, FactoryError
from .registry import CREATE_WORKTREE, level_roots, parse_step_text

TERMINALS = ("herdr",)
WORKTREE_STEP = CREATE_WORKTREE
STEP_KEYS = ("worktree_root", "base_ref")
MAX_COLUMN = 40
KEYS = ("library", "create_library", "terminal", "columns", "moves", "ticket_url", "unhide", "steps")


def terminal_choices(ctx):
    saved = adapters.terminal_name(ctx)
    return list(TERMINALS) + ([saved] if saved not in TERMINALS else [])


def open_count(ctx):
    return board.open_tasks(state.list_tasks(ctx))


def read(ctx):
    data = ctx.factory_yaml()
    return {
        "library": data.get("library") or "",
        "terminal": adapters.terminal_name(ctx),
        "terminals": terminal_choices(ctx),
        "columns": ctx.columns(),
        "ticket_url": data.get("ticket_url") or "",
        "ticket_default": init.TICKET_DEFAULT,
        "hidden_steps": hidden.ids(ctx),
        "steps": {WORKTREE_STEP: {k: str(config.get_value(ctx, WORKTREE_STEP, k) or "") for k in STEP_KEYS}},
        "open_tasks": open_count(ctx),
    }


def column_names(manifest):
    return [manifest.get("column")] if isinstance(manifest, dict) else []


def pipeline_columns(data):
    if not isinstance(data, dict):
        return []
    entries = data.get("steps") if isinstance(data.get("steps"), list) else []
    return [data.get("start_column")] + [e.get("column") for e in entries if isinstance(e, dict)]


def step_columns(path):
    manifest, _ = parse_step_text(path.read_text(), path)
    return column_names(manifest)


def file_columns(path):
    try:
        if path.suffix == ".md":
            return step_columns(path)
        return pipeline_columns(fsio.read_yaml(path, {}))
    except (FactoryError, OSError, UnicodeDecodeError):
        return []


def column_files(root):
    return sorted((root / "steps").glob("*.md")) + sorted((root / "pipelines").glob("*.yaml"))


def column_users(ctx, library, columns):
    roots = [root for level, root in level_roots(ctx) if level != "generic"]
    if library is not None:
        roots.append(library)
    users = {}
    for root in roots:
        for path in column_files(root):
            for name in set(file_columns(path)) & columns:
                users.setdefault(name, set()).add(str(path))
    return {name: sorted(paths) for name, paths in users.items()}


def tasks_in(ctx, columns):
    found = {}
    for task in state.list_tasks(ctx):
        if task["status"] == "finished":
            continue
        names = {task.get("column")} | {e.get("column") for e in task.get("steps", [])}
        for name in names & columns:
            found.setdefault(name, []).append(task["id"])
    return {name: sorted(ids) for name, ids in found.items()}


def wrong_type(key):
    return f"The setting `{key}` has a wrong type."


def is_str_list(value):
    return isinstance(value, list) and all(isinstance(v, str) for v in value)


def is_str_map(value):
    return isinstance(value, dict) and all(isinstance(k, str) and isinstance(v, str) for k, v in value.items())


def library_check(ctx, changes):
    saved = ctx.library()
    errors, warnings = [], []
    create = changes.get("create_library")
    if "create_library" in changes and not isinstance(create, bool):
        errors.append(wrong_type("create_library"))
    if "library" not in changes:
        return errors, warnings, saved
    value = changes["library"]
    if not isinstance(value, str):
        return errors + [wrong_type("library")], warnings, saved
    if not value.strip():
        new = None
    else:
        path = Path(value.strip()).expanduser()
        if not path.is_absolute():
            return errors + ["Give the full path of the library folder."], warnings, saved
        new = path.resolve()
        if not new.exists() and create is not True:
            errors.append(init.LIBRARY_MISSING)
    count = open_count(ctx)
    if new != saved and count:
        warnings.append(f"Tasks not finished: {count}. Steps and pipelines from the old library can disappear.")
    return errors, warnings, new


def terminal_check(ctx, changes):
    if "terminal" not in changes:
        return []
    value = changes["terminal"]
    if not isinstance(value, str):
        return [wrong_type("terminal")]
    if value not in terminal_choices(ctx):
        return [f"Unknown terminal `{value}`."]
    count = open_count(ctx)
    if value != adapters.terminal_name(ctx) and count:
        return [f"Finish or cancel the open tasks ({count}) before you change the terminal."]
    return []


def column_name_errors(names):
    errors = ["Add at least one column."] if not names else []
    seen = set()
    for name in names:
        if not name:
            errors.append("A column name cannot be empty.")
        elif name == repo.DONE_COLUMN:
            errors.append(f"The column `{name}` is reserved.")
        elif name in seen:
            errors.append(f"The column `{name}` is two times in the list.")
        elif len(name) > MAX_COLUMN:
            errors.append(f"The column name `{name}` is longer than {MAX_COLUMN} characters.")
        seen.add(name)
    return errors


def user_errors(ctx, library, removed):
    users = column_users(ctx, library, removed)
    return [f"The column `{c}` is used in {', '.join(users[c])}. Change that file first." for c in sorted(users)]


def moves_check(ctx, changes, new_columns, removed):
    moves = changes.get("moves", {})
    if not is_str_map(moves):
        return [wrong_type("moves")], {}
    needed = tasks_in(ctx, removed)
    bad = {c for c in needed if c in moves and moves[c] not in new_columns}
    errors = [f"Move the tasks of `{c}` to a column of the new list." for c in sorted(bad)]
    return errors, {c: ids for c, ids in needed.items() if c in bad or c not in moves}


def columns_check(ctx, changes, library):
    if "columns" not in changes:
        return [], {}
    if not is_str_list(changes["columns"]):
        return [wrong_type("columns")], {}
    names = [c.strip() for c in changes["columns"]]
    errors = column_name_errors(names)
    if errors:
        return errors, {}
    removed = set(ctx.columns()) - set(names)
    move_errors, needed = moves_check(ctx, changes, set(names), removed)
    return user_errors(ctx, library, removed) + move_errors, needed


def ticket_check(changes):
    if "ticket_url" not in changes:
        return []
    value = changes["ticket_url"]
    if not isinstance(value, str):
        return [wrong_type("ticket_url")]
    value = value.strip()
    if not value:
        return []
    if not value.startswith(("http://", "https://")):
        return ["The ticket URL must start with http:// or https://."]
    return [] if "{key}" in value else ["The ticket URL must contain {key}."]


def unhide_check(ctx, changes):
    if "unhide" not in changes:
        return []
    if not is_str_list(changes["unhide"]):
        return [wrong_type("unhide")]
    current = hidden.ids(ctx)
    return [f"The step `{i}` is not hidden." for i in changes["unhide"] if i not in current]


def worktree_root_check(value):
    if not value.strip():
        return ["The worktree folder cannot be empty."]
    if not Path(value.strip()).expanduser().is_absolute():
        return ["Give the full path of the worktree folder."]
    return []


def step_values_check(sid, values):
    errors = []
    for key, value in values.items():
        dotted = f"steps.{sid}.{key}"
        if key not in STEP_KEYS:
            errors.append(f"Unknown setting `{dotted}`.")
        elif not isinstance(value, str):
            errors.append(wrong_type(dotted))
        elif key == "worktree_root":
            errors += worktree_root_check(value)
    return errors


def config_file_check(ctx):
    path = config.config_path(ctx)
    try:
        data = fsio.require_map(path, fsio.read_yaml(path, {}))
    except FactoryError as e:
        return [str(e)]
    section = data.get(WORKTREE_STEP)
    if section is not None and not isinstance(section, dict):
        return [wrong_type(f"steps.{WORKTREE_STEP}")]
    return []


def steps_check(ctx, changes):
    if "steps" not in changes:
        return []
    steps = changes["steps"]
    if not isinstance(steps, dict):
        return [wrong_type("steps")]
    errors = config_file_check(ctx)
    for sid, values in steps.items():
        if sid != WORKTREE_STEP:
            errors.append(f"Unknown setting `steps.{sid}`.")
        elif not isinstance(values, dict):
            errors.append(wrong_type(f"steps.{sid}"))
        else:
            errors += step_values_check(sid, values)
    return errors


def check(ctx, changes):
    errors = [f"Unknown setting `{k}`." for k in changes if k not in KEYS]
    lib_errors, warnings, library = library_check(ctx, changes)
    column_errors, needed = columns_check(ctx, changes, library)
    errors += lib_errors + terminal_check(ctx, changes) + column_errors
    errors += ticket_check(changes) + unhide_check(ctx, changes) + steps_check(ctx, changes)
    return {"errors": errors, "warnings": warnings, "moves_needed": needed, "library": library}


def factory_updates(changes, library):
    updates = {}
    if "library" in changes:
        updates["library"] = str(library) if library else ""
    if "terminal" in changes:
        updates["terminal"] = changes["terminal"]
    if "columns" in changes:
        updates["columns"] = [c.strip() for c in changes["columns"]]
    if "ticket_url" in changes:
        updates["ticket_url"] = changes["ticket_url"].strip()
    return updates


def write_factory(ctx, changes, library):
    updates = factory_updates(changes, library)
    unhide = set(changes.get("unhide", []))
    if not updates and not unhide:
        return

    def change(data):
        data.update(updates)
        for sid in unhide:
            hidden.remove(data, sid)

    fsio.update_yaml(ctx.fdir / "factory.yaml", change)


def write_config(ctx, changes):
    if "steps" not in changes:
        return

    def change(data):
        fsio.require_map(config.config_path(ctx), data)
        for sid, values in changes["steps"].items():
            section = data.get(sid) or {}
            section.update({k: v.strip() for k, v in values.items()})
            if section.get("base_ref") == "":
                section.pop("base_ref")
            if section:
                data[sid] = section
            else:
                data.pop(sid, None)

    fsio.update_yaml(config.config_path(ctx), change)


def move_task(ctx, tid, targets):
    moved = []

    def change(task):
        for entry in task.get("steps", []):
            if entry.get("column") in targets:
                entry["column"] = targets[entry["column"]]
        if task.get("column") in targets:
            moved.append(task["column"])
            task["column"] = targets[task["column"]]

    try:
        state.update(ctx, tid, change)
    except FactoryError:
        return
    if moved:
        events.log(ctx, tid, "column_changed", None, **{"from": moved[0], "to": targets[moved[0]]})


def move_tasks(ctx, found, moves):
    targets = {c: moves[c] for c in found if c in moves}
    for tid in sorted({t for ids in found.values() for t in ids}):
        move_task(ctx, tid, targets)


def save(ctx, changes):
    result = check(ctx, changes)
    if result["errors"]:
        raise DetailedError("Settings not saved.", errors=result["errors"])
    if result["moves_needed"]:
        raise DetailedError(
            "Choose a column for the tasks in removed columns.", code="moves_needed", moves_needed=result["moves_needed"]
        )
    library = result["library"]
    if changes.get("create_library") and library and not library.exists():
        init.create_library_folder(library)
    found = tasks_in(ctx, set(ctx.columns()) - {c.strip() for c in changes["columns"]}) if "columns" in changes else {}
    write_factory(ctx, changes, library)
    write_config(ctx, changes)
    move_tasks(ctx, found, changes.get("moves", {}))
    return {"settings": read(ctx), "warnings": result["warnings"]}
