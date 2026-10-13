import pytest
import yaml

from conftest import task_json, write_pipeline, write_step
from factory import hidden, repo


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
