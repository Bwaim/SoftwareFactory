import importlib
import os
import re

from .base import AdapterError

ADAPTER_NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")


def installed_choice():
    """The terminal chosen by the install script, for repositories that have no choice of their own yet."""
    from ..workspaces import home
    try:
        return (home() / "terminal").read_text().strip() or None
    except OSError:
        return None


def terminal_name(ctx):
    return ctx.factory_yaml().get("terminal") or os.environ.get("FACTORY_TERMINAL") or installed_choice() or "herdr"


def get_adapter(ctx, name=None):
    name = name or terminal_name(ctx)
    if not ADAPTER_NAME_RE.match(name):
        raise AdapterError(f"Invalid terminal adapter name `{name}`.")
    try:
        module = importlib.import_module(f"factory.adapters.{name}")
    except ModuleNotFoundError:
        raise AdapterError(f"Unknown terminal adapter `{name}`.")
    return module.ADAPTER(ctx)
