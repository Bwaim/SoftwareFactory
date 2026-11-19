from . import adapters, attention, events, state
from .adapters.base import AdapterError
from .errors import FactoryError

SCREEN_LINES = 120
TEXT_MAX = 4000
KEYS = ("enter", "esc", "tab", "backspace", "space", "up", "down", "left", "right", "ctrl+c")


def screen(ctx, tid):
    """The last lines of the task's terminal session, with their colors, or why they cannot be read."""
    task = state.load(ctx, tid)
    handle = task.get("terminal_handle")
    if not handle:
        return {"available": False, "reason": "The task has no live session.", "can_type": False}
    try:
        adapter = adapters.get_adapter(ctx)
        caps = adapter.capabilities()
        if "read_screen" not in caps:
            return {"available": False, "reason": f"The {adapter.name} terminal adapter cannot read the session.", "can_type": False}
        return {"available": True, "text": adapter.read_screen(handle, SCREEN_LINES), "can_type": "type_input" in caps}
    except AdapterError as e:
        return {"available": False, "reason": str(e), "can_type": False}


def check_input(text, keys):
    if not isinstance(text, str) or not isinstance(keys, list):
        raise FactoryError("Send `text` as a string and `keys` as a list.")
    if not text and not keys:
        raise FactoryError("Nothing to send.")
    if len(text) > TEXT_MAX:
        raise FactoryError(f"The text is longer than {TEXT_MAX} characters.")
    if any(ord(c) < 32 or ord(c) == 127 for c in text):
        raise FactoryError("The text has control characters. Use the key buttons for Enter, Tab and other keys.")
    unknown = [k for k in keys if k not in KEYS]
    if unknown:
        raise FactoryError(f"Unknown keys: {', '.join(map(str, unknown))}. Known keys: {', '.join(KEYS)}.")


def send_input(ctx, tid, text, keys):
    """Type text, then press keys, in the task's terminal session."""
    check_input(text, keys)
    task = state.load(ctx, tid)
    handle = task.get("terminal_handle")
    if not handle:
        raise FactoryError(f"Task {tid} has no live session. Resume it first.")
    adapter = adapters.get_adapter(ctx)
    if "type_input" not in adapter.capabilities():
        raise FactoryError(f"The {adapter.name} terminal adapter cannot type in the session.")
    step = state.step_path_str(task)
    try:
        if text:
            adapter.send_text(handle, text)
        if keys:
            adapter.send_keys(handle, keys)
    except AdapterError as e:
        events.log(ctx, tid, "terminal_input_failed", step, keys=keys, reason=str(e))
        raise
    # The typed text stays out of the event log: a terminal can ask for a password or a token.
    events.log(ctx, tid, "terminal_input", step, chars=len(text), keys=keys)
    attention.clear(ctx, tid, "input")
    return {"ok": True}
