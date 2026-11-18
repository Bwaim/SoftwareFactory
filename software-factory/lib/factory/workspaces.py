import os
import re
from pathlib import Path

from . import fsio, repo
from .errors import FactoryError

MAX_NAME = 64
MAX_SLUG = 32


def home():
    return Path(os.environ.get("FACTORY_HOME", "~/.config/software-factory")).expanduser()


def list_path():
    return home() / "workspaces.yaml"


def mtime():
    try:
        return list_path().stat().st_mtime
    except FileNotFoundError:
        return None


def slug(name):
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:MAX_SLUG].strip("-")
    return s or "workspace"


def resolve_main(path):
    p = Path(path).expanduser()
    if not p.exists():
        raise FactoryError(f"The path {p} does not exist.")
    return repo.main_repo(p)


def rows(data):
    fsio.require_map(list_path(), data)
    if data.get("workspaces") is None:
        data["workspaces"] = []
    return data["workspaces"]


def list_all():
    data = fsio.read_yaml(list_path(), {})
    return [dict(w) for w in fsio.require_map(list_path(), data).get("workspaces") or []]


def get(wid):
    return next((w for w in list_all() if w["id"] == wid), None)


def find_by_path(path):
    target = Path(path).expanduser().resolve()
    return next((w for w in list_all() if Path(w["path"]).resolve() == target), None)


def unique_id(base, taken):
    wid, n = base, 2
    while wid in taken:
        wid, n = f"{base}-{n}", n + 1
    return wid


def same_path(w, main):
    return Path(w["path"]).resolve() == Path(main).resolve()


def append(items, main):
    entry = {"id": unique_id(slug(main.name), {w["id"] for w in items}), "name": main.name, "path": str(main)}
    items.append(entry)
    return dict(entry)


def add(main):
    main = Path(main)

    def fn(data):
        items = rows(data)
        for w in items:
            if same_path(w, main):
                raise FactoryError(f"{main} is already the workspace {w['name']}.")
        return append(items, main)

    return fsio.update_yaml(list_path(), fn)


def register(main):
    main = Path(main)

    def fn(data):
        items = rows(data)
        found = next((w for w in items if same_path(w, main)), None)
        return dict(found) if found else append(items, main)

    return find_by_path(main) or fsio.update_yaml(list_path(), fn)


def rename(wid, name):
    name = name.strip() if isinstance(name, str) else ""
    if not name or len(name) > MAX_NAME:
        raise FactoryError(f"A name has 1 to {MAX_NAME} characters.")

    def fn(data):
        for w in rows(data):
            if w["id"] == wid:
                w["name"] = name
                return dict(w)
        raise FactoryError(f"Unknown workspace {wid}.")

    return fsio.update_yaml(list_path(), fn)


def remove(wid):
    def fn(data):
        items = rows(data)
        for i, w in enumerate(items):
            if w["id"] == wid:
                return dict(items.pop(i))
        raise FactoryError(f"Unknown workspace {wid}.")

    return fsio.update_yaml(list_path(), fn)
