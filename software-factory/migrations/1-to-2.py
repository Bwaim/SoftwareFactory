import json
import os
import re
from pathlib import Path

import yaml

KEY_RE = re.compile(r"[a-z][a-z0-9_]*")
FRONT_RE = re.compile(r"^---\n(.*?)\n---\n?(.*)$", re.S)
PLACEHOLDER_RE = re.compile(r"\{\{([^{}]*)\}\}")
TYPE_MAP = {None: "ai", "prompt": "ai", "skill": "ai", "composite": "group", "script": "command"}
NEW_TYPES = ("ai", "command", "group")
REMOVED_PIPELINE = "new-step-assistant"
FIELD_ORDER = ("id", "description", "category", "type", "outputs", "done_when", "done_check", "config", "required",
               "run_in", "model", "effort", "requires", "column", "wait_external", "steps")
KEY_RULE = "must use lowercase letters, digits and `_`, and start with a letter"


def is_key(name):
    return isinstance(name, str) and KEY_RE.fullmatch(name) is not None


def read_step(path):
    m = FRONT_RE.match(path.read_text())
    if not m:
        return None
    return yaml.safe_load(m.group(1)) or {}, m.group(2).lstrip("\n")


def key_block(title, lines):
    return title + "\n" + "\n".join(lines)


def convert(manifest, body):
    m = dict(manifest)
    old_type = m.get("type")
    new_type = TYPE_MAP.get(old_type, old_type)
    m["type"] = new_type
    reads = list(m.pop("reads", None) or [])
    writes = list(m.pop("writes", None) or [])
    if writes and new_type != "group":
        outputs = dict(m.get("outputs") or {})
        for key in writes:
            outputs.setdefault(key, {"type": "text", "description": "", "optional": True})
        m["outputs"] = outputs
    if old_type == "script":
        first = next((line.strip() for line in body.splitlines() if line.strip()), "")
        body = f'bash "$FACTORY_STEP_DIR/{first}"\n'
    if new_type == "ai":
        blocks = []
        if reads:
            blocks.append(key_block("Task keys:", [f"- {k}: {{{{{k}}}}}" for k in reads]))
        config = m.get("config") or {}
        if config:
            blocks.append(key_block("Config:", [f"- {k}: {{{{config.{k}}}}}" for k in config]))
        if blocks:
            body = body.rstrip("\n") + "\n\n" + "\n\n".join(blocks) + "\n"
    if new_type == "group":
        body = ""
    return m, body, reads + writes


def dump(manifest, body):
    data = {k: v for k, v in manifest.items() if k == "required" or v not in (None, "", [], {})}
    ordered = {k: data[k] for k in FIELD_ORDER if k in data}
    ordered.update({k: v for k, v in data.items() if k not in ordered})
    text = "---\n" + yaml.safe_dump(ordered, sort_keys=False, allow_unicode=True) + "---\n"
    if ordered.get("type") != "group" and body.strip():
        text += "\n" + body.strip("\n") + "\n"
    return text


STEP_ID_RE = re.compile(r"[a-z][a-z0-9_-]{0,63}")
RUN_IN = ("session", "subagent")


def ai_errors(path, new_body, config):
    errors = []
    for m in PLACEHOLDER_RE.finditer(new_body):
        inner = m.group(1)
        if inner.startswith("config."):
            if inner[len("config."):] not in config:
                errors.append(f"{path}: the placeholder {m.group(0)} uses a config key that the step does not declare.")
        elif not is_key(inner):
            errors.append(f"{path}: the text {m.group(0)} is not a valid placeholder. Change it, then migrate again.")
    if not new_body.strip():
        errors.append(f"{path}: the prompt is empty. Write a prompt, then migrate again.")
    return errors


