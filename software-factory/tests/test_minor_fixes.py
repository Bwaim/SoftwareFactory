import json
from types import SimpleNamespace

import pytest

from conftest import events, fake_calls, fake_config, make_task, task_from_pipeline, task_json, write_pipeline, write_step
from factory import adapters, engine, pipeline_check, pipeline_store, repo, state
from factory.adapters.base import AdapterError
from factory.adapters.herdr import HerdrAdapter
from factory.errors import FactoryError
from factory.registry import Registry
from serverutil import info, request


@pytest.fixture
def ctx(inited):
    return repo.load_ctx(cwd=inited.repo)


def waiting_pipeline(inited, name, check="true"):
    write_step(inited.fdir, name, {"wait_external": True, "done_when": "Ready.", "done_check": check})
    write_pipeline(inited.fdir, {"id": f"p-{name}", "steps": [name]})


def test_poll_survives_a_task_with_a_missing_folder(inited, ctx):
    waiting_pipeline(inited, "wa")
    task_from_pipeline(inited, "p-wa", tid="t1", worktree=str(inited.work / "gone"), status="waiting_external")
    task_from_pipeline(inited, "p-wa", tid="t2", status="waiting_external")
    rows = {r["id"]: r for r in engine.poll(ctx)}
    assert rows["t1"]["ended"] is False and rows["t1"]["output"]
    assert rows["t2"]["ended"] is True


def test_poll_reports_a_broken_task_and_goes_on(inited, ctx):
    waiting_pipeline(inited, "wb")
    task_from_pipeline(inited, "p-wb", tid="t1", status="waiting_external")
    task_from_pipeline(inited, "p-wb", tid="t2", status="waiting_external")
    state.update(ctx, "t1", lambda t: t["steps"][t["position"]].__setitem__("id", "no-such-step"))
    rows = {r["id"]: r for r in engine.poll(ctx)}
    assert rows["t1"]["ended"] is False and "no-such-step" in rows["t1"]["error"]
    assert rows["t2"]["ended"] is True


def test_run_check_reports_missing_folder(inited, ctx):
    task = make_task(ctx, worktree=str(inited.work / "nowhere"))
    ok, message = engine.run_check(ctx, task, SimpleNamespace(path=inited.work / "step.md"), "true", 5)
    assert ok is False and message


def test_herdr_missing_binary_is_adapter_error(monkeypatch):
    monkeypatch.setenv("PATH", "/nonexistent")
    with pytest.raises(AdapterError, match="herdr"):
        adapters.herdr.run(["workspace", "list"])


def test_end_wait_on_last_step_only_notifies(inited, ctx):
    write_step(inited.fdir, "qa", {"wait_external": True, "done_when": "QA is done"})
    write_pipeline(inited.fdir, {"id": "last", "steps": ["qa"]})
    task_from_pipeline(inited, "last", terminal_handle={"agent": "t1"})
    inited.factory("next", "--task", "t1")
    inited.factory("wait", "--task", "t1")
    inited.factory("external-done", "t1")
    ops = [c["op"] for c in fake_calls(inited.fdir)]
    assert "notify" in ops and "send_prompt" not in ops and "start_session" not in ops
    assert task_json(inited.fdir, "t1")["status"] == "finished"


def test_list_tasks_skips_a_folder_that_vanished(inited, ctx, monkeypatch):
    make_task(ctx, tid="t1")
    make_task(ctx, tid="t2")
    original = state.fsio.read_json
    monkeypatch.setattr(state.fsio, "read_json", lambda p, default=None: None if "t2" in str(p) else original(p, default))
    assert [t["id"] for t in state.list_tasks(ctx)] == ["t1"]


def test_create_refuses_an_existing_task_folder(inited, ctx):
    make_task(ctx, tid="t1", description="first")
    with pytest.raises(FactoryError, match="already exists"):
        make_task(ctx, tid="t1", description="second")
    assert task_json(inited.fdir, "t1")["description"] == "first"


