import pytest
import yaml

from conftest import events, make_task, task_json, write_pipeline, write_step
from factory import config, hidden, repo, settings
from factory.errors import DetailedError


def ctx(inited):
    return repo.load_ctx(cwd=inited.repo)


def errors(inited, changes):
    return settings.check(ctx(inited), changes)["errors"]


def test_read_defaults(inited):
    s = settings.read(ctx(inited))
    assert s["columns"] == repo.DEFAULT_COLUMNS and s["terminal"] == "fake"
    assert s["terminals"] == ["herdr", "fake"] and s["ticket_default"] == "https://nextory.atlassian.net/browse/{key}"
    assert s["steps"]["create-worktree"]["worktree_root"] == str(inited.work / "worktrees") and s["steps"]["create-worktree"]["base_ref"] == ""


def test_unknown_key(inited): assert errors(inited, {"nope": 1}) == ["Unknown setting `nope`."]


@pytest.mark.parametrize("columns, text", [
    ([], "Add at least one column."),
    (["A", " "], "A column name cannot be empty."),
    (["A", "Done"], "The column `Done` is reserved."),
    (["A", "A "], "The column `A` is two times in the list."),
    (["x" * 41], f"The column name `{'x' * 41}` is longer than 40 characters."),
])
def test_column_rules(inited, columns, text): assert text in errors(inited, {"columns": columns})


def test_removed_column_with_user(inited):
    p = write_pipeline(inited.fdir, {"id": "p", "start_column": "Plan", "steps": ["user-validation"]})
    cols = [c for c in repo.DEFAULT_COLUMNS if c != "Plan"]
    assert errors(inited, {"columns": cols}) == [f"The column `Plan` is used in {p}. Change that file first."]


def test_check_uses_new_library(inited, tmp_path):
    cols = repo.DEFAULT_COLUMNS[:-1]
    old_user = write_step(inited.library, "s1", {"column": "QA"})
    new_lib = tmp_path / "lib2"
    (new_lib / "steps").mkdir(parents=True)
    assert errors(inited, {"columns": cols, "library": str(new_lib)}) == []
    old_user.unlink()
    new_user = write_step(new_lib, "s2", {"column": "QA"})
    assert errors(inited, {"columns": cols}) == []
    assert errors(inited, {"columns": cols, "library": str(new_lib)}) == [f"The column `QA` is used in {new_user}. Change that file first."]


def test_task_snapshot_needs_move(inited):
    step = {"id": "s", "path": ["s"], "with": {}, "column": "QA", "model": None, "effort": None}
    make_task(ctx(inited), tid="t1", column="Plan", steps=[step])
    result = settings.check(ctx(inited), {"columns": repo.DEFAULT_COLUMNS[:-1]})
    assert result["errors"] == [] and result["moves_needed"] == {"QA": ["t1"]}


def test_column_users_skip_broken_files(inited):
    (inited.fdir / "pipelines" / "bad.yaml").write_text("a: [")
    assert settings.column_users(ctx(inited), None, {"QA"}) == {}


def test_moves_needed(inited):
    make_task(ctx(inited), tid="t1", column="QA")
    cols = repo.DEFAULT_COLUMNS[:-1]
    assert settings.check(ctx(inited), {"columns": cols})["moves_needed"] == {"QA": ["t1"]}
    assert settings.check(ctx(inited), {"columns": cols, "moves": {"QA": "Review"}})["moves_needed"] == {}
    assert "Move the tasks of `QA` to a column of the new list." in errors(inited, {"columns": cols, "moves": {"QA": "QA"}})


def test_finished_tasks_are_not_moved(inited):
    make_task(ctx(inited), tid="t1", column="QA", status="finished")
    assert settings.check(ctx(inited), {"columns": repo.DEFAULT_COLUMNS[:-1]})["moves_needed"] == {}


def test_library_rules(inited, tmp_path):
    assert errors(inited, {"library": "rel/path"}) == ["Give the full path of the library folder."]
    assert errors(inited, {"library": str(tmp_path / "none")}) == ["The library folder does not exist. Create it, or leave the field blank."]
    assert errors(inited, {"library": str(tmp_path / "none"), "create_library": True}) == []
    assert errors(inited, {"library": ""}) == []


def test_library_warning_with_open_tasks(inited):
    make_task(ctx(inited))
    assert settings.check(ctx(inited), {"library": ""})["warnings"] == ["Tasks not finished: 1. Steps and pipelines from the old library can disappear."]


def test_terminal_rules(inited):
    assert errors(inited, {"terminal": "nope"}) == ["Unknown terminal `nope`."]
    make_task(ctx(inited))
    assert errors(inited, {"terminal": "herdr"}) == ["Finish or cancel the open tasks (1) before you change the terminal."]
    assert errors(inited, {"terminal": "fake"}) == []


@pytest.mark.parametrize("url, text", [
    ("ftp://x/{key}", "The ticket URL must start with http:// or https://."),
    ("https://x/browse", "The ticket URL must contain {key}."),
])
def test_ticket_rules(inited, url, text): assert errors(inited, {"ticket_url": url}) == [text]


def test_only_unhide(inited): assert errors(inited, {"unhide": ["create-task"]}) == ["The step `create-task` is not hidden."]


@pytest.mark.parametrize("changes, text", [
    ({"columns": "A"}, "The setting `columns` has a wrong type."),
    ({"columns": ["A", 1]}, "The setting `columns` has a wrong type."),
    ({"create_library": "yes"}, "The setting `create_library` has a wrong type."),
    ({"steps": {"create-worktree": {"base_ref": 3}}}, "The setting `steps.create-worktree.base_ref` has a wrong type."),
    ({"steps": {"rebase": {}}}, "Unknown setting `steps.rebase`."),
    ({"steps": {"create-worktree": {"nope": "x"}}}, "Unknown setting `steps.create-worktree.nope`."),
])
def test_type_and_step_rules(inited, changes, text): assert errors(inited, changes) == [text]


