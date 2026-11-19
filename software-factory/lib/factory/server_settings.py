import os

from . import fsio, workspaces
from .errors import FactoryError

POLL_MIN = 10
POLL_MAX = 86400
POLL_DEFAULT = 300
POLL_RANGE = f"The poll interval must be a whole number from {POLL_MIN} to {POLL_MAX} seconds."


def path():
    return workspaces.home() / "server.yaml"


def valid_poll(value):
    return isinstance(value, int) and not isinstance(value, bool) and POLL_MIN <= value <= POLL_MAX


def env_poll():
    try:
        return int(os.environ.get("FACTORY_POLL_SECONDS") or "")
    except ValueError:
        return None


def saved_poll():
    try:
        data = fsio.read_yaml(path(), {})
    except (FactoryError, OSError):
        return None
    value = data.get("poll_seconds") if isinstance(data, dict) else None
    return value if valid_poll(value) else None


def poll_seconds():
    for value in (env_poll(), saved_poll()):
        if value is not None:
            return value
    return POLL_DEFAULT


def read():
    return {
        "poll_seconds": poll_seconds(),
        "saved_poll_seconds": saved_poll(),
        "env_poll_seconds": env_poll(),
        "default_poll_seconds": POLL_DEFAULT,
    }


def save(body):
    value = body.get("poll_seconds")
    if value is not None and value != "" and not valid_poll(value):
        raise FactoryError(POLL_RANGE)

    def apply(data):
        if value in (None, ""):
            data.pop("poll_seconds", None)
        else:
            data["poll_seconds"] = value

    fsio.update_yaml(path(), apply)
    return read()
