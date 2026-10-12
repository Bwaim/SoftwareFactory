import pytest

from conftest import fake_config
from serverutil import alive, info, request, wait_dead


@pytest.fixture
def served(inited):
    inited.factory("dashboard")
    yield inited, info(inited.fdir)
    inited.factory("server", "stop", check=False)


def test_server_survives_the_command_and_is_reused(served):
    inited, i = served
    assert alive(i["pid"])
    assert request(i, "GET", "/api/ping")[0] == 200
    inited.factory("dashboard")
    assert info(inited.fdir)["pid"] == i["pid"]


def test_security_checks(served):
    inited, i = served
    assert request(i, "GET", "/api/ping", token=False)[0] == 401
    assert request(i, "GET", "/api/ping", token="wrong")[0] == 401
    assert request(i, "GET", "/api/ping", origin="http://evil.example")[0] == 403
    assert request(i, "GET", "/api/ping", host=f"localhost:{i['port']}")[0] == 403
    assert request(i, "GET", "/api/ping", origin=f"http://127.0.0.1:{i['port']}")[0] == 200
    status, page = request(i, "GET", "/dashboard", token=False)
    assert status == 200 and "<title>" in page


def test_stop(served):
    inited, i = served
    inited.factory("server", "stop")
    assert wait_dead(i["pid"])
    assert not (inited.fdir / "server.json").exists()


def test_idle_stop(inited):
    inited.factory("dashboard", env={"FACTORY_SERVER_IDLE_SECONDS": "2"})
    assert wait_dead(info(inited.fdir)["pid"], 15)


def test_adapter_check_failure_reported(inited):
    fake_config(inited.fdir, check_ok=False, check_message="Not in Herdr.")
    inited.factory("dashboard")
    try:
        status, data = request(info(inited.fdir), "GET", "/api/info")
        assert status == 200 and data["adapter"] == {"ok": False, "message": "Not in Herdr."}
    finally:
        inited.factory("server", "stop")
