import pytest

from conftest import SF
from serverutil import info, request
from test_exclusive_flow import base, flow, run, resource, holder

PAGE = (SF / "lib" / "factory" / "web" / "dashboard.html").read_text()
AUTHORING = (SF / "skills" / "factory-authoring" / "SKILL.md").read_text()
ORCHESTRATOR = (SF / "skills" / "software-factory" / "SKILL.md").read_text()


@pytest.fixture
def flow_server(flow):
    flow.factory("dashboard")
    yield flow, info(flow.fdir)
    flow.factory("server", "stop", check=False)


def test_row_for_waiting_task(flow):
    run(flow, "t1", "next")
    run(flow, "t2", "next")
    rows = {r["id"]: r for r in flow.factory.json("tasks")}
    assert rows["t2"]["exclusive"] == {"name": "emu", "holder": "t1", "holds": False, "waiting": True, "released": False, "paused": False}
    assert rows["t2"]["wait_has_check"] is None
    assert rows["t1"]["exclusive"]["holds"] is True
    assert rows["t3"]["exclusive"] is None or rows["t3"]["exclusive"]["holds"] is False


def test_waiting_task_with_done_check_has_no_check(base):
    from test_exclusive_flow import setup
    setup(base, ["emu-check", "after"], tids=("t1", "t2"))
    run(base, "t1", "next")
    run(base, "t2", "next")
    rows = {r["id"]: r for r in base.factory.json("tasks")}
    assert rows["t2"]["wait_has_check"] is None and rows["t2"]["next_check_at"] is None


def test_row_without_exclusive_step_is_null(inited):
    from conftest import make_task
    from factory import repo
    make_task(repo.load_ctx(cwd=inited.repo), tid="t1", worktree=str(inited.repo))
    assert inited.factory.json("tasks")[0]["exclusive"] is None


def test_api_release_route(flow_server):
    flow, i = flow_server
    run(flow, "t1", "next")
    run(flow, "t2", "next")
    status, body = request(i, "POST", "/api/exclusive/emu/release", {"task": "t2"})
    assert status == 200 and body == {"holder": "t1"}
    assert holder(flow) == "t2"
    status, rows = request(i, "GET", "/api/tasks")
    assert {r["id"]: r for r in rows}["t2"]["exclusive"]["holds"] is True


def test_api_release_free_resource_is_an_error(flow_server):
    flow, i = flow_server
    assert request(i, "POST", "/api/exclusive/emu/release", {})[0] >= 400


def test_status_command_lists_queue(flow):
    run(flow, "t1", "next")
    run(flow, "t2", "next")
    rows = flow.factory.json("exclusive", "status", "--json")
    assert rows[0]["name"] == "emu" and rows[0]["holder"] == "t1"
    assert [q["task"] for q in rows[0]["queue"]] == ["t2"]


def test_menu_has_release_action(inited):
    out = inited.factory("menu").stdout
    assert "Release a shared resource" in out
    assert out.index("Clean finished tasks") < out.index("Release a shared resource") < out.index("Create or edit a pipeline")


def test_dashboard_page_has_release():
    assert "Release" in PAGE and "Keeps " in PAGE and "/api/exclusive/" in PAGE and "t.exclusive" in PAGE
    assert "Its session loses the resource." in PAGE
    assert "window.confirm" not in PAGE and "confirm(" not in PAGE


def test_skill_documents_exclusive():
    assert "exclusive:" in AUTHORING and "factory exclusive acquire" in AUTHORING
    assert "exclusive-release" in ORCHESTRATOR and "factory exclusive release <name> --force" in ORCHESTRATOR
