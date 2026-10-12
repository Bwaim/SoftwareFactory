import json

from conftest import fake_config, write_pipeline, write_step
from factory import delete, engine, launch, repo, session

EXPECTED = {
    "task_created", "step_started", "step_done", "step_skipped", "done_check_failed", "config_asked",
    "task_deleted", "task_blocked", "task_unblocked", "task_paused", "task_resumed", "step_goto",
    "task_finished", "prompt_sent", "column_changed", "approval_requested", "approved",
    "changes_requested", "waiting_started", "external_event",
}


def test_all_event_types(inited):
    flag = inited.work / "ok.flag"
    write_step(inited.fdir, "cfg", {"config": {"k": {"description": "K"}}, "column": "Plan"})
    write_step(inited.fdir, "chk", {"done_check": f"test -f {flag}"})
    write_step(inited.fdir, "opt", {})
    write_step(inited.fdir, "ext", {"wait_external": True, "done_when": "Done outside."})
    write_pipeline(inited.fdir, {"id": "all", "steps": ["cfg", "chk", "opt", "user-validation", "ext"]})
    ctx = repo.load_ctx(cwd=inited.repo)
    tid = launch.launch(ctx, "all", "All events", {})["id"]
    engine.next_step(ctx, tid)
    inited.factory("config", "set", "cfg", "k", "v")
    engine.next_step(ctx, tid); engine.done(ctx, tid)
    engine.next_step(ctx, tid)
    try:
        engine.done(ctx, tid)
    except Exception:
        pass
    flag.write_text("x")
    engine.done(ctx, tid)
    engine.next_step(ctx, tid); engine.skip(ctx, tid)
    engine.next_step(ctx, tid)
    engine.request_changes(ctx, tid, "More")
    engine.next_step(ctx, tid)
    engine.approve(ctx, tid); engine.done(ctx, tid)
    engine.block(ctx, tid, "why"); engine.unblock(ctx, tid)
    engine.goto(ctx, tid, "opt", "redo"); engine.skip(ctx, tid)
    engine.next_step(ctx, tid); engine.approve(ctx, tid); engine.done(ctx, tid)
    session.send_prompt(ctx, tid, "hello")
    session.pause(ctx, tid); session.resume(ctx, tid)
    engine.next_step(ctx, tid); engine.wait(ctx, tid); engine.external_done(ctx, tid)
    delete.delete(ctx, tid, confirm_unpushed=True)
    log = inited.fdir / "tasks" / "archive" / tid / "events.jsonl"
    kinds = {json.loads(l)["type"] for l in log.read_text().splitlines()}
    assert EXPECTED <= kinds, EXPECTED - kinds
