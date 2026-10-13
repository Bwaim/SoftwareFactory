import pytest
import yaml

from conftest import commit_all, make_task, write_pipeline, write_step
from factory import repo
from serverutil import info, request


@pytest.fixture
def se(inited):
    commit_all(inited.library.parent, "library")
    write_step(inited.library, "gen", {"category": "git"}, body="Generic.\n")
    write_step(inited.fdir, "loc", {"category": "review"}, body="Local.\n")
    write_pipeline(inited.fdir, {"id": "uses-loc", "steps": ["loc"]})
    make_task(repo.load_ctx(cwd=inited.repo), tid="busy",
              steps=[{"id": "loc", "path": ["loc"], "with": {}, "column": None, "model": None, "effort": None}])
    inited.factory("pipeline", "edit")
    yield inited, info(inited.fdir)
    inited.factory("server", "stop", check=False)


NEW = {"id": "fresh", "description": "Fresh", "category": "test", "type": "ai",
       "outputs": {"spec": {"type": "file", "description": "Spec"}}, "config": {"style": {"description": "S", "default": "x"}}}


def save(i, manifest, body, level="local", mode="new"):
    return request(i, "POST", "/api/steps/save", {"manifest": manifest, "body": body, "level": level, "mode": mode})


def test_save_new_local_step(se):
    inited, i = se
    status, out = save(i, NEW, "Write {{description}} with {{config.style}}.")
    assert status == 200 and out["library_commit"] is None
    path = inited.fdir / "steps" / "fresh.md"
    assert out["path"] == str(path) and "type: ai" in path.read_text()
    assert "fresh" in [s["id"] for s in request(i, "GET", "/api/steps")[1]]


def test_save_generic_offers_commit(se):
    inited, i = se
    status, out = save(i, {**NEW, "id": "fresh-gen"}, "Do it.", level="generic")
    assert status == 200 and out["library_commit"]["message"] == "Factory library: add step fresh-gen"
    status, out = save(i, {**NEW, "id": "fresh-gen", "description": "Changed"}, "Do it.", level="generic", mode="edit")
    assert status == 200 and out["library_commit"]["message"] == "Factory library: update step fresh-gen"


def test_duplicate_id_refused_hidden_included(se):
    inited, i = se
    assert save(i, {**NEW, "id": "loc"}, "x")[0] == 409
    inited.factory("step", "hide", "gen")
    status, body = save(i, {**NEW, "id": "gen"}, "x")
    assert status == 409 and "already exists" in body["error"]


def test_builtin_edit_refused_and_copy_to_local(se):
    inited, i = se
    status, detail = request(i, "GET", "/api/steps/user-validation")
    status, body = save(i, detail["manifest"], detail["body"], mode="edit", level="local")
    assert status == 400 and "Built-in steps cannot be edited" in body["error"]
    status, out = save(i, detail["manifest"], detail["body"], mode="copy-local")
    assert status == 200 and out["level"] == "local"
    assert request(i, "GET", "/api/steps/user-validation")[1]["level"] == "local"
    assert save(i, detail["manifest"], detail["body"], mode="copy-local")[0] == 409


def test_errors_block_save_warnings_do_not(se):
    inited, i = se
    status, body = save(i, {**NEW, "id": "broken", "type": "command"}, "echo {{x}}")
    assert status == 400 and "A command cannot use" in body["error"]
    status, out = save(i, {**NEW, "id": "warned", "description": ""}, "x")
    assert status == 200 and "The description is empty." in out["warnings"]


def test_save_drops_empty_fields(se):
    inited, i = se
    manifest = {**NEW, "id": "tidy", "run_in": "", "model": "", "effort": "", "column": "", "outputs": {}, "requires": [], "done_check": ""}
    assert save(i, manifest, "Body.")[0] == 200
    head = yaml.safe_load((inited.fdir / "steps" / "tidy.md").read_text().split("---\n")[1])
    assert not {"run_in", "model", "effort", "column", "outputs", "requires", "done_check"} & set(head)
    assert request(i, "POST", "/api/steps/save", {"manifest": {**NEW, "id": "nobody"}, "level": "local", "mode": "new"})[0] == 400


def test_check_returns_uses_and_group_problems(se):
    inited, i = se
    status, out = request(i, "POST", "/api/steps/check", {"manifest": NEW, "body": "Use {{spec}} and {{ticket}}."})
    assert out["errors"] == [] and out["uses"] == ["spec", "ticket"] and list(out["outputs"]) == ["spec"]
    group = {"id": "grp", "description": "G", "type": "group", "steps": ["loc", "missing"]}
    status, out = request(i, "POST", "/api/steps/check", {"manifest": group, "body": ""})
    assert "The child step `missing` does not exist." in out["errors"]
    loop = {"id": "loc", "description": "L", "type": "group", "steps": ["loc"]}
    status, out = request(i, "POST", "/api/steps/check", {"manifest": loop, "body": ""})
    assert any("loop" in e for e in out["errors"])


def test_impact(se):
    inited, i = se
    status, out = request(i, "POST", "/api/steps/impact", {"id": "loc"})
    assert out["pipelines"] == [{"id": "uses-loc", "level": "local"}] and out["tasks"] == [{"id": "busy"}]
    assert out["warnings"] == []
    status, out = request(i, "POST", "/api/steps/impact", {"id": "gen"})
    assert out["warnings"] == ["Other repositories that use this library are not checked."]


def test_preview(se):
    inited, i = se
    status, out = request(i, "POST", "/api/steps/preview", {"manifest": {**NEW, "done_when": "Done."}, "body": "Write {{description}} with {{config.style}}."})
    assert out["text"].startswith("Write <description> with <config.style>.\n\n---\nStep: fresh\n")
    assert "- `spec` (file): Spec." in out["text"] and out["text"].rstrip().endswith("run `factory done`.")


def test_form_data(se):
    inited, i = se
    status, out = request(i, "GET", "/api/step-form")
    assert "git" in out["categories"] and out["library"] is True
    assert [k["name"] for k in out["factory_keys"]] == ["task_id", "description", "summary"]
    assert "user-validation" in out["step_ids"]


def test_routes_need_token(se):
    inited, i = se
    for path in ("/api/steps/check", "/api/steps/preview", "/api/steps/impact", "/api/steps/save"):
        assert request(i, "POST", path, {}, token=False)[0] == 401
    assert request(i, "GET", "/api/step-form", token=False)[0] == 401


def test_step_edit_cli(inited):
    try:
        out = inited.factory("step", "edit").stdout
        assert "Step editor: http://127.0.0.1:" in out and "new_step=1" in out
        out = inited.factory("step", "edit", "user-validation").stdout
        assert "step=user-validation" in out
        r = inited.factory("step", "edit", "nope", check=False)
        assert r.returncode == 1 and "does not exist" in r.stderr
    finally:
        inited.factory("server", "stop", check=False)


def test_skill_create_step_runs_step_edit():
    from conftest import SF
    skill = (SF / "skills" / "software-factory" / "SKILL.md").read_text()
    assert "**Create a new step** (`new-step`): run `factory step edit`" in skill
    assert "new-step-assistant" not in skill
