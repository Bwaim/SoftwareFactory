import json
import re
import subprocess
import sys
import time

import pytest

from conftest import BIN, task_from_pipeline, task_json, write_pipeline, write_step
from serverutil import alive, info, wait_dead

FAST = {"FACTORY_SERVER_IDLE_SECONDS": "2"}


@pytest.fixture
def waits(inited):
    flag = inited.work / "approved.flag"
    write_step(inited.fdir, "wait-review", {"wait_external": True, "done_when": "Approved.", "done_check": f"test -f {flag}"})
    write_step(inited.fdir, "wait-qa", {"wait_external": True, "done_when": "QA is done."})
    write_step(inited.fdir, "after", {})
    write_pipeline(inited.fdir, {"id": "w", "steps": ["wait-review", "after"]})
    write_pipeline(inited.fdir, {"id": "q", "steps": ["wait-qa", "after"]})
    return inited, flag


def server_pid(inited):
    path = inited.home / "server.json"
    return info()["pid"] if path.exists() else None


def failing_start(inited, monkeypatch):
    from factory import server
    from factory.errors import FactoryError
    for key, value in inited.factory.env.items():
        monkeypatch.setenv(key, value)
    monkeypatch.chdir(inited.repo)

    def fail():
        raise FactoryError(f"The local server did not start. See {server.log_path()}.")

    monkeypatch.setattr(server, "ensure_server", fail)
    return server


def test_server_stays_while_a_check_waits(waits):
    inited, flag = waits
    task_from_pipeline(inited, "w", worktree=str(inited.repo), terminal_handle={"agent": "t1"})
    inited.factory("next", "--task", "t1")
    inited.factory("wait", "--task", "t1", env=FAST)
    pid = server_pid(inited)
    time.sleep(6)
    assert alive(pid)
    flag.write_text("ok")
    inited.factory("poll")
    assert wait_dead(pid, 15)


def test_a_second_server_stops_the_first(waits):
    inited, _ = waits
    task_from_pipeline(inited, "w", worktree=str(inited.repo), status="waiting_external")
    inited.factory("tasks", env=FAST)
    first = server_pid(inited)
    env = {**inited.factory.env, **FAST}
    subprocess.Popen([sys.executable, str(BIN), "serve"], cwd=inited.repo, env=env,
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     start_new_session=True)
    end = time.time() + 15
    while time.time() < end and server_pid(inited) in (None, first):
        time.sleep(0.2)
    second = server_pid(inited)
    assert second not in (None, first)
    assert wait_dead(first, 15)
    assert alive(second)


def test_wait_starts_the_server_only_with_a_check(waits):
    inited, _ = waits
    task_from_pipeline(inited, "q", tid="t2", worktree=str(inited.repo), terminal_handle={"agent": "t2"})
    inited.factory("next", "--task", "t2")
    inited.factory("wait", "--task", "t2")
    assert server_pid(inited) is None
    task_from_pipeline(inited, "w", tid="t1", worktree=str(inited.repo), terminal_handle={"agent": "t1"})
    inited.factory("next", "--task", "t1")
    inited.factory("wait", "--task", "t1")
    assert alive(server_pid(inited))


def test_resume_starts_the_server(waits):
    inited, _ = waits
    task_from_pipeline(inited, "w", worktree=str(inited.repo), status="waiting_external")
    inited.factory("pause", "t1")
    inited.factory("server", "stop")
    inited.factory("resume", "t1")
    assert task_json(inited.fdir, "t1")["status"] == "waiting_external"
    assert alive(server_pid(inited))


def test_tasks_starts_the_server_only_with_a_check(waits):
    inited, _ = waits
    task_from_pipeline(inited, "q", tid="t2", worktree=str(inited.repo), status="waiting_external")
    inited.factory("tasks")
    assert server_pid(inited) is None
    task_from_pipeline(inited, "w", tid="t1", worktree=str(inited.repo), status="waiting_external")
    inited.factory("tasks", "--json")
    assert alive(server_pid(inited))


def test_stop_unless_waiting(waits):
    inited, _ = waits
    task_from_pipeline(inited, "w", worktree=str(inited.repo), status="waiting_external")
    inited.factory("tasks")
    pid = server_pid(inited)
    out = inited.factory("server", "stop", "--unless-waiting").stdout
    assert out.strip() == "The server keeps running for the done checks of tasks t1."
    assert alive(pid)
    inited.factory("pause", "t1")
    assert inited.factory("server", "stop", "--unless-waiting").stdout.strip() == "Server stopped."
    assert wait_dead(pid)


def test_wait_warns_when_the_server_does_not_start(waits, monkeypatch, capsys):
    from factory import cli
    inited, _ = waits
    task_from_pipeline(inited, "w", worktree=str(inited.repo), terminal_handle={"agent": "t1"})
    inited.factory("next", "--task", "t1")
    server = failing_start(inited, monkeypatch)
    assert cli.main(["wait", "--task", "t1"]) == 0
    assert capsys.readouterr().err.strip() == server.start_warning()
    assert task_json(inited.fdir, "t1")["status"] == "waiting_external"


def test_tasks_json_stays_valid_when_the_server_does_not_start(waits, monkeypatch, capsys):
    from factory import cli
    inited, _ = waits
    task_from_pipeline(inited, "w", worktree=str(inited.repo), status="waiting_external")
    server = failing_start(inited, monkeypatch)
    assert cli.main(["tasks", "--json"]) == 0
    out = capsys.readouterr()
    assert [row["id"] for row in json.loads(out.out)] == ["t1"]
    assert out.err.strip() == server.start_warning()


def one_line_error(result, path):
    assert result.returncode == 1
    assert "Traceback" not in result.stdout + result.stderr
    assert result.stderr.startswith(f"Error: {path}: ")
    return result.stderr.strip()


def test_invalid_factory_yaml(inited):
    path = (inited.fdir / "factory.yaml").resolve()
    path.write_text("version: 2\ncolumns: [a, b\n")
    text = one_line_error(inited.factory("tasks", check=False), path)
    assert re.search(r", line \d+\.$", text)


def test_invalid_config_yaml(inited):
    path = (inited.fdir / "config.yaml").resolve()
    path.write_text("create-worktree: {worktree_root: [x\n")
    text = one_line_error(inited.factory("config", "set", "create-worktree", "worktree_root", "y", check=False), path)
    assert re.search(r", line \d+\.$", text)


@pytest.mark.parametrize("content", ["- a\n- b\n", "[]\n"])
def test_factory_yaml_must_be_a_map(inited, content):
    path = (inited.fdir / "factory.yaml").resolve()
    path.write_text(content)
    text = one_line_error(inited.factory("tasks", check=False), path)
    assert text == f"Error: {path}: the file must be a map of keys."


@pytest.mark.parametrize("content", [b"version: 2\nbad: \x01\n", b"version: 2\nname: \xff\n"])
def test_unreadable_factory_yaml_is_one_line(inited, content):
    path = (inited.fdir / "factory.yaml").resolve()
    path.write_bytes(content)
    text = one_line_error(inited.factory("tasks", check=False), path)
    assert "\n" not in text
