import os
from pathlib import Path

import yaml


def pipeline_files(root):
    return sorted((Path(root) / "pipelines").glob("*.yaml"))


def load(path):
    try:
        return yaml.safe_load(path.read_text()), None
    except yaml.YAMLError as exc:
        return None, f"{path}: invalid YAML: {str(exc).splitlines()[0]}"


def folder_errors(root):
    errors = []
    for path in pipeline_files(root):
        data, problem = load(path)
        if problem:
            errors.append(problem)
        elif isinstance(data, dict) and "worktree" in data and not isinstance(data["worktree"], bool):
            errors.append(f"{path}: `worktree` must be `true` or `false`.")
    return errors


def check_repo(factory_dir):
    return folder_errors(factory_dir), []


def check_library(library_dir):
    return folder_errors(library_dir), []


def write_atomic(path, text):
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text)
    os.replace(tmp, path)


def add_worktree(root):
    for path in pipeline_files(root):
        data, problem = load(path)
        if problem or not isinstance(data, dict) or "worktree" in data:
            continue
        text = path.read_text()
        sep = "" if text.endswith("\n") or not text else "\n"
        write_atomic(path, text + sep + "worktree: true\n")


def migrate_repo(factory_dir):
    add_worktree(factory_dir)


def migrate_library(library_dir):
    add_worktree(library_dir)
