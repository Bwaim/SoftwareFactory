import pytest

from conftest import events, fake_calls, task_from_pipeline, task_json, write_pipeline, write_step
from factory import engine, repo
from factory.errors import FactoryError


@pytest.fixture
def waits(inited):
    flag = inited.work / "approved.flag"
    write_step(inited.fdir, "wait-review", {"wait_external": True, "done_when": "The MR is approved.", "done_check": f"test -f {flag}"})
    write_step(inited.fdir, "wait-qa", {"wait_external": True, "done_when": "QA is done."})
    write_step(inited.fdir, "after", {})
    write_pipeline(inited.fdir, {"id": "w", "steps": ["wait-review", "wait-qa", "after"]})
    task_from_pipeline(inited, "w", terminal_handle={"agent": "t1"})
    return inited, flag


def run(inited, *a, check=True):
    return inited.factory(*a, "--task", "t1", check=check)


def test_wait_then_poll_ends_on_check(waits):
    inited, flag = waits
    run(inited, "next")
    run(inited, "wait")
    t = task_json(inited.fdir, "t1")
    assert t["status"] == "waiting_external" and t["status_reason"] == "The MR is approved."
    assert inited.factory.json("poll")[0]["ended"] is False
    flag.write_text("ok")
    assert inited.factory.json("poll")[0]["ended"] is True
    t = task_json(inited.fdir, "t1")
    assert t["status"] == "active" and t["position"] == 2
    texts = [c.get("text", "") for c in fake_calls(inited.fdir)]
    assert any(x.startswith("The external event happened: The MR is approved.") for x in texts)
    assert any(c["op"] == "notify" for c in fake_calls(inited.fdir))
    assert [e for e in events(inited.fdir, "t1") if e["type"] == "external_event"][0]["how"] == "check"


def test_paused_task_not_polled(waits):
    inited, flag = waits
    run(inited, "next"); run(inited, "wait")
    inited.factory("pause", "t1")
    flag.write_text("ok")
    assert inited.factory.json("poll") == []
    inited.factory("resume", "t1")
    assert task_json(inited.fdir, "t1")["status"] == "waiting_external"


def test_external_done_manual(waits):
    inited, flag = waits
    flag.write_text("ok")
    run(inited, "next"); run(inited, "done"); run(inited, "next"); run(inited, "wait")
    r = inited.factory("external-done", "t1")
    t = task_json(inited.fdir, "t1")
    assert t["status"] == "active" and t["position"] == 3
    assert [e for e in events(inited.fdir, "t1") if e["type"] == "external_event"][-1]["how"] == "manual"


def test_external_done_refused_with_check(waits):
    inited, flag = waits
    run(inited, "next"); run(inited, "wait")
    r = inited.factory("external-done", "t1", check=False)
    assert r.returncode == 1 and "done check" in r.stderr


def test_wait_refused_on_normal_step(inited):
    write_step(inited.fdir, "plain", {})
    write_pipeline(inited.fdir, {"id": "p", "steps": ["plain"]})
    task_from_pipeline(inited, "p")
    run(inited, "next")
    assert run(inited, "wait", check=False).returncode == 1


def test_end_wait_refused_when_not_waiting(inited):
    write_step(inited.fdir, "plain", {})
    write_pipeline(inited.fdir, {"id": "p", "steps": ["plain"]})
    task_from_pipeline(inited, "p")
    ctx = repo.load_ctx(cwd=inited.repo)
    with pytest.raises(FactoryError, match="not waiting"):
        engine.end_wait(ctx, "t1", "manual")


def test_end_wait_adds_period_to_done_when(inited):
    write_step(inited.fdir, "qa", {"wait_external": True, "done_when": "QA is done"})
    write_pipeline(inited.fdir, {"id": "q", "steps": ["qa"]})
    task_from_pipeline(inited, "q", terminal_handle={"agent": "t1"})
    run = lambda *a: inited.factory(*a, "--task", "t1")
    run("next"); run("wait"); run("external-done", "t1")
    texts = [c.get("text", "") for c in fake_calls(inited.fdir)]
    assert texts[-1] == "The external event happened: QA is done. Run `factory next --task t1`."
