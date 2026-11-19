import threading
import time

import pytest
import yaml

from conftest import *
from factory import server, server_settings
from factory.errors import FactoryError
from serverutil import info, request


def wait_until(fn, seconds=5):
    end = time.time() + seconds
    while time.time() < end:
        if fn():
            return
        time.sleep(0.05)
    raise AssertionError("condition not met")


def test_poll_order(monkeypatch):
    monkeypatch.delenv("FACTORY_POLL_SECONDS", raising=False)
    assert server_settings.poll_seconds() == 300
    server_settings.save({"poll_seconds": 60})
    assert server_settings.poll_seconds() == 60
    monkeypatch.setenv("FACTORY_POLL_SECONDS", "5")
    assert server_settings.poll_seconds() == 5
    assert server_settings.read() == {"poll_seconds": 5, "saved_poll_seconds": 60, "env_poll_seconds": 5, "default_poll_seconds": 300}


def test_invalid_env_falls_back(monkeypatch):
    server_settings.save({"poll_seconds": 45})
    monkeypatch.setenv("FACTORY_POLL_SECONDS", "abc")
    assert server_settings.poll_seconds() == 45


def test_bad_file_falls_back(monkeypatch):
    monkeypatch.delenv("FACTORY_POLL_SECONDS", raising=False)
    server_settings.path().parent.mkdir(parents=True, exist_ok=True)
    server_settings.path().write_text("poll_seconds: [")
    assert server_settings.poll_seconds() == 300


@pytest.mark.parametrize("value", [9, 86401, "60", 1.5, True])
def test_save_rejects(value):
    with pytest.raises(FactoryError, match="whole number from 10 to 86400"):
        server_settings.save({"poll_seconds": value})


def test_empty_removes_key():
    server_settings.save({"poll_seconds": 60})
    server_settings.save({"poll_seconds": None})
    assert "poll_seconds" not in (yaml.safe_load(server_settings.path().read_text()) or {})


def test_reschedule_wakes_loop_without_poll(monkeypatch):
    monkeypatch.delenv("FACTORY_POLL_SECONDS", raising=False)
    s = server.Server()
    polls = []
    monkeypatch.setattr(s, "poll_all", lambda: polls.append(1))
    threading.Thread(target=s.poll_loop, daemon=True).start()
    wait_until(lambda: s.next_poll is not None)
    first = s.next_poll
    server_settings.save({"poll_seconds": 10})
    s.reschedule()
    wait_until(lambda: s.next_poll != first)
    assert s.next_poll - time.time() <= 11 and polls == []
    s.httpd.server_close()


def test_routes(inited):
    inited.factory("dashboard")
    i = info()
    assert request(i, "POST", "/api/server-settings/save", {"poll_seconds": 120})[1]["saved_poll_seconds"] == 120
    assert request(i, "GET", "/api/server-settings")[1]["saved_poll_seconds"] == 120
    status, body = request(i, "POST", "/api/server-settings/save", {"poll_seconds": 5})
    assert status == 400 and "whole number" in body["error"]
