import http.client
import os
import stat
import time

import pytest

from conftest import fake_config
from serverutil import alive, info, request, wait_dead


@pytest.fixture
def served(inited):
    inited.factory("dashboard")
    yield inited, info(inited.fdir)
    inited.factory("server", "stop", check=False)


def page_headers(i, path):
    conn = http.client.HTTPConnection("127.0.0.1", i["port"], timeout=30)
    conn.request("GET", path, headers={"Host": f"127.0.0.1:{i['port']}"})
    r = conn.getresponse()
    r.read()
    return r.getheaders()


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


def test_non_ascii_token_is_refused(served):
    inited, i = served
    assert request(i, "GET", "/api/ping", token="\u00e9t\u00e9")[0] == 401


def test_invalid_json_body_is_refused(served):
    inited, i = served
    assert request(i, "POST", "/api/pipelines/check", body=b"{not json") == (400, {"error": "Invalid JSON body."})
    assert request(i, "POST", "/api/pipelines/check", body=b"[1, 2]")[0] == 400


def test_server_info_file_is_private(served):
    inited, i = served
    assert stat.S_IMODE(os.stat(inited.fdir / "server.json").st_mode) == 0o600


def test_pages_send_privacy_headers(served):
    inited, i = served
    headers = dict(page_headers(i, "/dashboard"))
    assert headers["Referrer-Policy"] == "no-referrer"
    assert headers["X-Frame-Options"] == "DENY"


def test_shutdown_needs_token_and_safe_origin(served):
    inited, i = served
    assert request(i, "POST", "/api/shutdown", body={}, token=False)[0] == 401
    assert request(i, "POST", "/api/shutdown", body={}, origin="http://evil.example")[0] == 403
    assert alive(i["pid"])


def test_refused_requests_do_not_keep_server_alive(inited):
    inited.factory("dashboard", env={"FACTORY_SERVER_IDLE_SECONDS": "2"})
    i = info(inited.fdir)
    end = time.time() + 8
    while time.time() < end and alive(i["pid"]):
        try:
            request(i, "GET", "/api/ping", token="wrong")
        except OSError:
            pass
        time.sleep(0.3)
    assert not alive(i["pid"])


def test_adapter_check_exception_reported(inited):
    fake_config(inited.fdir, check_raises="Adapter exploded.")
    inited.factory("dashboard")
    try:
        status, data = request(info(inited.fdir), "GET", "/api/info")
        assert status == 200 and data["adapter"] == {"ok": False, "message": "Adapter exploded."}
        assert data["capabilities"] == []
    finally:
        inited.factory("server", "stop")
