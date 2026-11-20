import os
import re
import sys
import threading
import time
from types import SimpleNamespace

import pytest

from conftest import BIN
from factory import api, server
from factory.server import ping
from serverutil import request


@pytest.fixture
def live():
    srv = server.Server()
    thread = threading.Thread(target=srv.httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield SimpleNamespace(server=srv, info={"port": srv.port, "token": srv.token})
    finally:
        srv.httpd.shutdown()
        srv.httpd.server_close()


def test_post_refused_while_updating(live):
    live.server.updating = True
    status, body = request(live.info, "POST", "/api/server-settings/save", {})
    assert (status, body["error"]) == (409, "An update is running.")
    assert request(live.info, "GET", "/api/ping")[0] == 200


def test_update_routes_allowed_while_updating(live):
    live.server.updating = True
    for path in ("/api/update/run", "/api/update/close"):
        assert request(live.info, "POST", path, {})[0] != 409


def test_pause_waits_for_running_activity(live):
    srv = live.server
    entered, release = threading.Event(), threading.Event()

    def busy():
        with srv.activity():
            entered.set()
            release.wait(5)

    threading.Thread(target=busy).start()
    entered.wait(5)
    t = threading.Thread(target=srv.pause_for_update)
    t.start()
    time.sleep(0.3)
    assert t.is_alive() and srv.updating
    release.set()
    t.join(5)
    assert not t.is_alive()


def test_activity_refused_while_updating(live):
    live.server.updating = True
    with pytest.raises(server.UpdateRunning, match="An update is running."):
        with live.server.activity():
            pass


def test_route_in_activity_answers_409(live, monkeypatch):
    def busy_route(srv, query, body):
        with srv.activity():
            return {"ok": True}

    monkeypatch.setitem(api.ROUTES, "global", [("POST", re.compile("^/api/update/run$"), busy_route)])
    live.server.updating = True
    status, body = request(live.info, "POST", "/api/update/run", {})
    assert (status, body["error"]) == (409, "An update is running.")


def test_reschedule_does_nothing_while_updating(live):
    live.server.updating = True
    live.server.reschedule()
    assert not live.server.wake.is_set()


def test_resume_wakes_the_poll(live):
    live.server.updating = True
    live.server.resume_after_update()
    assert not live.server.updating and live.server.wake.is_set()


def test_spawn_server_starts_a_new_server(factory_home):
    info = server.spawn_server([sys.executable, str(BIN), "serve"])
    try:
        assert ping(info) and info["pid"] != os.getpid()
    finally:
        server.stop_server()
