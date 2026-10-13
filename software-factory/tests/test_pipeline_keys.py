import pytest

from conftest import write_pipeline, write_step
from serverutil import info, request


@pytest.fixture
def kp(inited):
    write_step(inited.fdir, "spec", {"outputs": {"spec": {"type": "file", "description": "Spec"}}})
    write_step(inited.fdir, "branchy", {"outputs": {"branch": {"type": "text", "description": "B", "optional": True}}})
    write_step(inited.fdir, "uses", {}, body="Use {{spec}}, {{branch}}, {{summary}} and {{ghost}}.\n")
    write_pipeline(inited.fdir, {"id": "kp", "inputs": {"crash_url": {"type": "text", "description": "Link"},
                                                       "notes": {"type": "long-text", "description": "N"}},
                                 "steps": ["spec", "branchy", "uses"]})
    return inited


def test_keys_cli_text_and_json(kp):
    rows = {r["name"]: r for r in kp.factory.json("pipeline", "keys", "kp")}
    assert rows["task_id"] == {"name": "task_id", "type": "text", "source": "factory", "set": "always"}
    assert rows["summary"]["set"] == "maybe" and rows["summary"]["type"] == "long-text"
    assert rows["crash_url"]["source"] == "input" and rows["notes"]["type"] == "long-text"
    assert rows["spec"] == {"name": "spec", "type": "file", "source": "step spec", "set": "always"}
    assert rows["branch"]["set"] == "maybe"
    at2 = {r["name"] for r in kp.factory.json("pipeline", "keys", "kp", "--at", "2")}
    assert "spec" in at2 and "branch" not in at2
    at1 = {r["name"] for r in kp.factory.json("pipeline", "keys", "kp", "--at", "1")}
    assert "spec" not in at1
    text = kp.factory("pipeline", "keys", "kp").stdout
    assert "spec (file) from step spec, always set" in text and "summary (long-text) from factory, maybe set" in text
    r = kp.factory("pipeline", "keys", "kp", "--at", "9", check=False)
    assert r.returncode == 1 and "between 1 and 4" in r.stderr


def test_latest_source_wins(kp):
    write_step(kp.fdir, "respec", {"outputs": {"spec": {"type": "text", "description": "S", "optional": True}}})
    write_pipeline(kp.fdir, {"id": "two", "steps": ["spec", "respec"]})
    rows = {r["name"]: r for r in kp.factory.json("pipeline", "keys", "two")}
    assert rows["spec"]["source"] == "step respec" and rows["spec"]["set"] == "maybe"


def test_new_check_warnings(kp):
    write_step(kp.fdir, "retype", {"outputs": {"crash_url": {"type": "file", "description": "C"}}})
    write_pipeline(kp.fdir, {"id": "warn", "inputs": {"crash_url": {"type": "text"}}, "steps": ["uses", "retype"]})
    out = kp.factory("pipeline", "check", "warn").stdout
    assert "Step `uses` uses `ghost`, which no input, earlier step or factory key sets." in out
    assert "Step `uses` uses `spec`" in out
    assert "The key `crash_url` is set with two types: text (input) and file (step retype)." in out
    assert "uses `summary`" not in out


def test_own_output_is_not_an_unset_key(kp):
    write_step(kp.fdir, "selfcheck", {"outputs": {"plan": {"type": "file", "description": "P"}},
                                      "done_check": 'test -f "$FACTORY_KEY_PLAN"'}, body="Write the plan to {{plan}}. Also see {{other}}.\n")
    write_pipeline(kp.fdir, {"id": "own", "steps": ["selfcheck"]})
    out = kp.factory("pipeline", "check", "own").stdout
    assert "Step `selfcheck` uses `other`, which no input, earlier step or factory key sets." in out
    assert "uses `plan`" not in out


def test_bad_input_name_and_type_are_errors(kp):
    write_pipeline(kp.fdir, {"id": "bad", "inputs": {"Bad-Name": {}, "ok": {"type": "number"}}, "steps": ["spec"]})
    r = kp.factory("pipeline", "check", "bad", check=False)
    assert r.returncode == 1 and "The input `Bad-Name`" in r.stdout and "unknown type `number`" in r.stdout


def test_keys_route(kp):
    kp.factory("pipeline", "edit", "kp")
    i = info(kp.fdir)
    try:
        data = {"id": "kp", "steps": ["spec", "uses"]}
        status, rows = request(i, "POST", "/api/pipelines/keys", {"data": data, "at": 2})
        assert status == 200 and "spec" in [r["name"] for r in rows]
        assert request(i, "POST", "/api/pipelines/keys", {"data": data, "at": 2}, token=False)[0] == 401
    finally:
        kp.factory("server", "stop", check=False)
