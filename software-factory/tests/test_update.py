import json
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from factory import cli, update


class Api:
    body = None
    raw = None


@pytest.fixture
def fake_api():
    api = Api()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            data = api.raw if api.raw is not None else json.dumps(api.body).encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    api.url = f"http://127.0.0.1:{server.server_port}/"
    yield api
    server.shutdown()
    server.server_close()


def test_newer_compares_numbers():
    assert update.newer("0.10.0", "0.9.0")
    assert update.newer("v0.3.0", "0.2.0")
    assert not update.newer("0.2.0", "0.2.0")
    assert not update.newer("0.1.9", "0.2.0")


@pytest.mark.parametrize("tag", ["v0.3.0-rc1", "latest", "", None, "v1.2"])
def test_bad_tags_give_no_update(tag):
    assert not update.newer(tag, "0.2.0")


def test_fetch_reads_tag_name(fake_api):
    fake_api.body = {"tag_name": "v0.3.0"}
    assert update.fetch_latest(fake_api.url) == "0.3.0"


def test_fetch_bad_body_gives_none(fake_api, capsys):
    fake_api.raw = b"<html>rate limited</html>"
    assert update.fetch_latest(fake_api.url) is None
    assert capsys.readouterr().err.count("\n") == 1


def test_fetch_offline_gives_none():
    assert update.fetch_latest("http://127.0.0.1:9/") is None


def test_dismiss_round_trip(factory_home):
    assert update.dismissed() is None
    update.dismiss("0.3.0")
    assert update.dismissed() == "0.3.0"
    assert (factory_home / "update-dismissed").read_text().strip() == "0.3.0"


def test_checker_keeps_only_newer(fake_api, monkeypatch):
    monkeypatch.setattr(cli, "VERSION", "0.2.0")
    monkeypatch.setenv("FACTORY_UPDATE_URL", fake_api.url)
    fake_api.body = {"tag_name": "v0.2.0"}
    c = update.Checker()
    c.check_once()
    assert c.latest is None and c.checked_at is not None
    fake_api.body = {"tag_name": "v0.3.0"}
    c.check_once()
    assert c.latest == "0.3.0"


def test_no_update_check_env_skips_the_check(monkeypatch, tmp_path):
    assert os.environ["FACTORY_NO_UPDATE_CHECK"] == "1"
    monkeypatch.setenv("FACTORY_UPDATE_ROOT", str(tmp_path))
    (tmp_path / ".installed-by-script").touch()
    c = update.Checker()
    c.start()
    assert c.checked_at is None


def test_no_check_without_script_install(monkeypatch, tmp_path):
    monkeypatch.delenv("FACTORY_NO_UPDATE_CHECK")
    monkeypatch.setenv("FACTORY_UPDATE_ROOT", str(tmp_path))
    c = update.Checker()
    c.start()
    assert c.checked_at is None
