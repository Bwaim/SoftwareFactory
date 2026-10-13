import pytest
import yaml

from conftest import task_json, write_pipeline, write_step
from factory import hidden, repo
from serverutil import info, request


@pytest.fixture
def ctx(inited):
    return repo.load_ctx(cwd=inited.repo)


def set_hidden(inited, ids):
    p = inited.fdir / "factory.yaml"
    data = yaml.safe_load(p.read_text())
    data["hidden_steps"] = ids
    p.write_text(yaml.safe_dump(data, sort_keys=False))


def factory_yaml(inited):
    return yaml.safe_load((inited.fdir / "factory.yaml").read_text())


def test_hide_and_unhide(inited, ctx):
    write_step(inited.fdir, "quiet", {})
    assert inited.factory("step", "hide", "quiet").stdout.strip() == "Step quiet is hidden."
    assert hidden.ids(ctx) == ["quiet"]
    assert inited.factory("step", "hide", "quiet").stdout.strip() == "Step quiet is already hidden."
    assert hidden.ids(ctx) == ["quiet"]
    assert inited.factory("step", "unhide", "quiet").stdout.strip() == "Step quiet is visible again."
    assert hidden.ids(ctx) == []
    assert inited.factory("step", "unhide", "quiet").stdout.strip() == "Step quiet is not hidden."


def test_hide_unknown_refused_unhide_stale_allowed(inited, ctx):
    r = inited.factory("step", "hide", "ghost", check=False)
    assert r.returncode == 1 and "The step `ghost` does not exist." in r.stderr
    assert hidden.ids(ctx) == []
    set_hidden(inited, ["ghost"])
    assert inited.factory("step", "unhide", "ghost").stdout.strip() == "Step ghost is visible again."
    assert hidden.ids(ctx) == []


def test_hide_any_level(inited, ctx):
    write_step(inited.library, "gen", {})
    write_step(inited.fdir, "loc", {})
    for sid in ("user-validation", "gen", "loc"):
        inited.factory("step", "hide", sid)
    assert hidden.ids(ctx) == ["user-validation", "gen", "loc"]


def test_step_list_and_show(inited):
    write_step(inited.fdir, "quiet", {})
    write_step(inited.fdir, "loud", {})
    inited.factory("step", "hide", "quiet")
    rows = {r["id"]: r for r in inited.factory.json("step", "list")}
    assert "quiet" not in rows and rows["loud"]["hidden"] is False
    rows = {r["id"]: r for r in inited.factory.json("step", "list", "--all")}
    assert rows["quiet"]["hidden"] is True and rows["loud"]["hidden"] is False
    lines = inited.factory("step", "list", "--all").stdout.splitlines()
    assert [l for l in lines if l.startswith("quiet ")][0].endswith("hidden): Step quiet")
    assert "quiet " not in inited.factory("step", "list").stdout
    assert inited.factory.json("step", "show", "quiet")["hidden"] is True
    assert inited.factory("step", "show", "quiet").stdout.splitlines()[0].endswith("(hidden)")


def test_data_without_hidden_steps(inited, ctx):
    assert "hidden_steps" not in factory_yaml(inited)
    assert hidden.ids(ctx) == []
    version = factory_yaml(inited)["version"]
    report = inited.factory.json("version", "check")
    inited.factory("step", "hide", "user-validation")
    inited.factory("step", "unhide", "user-validation")
    assert "hidden_steps" not in factory_yaml(inited)
    assert factory_yaml(inited)["version"] == version
    assert inited.factory.json("version", "check") == report


def hidden_pipeline(inited):
    write_step(inited.fdir, "quiet", {})
    write_pipeline(inited.fdir, {"id": "hp", "steps": ["quiet", "quiet"]})
    inited.factory("step", "hide", "quiet")


def test_pipeline_check_warns_hidden_once(inited):
    hidden_pipeline(inited)
    r = inited.factory("pipeline", "check", "hp")
    assert r.returncode == 0
    assert r.stdout.count("WARNING: A hidden step is used: `quiet`.") == 1


def test_pipeline_with_hidden_step_runs_to_end(inited):
    hidden_pipeline(inited)
    task = inited.factory.json("launch", "hp", "--description", "Hidden run")
    tid = task["id"]
    for _ in range(2):
        inited.factory("next", "--task", tid)
        inited.factory("done", "--task", tid)
    assert task_json(inited.fdir, tid)["status"] == "finished"


def test_api_hide_unhide_list_check(inited, ctx):
    write_step(inited.fdir, "quiet", {})
    inited.factory("pipeline", "edit")
    i = info(inited.fdir)
    try:
        assert request(i, "POST", "/api/steps/quiet/hide", {}, token=False)[0] == 401
        assert hidden.ids(ctx) == []
        status, out = request(i, "POST", "/api/steps/quiet/hide", {})
        assert status == 200 and out == {"message": "Step quiet is hidden."} and hidden.ids(ctx) == ["quiet"]
        status, steps = request(i, "GET", "/api/steps")
        by_id = {s["id"]: s for s in steps}
        assert by_id["quiet"]["hidden"] is True and by_id["user-validation"]["hidden"] is False
        assert request(i, "GET", "/api/steps/quiet")[1]["hidden"] is True
        status, problems = request(i, "POST", "/api/pipelines/check", {"data": {"id": "x", "steps": ["quiet"]}, "level": "local"})
        assert {"level": "warning", "message": "A hidden step is used: `quiet`."} in problems
        status, err = request(i, "POST", "/api/steps/ghost/hide", {})
        assert status == 400 and "does not exist" in err["error"]
        assert request(i, "POST", "/api/steps/quiet/unhide", {}, token=False)[0] == 401
        status, out = request(i, "POST", "/api/steps/quiet/unhide", {})
        assert status == 200 and out == {"message": "Step quiet is visible again."} and hidden.ids(ctx) == []
    finally:
        inited.factory("server", "stop", check=False)


def test_editor_page_has_hide_ui():
    from conftest import SF
    page = (SF / "lib" / "factory" / "web" / "editor.html").read_text()
    for text in ("Show hidden steps", '"Unhide"', '"Hide"', "localStorage", '"/hide"', '"/unhide"', '"hidden"'):
        assert text in page


def test_docs_describe_hide():
    from conftest import SF
    readme = (SF / "README.md").read_text()
    skill = (SF / "skills" / "software-factory" / "SKILL.md").read_text()
    assistant = (SF / "builtin" / "steps" / "new-step.md").read_text()
    for text in ("`factory step hide <id>`", "`factory step unhide <id>`", "`factory step list [--all]`",
                 "Show hidden steps", "`hidden_steps`"):
        assert text in readme
    assert "factory step list --all --json" in skill
    assert "factory step list --all" in assistant
