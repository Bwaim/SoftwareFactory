import difflib
import shutil

from . import fsio, library, repo, requires
from .errors import FactoryError
from .registry import Registry, parse_step_text

CATALOG = repo.PLUGIN_ROOT / "catalog"


def step_files(sid):
    files = [CATALOG / "steps" / f"{sid}.md"]
    script = CATALOG / "steps" / f"{sid}.sh"
    if script.exists():
        files.append(script)
    return files


def item_files(kind, item_id):
    if kind == "pipeline":
        return [CATALOG / "pipelines" / f"{item_id}.yaml"]
    return step_files(item_id)


def catalog_items():
    out = []
    for p in sorted((CATALOG / "pipelines").glob("*.yaml")):
        data = fsio.read_yaml(p, {})
        out.append({"kind": "pipeline", "id": data["id"], "category": "pipeline", "description": data.get("description", ""),
                    "requires": [], "steps": [s if isinstance(s, str) else s["id"] for s in data.get("steps", [])]})
    for p in sorted((CATALOG / "steps").glob("*.md")):
        manifest, _ = parse_step_text(p.read_text(), p)
        out.append({"kind": "step", "id": manifest["id"], "category": manifest.get("category", ""),
                    "description": manifest.get("description", ""), "requires": list(manifest.get("requires") or []), "steps": None})
    return out


def find_item(item_id):
    for item in catalog_items():
        if item["id"] == item_id:
            return item
    raise FactoryError(f"The catalog has no item `{item_id}`.")


def dest_root(ctx, target):
    if target == "local":
        return ctx.fdir
    lib = ctx.library()
    if not lib:
        raise FactoryError("No library is configured.")
    return lib


def dest_of(root, src):
    return root / src.parent.name / src.name


def status_in(root, kind, item_id):
    files = item_files(kind, item_id)
    dests = [dest_of(root, f) for f in files]
    if not dests[0].exists():
        return None
    same = all(d.exists() and d.read_bytes() == f.read_bytes() for f, d in zip(files, dests))
    return "installed" if same else "changed"


def items(ctx):
    roots = [("local", ctx.fdir)] + ([("generic", ctx.library())] if ctx.library() else [])
    out = []
    for item in catalog_items():
        status, location = "not installed", None
        for name, root in roots:
            found = status_in(root, item["kind"], item["id"])
            if found:
                status, location = found, name
                break
        out.append({**item, "status": status, "location": location,
                    "missing_requires": requires.missing(item["requires"], ctx.main)})
    return out


def diff(dest, src):
    return "".join(difflib.unified_diff(dest.read_text().splitlines(True), src.read_text().splitlines(True),
                                        fromfile=str(dest), tofile=f"catalog/{src.parent.name}/{src.name}"))


def missing_steps(ctx, item):
    if item["kind"] != "pipeline":
        return []
    reg = Registry.load(ctx)
    catalog_steps = {i["id"] for i in catalog_items() if i["kind"] == "step"}
    return sorted({s for s in item["steps"] if s not in reg.steps and s in catalog_steps})


def install(ctx, item_id, target, with_steps=False, replace=False, dry_run=False):
    item = find_item(item_id)
    root = dest_root(ctx, target)
    missing = missing_steps(ctx, item)
    sources = list(item_files(item["kind"], item_id))
    if with_steps:
        for sid in missing:
            sources += step_files(sid)
    plan = {"files": [], "conflicts": [], "missing_steps": missing, "written": [], "library_commit": None}
    for src in sources:
        dest = dest_of(root, src)
        plan["files"].append(str(dest))
        if dest.exists() and dest.read_bytes() != src.read_bytes():
            plan["conflicts"].append({"path": str(dest), "diff": diff(dest, src)})
    if dry_run:
        return plan
    if plan["conflicts"] and not replace:
        raise FactoryError("Some files already exist and differ. Show the difference to the user, then run again with --replace after approval.")
    for src in sources:
        dest = dest_of(root, src)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dest)
        if src.suffix == ".sh":
            dest.chmod(0o755)
        plan["written"].append(str(dest))
    if target == "generic" and library.in_git(root):
        plan["library_commit"] = {"message": library.message("add", item["kind"], item_id), "paths": plan["written"]}
    return plan
