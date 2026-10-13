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


def check_messages(inited, pid, steps):
    write_pipeline(inited.fdir, {"id": pid, "steps": steps})
    r = inited.factory("pipeline", "check", pid, "--json", check=False)
    return [(p["level"], p["message"]) for p in json.loads(r.stdout)]


def test_check_errors_and_warnings(inited):
    out_k = {"outputs": {"k": {"type": "text", "description": "K"}}}
    write_step(inited.fdir, "a", {})
    write_step(inited.fdir, "b", out_k)
    write_step(inited.fdir, "opt", {"outputs": {"k": {"type": "text", "description": "K", "optional": True}}})
    cases = {
        "not-map": (["a", {"id": "b", "loop": "a"}, "a"], ("error", "Step `b`: `loop` must be a map with `back_to`, `while` and `max`.")),
        "unknown": (["a", {"id": "b", "loop": {**loop("a", "k", 2), "until": 1}}, "a"], ("error", "Step `b`: `loop` has an unknown field `until`.")),
        "later": (["a", {"id": "b", "loop": loop("c", "k", 2)}, "a"], ("error", "Step `b`: `loop.back_to` must be this step or an earlier step of the pipeline.")),
        "worktree": (["create-worktree", "a", {"id": "b", "loop": loop("create-worktree", "k", 2)}, "a"],
                     ("error", "Step `b`: `loop.back_to` cannot be `create-worktree`. It cannot run again.")),
        "max-zero": (["a", {"id": "b", "loop": loop("a", "k", 0)}, "a"], ("error", "Step `b`: `loop.max` must be an integer from 1 to 20.")),
        "max-big": (["a", {"id": "b", "loop": loop("a", "k", 21)}, "a"], ("error", "Step `b`: `loop.max` must be an integer from 1 to 20.")),
        "max-text": (["a", {"id": "b", "loop": loop("a", "k", "2")}, "a"], ("error", "Step `b`: `loop.max` must be an integer from 1 to 20.")),
        "max-bool": (["a", {"id": "b", "loop": loop("a", "k", True)}, "a"], ("error", "Step `b`: `loop.max` must be an integer from 1 to 20.")),
        "bad-key": (["a", {"id": "b", "loop": loop("a", "Bad-Key", 2)}, "a"],
                    ("error", "Step `b`: `loop.while` must be a key name: lowercase letters, digits and `_`, starting with a letter.")),
        "no-output": (["a", {"id": "a", "loop": loop("a", "k", 2)}, "b"], ("warning", "Step `a`: no step inside the loop outputs `k`. The loop never ends early.")),
        "optional": (["a", {"id": "opt", "loop": loop("a", "k", 2)}, "a"], ("warning", "Step `opt`: `k` is optional in every step that outputs it inside the loop.")),
        "last": (["a", {"id": "b", "loop": loop("a", "k", 2)}],
                 ("warning", "Step `b`: the loop is on the last step. At the limit, the task finishes without asking the user. Add a step after it, for example `user-validation`.")),
    }
    for pid, (steps, expected) in cases.items():
        assert expected in check_messages(inited, pid, steps), pid


def test_overlap_names_both_loops_and_nested_is_fine(inited):
    out_k = {"outputs": {"k": {"type": "text", "description": "K"}}}
    for sid in ("a", "b", "c", "d"):
        write_step(inited.fdir, sid, out_k)
    overlap = check_messages(inited, "ov", ["a", "b", {"id": "c", "loop": loop("a", "k", 2)}, {"id": "d", "loop": loop("b", "k", 2)}, "a"])
    assert ("error", "The loops of `c` and `d` overlap. One loop must be inside the other.") in overlap
    nested = check_messages(inited, "ok", ["a", {"id": "b", "loop": loop("b", "k", 2)}, {"id": "c", "loop": loop("a", "k", 2)}, "d"])
    assert nested == []


def test_back_to_uses_the_nearest_earlier_entry(inited):
    for sid in ("a", "b"):
        write_step(inited.fdir, sid, {"outputs": {"k": {"type": "text", "description": "K"}}})
    write_pipeline(inited.fdir, {"id": "near", "steps": ["a", "b", "a", {"id": "b", "loop": loop("a", "k", 2)}, "b"]})
    reg = Registry.load(repo.load_ctx(cwd=inited.repo))
    assert [(l["first"], l["last"]) for l in loops.snapshot(reg, reg.pipeline("near"))] == [(3, 4)]
    assert check_messages(inited, "near", ["a", "b", "a", {"id": "b", "loop": loop("a", "k", 2)}, "b"]) == []


def test_key_set_later_in_the_loop_is_available_inside_the_range(inited):
    write_step(inited.fdir, "write", {}, body="Fix {{findings}}.\n")
    write_step(inited.fdir, "review", {"outputs": {"findings": {"type": "long-text", "description": "Findings"}}})
    write_step(inited.fdir, "after", {}, body="Read {{findings}}.\n")
    write_step(inited.fdir, "before", {}, body="Read {{findings}}.\n")
    messages = check_messages(inited, "lk", ["before", "write", {"id": "review", "loop": loop("write", "findings", 2)}, "after"])
    assert messages == [("warning", "Step `before` uses `findings`, which no input, earlier step or factory key sets.")]
