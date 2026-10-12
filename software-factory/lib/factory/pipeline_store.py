from . import fsio, pipeline_check, repo
from .errors import FactoryError
from .registry import STEP_ID_RE, Registry, normalize_entry


def step_summary(step):
    return {"id": step.id, "description": step.description, "category": step.category, "type": step.type,
            "level": step.level, "run_in": step.run_in, "path": str(step.path)}


def step_detail(reg, step):
    reads, writes = reg.io(step.id)
    return {**step_summary(step), "manifest": step.manifest, "body": step.body,
            "reads": reads, "writes": writes, "children": step.children}


def list_pipelines(reg):
    return [{"id": p.id, "description": p.data.get("description", ""), "level": p.level, "path": str(p.path)}
            for p in sorted(reg.pipelines.values(), key=lambda p: p.id)]


def load(reg, pid):
    p = reg.pipeline(pid)
    return {"data": p.data, "level": p.level, "path": str(p.path)}


def copy(reg, source_id, new_id):
    data = dict(reg.pipeline(source_id).data)
    data["id"] = new_id
    return {"data": data}


def check(ctx, data, level):
    reg = Registry.load(ctx)
    return [p.to_dict() for p in pipeline_check.check(reg, data, ctx.columns(), level)]


def is_empty(value):
    return value in (None, "", {}, [])


def prune(value):
    if not isinstance(value, dict):
        return value
    pruned = {k: prune(v) for k, v in value.items()}
    return {k: v for k, v in pruned.items() if not is_empty(v)}


def compact(data):
    steps = []
    for entry in data.get("steps") or []:
        e = prune(normalize_entry(entry))
        steps.append(e["id"] if list(e) == ["id"] else e)
    clean = prune({k: v for k, v in data.items() if not k.startswith("_")})
    if data.get("inputs"):
        clean["inputs"] = {k: prune(v or {}) for k, v in data["inputs"].items()}
    clean["steps"] = steps
    return clean


def target_root(ctx, level):
    if level == "local":
        return ctx.fdir
    if level == "generic":
        lib = ctx.library()
        if not lib:
            raise FactoryError("No library is configured.")
        return lib
    raise FactoryError("Save as `generic` or `local`.")


def library_in_git(lib):
    return repo.git(["rev-parse", "--show-toplevel"], lib, check=False).returncode == 0


def save(ctx, data, level):
    problems = check(ctx, data, level)
    errors = [p["message"] for p in problems if p["level"] == "error"]
    if errors:
        raise FactoryError("The pipeline has errors:\n" + "\n".join(errors))
    pid = data["id"]
    if not STEP_ID_RE.match(pid):
        raise FactoryError("Invalid pipeline id.")
    path = target_root(ctx, level) / "pipelines" / f"{pid}.yaml"
    existed = path.exists()
    fsio.write_yaml(path, compact(data))
    offer = None
    if level == "generic" and library_in_git(ctx.library()):
        offer = {"message": f"Factory library: {'update' if existed else 'add'} pipeline {pid}", "paths": [str(path)]}
    return {"path": str(path), "level": level, "library_commit": offer, "problems": problems}
