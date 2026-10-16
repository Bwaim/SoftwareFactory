import json
import subprocess
import sys

import pytest

from conftest import BIN, events, fake_calls, task_from_pipeline, task_json, write_pipeline, write_step

WAIT_T2 = "The step `emu` needs `emu`, now used by task `t1`. The factory starts this task when it is free. End your turn."
NEXT_PROMPT = "`emu` is yours now. Run `factory next`."
ACQUIRE_PROMPT = "`emu` is yours now. Continue the step."
RELEASED = "You released `emu`. Run `factory exclusive acquire emu` before you use it again."


@pytest.fixture
def base(inited):
    write_step(inited.fdir, "emu", {"exclusive": "emu"})
    write_step(inited.fdir, "emu2", {"exclusive": "emu"})
    write_step(inited.fdir, "emu-check", {"exclusive": "emu", "done_check": "true"})
    write_step(inited.fdir, "emu-loop", {"exclusive": "emu", "outputs": {"k": {"type": "text", "description": "K", "optional": True}}})
    write_step(inited.fdir, "before", {})
    write_step(inited.fdir, "after", {})
    return inited


def setup(inited, steps, tids=("t1", "t2", "t3")):
    write_pipeline(inited.fdir, {"id": "e", "steps": steps})
    for tid in tids:
        task_from_pipeline(inited, "e", tid=tid, worktree=str(inited.repo), terminal_handle={"agent": tid})
    return inited


@pytest.fixture
def flow(base):
    return setup(base, ["emu", "after"])


def run(flow, tid, *a, check=True):
    return flow.factory(*a, "--task", tid, check=check)


def ctx_of(flow):
    from factory import repo
    return repo.load_ctx(cwd=flow.repo)


def resource(flow, name="emu"):
    from factory import exclusive
    return exclusive.read(ctx_of(flow), name)


def holder(flow):
    return resource(flow)["holder"]


def queue(flow):
    return [q["task"] for q in resource(flow)["queue"]]


def prompts_to(flow, tid):
    return [c["text"] for c in fake_calls(flow.fdir) if c["op"] == "send_prompt" and c["handle"].get("agent") == tid]


def of_type(flow, tid, kind):
    return [e for e in events(flow.fdir, tid) if e["type"] == kind]


def detach(flow, tid):
    from factory import state
    state.update(ctx_of(flow), tid, lambda t: t.__setitem__("worktree", None))


def test_second_task_waits_then_starts_after_done(flow):
    run(flow, "t1", "next")
    out = run(flow, "t2", "next").stdout
    assert "The step `emu` needs `emu`, now used by task `t1`." in out and "End your turn." in out
    assert WAIT_T2 in out and "Do the step." not in out
    t2 = task_json(flow.fdir, "t2")
    assert t2["status"] == "waiting_external" and t2["status_reason"] == "Waiting for emu, used by t1"
    assert t2["started"] is None
    run(flow, "t1", "done")
    assert task_json(flow.fdir, "t2")["status"] == "active"
    assert prompts_to(flow, "t2") == [NEXT_PROMPT]
    assert "Do the step." in run(flow, "t2", "next").stdout
    assert holder(flow) == "t2"
    assert of_type(flow, "t2", "exclusive_start")[0]["name"] == "emu"


def test_holder_next_again_has_no_released_line(flow):
    run(flow, "t1", "next")
    out = run(flow, "t1", "next").stdout
    assert "Do the step." in out and RELEASED not in out


def test_three_tasks_in_wait_order(flow):
    for tid in ("t1", "t2", "t3"):
        run(flow, tid, "next")
    assert queue(flow) == ["t2", "t3"]
    run(flow, "t1", "done")
    assert holder(flow) == "t2" and prompts_to(flow, "t3") == []
    run(flow, "t2", "next")
    run(flow, "t2", "done")
    assert holder(flow) == "t3" and prompts_to(flow, "t3") == [NEXT_PROMPT]


def test_third_task_cannot_jump_queue(flow):
    run(flow, "t1", "next")
    run(flow, "t2", "next")
    run(flow, "t1", "done")
    assert holder(flow) == "t2"
    out = run(flow, "t3", "next").stdout
    assert "now used by task `t2`" in out
    assert holder(flow) == "t2" and queue(flow) == ["t3"]
    assert task_json(flow.fdir, "t3")["status"] == "waiting_external"


