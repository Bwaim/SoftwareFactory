from . import adapters, attention, events, state
from .errors import FactoryError
from .pty_sessions import REGISTRY


def key(ctx, tid):
    return (str(ctx.main), tid)


def open_terminal(ctx, tid, cols, rows):
    """Attach a live terminal to the task's session, or reuse the one already attached."""
    task = state.load(ctx, tid)
    handle = task.get("terminal_handle")
    if not handle:
        raise FactoryError(f"Task {tid} has no live session. Resume it first.")
    adapter = adapters.get_adapter(ctx)
    if "attach" not in adapter.capabilities():
        raise FactoryError(f"The {adapter.name} terminal adapter cannot attach a live terminal.")
    _, started = REGISTRY.open(key(ctx, tid), adapter.attach_command(handle), cols, rows)
    if started:
        events.log(ctx, tid, "terminal_attached", state.step_path_str(task))
    return {"ok": True, "started": started}


def stream(ctx, tid):
    state.load(ctx, tid)
    return REGISTRY.get(key(ctx, tid)).stream()


def write(ctx, tid, data):
    REGISTRY.get(key(ctx, tid)).write(data)
    attention.clear(ctx, tid, "input")
    return {"ok": True}


def resize(ctx, tid, cols, rows):
    REGISTRY.get(key(ctx, tid)).resize(cols, rows)
    return {"ok": True}


def close(ctx, tid):
    REGISTRY.close(key(ctx, tid))
    return {"ok": True}
