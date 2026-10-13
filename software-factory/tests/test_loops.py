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


def test_review_loop_jumps_twice_then_moves_on(inited):
    run = review_pipeline(inited)
    outs = [review_round(run, v).stdout.strip() for v in ("two bugs", "one bug", "none")]
    assert outs == ["Loop 1 of 2: back to `write`. Run `factory next`.",
                    "Loop 2 of 2: back to `write`. Run `factory next`.",
                    "Step done. Run `factory next`."]
    assert current_id(inited) == "after" and task_json(inited.fdir, "t1")["status"] == "active"
    backs = of_type(inited, "loop_back")
    assert [(e["entry"], e["to"], e["round"], e["max"]) for e in backs] == [("review", "write", 1, 2), ("review", "write", 2, 2)]


def test_limit_moves_on_and_blocks(inited):
    run = review_pipeline(inited)
    review_round(run, "a")
    review_round(run, "b")
    out = review_round(run, "c").stdout
    assert LIMIT in out and "The task is blocked." in out and 'factory goto "write"' in out
    t = task_json(inited.fdir, "t1")
    assert current_id(inited) == "after" and t["status"] == "blocked" and t["status_reason"] == LIMIT
    limit = of_type(inited, "loop_limit")
    assert [(e["entry"], e["key"]) for e in limit] == [("review", "findings")]
    assert of_type(inited, "task_blocked")[-1]["reason"] == LIMIT


def test_goto_after_limit_gives_one_more_round(inited):
    run = review_pipeline(inited)
    for value in ("a", "b", "c"):
        review_round(run, value)
    run("goto", "write", "--reason", "one more round")
    assert LIMIT in review_round(run, "d").stdout
    assert task_json(inited.fdir, "t1")["status"] == "blocked"


def test_limit_on_last_entry_finishes(inited):
    run = review_pipeline(inited, limit=1, after=False)
    review_round(run, "a")
    out = review_round(run, "b").stdout
    assert "The pipeline is finished, but the loop limit was reached on `review`: `findings` is still set." in out
    assert task_json(inited.fdir, "t1")["status"] == "finished"
    assert [(e["entry"], e["key"]) for e in of_type(inited, "loop_limit")] == [("review", "findings")]


def test_group_loop_back_to_itself(inited):
    write_step(inited.fdir, "split", {})
    write_step(inited.fdir, "pick", {"outputs": {"remaining": {"type": "long-text", "description": "Left"}}})
    write_step(inited.fdir, "build", {})
    write_step(inited.fdir, "round", {"type": "group", "steps": ["pick", "build"]}, body="")
    write_pipeline(inited.fdir, {"id": "tl", "steps": ["split", {"id": "round", "loop": loop("round", "remaining", 20)}]})
    task_from_pipeline(inited, "tl")
    run = runner(inited)
    run("next")
    run("done")
    outs = []
    for left in ("b\nc", "c", "none"):
        run("next")
        run("state", "set", "remaining", left)
        run("done")
        run("next")
        outs.append(run("done").stdout.strip())
    assert outs == ["Loop 1 of 20: back to `round > pick`. Run `factory next`.",
                    "Loop 2 of 20: back to `round > pick`. Run `factory next`.",
                    "The pipeline is finished. Tell the user that the task is finished."]
    t = task_json(inited.fdir, "t1")
    assert t["goto_counts"] == {} and t["status"] == "finished"


def nested_pipeline(inited):
    write_step(inited.fdir, "a", {})
    write_step(inited.fdir, "b", {"outputs": {"inner": {"type": "text", "description": "Inner"}}})
    write_step(inited.fdir, "c", {"outputs": {"outer": {"type": "text", "description": "Outer"}}})
    write_step(inited.fdir, "end", {})
    write_pipeline(inited.fdir, {"id": "nest", "steps": [
        "a", {"id": "b", "loop": loop("b", "inner", 1)}, {"id": "c", "loop": loop("a", "outer", 2)}, "end"]})
    task_from_pipeline(inited, "nest")
    return runner(inited)


def step_with(run, key=None, value=None):
    run("next")
    if key:
        run("state", "set", key, value)
    return run("done").stdout.strip()


def test_nested_inner_loop_resets_after_outer_jump(inited):
    run = nested_pipeline(inited)
    step_with(run)
    assert step_with(run, "inner", "x") == "Loop 1 of 1: back to `b`. Run `factory next`."
    assert "Loop limit reached on `b`" in step_with(run, "inner", "x")
    run("unblock")
    assert step_with(run, "outer", "y") == "Loop 1 of 2: back to `a`. Run `factory next`."
    step_with(run)
    assert step_with(run, "inner", "x") == "Loop 1 of 1: back to `b`. Run `factory next`."