def type_errors(path, manifest, new_m, new_body, config):
    stype = new_m["type"]
    if stype not in NEW_TYPES:
        return [f"{path}: unknown step type `{manifest.get('type')}`."]
    if stype == "ai":
        return ai_errors(path, new_body, config)
    if stype == "command":
        errors = []
        if PLACEHOLDER_RE.search(new_body):
            errors.append(f"{path}: the command contains `{{{{`. Remove it, then migrate again.")
        if not new_body.strip() or new_body.strip() == 'bash "$FACTORY_STEP_DIR/"':
            errors.append(f"{path}: the script step names no script file. Write the file name in the body, then migrate again.")
        return errors
    children = new_m.get("steps")
    if not isinstance(children, list) or not children:
        return [f"{path}: the composite step has no `steps` list. Add its child steps, then migrate again."]
    return []


def step_errors(path, manifest, new_m, new_body, used):
    errors = []
    if not (isinstance(new_m.get("id"), str) and STEP_ID_RE.fullmatch(new_m["id"])):
        errors.append(f"{path}: the step id `{new_m.get('id')}` must be lowercase: letters, digits, `-` or `_`, starting with a letter.")
    for key in used:
        if not is_key(key):
            errors.append(f"{path}: the key `{key}` {KEY_RULE}.")
    config = new_m.get("config") or {}
    if not isinstance(config, dict):
        errors.append(f"{path}: `config` must be a mapping of config keys.")
        config = {}
    for key in config:
        if not is_key(key):
            errors.append(f"{path}: the config key `{key}` {KEY_RULE}.")
    errors += type_errors(path, manifest, new_m, new_body, config)
    if PLACEHOLDER_RE.search(str(new_m.get("done_check") or "")):
        errors.append(f"{path}: the done check contains `{{{{`. Remove it, then migrate again.")
    run_in = new_m.get("run_in")
    if run_in is not None and run_in not in RUN_IN:
        errors.append(f"{path}: `run_in` must be `session` or `subagent`.")
    return errors


def folder_errors(root):
    root = Path(root)
    errors = []
    for path in sorted((root / "steps").glob("*.md")):
        parsed = read_step(path)
        if parsed is None:
            errors.append(f"{path}: the step file has no YAML frontmatter.")
            continue
        manifest, body = parsed
        manifest.setdefault("id", path.stem)
        new_m, new_body, used = convert(manifest, body)
        errors += step_errors(path, manifest, new_m, new_body, used)
    for path in sorted((root / "pipelines").glob("*.yaml")):
        data = yaml.safe_load(path.read_text()) or {}
        for key in (data.get("inputs") or {}):
            if not is_key(key):
                errors.append(f"{path}: the input `{key}` {KEY_RULE}.")
    return errors


def task_problems(factory_dir):
    errors, warnings = [], []
    for path in sorted((Path(factory_dir) / "tasks").glob("*/task.json")):
        task = json.loads(path.read_text())
        if task.get("status") == "finished":
            continue
        tid = task.get("id")
        if task.get("pipeline") == REMOVED_PIPELINE:
            errors.append(f"Task {tid} uses the removed pipeline `{REMOVED_PIPELINE}`. Delete it with the previous factory version, "
                          f"or move `.factory/tasks/{tid}` to `.factory/tasks/archive/{tid}`, then migrate again.")
        for key in (task.get("state") or {}):
            if not is_key(key):
                warnings.append(f"Task {tid}: the state key `{key}` does not follow the key name rule. Steps cannot use it in a placeholder.")
    return errors, warnings


def check_repo(factory_dir):
    errors, warnings = task_problems(factory_dir)
    return folder_errors(factory_dir) + errors, warnings


def check_library(library_dir):
    return folder_errors(library_dir), []


def write_atomic(path, text):
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text)
    os.replace(tmp, path)


def convert_folder(root):
    for path in sorted((Path(root) / "steps").glob("*.md")):
        parsed = read_step(path)
        if parsed is None:
            continue
        manifest, body = parsed
        manifest.setdefault("id", path.stem)
        new_m, new_body, _ = convert(manifest, body)
        write_atomic(path, dump(new_m, new_body))


def migrate_repo(factory_dir):
    convert_folder(factory_dir)


def migrate_library(library_dir):
    convert_folder(library_dir)
