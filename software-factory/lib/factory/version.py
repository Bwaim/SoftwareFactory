import os

from . import fsio
from .errors import FactoryError

DATA_VERSION = int(os.environ.get("FACTORY_DATA_VERSION", "2"))


def compare(v):
    if v == DATA_VERSION:
        return "same"
    return "older" if v < DATA_VERSION else "newer"


def repo_version(ctx):
    return ctx.factory_yaml().get("version")


def library_version(lib):
    if not lib or not (lib / "factory.yaml").exists():
        return None
    return (fsio.read_yaml(lib / "factory.yaml", {}) or {}).get("version")


def require_repo(ctx):
    if not ctx.initialized():
        raise FactoryError("The factory is not initialized in this repository. Run `factory init --library <path>`.")
    v = repo_version(ctx)
    if v != DATA_VERSION:
        raise FactoryError(
            f"The repository data version is {v}, and this factory uses version {DATA_VERSION}. "
            "Run `factory migrate`, or run the install script again to update the factory."
        )


def require_library(lib):
    v = library_version(lib)
    if v is not None and v != DATA_VERSION:
        raise FactoryError(
            f"The library data version is {v}, and this factory uses version {DATA_VERSION}. "
            "Run `factory migrate`, or run the install script again to update the factory."
        )


def report(ctx):
    initialized = ctx.initialized()
    rv = repo_version(ctx) if initialized else None
    lv = library_version(ctx.library()) if initialized else None
    states = [compare(v) for v in (rv, lv) if v is not None]
    overall = "newer" if "newer" in states else "older" if "older" in states else "same"
    return {
        "factory": DATA_VERSION,
        "repo": rv,
        "library": lv,
        "repo_state": compare(rv) if rv is not None else None,
        "library_state": compare(lv) if lv is not None else None,
        "state": overall,
        "initialized": initialized,
    }
