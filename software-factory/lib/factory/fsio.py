import fcntl
import json
import os
import tempfile
from contextlib import contextmanager
from pathlib import Path

import yaml


def atomic_write_text(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


@contextmanager
def locked(path):
    path = Path(path)
    lock = path.with_name(path.name + ".lock")
    lock.parent.mkdir(parents=True, exist_ok=True)
    with open(lock, "a") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def read_text(path, default=""):
    path = Path(path)
    return path.read_text() if path.exists() else default


def read_yaml(path, default=None):
    path = Path(path)
    if not path.exists():
        return default
    data = yaml.safe_load(path.read_text())
    return default if data is None else data


def dump_yaml(data):
    return yaml.safe_dump(data, sort_keys=False, allow_unicode=True)


def write_yaml(path, data):
    atomic_write_text(path, dump_yaml(data))


def read_json(path, default=None):
    path = Path(path)
    if not path.exists():
        return default
    return json.loads(path.read_text())


def write_json(path, data):
    atomic_write_text(path, json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def update_json(path, fn, default_factory=dict):
    with locked(path):
        data = read_json(path)
        data = default_factory() if data is None else data
        result = fn(data)
        write_json(path, data)
        return result


def update_yaml(path, fn, default_factory=dict):
    with locked(path):
        data = read_yaml(path)
        data = default_factory() if data is None else data
        result = fn(data)
        write_yaml(path, data)
        return result


def update_text(path, fn):
    with locked(path):
        new = fn(read_text(path))
        atomic_write_text(path, new)
        return new


def append_line(path, line):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with locked(path):
        with open(path, "a") as f:
            f.write(line.rstrip("\n") + "\n")