def test_acquire_waiter_continues_step(flow):
    run(flow, "t1", "next")
    run(flow, "t1", "exclusive", "release", "emu")
    run(flow, "t2", "next")
    assert holder(flow) == "t2"
    run(flow, "t2", "exclusive", "release", "emu")
    assert "`emu` is yours. Continue the step." in run(flow, "t1", "exclusive", "acquire", "emu").stdout
    out = run(flow, "t2", "exclusive", "acquire", "emu").stdout
    assert out.strip() == "`emu` is used by task `t1`. The factory sends you a message when it is free. End your turn."
    t2 = task_json(flow.fdir, "t2")
    assert t2["status"] == "waiting_external" and t2["exclusive_wait"] == {"name": "emu", "mode": "acquire"}
    run(flow, "t1", "done")
    assert holder(flow) == "t2"
    assert prompts_to(flow, "t2") == [ACQUIRE_PROMPT]
    t2 = task_json(flow.fdir, "t2")
    assert t2["status"] == "active" and "exclusive_released" not in t2 and "exclusive_wait" not in t2
    assert t2["started"] == t2["position"]


def test_acquire_by_holder(flow):
    run(flow, "t1", "next")
    assert run(flow, "t1", "exclusive", "acquire", "emu").stdout.strip() == "You hold `emu`."


def test_acquire_refused_on_other_name_or_not_started(flow):
    r = run(flow, "t1", "exclusive", "acquire", "emu", check=False)
    assert r.returncode == 1 and "Run `factory next` first." in r.stderr
    run(flow, "t1", "next")
    r = run(flow, "t1", "exclusive", "acquire", "other", check=False)
    assert r.returncode == 1 and "The current step does not use `other`." in r.stderr


def test_release_refused_when_not_holder(flow):
    run(flow, "t1", "next")
    run(flow, "t2", "next")
    r = run(flow, "t2", "exclusive", "release", "emu", check=False)
    assert r.returncode == 1
    assert holder(flow) == "t1" and queue(flow) == ["t2"]
    assert "exclusive_released" not in task_json(flow.fdir, "t2")


def test_paused_waiter_then_resume(flow):
    for tid in ("t1", "t2", "t3"):
        run(flow, tid, "next")
    flow.factory("pause", "t2")
    run(flow, "t1", "done")
    assert holder(flow) == "t3" and queue(flow) == ["t2"]
    flow.factory("resume", "t2")
    assert task_json(flow.fdir, "t2")["status"] == "waiting_external"
    assert holder(flow) == "t3"
    run(flow, "t3", "next")
    run(flow, "t3", "done")
    assert holder(flow) == "t2"
    assert task_json(flow.fdir, "t2")["status"] == "active"
    assert prompts_to(flow, "t2") == [NEXT_PROMPT]


def test_resume_gets_free_resource_at_once(flow):
    run(flow, "t1", "next")
    run(flow, "t2", "next")
    flow.factory("pause", "t2")
    run(flow, "t1", "done")
    assert holder(flow) is None and queue(flow) == ["t2"]
    flow.factory("resume", "t2")
    assert holder(flow) == "t2"
    assert task_json(flow.fdir, "t2")["status"] == "active"
    assert prompts_to(flow, "t2") == [NEXT_PROMPT]


def test_deleted_waiter_leaves_queue(flow):
    for tid in ("t1", "t2", "t3"):
        run(flow, tid, "next")
    detach(flow, "t2")
    flow.factory("delete", "t2")
    assert queue(flow) == ["t3"]
    run(flow, "t1", "done")
    assert holder(flow) == "t3"


def test_delete_holder_hands_over(flow):
    run(flow, "t1", "next")
    run(flow, "t2", "next")
    detach(flow, "t1")
    flow.factory("delete", "t1")
    assert holder(flow) == "t2"
    assert task_json(flow.fdir, "t2")["status"] == "active"
    assert prompts_to(flow, "t2") == [NEXT_PROMPT]


