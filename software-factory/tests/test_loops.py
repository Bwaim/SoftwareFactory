import json

import pytest

from conftest import events, fake_calls, task_from_pipeline, task_json, write_pipeline, write_step
from factory import loops, repo
from factory.registry import Registry

LIMIT = "Loop limit reached on `review`: `findings` is still set"


def runner(inited, tid="t1"):
    return lambda *a, check=True: inited.factory(*a, "--task", tid, check=check)


def loop(back_to, key, limit):
    return {"back_to": back_to, "while": key, "max": limit}


def review_pipeline(inited, limit=2, after=True):
    write_step(inited.fdir, "write", {})
    write_step(inited.fdir, "review", {"outputs": {"findings": {"type": "long-text", "description": "Findings"}}})
    write_step(inited.fdir, "after", {})
    steps = ["write", {"id": "review", "loop": loop("write", "findings", limit)}]
    if after:
        steps.append("after")
    write_pipeline(inited.fdir, {"id": "rl", "steps": steps})
    task_from_pipeline(inited, "rl")
    return runner(inited)


def review_round(run, value):
    run("next")
    run("done")
    run("next")
    run("state", "set", "findings", value)
    return run("done", check=False)


def current_id(inited, tid="t1"):
    t = task_json(inited.fdir, tid)
    return t["steps"][t["position"]]["id"] if t["position"] < len(t["steps"]) else None


def of_type(inited, kind, tid="t1"):
    return [e for e in events(inited.fdir, tid) if e["type"] == kind]


def test_is_set():
    for value in (None, "", "  ", "none", "None", " None ", "NONE"):
        assert loops.is_set(value) is False
    for value in ("x", "nonesuch", "0", 0):
        assert loops.is_set(value) is True


def test_snapshot_positions(inited):
    write_step(inited.fdir, "a", {})
    write_step(inited.fdir, "b", {})
    write_step(inited.fdir, "g", {"type": "group", "steps": ["a", "b"]}, body="")
    write_pipeline(inited.fdir, {"id": "s1", "steps": ["a", {"id": "g", "loop": loop("a", "k", 3)}, "b"]})
    write_pipeline(inited.fdir, {"id": "s2", "steps": [{"id": "create-worktree", "with": {"base_ref": "main"}}, "a",
                                                         {"id": "g", "loop": loop("g", "k", 3)}]})
    reg = Registry.load(repo.load_ctx(cwd=inited.repo))
    assert loops.snapshot(reg, reg.pipeline("s1")) == [
        {"entry": "g", "back_to": "a", "first": 1, "last": 3, "while": "k", "max": 3, "jumps": 0}]
    assert loops.snapshot(reg, reg.pipeline("s2")) == [
        {"entry": "g", "back_to": "g", "first": 2, "last": 3, "while": "k", "max": 3, "jumps": 0}]
