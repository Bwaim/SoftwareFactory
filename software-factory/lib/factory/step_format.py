import re

import yaml

from . import keys

STEP_ID_RE = re.compile(r"[a-z][a-z0-9_-]{0,63}")
TYPES = ("ai", "command", "group")
OLD_TYPES = ("prompt", "skill", "script", "composite")
RUN_IN = ("session", "subagent")
FIELD_ORDER = ("id", "description", "category", "type", "outputs", "done_when", "done_check", "config", "required",
               "run_in", "model", "effort", "requires", "column", "wait_external", "steps")
KEY_RULE = "must use lowercase letters, digits and `_`, and start with a letter"


def is_valid_id(value):
    return isinstance(value, str) and STEP_ID_RE.fullmatch(value) is not None


def is_empty(value):
    return value is None or value is False or value == "" or value == [] or value == {}


def clean(manifest):
    return {k: v for k, v in manifest.items() if k == "required" or not is_empty(v)}


def check_outputs(manifest, errors, warnings):
    outputs = manifest.get("outputs") or {}
    if not isinstance(outputs, dict):
        errors.append("`outputs` must be a mapping of key names.")
        return
    for name, spec in outputs.items():
        if not keys.is_key(name):
            errors.append(f"The output `{name}` {KEY_RULE}.")
        if spec is not None and not isinstance(spec, dict):
            errors.append(f"The output `{name}` must be a mapping with `type` and `description`.")
            continue
        if keys.key_type(spec) not in keys.KEY_TYPES:
            errors.append(f"The output `{name}` has an unknown type `{keys.key_type(spec)}`. Use text, long-text or file.")
        elif not (spec or {}).get("description"):
            warnings.append(f"The output `{name}` has no description.")


def config_of(manifest, errors):
    config = manifest.get("config") or {}
    if not isinstance(config, dict):
        errors.append("`config` must be a mapping of config keys.")
        return {}
    for name in config:
        if not keys.is_key(name):
            errors.append(f"The config key `{name}` {KEY_RULE}.")
    return config


def check_body(stype, manifest, body, config, errors):
    text = body or ""
    if stype == "ai":
        _, used_config, invalid = keys.placeholders(text)
        for p in invalid:
            errors.append(f"Invalid placeholder {p}. Use {{{{<key>}}}} or {{{{config.<key>}}}}.")
        for name in used_config:
            if name not in config:
                errors.append(f"The placeholder {{{{config.{name}}}}} uses a config key that `config` does not declare.")
        if not text.strip():
            errors.append("The prompt is empty.")
    elif stype == "command":
        if keys.has_placeholder(text):
            errors.append("A command cannot use `{{...}}` placeholders. Use $FACTORY_KEY_<KEY> and $FACTORY_CONFIG_<KEY>.")
        if not text.strip():
            errors.append("The command is empty.")
    elif stype == "group":
        children = manifest.get("steps")
        if not isinstance(children, list) or not children:
            errors.append("A group step needs a `steps` list of child step ids.")
        if text.strip():
            errors.append("A group step has no body.")
        if manifest.get("outputs"):
            errors.append("A group step computes its outputs from its child steps. Remove `outputs`.")


def check_run(stype, manifest, errors, warnings):
    run_in = manifest.get("run_in")
    if run_in is not None and run_in not in RUN_IN:
        errors.append("`run_in` must be `session` or `subagent`.")
    if stype in ("command", "group"):
        for name in ("run_in", "model", "effort"):
            if manifest.get(name):
                warnings.append(f"`{name}` applies only to `ai` steps.")
    elif stype == "ai" and (run_in or "session") == "session":
        for name in ("model", "effort"):
            if manifest.get(name):
                warnings.append(f"`{name}` has no effect on a step that runs in the session.")


def validate(manifest, body):
    if not isinstance(manifest, dict):
        return ["The manifest must be a YAML mapping."], []
    errors, warnings = [], []
    sid = manifest.get("id")
    if sid is None or str(sid).strip() == "":
        errors.append("The id is empty.")
    elif not is_valid_id(sid):
        errors.append(f"The id `{sid}` must be lowercase: letters, digits, `-` or `_`, starting with a letter.")
    stype = manifest.get("type")
    if stype in OLD_TYPES:
        errors.append(f"The type `{stype}` is from data version 1. Run the migration.")
    elif stype not in TYPES:
        errors.append("The type must be `ai`, `command` or `group`.")
    for old in ("reads", "writes"):
        if old in manifest:
            errors.append(f"`{old}` is from data version 1. Run the migration.")
    check_outputs(manifest, errors, warnings)
    config = config_of(manifest, errors)
    check_body(stype, manifest, body, config, errors)
    if keys.has_placeholder(str(manifest.get("done_check") or "")):
        errors.append("`done_check` cannot use `{{...}}` placeholders. Use $FACTORY_KEY_<KEY>.")
    check_run(stype, manifest, errors, warnings)
    if not manifest.get("description"):
        warnings.append("The description is empty.")
    return errors, warnings


def dump(manifest, body):
    data = clean(manifest)
    ordered = {k: data[k] for k in FIELD_ORDER if k in data}
    ordered.update({k: v for k, v in data.items() if k not in ordered})
    text = "---\n" + yaml.safe_dump(ordered, sort_keys=False, allow_unicode=True) + "---\n"
    if manifest.get("type") != "group" and (body or "").strip():
        text += "\n" + body.strip("\n") + "\n"
    return text
