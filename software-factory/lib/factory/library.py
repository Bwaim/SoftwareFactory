from pathlib import Path

from . import repo
from .errors import FactoryError


def repo_root(lib):
    if not lib or not Path(lib).exists():
        return None
    r = repo.git(["rev-parse", "--show-toplevel"], lib, check=False)
    return Path(r.stdout.strip()).resolve() if r.returncode == 0 else None


def in_git(lib):
    return repo_root(lib) is not None


def message(action, kind, item_id):
    return f"Factory library: {action} {kind} {item_id}"


def library_yaml_change(lib, top, rels):
    rel = str((Path(lib).resolve() / "factory.yaml").relative_to(top))
    if rel in rels or not (top / rel).exists():
        return []
    changed = repo.git(["status", "--porcelain", "--", rel], top).stdout.strip()
    return [rel] if changed else []


def commit(ctx, message_text, paths):
    lib = ctx.library()
    top = repo_root(lib)
    if top is None:
        raise FactoryError("The library is not in a git repository. Library commits are disabled.")
    rels = []
    for p in paths:
        full = Path(p).expanduser()
        full = full.parent.resolve() / full.name
        if not full.is_relative_to(lib):
            raise FactoryError(f"{full} is not in the library {lib}.")
        rels.append(str(full.relative_to(top)))
    if not rels:
        raise FactoryError("No file to commit.")
    rels += library_yaml_change(lib, top, rels)
    repo.git(["add", "-A", "--", *rels], top)
    repo.git(["commit", "--only", "-m", message_text, "--", *rels], top)
    return repo.git(["rev-parse", "HEAD"], top).stdout.strip()
