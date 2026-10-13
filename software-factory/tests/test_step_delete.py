from pathlib import Path

import pytest
import yaml

from conftest import git, make_task, task_json, write_pipeline, write_step
from factory import catalog, hidden, repo, step_delete
from factory.errors import FactoryError
from factory.registry import Registry, all_pipeline_files
from serverutil import info, request


@pytest.fixture
def ctx(inited):
    return repo.load_ctx(cwd=inited.repo)


def set_hidden(inited, ids):
    p = inited.fdir / "factory.yaml"
    data = yaml.safe_load(p.read_text())
    data["hidden_steps"] = ids
    p.write_text(yaml.safe_dump(data, sort_keys=False))


def test_registry_keeps_every_level(inited, ctx):
    write_step(inited.library, "dup", {"description": "generic one"})
    write_step(inited.fdir, "dup", {"description": "local one"})
    reg = Registry.load(ctx)
    assert [s.level for s in reg.variants["dup"]] == ["generic", "local"]
    assert reg.steps["dup"] is reg.variants["dup"][-1]
    assert [s.level for s in reg.variants["user-validation"]] == ["builtin"]


def test_all_pipeline_files_includes_overridden(inited, ctx):
    write_pipeline(inited.library, {"id": "same", "steps": ["a"]})
    write_pipeline(inited.fdir, {"id": "same", "steps": ["b"]})
    found = [(level, pid) for level, pid, _ in all_pipeline_files(ctx) if pid == "same"]
    assert found == [("generic", "same"), ("local", "same")]


def test_hidden_ids_and_discard(inited, ctx):
    assert hidden.ids(ctx) == []
    set_hidden(inited, ["a", "b"])
    assert hidden.ids(ctx) == ["a", "b"]
    hidden.discard(ctx, "a")
    assert hidden.ids(ctx) == ["b"]
    hidden.discard(ctx, "b")
    assert "hidden_steps" not in yaml.safe_load((inited.fdir / "factory.yaml").read_text())
    before = (inited.fdir / "factory.yaml").read_text()
    hidden.discard(ctx, "zzz")
    assert (inited.fdir / "factory.yaml").read_text() == before


def commit_library(inited):
    root = inited.library.parent
    git("add", "-A", cwd=root)
    git("commit", "-m", "library", cwd=root)
    return root


