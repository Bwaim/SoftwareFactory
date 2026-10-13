import json

import pytest

from conftest import events, fake_calls, task_from_pipeline, task_json, write_pipeline, write_step
from factory import engine, loops, repo, state
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


FOOTER = "This step controls a loop. Set `k` to `none` when nothing is left."


def test_footer_line_only_on_the_controlling_step(inited):
    out_k = {"outputs": {"k": {"type": "text", "description": "K"}}}
    write_step(inited.fdir, "pre", out_k)
    write_step(inited.fdir, "a", {})
    write_step(inited.fdir, "b", out_k)
    write_step(inited.fdir, "post", out_k)
    write_pipeline(inited.fdir, {"id": "ft", "steps": ["pre", "a", {"id": "b", "loop": loop("a", "k", 2)}, "post"]})
    task_from_pipeline(inited, "ft")
    run = runner(inited)
    seen = {}
    for sid in ("pre", "a", "b", "post"):
        out = run("next").stdout
        seen[sid] = FOOTER in out
        if sid != "a":
            run("state", "set", "k", "none")
        run("done")
    assert seen == {"pre": False, "a": False, "b": True, "post": False}


def test_footer_line_for_subagent_and_command(inited):
    write_step(inited.fdir, "sub", {"run_in": "subagent", "outputs": {"k": {"type": "text", "description": "K"}}})
    write_step(inited.fdir, "cmd", {"type": "command", "outputs": {"k": {"type": "text", "description": "K"}}},
               body="factory state set k none\n")
    write_step(inited.fdir, "end", {})
    write_pipeline(inited.fdir, {"id": "sc", "steps": [{"id": "sub", "loop": loop("sub", "k", 2)},
                                                        {"id": "cmd", "loop": loop("cmd", "k", 2)}, "end"]})
    task_from_pipeline(inited, "sc")
    run = runner(inited)
    sub = run("next").stdout
    assert FOOTER in sub.split("<<<", 1)[1].split(">>>", 1)[0]
    run("state", "set", "k", "none")
    run("done")
    cmd = run("next").stdout
    assert "This step controls a loop. The command sets `k` to `none` when nothing is left." in cmd
    assert "factory state set" not in cmd


def test_status_shows_loop_count(inited):
    run = review_pipeline(inited)
    assert ", loop" not in run("status").stdout
    review_round(run, "bugs")
    assert "Step: write (2 of 4), loop 1 of 2" in run("status").stdout


def test_status_shows_the_innermost_loop(inited):
    run = nested_pipeline(inited)
    step_with(run)
    step_with(run, "inner", "x")
    step_with(run, "inner", "x")
    run("unblock")
    step_with(run, "outer", "y")
    assert "Step: a (2 of 5), loop 1 of 2" in run("status").stdout
    step_with(run)
    step_with(run, "inner", "x")
    assert "Step: b (3 of 5), loop 1 of 1" in run("status").stdout


def notifications(inited):
    return [c["text"] for c in fake_calls(inited.fdir) if c["op"] == "notify"]


def ready_for_last_review(inited, value):
    run = review_pipeline(inited)
    review_round(run, "a")
    review_round(run, "b")
    run("next")
    run("done")
    run("next")
    run("state", "set", "findings", value)
    return repo.load_ctx(cwd=inited.repo)


def test_limit_message_text(inited):
    run = review_pipeline(inited)
    review_round(run, "a")
    review_round(run, "b")
    assert review_round(run, "c").stdout.strip() == (
        f"{LIMIT}. The task is blocked. Ask the user what to do. When the user says to go on, run `factory unblock`. "
        'For one more round, after the user approves, run `factory goto "write" --reason "<why>"`.')


def test_limit_is_one_atomic_update(inited, monkeypatch):
    ctx = ready_for_last_review(inited, "c")
    original, seen = state.update, []

    def update(ctx, tid, fn):
        task = original(ctx, tid, fn)
        seen.append((task["status"], task["steps"][task["position"]]["id"]))
        return task

    monkeypatch.setattr(state, "update", update)
    engine.done(ctx, "t1")
    assert seen == [("blocked", "after")]
    types = [e["type"] for e in events(inited.fdir, "t1")]
    assert types[-3:] == ["step_done", "loop_limit", "task_blocked"]


