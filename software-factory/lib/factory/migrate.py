import importlib.util
import os
import shutil
from datetime import datetime
from pathlib import Path

from . import events, fsio, library, repo, state, version
from .errors import FactoryError


def migrations_dir():
    return Path(os.environ.get("FACTORY_MIGRATIONS_DIR") or repo.PLUGIN_ROOT / "migrations")


def load_script(from_version):
    path = migrations_dir() / f"{from_version}-to-{from_version + 1}.py"
    if not path.exists():
        raise FactoryError(f"The migration script {path.name} is missing.")
    spec = importlib.util.spec_from_file_location(f"factory_migration_{from_version}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def stamp():
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def backup_path(parent, name):
    base = f"{name}.backup-{stamp()}"
    target, n = parent / base, 1
    while target.exists():
        n += 1
        target = parent / f"{base}-{n}"
    return target


def plan(ctx):
    current = version.DATA_VERSION
    rv = version.repo_version(ctx)
    lib = ctx.library()
    lv = version.library_version(lib)
    if (rv or 0) > current or (lv or 0) > current:
        raise FactoryError("The data is newer than this factory. Please update the factory plugin.")
    return {
        "current": current,
        "repo": {"from": rv, "migrate": rv is not None and rv < current},
        "library": {"path": str(lib) if lib else None, "from": lv, "migrate": lv is not None and lv < current,
                    "in_git": library.in_git(lib)},
    }


def require_clean_library(lib):
    top = library.repo_root(lib)
    status = repo.git(["status", "--porcelain", "--", str(lib)], top).stdout.strip()
    if status:
        raise FactoryError("The library has uncommitted changes. Commit or stash them, then migrate again.\n" + status)


def bump(path, new_version):
    fsio.update_yaml(path, lambda d: d.__setitem__("version", new_version))


def run_checks(ctx, p):
    errors, warnings = [], []
    targets = [("library", ctx.library(), "check_library"), ("repo", ctx.fdir, "check_repo")]
    for part, root, name in targets:
        if not p[part]["migrate"]:
            continue
        for v in range(p[part]["from"], p["current"]):
            check = getattr(load_script(v), name, None)
            if check:
                e, w = check(root)
                errors += e
                warnings += w
    return errors, warnings


def migrate(ctx, dry_run=False):
    p = plan(ctx)
    p["errors"], p["warnings"] = run_checks(ctx, p)
    p["backups"], p["library_commit"] = [], None
    if dry_run:
        return p
    if p["errors"]:
        raise FactoryError("The migration cannot start. Fix these first:\n" + "\n".join(f"- {e}" for e in p["errors"]))
    lib = ctx.library()
    if p["library"]["migrate"]:
        if p["library"]["in_git"]:
            require_clean_library(lib)
        else:
            target = backup_path(lib.parent, lib.name)
            shutil.copytree(lib, target)
            p["backups"].append(str(target))
    if p["library"]["migrate"]:
        for v in range(p["library"]["from"], p["current"]):
            load_script(v).migrate_library(lib)
            bump(lib / "factory.yaml", v + 1)
        if p["library"]["in_git"]:
            p["library_commit"] = {"message": f"Factory library: migrate to version {p['current']}", "paths": [str(lib)]}
    if p["repo"]["migrate"]:
        target = backup_path(ctx.main, ".factory")
        shutil.copytree(ctx.fdir, target)
        p["backups"].append(str(target))
        for v in range(p["repo"]["from"], p["current"]):
            load_script(v).migrate_repo(ctx.fdir)
            bump(ctx.fdir / "factory.yaml", v + 1)
            for task in state.list_tasks(ctx):
                events.log(ctx, task["id"], "migrated", None, from_version=v, to_version=v + 1)
    return p
