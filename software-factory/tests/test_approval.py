import pytest

from conftest import events, fake_calls, task_from_pipeline, task_json, write_pipeline, write_step
from factory import engine, repo
from factory.errors import FactoryError


@pytest.fixture
def uv(inited):
    write_step(inited.fdir, "spec", {"writes": ["spec"]})
    write_pipeline(inited.fdir, {"id": "uvp", "steps": ["spec", {"id": "user-validation", "with": {"target": "artifact", "artifact_key": "spec"}}]})
    task_from_pipeline(inited, "uvp", terminal_handle={"agent": "t1"}, state={"spec": "/tmp/spec.md"})
    run = lambda *a, check=True: inited.factory(*a, "--task", "t1", check=check)
    run("next"); run("done"); run("next")
    return inited, run


def test_awaiting_approval_then_approve(uv):
    inited, run = uv
    t = task_json(inited.fdir, "t1")
    assert t["status"] == "awaiting_approval"
    assert t["approval"]["target"] == "artifact" and t["approval"]["artifact_key"] == "spec"
    rows = {r["id"]: r for r in inited.factory.json("tasks")}
    assert rows["t1"]["approval"]["artifact"] == "/tmp/spec.md"
    assert run("done", check=False).returncode == 1
    run("approve", "--send")
    assert fake_calls(inited.fdir)[-1]["text"].startswith("The user approved. Run `factory done --task t1`")
    run("done")
    assert task_json(inited.fdir, "t1")["status"] == "finished"
    kinds = [e["type"] for e in events(inited.fdir, "t1")]
    assert "approval_requested" in kinds and "approved" in kinds


def test_request_changes(uv):
    inited, run = uv
    run("request-changes", "Add a test plan", "--send")
    t = task_json(inited.fdir, "t1")
    assert t["status"] == "active"
    assert "Add a test plan" in fake_calls(inited.fdir)[-1]["text"]
    run("next")
    assert task_json(inited.fdir, "t1")["status"] == "awaiting_approval"
    assert [e["type"] for e in events(inited.fdir, "t1")].count("approval_requested") == 2


def test_approve_refused_when_not_waiting(inited):
    from conftest import make_task
    ctx = repo.load_ctx(cwd=inited.repo)
    make_task(ctx)
    with pytest.raises(FactoryError, match="approval"):
        engine.approve(ctx, "t1")


def test_open_ide_needs_command(uv, monkeypatch):
    inited, run = uv
    r = run("open-ide", check=False)
    assert r.returncode == 1 and "ide_command" in r.stderr
    inited.factory("config", "set", "user-validation", "ide_command", "code {path}")
    ctx = repo.load_ctx(cwd=inited.repo)
    started = []
    monkeypatch.setattr(engine.subprocess, "Popen", lambda argv, **kwargs: started.append(argv))
    argv = engine.open_ide(ctx, "t1")
    assert argv == ["code", str(inited.repo)]


def test_open_ide_bad_command_is_factory_error(uv):
    inited, run = uv
    for command in ("code 'unclosed {path}", "no-such-ide-command-xyz {path}", "   "):
        inited.factory("config", "set", "user-validation", "ide_command", command)
        r = run("open-ide", check=False)
        assert r.returncode == 1 and "Traceback" not in r.stderr and r.stderr.startswith("Error:")
