from pathlib import Path

from . import fsio, keys, library, render, step_format
from .errors import ExistsError, FactoryError
from .registry import Registry, Step

BUILTIN_EDIT = "Built-in steps cannot be edited. Copy the step to local instead."
MODES = ("new", "edit", "copy-local")


def require_input(manifest, body):
    if not isinstance(manifest, dict):
        raise FactoryError("The manifest must be an object.")
    if not isinstance(body, str):
        raise FactoryError("The body must be text.")
    return step_format.clean(manifest)


def form_data(ctx):
    reg = Registry.load(ctx)
    factory_keys = [{"name": n, "type": s["type"], "source": "factory", "set": s["set"]} for n, s in keys.FACTORY_KEYS.items()]
    return {"categories": reg.categories(), "columns": ctx.columns(), "library": ctx.library() is not None,
            "factory_keys": factory_keys, "key_types": list(keys.KEY_TYPES), "step_ids": sorted(reg.variants)}


def candidate(manifest, body):
    sid = manifest.get("id")
    return Step(sid, "candidate", Path(f"{sid}.md"), dict(manifest), body)


def check(ctx, manifest, body, level="local"):
    manifest = require_input(manifest, body)
    errors, warnings = step_format.validate(manifest, body)
    uses, outputs = [], {}
    if not errors:
        reg = Registry.load(ctx)
        step = candidate(manifest, body)
        if step.type == "group":
            errors += [f"The child step `{c}` does not exist." for c in step.children if c != step.id and c not in reg.steps]
        if not errors:
            reg.steps[step.id] = step
            try:
                reg.check_loops()
                uses, outputs = keys.step_uses(reg, step.id), keys.step_outputs(reg, step.id)
            except FactoryError as e:
                errors.append(str(e))
    if not errors and manifest.get("type") == "command":
        warnings = warnings + missing_scripts(ctx, body, level)
    return {"errors": errors, "warnings": warnings, "uses": uses, "outputs": outputs}


def missing_scripts(ctx, body, level):
    from .pipeline_store import target_root
    from .step_delete import SCRIPT_REF_RE
    try:
        folder = target_root(ctx, level if level == "generic" else "local") / "steps"
    except FactoryError:
        return []
    names = dict.fromkeys(SCRIPT_REF_RE.findall(body))
    return [f"The script `{n}` is not in {folder}. Copy it there by hand." for n in names if not (folder / n).exists()]


def preview(ctx, manifest, body):
    manifest = require_input(manifest, body)
    step = candidate(manifest, body)
    text = render.step_text(step, render.show_names(body), f"Step: {step.id}", keys.outputs_of(step), step.model, step.effort)
    return {"text": text}


def impact(ctx, sid):
    from .step_delete import OTHER_REPOS, find_users
    reg = Registry.load(ctx)
    step = reg.step(sid)
    users = find_users(ctx, reg, sid, step)
    return {
        "pipelines": [{"id": u["id"], "level": u["level"]} for u in users if u["kind"] == "pipeline"],
        "groups": [{"id": u["id"], "level": u["level"]} for u in users if u["kind"] == "group"],
        "tasks": [{"id": u["id"]} for u in users if u["kind"] == "task"],
        "warnings": [OTHER_REPOS] if step.level == "generic" else [],
    }


def target(ctx, reg, sid, level, mode):
    from .pipeline_store import target_root
    variants = reg.variants.get(sid, [])
    if mode == "new":
        path = target_root(ctx, level) / "steps" / f"{sid}.md"
        if variants or path.exists():
            raise ExistsError(f"A step named `{sid}` already exists.")
        return level, path, "add"
    if not variants:
        raise FactoryError(f"The step `{sid}` does not exist.")
    if mode == "edit":
        current = variants[-1]
        if current.level == "builtin":
            raise FactoryError(BUILTIN_EDIT)
        if current.level != level:
            raise FactoryError(f"The step `{sid}` in use is {current.level}, not {level}.")
        return level, current.path, "update"
    if any(s.level == "local" for s in variants):
        raise ExistsError(f"A local step named `{sid}` already exists.")
    return "local", ctx.fdir / "steps" / f"{sid}.md", "add"


def save(ctx, manifest, body, level, mode):
    if mode not in MODES:
        raise FactoryError("The mode must be `new`, `edit` or `copy-local`.")
    result = check(ctx, manifest, body, "local" if mode == "copy-local" else level)
    if result["errors"]:
        raise FactoryError("The step has errors:\n" + "\n".join(result["errors"]))
    manifest = step_format.clean(manifest)
    reg = Registry.load(ctx)
    level, path, action = target(ctx, reg, manifest["id"], level, mode)
    path.parent.mkdir(parents=True, exist_ok=True)
    fsio.atomic_write_text(path, step_format.dump(manifest, body))
    offer = None
    if level == "generic" and library.in_git(ctx.library()):
        offer = {"message": library.message(action, "step", manifest["id"]), "paths": [str(path)]}
    return {"path": str(path), "level": level, "warnings": result["warnings"], "library_commit": offer}
