import pytest

from factory import repo
from serverutil import info, request


@pytest.fixture
def dash(inited):
    inited.factory("dashboard")
    yield inited, info(inited.fdir)
    inited.factory("server", "stop", check=False)


def test_get_and_save(dash):
    inited, i = dash
    assert request(i, "GET", "/api/settings")[1]["columns"] == repo.DEFAULT_COLUMNS
    status, body = request(i, "POST", "/api/settings/save", {"columns": ["A", "B"]})
    assert status == 200 and body["settings"]["columns"] == ["A", "B"]
    assert request(i, "GET", "/api/info")[1]["columns"] == ["A", "B"]


def test_save_errors_are_400(dash):
    inited, i = dash
    status, body = request(i, "POST", "/api/settings/save", {"columns": []})
    assert status == 400 and body["error"] == "Settings not saved." and body["errors"] == ["Add at least one column."]