def snapshot(root):
    return {str(p.relative_to(root)): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


def entry(sid, path=None):
    return {"id": sid, "path": path or [sid], "with": {}, "column": None, "model": None, "effort": None}


def test_plan_local_step(inited, ctx):
    write_step(inited.fdir, "solo", {})
    out = step_delete.plan(ctx, "solo")
    assert out["level"] == "local" and [Path(p).name for p in out["files"]] == ["solo.md"]
    assert out["replaced_by"] is None and out["in_use_stays"] is None and out["users"] == []
    assert out["warnings"] == [] and out["blocked"] is False


def test_delete_local_step_removes_file(inited, ctx):
    write_step(inited.fdir, "solo", {})
    out = step_delete.delete(ctx, "solo")
    assert not (inited.fdir / "steps" / "solo.md").exists()
    assert [Path(p).name for p in out["removed"]] == ["solo.md"] and out["library_commit"] is None


def test_local_override_is_replaced_by_generic(inited, ctx):
    write_step(inited.library, "dup", {"description": "generic one"})
    write_step(inited.fdir, "dup", {"description": "local one"})
    write_pipeline(inited.fdir, {"id": "uses-dup", "steps": ["dup"]})
    out = step_delete.plan(ctx, "dup")
    assert out["level"] == "local" and out["replaced_by"] == "generic" and out["users"] == [] and not out["blocked"]
    step_delete.delete(ctx, "dup")
    assert Registry.load(ctx).steps["dup"].level == "generic"


def test_generic_under_local_override(inited, ctx):
    write_step(inited.library, "dup", {})
    write_step(inited.fdir, "dup", {})
    write_pipeline(inited.fdir, {"id": "p", "steps": ["dup"]})
    out = step_delete.delete(ctx, "dup", "generic")
    assert out["in_use_stays"] == "local" and out["replaced_by"] is None and not out["blocked"]
    assert not (inited.library / "steps" / "dup.md").exists() and (inited.fdir / "steps" / "dup.md").exists()
    with pytest.raises(FactoryError, match="There is no generic step `dup`."):
        step_delete.plan(ctx, "dup", "generic")


def test_unknown_step(inited, ctx):
    with pytest.raises(FactoryError, match="The step `nope` does not exist."):
        step_delete.plan(ctx, "nope")


def test_generic_step_offers_commit_of_removed_file_only(inited, ctx):
    write_step(inited.library, "gstep", {})
    root = commit_library(inited)
    (root / "other.txt").write_text("staged\n")
    git("add", "other.txt", cwd=root)
    out = step_delete.delete(ctx, "gstep")
    assert out["warnings"] == ["Other repositories that use this library are not checked."]
    offer = out["library_commit"]
    assert offer["message"] == "Factory library: delete step gstep"
    assert [Path(p).name for p in offer["paths"]] == ["gstep.md"]
    inited.factory("library", "commit", offer["message"], *offer["paths"])
    assert git("show", "--name-status", "--format=", "HEAD", cwd=root) == "D\tfactory-library/steps/gstep.md"
    assert git("diff", "--cached", "--name-only", cwd=root) == "other.txt"


def test_untracked_generic_step_has_no_commit_offer(inited, ctx):
    commit_library(inited)
    write_step(inited.library, "fresh", {})
    out = step_delete.delete(ctx, "fresh")
    assert out["library_commit"] is None and not (inited.library / "steps" / "fresh.md").exists()


def test_script_step_removes_its_script(inited, ctx):
    write_step(inited.fdir, "runner", {"type": "script"}, body="runner.sh\n")
    (inited.fdir / "steps" / "runner.sh").write_text("echo hi\n")
    out = step_delete.plan(ctx, "runner")
    assert [Path(p).name for p in out["files"]] == ["runner.md", "runner.sh"]
    step_delete.delete(ctx, "runner")
    assert not (inited.fdir / "steps" / "runner.sh").exists()


def test_shared_script_stays(inited, ctx):
    for sid in ("one", "two"):
        write_step(inited.fdir, sid, {"type": "script"}, body="shared.sh\n")
    (inited.fdir / "steps" / "shared.sh").write_text("echo hi\n")
    out = step_delete.delete(ctx, "one")
    assert [Path(p).name for p in out["removed"]] == ["one.md"]
    assert (inited.fdir / "steps" / "shared.sh").exists()


def test_script_step_with_missing_script(inited, ctx):
    write_step(inited.fdir, "broken", {"type": "script"}, body="missing.sh\n")
    out = step_delete.delete(ctx, "broken")
    assert [Path(p).name for p in out["removed"]] == ["broken.md"]


def test_builtin_step_cannot_be_deleted(inited, ctx):
    message = "Built-in steps cannot be deleted. Hide the step instead: `factory step hide user-validation`."
    for level in (None, "local", "generic"):
        with pytest.raises(FactoryError) as e:
            step_delete.plan(ctx, "user-validation", level)
        assert str(e.value) == message


def test_refused_while_used(inited, ctx):
    write_step(inited.library, "core", {})
    write_pipeline(inited.library, {"id": "gp", "steps": [{"id": "core", "with": {}}]})
    write_step(inited.fdir, "combo", {"type": "composite", "steps": ["core"]}, body="")
    make_task(ctx, tid="t1", steps=[entry("core", ["combo", "core"])])
    make_task(ctx, tid="t2", status="finished", steps=[entry("core")])
    out = step_delete.plan(ctx, "core")
    assert out["blocked"] is True
    assert {(u["kind"], u["id"], u["level"]) for u in out["users"]} == {
        ("pipeline", "gp", "generic"), ("composite", "combo", "local"), ("task", "t1", None)}
    with pytest.raises(FactoryError) as e:
        step_delete.delete(ctx, "core")
    text = str(e.value)
    assert text.startswith("Step core is still used. Remove it from these first:")
    for line in ("- pipeline gp (generic)", "- composite step combo (local)", "- task t1"):
        assert line in text
    assert "t2" not in text
    assert (inited.library / "steps" / "core.md").exists()


def test_overridden_pipeline_is_a_user(inited, ctx):
    write_step(inited.fdir, "old", {})
    write_step(inited.fdir, "new", {})
    write_pipeline(inited.library, {"id": "same", "steps": ["old"]})
    write_pipeline(inited.fdir, {"id": "same", "steps": ["new"]})
    users = step_delete.plan(ctx, "old")["users"]
    assert users == [{"kind": "pipeline", "id": "same", "level": "generic"}]


def test_dry_run_changes_nothing(inited, ctx):
    write_step(inited.library, "gone", {"type": "script"}, body="gone.sh\n")
    (inited.library / "steps" / "gone.sh").write_text("echo\n")
    write_step(inited.fdir, "gone", {})
    set_hidden(inited, ["gone"])
    before = snapshot(inited.fdir), snapshot(inited.library)
    for level in (None, "local", "generic"):
        step_delete.plan(ctx, "gone", level)
    inited.factory("step", "delete", "gone", "--dry-run")
    inited.factory("step", "delete", "gone", "--level", "generic", "--dry-run")
    assert (snapshot(inited.fdir), snapshot(inited.library)) == before


def test_delete_removes_id_from_hidden_steps(inited, ctx):
    write_step(inited.fdir, "lonely", {})
    write_step(inited.library, "both", {})
    write_step(inited.fdir, "both", {})
    set_hidden(inited, ["lonely", "both"])
    step_delete.delete(ctx, "lonely")
    step_delete.delete(ctx, "both")
    assert hidden.ids(ctx) == ["both"]


def test_config_section_is_kept(inited, ctx):
    write_step(inited.fdir, "cfg", {"config": {"k": {"description": "d"}}})
    inited.factory("config", "set", "cfg", "k", "v")
    step_delete.delete(ctx, "cfg")
    assert yaml.safe_load((inited.fdir / "config.yaml").read_text())["cfg"]["k"] == "v"


def test_deleted_catalog_step_shows_not_installed(inited, ctx):
    inited.factory("catalog", "install", "push", "--local")
    rows = {i["id"]: i for i in catalog.items(ctx)}
    assert rows["push"]["status"] == "installed"
    out = step_delete.delete(ctx, "push")
    assert sorted(Path(p).name for p in out["removed"]) == ["push.md", "push.sh"]
    rows = {i["id"]: i for i in catalog.items(ctx)}
    assert rows["push"]["status"] == "not installed"


def test_cli_delete_and_dry_run(inited):
    write_step(inited.fdir, "solo", {})
    out = inited.factory.json("step", "delete", "solo", "--dry-run")
    assert out["blocked"] is False and (inited.fdir / "steps" / "solo.md").exists()
    text = inited.factory("step", "delete", "solo", "--dry-run").stdout
    assert "Dry run: delete the local step `solo`." in text and "solo.md" in text
    text = inited.factory("step", "delete", "solo").stdout
    assert "Deleted the local step `solo`." in text and not (inited.fdir / "steps" / "solo.md").exists()


def test_cli_refusals(inited):
    r = inited.factory("step", "delete", "user-validation", check=False)
    assert r.returncode == 1
    assert "Built-in steps cannot be deleted. Hide the step instead: `factory step hide user-validation`." in r.stderr
    write_step(inited.fdir, "kept", {})
    write_pipeline(inited.fdir, {"id": "pk", "steps": ["kept"]})
    r = inited.factory("step", "delete", "kept", check=False)
    assert r.returncode == 1 and "- pipeline pk (local)" in r.stderr
    r = inited.factory("step", "delete", "kept", "--level", "builtin", check=False)
    assert r.returncode == 2


def test_cli_generic_offer_text(inited):
    write_step(inited.library, "gstep", {})
    commit_library(inited)
    text = inited.factory("step", "delete", "gstep").stdout
    assert "Warning: Other repositories that use this library are not checked." in text
    assert "Library commit offer: factory library commit 'Factory library: delete step gstep'" in text


def test_api_dry_run_and_delete(inited, ctx):
    write_step(inited.fdir, "apistep", {})
    write_step(inited.fdir, "kept", {})
    write_pipeline(inited.fdir, {"id": "pk", "steps": ["kept"]})
    inited.factory("pipeline", "edit")
    i = info(inited.fdir)
    try:
        status, plan = request(i, "POST", "/api/steps/apistep/delete/dry-run", {"level": None})
        assert status == 200 and plan == step_delete.plan(ctx, "apistep")
        assert (inited.fdir / "steps" / "apistep.md").exists()
        assert request(i, "POST", "/api/steps/apistep/delete/dry-run", {}, token=False)[0] == 401
        assert request(i, "POST", "/api/steps/apistep/delete", {}, token=False)[0] == 401
        assert (inited.fdir / "steps" / "apistep.md").exists()
        status, done = request(i, "POST", "/api/steps/apistep/delete", {"level": "local"})
        assert status == 200 and [Path(p).name for p in done["removed"]] == ["apistep.md"]
        assert not (inited.fdir / "steps" / "apistep.md").exists()
        status, err = request(i, "POST", "/api/steps/kept/delete", {})
        assert status == 400 and "- pipeline pk (local)" in err["error"]
        status, err = request(i, "POST", "/api/steps/user-validation/delete/dry-run", {})
        assert status == 400 and "Built-in steps cannot be deleted" in err["error"]
    finally:
        inited.factory("server", "stop", check=False)


def test_editor_page_has_delete_flow(inited):
    from conftest import SF
    page = (SF / "lib" / "factory" / "web" / "editor.html").read_text()
    for text in ("/delete/dry-run", "Confirm delete", "function commitBox", 'd.level !== "builtin"'):
        assert text in page


def test_menu_has_delete_step_after_new_step(inited):
    actions = [a for g in inited.factory.json("menu")["groups"] for a in g["actions"]]
    keys = [a["key"] for a in actions]
    assert keys[keys.index("new-step") + 1] == "step-delete"
    assert actions[keys.index("step-delete")]["label"] == "Delete a step"


def test_docs_describe_delete():
    from conftest import SF
    readme = (SF / "README.md").read_text()
    skill = (SF / "skills" / "software-factory" / "SKILL.md").read_text()
    assert "**Delete a step**" in readme and "`factory step delete <id> [--level local|generic] [--dry-run]`" in readme
    assert "### Pipeline editor" in readme
    assert "(`step-delete`)" in skill and "factory step delete <id> --level <level> --dry-run --json" in skill
