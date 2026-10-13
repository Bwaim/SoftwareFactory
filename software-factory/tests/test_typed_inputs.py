from conftest import task_json, write_pipeline, write_step
from serverutil import info, request


def setup(inited):
    write_step(inited.fdir, "w", {})
    write_pipeline(inited.fdir, {"id": "f", "inputs": {"log": {"type": "file", "description": "Log file"},
                                                      "notes": {"type": "long-text", "description": "Notes"}},
                                 "steps": ["w"]})


def test_missing_file_input_is_a_dry_run_error(inited):
    setup(inited)
    rep = inited.factory.json("launch", "f", "--description", "x", "--input", "log=nope.txt", "--input", "notes=a", "--dry-run", check=False)
    expected = f"The input `log` is a path that does not exist: {inited.repo / 'nope.txt'}."
    assert not rep["ok"] and expected in rep["errors"]


def test_relative_file_input_saved_absolute(inited):
    setup(inited)
    (inited.repo / "logs").mkdir()
    (inited.repo / "logs" / "a.txt").write_text("x")
    task = inited.factory.json("launch", "f", "--description", "x", "--input", "log=logs/a.txt", "--input", "notes=line one\nline two")
    saved = task_json(inited.fdir, task["id"])["state"]
    assert saved["log"] == str((inited.repo / "logs" / "a.txt").resolve())
    assert saved["notes"] == "line one\nline two"


def test_pipeline_list_has_typed_inputs(inited):
    setup(inited)
    rows = {r["id"]: r for r in inited.factory.json("pipeline", "list")}
    assert rows["f"]["inputs"]["notes"] == {"type": "long-text", "description": "Notes"}
    assert rows["f"]["inputs"]["log"]["type"] == "file"


def test_dashboard_has_textarea_for_long_text(inited):
    inited.factory("dashboard")
    i = info(inited.fdir)
    try:
        status, page = request(i, "GET", "/dashboard")
        assert 'type === "long-text"' in page and "relative to the main repository" in page
    finally:
        inited.factory("server", "stop", check=False)
