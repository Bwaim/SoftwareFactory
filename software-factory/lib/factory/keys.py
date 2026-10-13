import re

KEY_RE = re.compile(r"[a-z][a-z0-9_]*")
KEY_TYPES = ("text", "long-text", "file")
FACTORY_KEYS = {
    "task_id": {"type": "text", "set": "always"},
    "description": {"type": "text", "set": "always"},
    "summary": {"type": "long-text", "set": "maybe"},
}
PLACEHOLDER_RE = re.compile(r"\{\{([^{}]*)\}\}")
ENV_PREFIX = "FACTORY_KEY_"
ENV_RE = re.compile(r"\$\{?" + ENV_PREFIX + r"([A-Z][A-Z0-9_]*)")
CONFIG_PREFIX = "config."


def is_key(name):
    return isinstance(name, str) and KEY_RE.fullmatch(name) is not None


def key_type(spec):
    value = spec.get("type") if isinstance(spec, dict) else None
    return value or "text"


def env_name(key):
    return ENV_PREFIX + key.upper()


def add_once(items, value):
    if value not in items:
        items.append(value)


def placeholders(text):
    found_keys, found_config, invalid = [], [], []
    for m in PLACEHOLDER_RE.finditer(text or ""):
        inner = m.group(1)
        if inner.startswith(CONFIG_PREFIX) and is_key(inner[len(CONFIG_PREFIX):]):
            add_once(found_config, inner[len(CONFIG_PREFIX):])
        elif is_key(inner):
            add_once(found_keys, inner)
        else:
            add_once(invalid, m.group(0))
    return found_keys, found_config, invalid


def has_placeholder(text):
    return PLACEHOLDER_RE.search(text or "") is not None


def env_refs(text):
    found = []
    for m in ENV_RE.finditer(text or ""):
        add_once(found, m.group(1).lower())
    return found


def outputs_of(step):
    out = {}
    for name, spec in (step.get("outputs") or {}).items():
        spec = spec if isinstance(spec, dict) else {}
        out[name] = {"type": key_type(spec), "description": spec.get("description") or "", "optional": bool(spec.get("optional"))}
    return out


def leaf_uses(step):
    used = placeholders(step.body)[0] if step.type == "ai" else env_refs(step.body)
    used = list(used)
    for key in env_refs(step.done_check or ""):
        add_once(used, key)
    return used


def step_uses(reg, sid):
    step = reg.step(sid)
    if step.type != "group":
        return leaf_uses(step)
    used, set_before = [], set()
    for path in reg.leaves(sid):
        leaf = reg.step(path[-1])
        for key in leaf_uses(leaf):
            if key not in set_before:
                add_once(used, key)
        set_before |= set(outputs_of(leaf))
    return used


def step_outputs(reg, sid):
    step = reg.step(sid)
    if step.type != "group":
        return outputs_of(step)
    out = {}
    for path in reg.leaves(sid):
        out.update(outputs_of(reg.step(path[-1])))
    return out


def put(rows, name, ktype, source, set_state):
    rows.pop(name, None)
    rows[name] = {"name": name, "type": ktype, "source": source, "set": set_state}


def pipeline_entries(data):
    from .registry import normalize_entry
    return [normalize_entry(e) for e in data.get("steps") or []]


def start_rows(data):
    rows = {}
    for name, spec in FACTORY_KEYS.items():
        put(rows, name, spec["type"], "factory", spec["set"])
    for name, spec in (data.get("inputs") or {}).items():
        put(rows, name, key_type(spec), "input", "always")
    return rows


def entry_leaves(reg, entry):
    from .errors import FactoryError
    sid = entry.get("id")
    if sid not in reg.steps:
        return []
    try:
        return [reg.steps[path[-1]] for path in reg.leaves(sid) if path[-1] in reg.steps]
    except FactoryError:
        return []


def add_outputs(rows, leaf):
    for name, out in outputs_of(leaf).items():
        put(rows, name, out["type"], f"step {leaf.id}", "maybe" if out["optional"] else "always")


def available(reg, data, at=None):
    from .errors import FactoryError
    entries = pipeline_entries(data)
    last = len(entries) + 1
    at = last if at is None else at
    if not isinstance(at, int) or not 1 <= at <= last:
        raise FactoryError(f"The position must be between 1 and {last}.")
    rows = start_rows(data)
    for entry in entries[:at - 1]:
        for leaf in entry_leaves(reg, entry):
            add_outputs(rows, leaf)
    return list(rows.values())