@pytest.mark.parametrize("move", ["skip", "goto", "loop"])
def test_moves_release(base, move):
    steps = {"skip": ["emu", "after"], "goto": ["before", "emu"],
             "loop": ["before", {"id": "emu-loop", "loop": {"back_to": "before", "while": "k", "max": 3}}]}[move]
    flow = setup(base, steps, ("t1", "t2"))
    for tid in ("t1", "t2"):
        if move != "skip":
            run(flow, tid, "next")
            run(flow, tid, "done")
        run(flow, tid, "next")
    assert holder(flow) == "t1" and queue(flow) == ["t2"]
    if move == "skip":
        run(flow, "t1", "skip")
    elif move == "goto":
        run(flow, "t1", "goto", "before", "--reason", "again")
    else:
        run(flow, "t1", "state", "set", "k", "1")
        assert "Loop 1 of 3" in run(flow, "t1", "done").stdout
    assert holder(flow) == "t2" and queue(flow) == []
    assert prompts_to(flow, "t2") == [NEXT_PROMPT]
    t1 = task_json(flow.fdir, "t1")
    assert t1["status"] == "active" and "exclusive_wait" not in t1


def test_skip_of_waiting_task_leaves_queue(flow):
    for tid in ("t1", "t2", "t3"):
        run(flow, tid, "next")
    run(flow, "t2", "skip")
    t2 = task_json(flow.fdir, "t2")
    assert t2["status"] == "active" and "exclusive_wait" not in t2
    assert queue(flow) == ["t3"] and holder(flow) == "t1"


def test_next_step_with_same_name_keeps_resource(base):
    flow = setup(base, ["emu", "emu2", "after"], ("t1", "t2"))
    run(flow, "t1", "next")
    run(flow, "t2", "next")
    run(flow, "t1", "done")
    assert holder(flow) == "t1" and queue(flow) == ["t2"]
    assert "Do the step." in run(flow, "t1", "next").stdout
    run(flow, "t1", "done")
    assert holder(flow) == "t2"


def test_paused_holder_keeps(flow):
    run(flow, "t1", "next")
    run(flow, "t2", "next")
    flow.factory("pause", "t1")
    flow.factory("poll")
    assert holder(flow) == "t1" and queue(flow) == ["t2"]
    assert task_json(flow.fdir, "t2")["status"] == "waiting_external"


def test_finish_releases(base):
    flow = setup(base, ["emu"], ("t1", "t2"))
    run(flow, "t1", "next")
    run(flow, "t2", "next")
    run(flow, "t1", "done")
    assert task_json(flow.fdir, "t1")["status"] == "finished"
    assert holder(flow) == "t2"


def test_release_mid_step_then_acquire_waits(flow):
    run(flow, "t1", "next")
    run(flow, "t2", "next")
    position = task_json(flow.fdir, "t1")["position"]
    assert run(flow, "t1", "exclusive", "release", "emu").stdout.strip() == "Released `emu`."
    assert holder(flow) == "t2"
    t1 = task_json(flow.fdir, "t1")
    assert t1["position"] == position and t1["started"] == position and t1["exclusive_released"] == "emu"
    assert of_type(flow, "t1", "exclusive_release")[0]["name"] == "emu"
    out = run(flow, "t1", "next").stdout
    assert "Do the step." in out and RELEASED in out
    assert holder(flow) == "t2"
    out = run(flow, "t1", "exclusive", "acquire", "emu").stdout
    assert "`emu` is used by task `t2`." in out
    run(flow, "t2", "next")
    run(flow, "t2", "done")
    assert holder(flow) == "t1"
    assert prompts_to(flow, "t1") == [ACQUIRE_PROMPT]
    t1 = task_json(flow.fdir, "t1")
    assert "exclusive_released" not in t1 and t1["status"] == "active"
    assert RELEASED not in run(flow, "t1", "next").stdout


def test_force_release_blocked_holder(flow):
    run(flow, "t1", "next")
    run(flow, "t1", "block", "stuck")
    run(flow, "t2", "next")
    r = run(flow, "t2", "exclusive", "release", "emu", "--force")
    assert "t1" in r.stdout
    for tid in ("t1", "t2"):
        forced = of_type(flow, tid, "exclusive_forced")
        assert forced and forced[0]["name"] == "emu" and forced[0]["holder"] == "t1" and forced[0]["by"] == "t2"
    assert task_json(flow.fdir, "t1")["exclusive_released"] == "emu"
    assert task_json(flow.fdir, "t2")["status"] == "active"
    assert prompts_to(flow, "t2") == [NEXT_PROMPT]
    assert holder(flow) == "t2"


def test_force_release_without_task(flow):
    run(flow, "t1", "next")
    for tid in ("t1", "t2", "t3"):
        detach(flow, tid)
    flow.factory("exclusive", "release", "emu", "--force")
    forced = of_type(flow, "t1", "exclusive_forced")
    assert forced and forced[0]["by"] is None
    assert holder(flow) is None


