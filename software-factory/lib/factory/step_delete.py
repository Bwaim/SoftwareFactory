import shlex
from pathlib import Path

from . import hidden, library, repo, state
from .errors import FactoryError
from .registry import Registry, all_pipeline_files, normalize_entry

LEVELS = ("local", "generic")
BUILTIN_REFUSAL = "Built-in steps cannot be deleted. Hide the step instead: `factory step hide {id}`."
OTHER_REPOS = "Other repositories that use this library are not checked."


def target_step(reg, sid, level):
    variants = reg.variants.get(sid)
    if not variants:
        raise FactoryError(f"The step `{sid}` does not exist.")
    if level is None:
        target = variants[-1]
    elif all(s.level == "builtin" for s in variants):
        target = variants[-1]
    elif level not in LEVELS:
        raise FactoryError("The level must be `local` or `generic`.")
    else:
        found = [s for s in variants if s.level == level]
        if not found:
            raise FactoryError(f"There is no {level} step `{sid}`.")
        target = found[-1]
    if target.level == "builtin":
        raise FactoryError(BUILTIN_REFUSAL.format(id=sid))
    return target


def script_of(step):
    if step.type != "script":
        return None
    lines = [line.strip() for line in step.body.splitlines() if line.strip()]
    return (step.path.parent / lines[0]).resolve() if lines else None


def script_files(reg, target):
    script = script_of(target)
    if script is None or not script.is_file() or script.parent != target.path.parent.resolve():
        return []
    if script in {s.path.resolve() for variants in reg.variants.values() for s in variants}:
        return []
    for variants in reg.variants.values():
        for other in variants:
            if other.path.resolve() != target.path.resolve() and script_of(other) == script:
                return []
    return [script]


def entry_ids(data):
    steps = data.get("steps") if isinstance(data, dict) else None
    return [normalize_entry(e).get("id") for e in steps or [] if isinstance(e, (str, dict))]


def find_users(ctx, reg, sid, target):
    found = []
    for level, pid, data in all_pipeline_files(ctx):
        if sid in entry_ids(data):
            found.append({"kind": "pipeline", "id": pid, "level": level})
    for other_id in sorted(reg.variants):
        for step in reg.variants[other_id]:
            if step.type == "composite" and step.path != target.path and sid in step.children:
                found.append({"kind": "composite", "id": step.id, "level": step.level})
    for task in state.list_tasks(ctx):
        if task.get("status") == "finished":
            continue
        if any(sid in (e.get("path") or [e.get("id")]) for e in task.get("steps") or []):
            found.append({"kind": "task", "id": task["id"], "level": None})
    return found


def plan(ctx, sid, level=None):
    reg = Registry.load(ctx)
    target = target_step(reg, sid, level)
    variants = reg.variants[sid]
    others = [s for s in variants if s is not target]
    in_use = variants[-1]
    in_use_stays = in_use.level if in_use is not target else None
    replaced_by = others[-1].level if others and in_use is target else None
    users = [] if others else find_users(ctx, reg, sid, target)
    return {
        "id": sid,
        "level": target.level,
        "files": [str(p) for p in [target.path] + script_files(reg, target)],
        "replaced_by": replaced_by,
        "in_use_stays": in_use_stays,
        "users": users,
        "warnings": [OTHER_REPOS] if target.level == "generic" else [],
        "blocked": bool(users),
    }


def describe(user):
    if user["kind"] == "task":
        return f"- task {user['id']}"
    kind = "pipeline" if user["kind"] == "pipeline" else "composite step"
    return f"- {kind} {user['id']} ({user['level']})"


def tracked(ctx, files):
    top = library.repo_root(ctx.library())
    if top is None:
        return []
    return [p for p in files if repo.git(["ls-files", "--error-unmatch", "--", str(p)], top, check=False).returncode == 0]


def delete(ctx, sid, level=None):
    result = plan(ctx, sid, level)
    if result["blocked"]:
        raise FactoryError(f"Step {sid} is still used. Remove it from these first:\n" + "\n".join(describe(u) for u in result["users"]))
    files = [Path(p) for p in result["files"]]
    in_git = tracked(ctx, files) if result["level"] == "generic" else []
    removed = []
    for p in files:
        try:
            p.unlink()
        except FileNotFoundError:
            continue
        removed.append(str(p))
    if not result["replaced_by"] and not result["in_use_stays"]:
        hidden.discard(ctx, sid)
    offer = None
    if in_git:
        offer = {"message": library.message("delete", "step", sid), "paths": [str(p) for p in in_git]}
    return {**result, "removed": removed, "library_commit": offer}


def render(result, dry_run):
    sid = result["id"]
    lines = [f"{'Dry run: delete' if dry_run else 'Deleted'} the {result['level']} step `{sid}`."]
    lines.append("Files to remove:" if dry_run else "Removed files:")
    lines += [f"- {p}" for p in (result["files"] if dry_run else result["removed"])]
    if result["replaced_by"]:
        lines.append(f"The {result['replaced_by']} step `{sid}` is used {'after the delete' if dry_run else 'now'}.")
    if result["in_use_stays"]:
        lines.append(f"The {result['in_use_stays']} step `{sid}` stays in use.")
    if result["users"]:
        lines.append(f"Step {sid} is still used. Remove it from these first:")
        lines += [describe(u) for u in result["users"]]
    lines += [f"Warning: {w}" for w in result["warnings"]]
    offer = result.get("library_commit")
    if offer:
        paths = " ".join(shlex.quote(p) for p in offer["paths"])
        lines.append(f"Library commit offer: factory library commit {shlex.quote(offer['message'])} {paths}")
    return "\n".join(lines)