@pytest.mark.parametrize("value, text", [
    ("", "The worktree folder cannot be empty."),
    ("rel/wt", "Give the full path of the worktree folder."),
])
def test_worktree_rules(inited, value, text):
    assert errors(inited, {"steps": {"create-worktree": {"worktree_root": value}}}) == [text]


def test_bad_config_file(inited):
    (inited.fdir / "config.yaml").write_text("a: [")
    assert len(errors(inited, {"steps": {"create-worktree": {"base_ref": "b"}}})) == 1


def test_save_writes_only_changed_keys(inited):
    before = yaml.safe_load((inited.fdir / "factory.yaml").read_text())
    settings.save(ctx(inited), {"ticket_url": "https://x/{key}"})
    after = yaml.safe_load((inited.fdir / "factory.yaml").read_text())
    assert after == {**before, "ticket_url": "https://x/{key}"}


def test_save_moves_tasks_and_logs(inited):
    make_task(ctx(inited), tid="t1", column="QA")
    settings.save(ctx(inited), {"columns": repo.DEFAULT_COLUMNS[:-1], "moves": {"QA": "Review"}})
    assert task_json(inited.fdir, "t1")["column"] == "Review"
    ev = events(inited.fdir, "t1")[-1]
    assert (ev["type"], ev["from"], ev["to"]) == ("column_changed", "QA", "Review")


def test_save_step_keys(inited, tmp_path):
    settings.save(ctx(inited), {"steps": {"create-worktree": {"base_ref": "develop", "worktree_root": str(tmp_path / "wt")}}})
    assert config.get_value(ctx(inited), "create-worktree", "base_ref") == "develop"
    assert config.get_value(ctx(inited), "create-worktree", "worktree_root") == str(tmp_path / "wt")
    settings.save(ctx(inited), {"steps": {"create-worktree": {"base_ref": ""}}})
    assert config.get_value(ctx(inited), "create-worktree", "base_ref") is None


def test_save_replaces_snapshot_column(inited):
    step = {"id": "s", "path": ["s"], "with": {}, "column": "QA", "model": None, "effort": None}
    make_task(ctx(inited), tid="t1", column="Plan", steps=[step])
    settings.save(ctx(inited), {"columns": repo.DEFAULT_COLUMNS[:-1], "moves": {"QA": "Review"}})
    task = task_json(inited.fdir, "t1")
    assert task["column"] == "Plan" and task["steps"][0]["column"] == "Review"


def test_save_unhide_keeps_other_hidden(inited):
    hidden.hide(ctx(inited), "create-task")
    hidden.hide(ctx(inited), "delete-task")
    settings.save(ctx(inited), {"unhide": ["create-task"]})
    assert hidden.ids(ctx(inited)) == ["delete-task"]
    settings.save(ctx(inited), {"unhide": ["delete-task"]})
    assert "hidden_steps" not in yaml.safe_load((inited.fdir / "factory.yaml").read_text())


def test_save_skips_unchanged_file(inited):
    path = inited.fdir / "factory.yaml"
    path.write_text("# keep\n" + path.read_text())
    settings.save(ctx(inited), {"steps": {"create-worktree": {"base_ref": "develop"}}})
    assert path.read_text().startswith("# keep")


def test_save_creates_library(inited, tmp_path):
    settings.save(ctx(inited), {"library": str(tmp_path / "new"), "create_library": True})
    assert (tmp_path / "new" / "factory.yaml").exists() and ctx(inited).library() == (tmp_path / "new").resolve()


def test_failed_check_writes_nothing(inited):
    paths = [inited.fdir / "factory.yaml", inited.fdir / "config.yaml"]
    before = [p.read_text() for p in paths]
    with pytest.raises(DetailedError) as e:
        settings.save(ctx(inited), {"ticket_url": "https://x/{key}", "steps": {"create-worktree": {"base_ref": "b"}}, "columns": []})
    assert e.value.details["errors"] == ["Add at least one column."]
    assert [p.read_text() for p in paths] == before


def test_save_moves_needed(inited):
    make_task(ctx(inited), tid="t1", column="QA")
    with pytest.raises(DetailedError) as e:
        settings.save(ctx(inited), {"columns": repo.DEFAULT_COLUMNS[:-1]})
    assert e.value.details == {"code": "moves_needed", "moves_needed": {"QA": ["t1"]}}


def test_config_step_not_a_map(inited):
    (inited.fdir / "config.yaml").write_text("create-worktree: x\n")
    before = (inited.fdir / "factory.yaml").read_text()
    with pytest.raises(DetailedError) as e:
        settings.save(ctx(inited), {"ticket_url": "https://x/{key}", "steps": {"create-worktree": {"base_ref": "b"}}})
    assert e.value.details["errors"] == ["The setting `steps.create-worktree` has a wrong type."]
    assert (inited.fdir / "factory.yaml").read_text() == before


def test_move_skips_entry_without_column(inited):
    step = {"id": "s", "path": ["s"], "with": {}, "column": "QA", "model": None, "effort": None}
    bare = {"id": "b", "path": ["b"], "with": {}, "model": None, "effort": None}
    make_task(ctx(inited), tid="t1", column="Plan", steps=[step, bare])
    settings.move_task(ctx(inited), "t1", {"QA": "Review"})
    task = task_json(inited.fdir, "t1")
    assert task["steps"][0]["column"] == "Review" and "column" not in task["steps"][1]
