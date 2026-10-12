import json

from conftest import fake_calls


def test_start_session_close_state_notify_wait_idle(inited):
    f = inited.factory
    started = f("terminal", "start-session", "t9", str(inited.repo), "hello there", "--worktree", "--", "--name", "t9", "--model", "opus")
    handle = json.loads(started.stdout)
    assert handle == {"agent": "t9", "fake": True}
    call = [c for c in fake_calls(inited.fdir) if c["op"] == "start_session"][-1]
    assert call["name"] == "t9" and call["prompt"] == "hello there" and call["in_worktree"] is True
    assert call["args"] == ["--name", "t9", "--model", "opus"] and call["cwd"] == str(inited.repo)
    assert f("terminal", "state", json.dumps(handle)).stdout.strip() == "idle"
    f("terminal", "wait-idle", json.dumps(handle), "--timeout", "5")
    f("terminal", "notify", "Look here")
    f("terminal", "close", json.dumps(handle))
    ops = [c["op"] for c in fake_calls(inited.fdir)]
    assert ops[-3:] == ["wait_idle", "notify", "close"]
    assert [c for c in fake_calls(inited.fdir) if c["op"] == "close"][-1]["handle"] == handle


def test_start_session_without_worktree_flag_or_args(inited):
    inited.factory("terminal", "start-session", "t9", str(inited.repo), "p")
    call = [c for c in fake_calls(inited.fdir) if c["op"] == "start_session"][-1]
    assert call["in_worktree"] is False and call["args"] == []


def test_bad_handle_json_is_an_error(inited):
    r = inited.factory("terminal", "close", "{not json", check=False)
    assert r.returncode == 1 and r.stderr.startswith("Error:") and "Traceback" not in r.stderr
