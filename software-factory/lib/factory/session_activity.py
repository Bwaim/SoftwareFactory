"""What each Claude session last did, written by the factory's Claude hooks.

Adapters that cannot ask their terminal whether Claude works (Warp) read it here: a prompt means working, a stop means idle.
"""
import re

from . import fsio

KINDS = {"prompt": "working", "stop": "idle"}
SESSION_ID_RE = re.compile(r"[A-Za-z0-9-]{1,64}")


def path(ctx, session_id):
    return ctx.fdir / "session-activity" / f"{session_id}.json"


def record(ctx, session_id, kind):
    if kind not in KINDS or not isinstance(session_id, str) or not SESSION_ID_RE.fullmatch(session_id):
        return
    p = path(ctx, session_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    fsio.write_json(p, {"state": KINDS[kind]})


def read(ctx, session_id):
    if not isinstance(session_id, str) or not SESSION_ID_RE.fullmatch(session_id):
        return None
    return (fsio.read_json(path(ctx, session_id), {}) or {}).get("state")


def forget(ctx, session_id):
    if isinstance(session_id, str) and SESSION_ID_RE.fullmatch(session_id):
        path(ctx, session_id).unlink(missing_ok=True)