def test_external_done_refused_while_waiting(flow):
    run(flow, "t1", "next")
    run(flow, "t2", "next")
    r = flow.factory("external-done", "t2", check=False)
    assert r.returncode == 1
    assert ("Task t2 waits for `emu`, not for an external event. Release it with "
            "`factory exclusive release emu --force` if the holder is stuck.") in r.stderr
    assert task_json(flow.fdir, "t2")["status"] == "waiting_external"


def test_done_and_run_command_refused_while_waiting(flow):
    run(flow, "t1", "next")
    run(flow, "t2", "next")
    position = task_json(flow.fdir, "t2")["position"]
    text = "The step waits for `emu`. End your turn. The factory sends you a message when it is free."
    for command in ("done", "run-command"):
        r = run(flow, "t2", command, check=False)
        assert r.returncode == 1 and text in r.stderr
    t2 = task_json(flow.fdir, "t2")
    assert t2["position"] == position and t2["status"] == "waiting_external"


def test_poll_ignores_exclusive_wait(base):
    flow = setup(base, ["emu-check", "after"], ("t1", "t2"))
    run(flow, "t1", "next")
    run(flow, "t2", "next")
    position = task_json(flow.fdir, "t2")["position"]
    assert flow.factory.json("poll") == []
    t2 = task_json(flow.fdir, "t2")
    assert t2["status"] == "waiting_external" and t2["position"] == position
    assert queue(flow) == ["t2"]


def test_poll_recovers_missed_handover(flow):
    from factory import exclusive, state
    ctx = ctx_of(flow)
    exclusive.resource_dir(ctx).mkdir(parents=True, exist_ok=True)
    data = {"holder": None, "since": None, "queue": [{"task": "t2", "since": state.now(), "mode": "next"}]}
    (exclusive.resource_dir(ctx) / "emu.json").write_text(json.dumps(data))

    def wait(t):
        state.set_status(t, "waiting_external", "Waiting for emu, used by t1")
        t["exclusive_wait"] = {"name": "emu", "mode": "next"}

    state.update(ctx, "t2", wait)
    flow.factory("poll")
    assert holder(flow) == "t2"
    assert task_json(flow.fdir, "t2")["status"] == "active"
    assert prompts_to(flow, "t2") == [NEXT_PROMPT]


def test_status_shows_holder(flow):
    run(flow, "t1", "next")
    run(flow, "t2", "next")
    assert "Exclusive: waiting for `emu`, used by `t1`" in run(flow, "t2", "status").stdout
    assert "Exclusive: `emu`, held by this task" in run(flow, "t1", "status").stdout
    assert "Exclusive" not in run(flow, "t3", "status").stdout


def test_exclusive_status_command(flow):
    run(flow, "t1", "next")
    run(flow, "t2", "next")
    rows = flow.factory.json("exclusive", "status")
    assert rows[0]["name"] == "emu" and rows[0]["holder"] == "t1"
    assert [q["task"] for q in rows[0]["queue"]] == ["t2"]
    out = flow.factory("exclusive", "status").stdout
    assert "emu" in out and "t1" in out and "t2" in out


def test_step_without_exclusive_unchanged(base):
    flow = setup(base, ["after"], ("t1",))
    out = run(flow, "t1", "next").stdout
    assert "exclusive" not in out
    run(flow, "t1", "done")
    from factory import exclusive
    assert not list(exclusive.resource_dir(ctx_of(flow)).glob("*.json"))
    assert task_json(flow.fdir, "t1")["status"] == "finished"


def test_two_processes_claim_once(flow):
    procs = [subprocess.Popen([sys.executable, str(BIN), "next", "--task", tid], cwd=flow.repo, env=flow.factory.env,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for tid in ("t1", "t2")]
    for p in procs:
        p.communicate(timeout=180)
        assert p.returncode == 0
    tasks = {tid: task_json(flow.fdir, tid) for tid in ("t1", "t2")}
    started = [tid for tid, t in tasks.items() if t["started"] == t["position"]]
    assert len(started) == 1
    assert holder(flow) == started[0]
    other = "t2" if started[0] == "t1" else "t1"
    assert tasks[other]["status"] == "waiting_external" and tasks[other]["started"] is None
    assert queue(flow) == [other]
