import subprocess
import sys
import threading
import time

import pytest

from conftest import BIN, events, task_from_pipeline, task_json, write_pipeline, write_step
from factory import engine, repo
from serverutil import info, request


@pytest.fixture
def waits(inited, monkeypatch):
    for key, value in inited.factory.env.items():
        monkeypatch.setenv(key, value)
    flag = inited.work / "ok.flag"
    write_step(inited.fdir, "wait-review", {"wait_external": True, "done_when": "Approved.",
                                            "done_check": f"echo 'CodeRabbit review pending'; sleep ${{CHECK_SLEEP:-0}}; test -f {flag}"})
    write_step(inited.fdir, "after", {})
    write_pipeline(inited.fdir, {"id": "w", "steps": ["wait-review", "after"]})
    return inited, flag


def waiting_task(inited, tid="t1"):
    task_from_pipeline(inited, "w", tid=tid, worktree=str(inited.repo), terminal_handle={"agent": tid},
                       status="waiting_external", started=0)
    return tid


def ended_count(fdir, tid):
    return sum(1 for e in events(fdir, tid) if e["type"] == "external_event")


def sent_count(fdir, tid):
    return sum(1 for e in events(fdir, tid) if e["type"] == "prompt_sent")


def test_poll_task_failing_check_saves_result(waits):
    inited, _ = waits
    waiting_task(inited)
    rows = inited.factory.json("poll", "--task", "t1")
    assert rows[0]["ended"] is False
    last = task_json(inited.fdir, "t1")["last_check"]
    assert last["ended"] is False and "CodeRabbit review pending" in last["output"] and last["at"]
    assert task_json(inited.fdir, "t1")["status"] == "waiting_external"


def test_poll_task_passing_check_ends_wait(waits):
    inited, flag = waits
    waiting_task(inited)
    flag.write_text("ok")
    rows = inited.factory.json("poll", "--task", "t1")
    assert rows[0]["ended"] is True
    assert task_json(inited.fdir, "t1")["last_check"]["ended"] is True
    assert task_json(inited.fdir, "t1")["status"] != "waiting_external"


def test_poll_task_not_waiting_runs_nothing(waits):
    inited, _ = waits
    task_from_pipeline(inited, "w", tid="t2", worktree=str(inited.repo))
    rows = inited.factory.json("poll", "--task", "t2")
    assert rows[0]["error"] == engine.NOT_WAITING
    assert "last_check" not in task_json(inited.fdir, "t2")


def test_two_threads_end_the_wait_once(waits, monkeypatch):
    inited, flag = waits
    waiting_task(inited)
    flag.write_text("ok")
    monkeypatch.setenv("CHECK_SLEEP", "1")
    ctx = repo.load_ctx(cwd=inited.repo)
    results = []
    threads = [threading.Thread(target=lambda: results.append(engine.check_task(ctx, "t1"))) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(r["ended"] for r in results) == [False, True]
    assert any(r["error"] in (engine.CHECK_BUSY, engine.NOT_WAITING) for r in results)
    assert ended_count(inited.fdir, "t1") == 1
    assert sent_count(inited.fdir, "t1") == 1


def test_cli_and_in_process_check_end_the_wait_once(waits, monkeypatch):
    inited, flag = waits
    waiting_task(inited)
    flag.write_text("ok")
    monkeypatch.setenv("CHECK_SLEEP", "1")
    env = {**inited.factory.env, "CHECK_SLEEP": "1"}
    cli = subprocess.Popen([sys.executable, str(BIN), "poll", "--task", "t1"], cwd=inited.repo, env=env,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    ctx = repo.load_ctx(cwd=inited.repo)
    engine.check_task(ctx, "t1")
    cli.wait(timeout=60)
    assert ended_count(inited.fdir, "t1") == 1
    assert sent_count(inited.fdir, "t1") == 1


@pytest.fixture
def served(waits):
    inited, flag = waits
    inited.factory("dashboard", env={"FACTORY_POLL_SECONDS": "600", "CHECK_SLEEP": "5"})
    yield inited, flag, info(inited.fdir)
    inited.factory("server", "stop", check=False)


def test_api_returns_next_check_time(served):
    inited, _, i = served
    waiting_task(inited)
    end = time.time() + 5
    row = None
    while time.time() < end:
        row = request(i, "GET", "/api/tasks")[1][0]
        if row["next_check_at"]:
            break
        time.sleep(0.2)
    assert row["next_check_at"]
    assert row["last_check"] is None


def test_check_now_answers_at_once_with_a_job(served):
    inited, flag, i = served
    waiting_task(inited)
    flag.write_text("ok")
    start = time.time()
    status, res = request(i, "POST", "/api/tasks/t1/check", {})
    assert status == 200 and res["job"] and time.time() - start < 1
    start = time.time()
    assert request(i, "GET", "/api/tasks")[0] == 200 and time.time() - start < 2
    end = time.time() + 30
    job = None
    while time.time() < end:
        job = request(i, "GET", f"/api/jobs/{res['job']}")[1]
        if job["status"] != "running":
            break
        time.sleep(0.3)
    assert job["status"] == "done" and job["result"]["ended"] is True
    assert ended_count(inited.fdir, "t1") == 1


def test_paused_task_has_no_countdown(served):
    inited, _, i = served
    task_from_pipeline(inited, "w", tid="t3", worktree=str(inited.repo), status="paused")
    row = request(i, "GET", "/api/tasks")[1][0]
    assert row["next_check_at"] is None