def test_goto_resets_only_before_the_range(inited):
    run = nested_pipeline(inited)
    step_with(run)
    step_with(run, "inner", "x")
    step_with(run, "inner", "x")
    run("unblock")
    run("goto", "b", "--reason", "again")
    assert "Loop limit reached on `b`" in step_with(run, "inner", "x")
    run("unblock")
    run("goto", "a", "--reason", "from the start")
    step_with(run)
    assert step_with(run, "inner", "x") == "Loop 1 of 1: back to `b`. Run `factory next`."


def test_not_set_values_move_on(inited):
    run = review_pipeline(inited)
    assert review_round(run, " None ").stdout.strip() == "Step done. Run `factory next`."
    write_step(inited.fdir, "solo", {})
    write_step(inited.fdir, "end", {})
    write_pipeline(inited.fdir, {"id": "never", "steps": [{"id": "solo", "loop": loop("solo", "unset_key", 2)}, "end"]})
    task_from_pipeline(inited, "never", tid="t2")
    run2 = runner(inited, "t2")
    run2("next")
    assert run2("done").stdout.strip() == "Step done. Run `factory next`."
    assert of_type(inited, "loop_back") == [] and of_type(inited, "loop_back", "t2") == []


def test_skipped_loop_step_does_not_jump(inited):
    run = review_pipeline(inited)
    run("next")
    run("done")
    run("next")
    run("state", "set", "findings", "bugs")
    run("skip")
    assert current_id(inited) == "after" and of_type(inited, "loop_back") == []


def test_three_loop_rounds_do_not_block_like_goto(inited):
    run = review_pipeline(inited, limit=5)
    for value in ("a", "b", "c"):
        review_round(run, value)
    t = task_json(inited.fdir, "t1")
    assert t["goto_counts"] == {} and t["status"] == "active" and current_id(inited) == "write"


def test_jump_resets_fields_and_keeps_keys(inited):
    write_step(inited.fdir, "chk", {"type": "command", "outputs": {"k": {"type": "text", "description": "K"}}},
               body="factory state set k again\n")
    write_step(inited.fdir, "end", {})
    write_pipeline(inited.fdir, {"id": "cl", "steps": [{"id": "chk", "loop": loop("chk", "k", 2)}, "end"]})
    task_from_pipeline(inited, "cl", state={"keep": "me"})
    run = runner(inited)
    run("next")
    run("run-command")
    path = inited.fdir / "tasks" / "t1" / "task.json"
    data = json.loads(path.read_text())
    data["approval"] = {"position": 1, "approved": True, "target": "worktree", "artifact_key": None}
    path.write_text(json.dumps(data))
    assert run("done").stdout.startswith("Loop 1 of 2")
    t = task_json(inited.fdir, "t1")
    assert t["command_result"] is None and t["approval"] is None and t["started"] is None
    assert t["state"] == {"keep": "me", "k": "again"}


def test_wait_step_loop_jumps_on_external_done(inited):
    write_step(inited.fdir, "w", {"wait_external": True, "done_when": "QA is done.",
                                  "outputs": {"bugs": {"type": "text", "description": "Bugs"}}})
    write_step(inited.fdir, "end", {})
    write_pipeline(inited.fdir, {"id": "wl", "steps": [{"id": "w", "loop": loop("w", "bugs", 2)}, "end"]})
    task_from_pipeline(inited, "wl", terminal_handle={"agent": "t1"})
    run = runner(inited)
    run("next")
    run("state", "set", "bugs", "two")
    run("wait")
    inited.factory("external-done", "t1")
    assert current_id(inited) == "w" and task_json(inited.fdir, "t1")["status"] == "active"
    texts = [c.get("text", "") for c in fake_calls(inited.fdir)]
    assert "The external event happened: QA is done. Loop 1 of 2: back to `w`. Run `factory next`." in texts


def test_old_task_without_loops(inited):
    write_step(inited.fdir, "a", {})
    write_pipeline(inited.fdir, {"id": "old", "steps": ["a"]})
    task_from_pipeline(inited, "old")
    path = inited.fdir / "tasks" / "t1" / "task.json"
    data = json.loads(path.read_text())
    del data["loops"]
    path.write_text(json.dumps(data))
    run = runner(inited)
    run("next")
    assert "The pipeline is finished" in run("done").stdout
    assert ", loop" not in run("status").stdout