def test_loop_decision_reads_the_key_inside_the_update(inited, monkeypatch):
    ctx = ready_for_last_review(inited, "c")
    original, fired = state.update, []

    def update(ctx, tid, fn):
        if not fired:
            fired.append(True)
            original(ctx, tid, lambda t: t["state"].__setitem__("findings", "none"))
        return original(ctx, tid, fn)

    monkeypatch.setattr(state, "update", update)
    assert engine.done(ctx, "t1") == "Step done. Run `factory next`."
    t = task_json(inited.fdir, "t1")
    assert current_id(inited) == "after" and t["status"] == "active" and of_type(inited, "loop_limit") == []


def test_limit_on_last_entry_sends_one_notification(inited):
    run = review_pipeline(inited, limit=1, after=False)
    review_round(run, "a")
    before = len(notifications(inited))
    review_round(run, "b")
    assert notifications(inited)[before:] == [
        "Task t1 finished, but the loop limit was reached on `review`: `findings` is still set."]
    types = [e["type"] for e in events(inited.fdir, "t1")]
    assert types.index("loop_limit") < types.index("task_finished")


def test_limit_through_end_wait(inited):
    write_step(inited.fdir, "w", {"wait_external": True, "done_when": "QA is done.",
                                  "outputs": {"bugs": {"type": "text", "description": "Bugs"}}})
    write_step(inited.fdir, "end", {})
    write_pipeline(inited.fdir, {"id": "wl", "steps": [{"id": "w", "loop": loop("w", "bugs", 1)}, "end"]})
    task_from_pipeline(inited, "wl", terminal_handle={"agent": "t1"})
    run = runner(inited)
    for _ in range(2):
        run("next")
        run("state", "set", "bugs", "two")
        run("wait")
        inited.factory("external-done", "t1")
    limit = "Loop limit reached on `w`: `bugs` is still set"
    t = task_json(inited.fdir, "t1")
    assert current_id(inited) == "end" and t["status"] == "blocked" and t["status_reason"] == limit
    texts = [c.get("text", "") for c in fake_calls(inited.fdir)]
    assert any(text.startswith(f"The external event happened: QA is done. {limit}. The task is blocked.") for text in texts)


def test_inner_loop_on_the_same_first_step_gets_its_full_max_again(inited):
    write_step(inited.fdir, "a", {})
    write_step(inited.fdir, "b", {"outputs": {"inner": {"type": "text", "description": "Inner"}}})
    write_step(inited.fdir, "c", {"outputs": {"outer": {"type": "text", "description": "Outer"}}})
    write_step(inited.fdir, "end", {})
    write_pipeline(inited.fdir, {"id": "same", "steps": [
        "a", {"id": "b", "loop": loop("b", "inner", 1)}, {"id": "c", "loop": loop("b", "outer", 2)}, "end"]})
    task_from_pipeline(inited, "same")
    run = runner(inited)
    step_with(run)
    assert step_with(run, "inner", "x") == "Loop 1 of 1: back to `b`. Run `factory next`."
    assert "Loop limit reached on `b`" in step_with(run, "inner", "x")
    run("unblock")
    assert step_with(run, "outer", "y") == "Loop 1 of 2: back to `b`. Run `factory next`."
    assert step_with(run, "inner", "x") == "Loop 1 of 1: back to `b`. Run `factory next`."


def test_running_task_keeps_its_loop_snapshot(inited):
    run = review_pipeline(inited)
    steps = ["write", {"id": "review", "loop": loop("write", "findings", 1)}, "after"]
    write_pipeline(inited.fdir, {"id": "rl", "steps": steps})
    assert review_round(run, "a").stdout.strip() == "Loop 1 of 2: back to `write`. Run `factory next`."
    assert review_round(run, "b").stdout.strip() == "Loop 2 of 2: back to `write`. Run `factory next`."
    assert [l["max"] for l in task_json(inited.fdir, "t1")["loops"]] == [2]


def test_check_skips_the_loop_of_an_unknown_step(inited):
    write_step(inited.fdir, "a", {})
    messages = check_messages(inited, "ghost", ["a", {"id": "ghost", "loop": loop("nowhere", "Bad-Key", 0)}, "a"])
    assert messages and not any("loop" in m for _, m in messages)