def test_goto_and_block_refuse_finished_tasks(inited, ctx):
    write_step(inited.fdir, "one", {})
    write_step(inited.fdir, "two", {})
    write_pipeline(inited.fdir, {"id": "fin", "steps": ["one", "two"]})
    task_from_pipeline(inited, "fin")
    engine.done(ctx, "t1"); engine.done(ctx, "t1")
    assert task_json(inited.fdir, "t1")["status"] == "finished"
    with pytest.raises(FactoryError, match="finished"):
        engine.goto(ctx, "t1", "one", "again")
    with pytest.raises(FactoryError, match="finished"):
        engine.block(ctx, "t1", "why")
    assert task_json(inited.fdir, "t1")["status"] == "finished"


def test_block_refuses_paused_tasks(inited, ctx):
    make_task(ctx, status="paused")
    with pytest.raises(FactoryError, match="paused"):
        engine.block(ctx, "t1", "why")
    assert task_json(inited.fdir, "t1")["status"] == "paused"


@pytest.mark.parametrize("bad", ["plan.md\n", "", 5, None, ["a"]])
def test_artifact_name_must_be_a_plain_string(inited, ctx, bad):
    make_task(ctx)
    with pytest.raises(FactoryError):
        state.artifact_file(ctx, "t1", bad)


@pytest.mark.parametrize("bad", ["ab\n", 5, ["x"]])
def test_pipeline_id_must_be_a_plain_string(inited, ctx, bad):
    reg = Registry.load(ctx)
    problems = pipeline_check.check(reg, {"id": bad, "steps": ["user-validation"]}, ctx.columns())
    assert any(p.level == "error" and "pipeline id" in p.message for p in problems)
    with pytest.raises(FactoryError):
        pipeline_store.copy(reg, "user-validation", bad)


def test_api_rejects_non_string_values_with_400(inited):
    inited.factory("dashboard")
    i = info(inited.fdir)
    try:
        write_step(inited.fdir, "w", {})
        write_pipeline(inited.fdir, {"id": "p", "steps": ["w"]})
        for body in (
            {"pipeline": "p", "description": "x", "inputs": {"a": 5}},
            {"pipeline": "p", "description": "x", "inputs": {"a": ["z"]}},
            {"pipeline": "p", "description": "x", "id": 5},
            {"pipeline": ["p"], "description": "x"},
        ):
            status, body_out = request(i, "POST", "/api/launch/dry-run", body)
            assert status == 400, body
        status, _ = request(i, "POST", "/api/pipelines/save", {"data": {"id": 5, "steps": ["w"]}, "level": "local"})
        assert status == 400
    finally:
        inited.factory("server", "stop", check=False)


def awaiting_task(inited):
    write_pipeline(inited.fdir, {"id": "ap", "steps": ["user-validation"]})
    task_from_pipeline(inited, "ap", terminal_handle={"agent": "t1"})
    inited.factory("next", "--task", "t1")


def test_approve_send_with_delivery_failure_keeps_approval(inited, ctx):
    awaiting_task(inited)
    fake_config(inited.fdir, capabilities=[])
    message, delivery_error = engine.approve(ctx, "t1", send=True)
    assert "Approved" in message and "send-prompt" in delivery_error
    assert task_json(inited.fdir, "t1")["approval"]["approved"] is True


def test_cli_approve_send_warns_and_exits_zero(inited):
    awaiting_task(inited)
    fake_config(inited.fdir, capabilities=[])
    r = inited.factory("approve", "--send", "--task", "t1")
    assert r.returncode == 0 and "Approved" in r.stdout and "Warning" in r.stderr
    assert task_json(inited.fdir, "t1")["approval"]["approved"] is True


def test_api_approve_returns_delivery_error(inited):
    awaiting_task(inited)
    fake_config(inited.fdir, capabilities=[])
    inited.factory("dashboard")
    i = info(inited.fdir)
    try:
        status, body = request(i, "POST", "/api/tasks/t1/approve", {})
        assert status == 200 and "send-prompt" in body["delivery_error"]
        assert task_json(inited.fdir, "t1")["approval"]["approved"] is True
    finally:
        inited.factory("server", "stop", check=False)
