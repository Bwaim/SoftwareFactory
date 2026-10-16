import pytest

from conftest import SF, commit_all, write_pipeline, write_step, task_from_pipeline
from factory import render, step_format
from serverutil import info, request

EDITOR_PAGE = (SF / "lib" / "factory" / "web" / "editor.html").read_text()


def test_valid_exclusive_name():
    errors, _ = step_format.validate({"id": "s", "type": "ai", "description": "d", "exclusive": "android-emulator"}, "Do it.")
    assert errors == []


@pytest.mark.parametrize("bad", ["Android", "1emu", "emu lator", ""])
def test_bad_exclusive_name(bad):
    errors, _ = step_format.validate({"id": "s", "type": "ai", "description": "d", "exclusive": bad}, "Do it.")
    assert any("exclusive" in e for e in errors)


def test_exclusive_on_group_is_error():
    errors, _ = step_format.validate({"id": "g", "type": "group", "description": "d", "steps": ["a"], "exclusive": "emu"}, "")
    assert "`exclusive` applies only to `ai` and `command` steps. Set it on the child steps." in errors


def test_footer_names_resource(inited):
    write_step(inited.fdir, "emu", {"exclusive": "android-emulator"})
    write_pipeline(inited.fdir, {"id": "p", "steps": ["emu"]})
    task_from_pipeline(inited, "p", worktree=str(inited.repo))
    out = inited.factory("next", "--task", "t1").stdout
    assert "This step uses `android-emulator`. Only one task at a time runs it." in out
    assert "`factory exclusive release android-emulator`" in out


def test_footer_in_command_step(inited):
    write_step(inited.fdir, "emu", {"type": "command", "exclusive": "android-emulator"}, body="true\n")
    write_pipeline(inited.fdir, {"id": "p", "steps": ["emu"]})
    task_from_pipeline(inited, "p", worktree=str(inited.repo))
    out = inited.factory("next", "--task", "t1").stdout
    assert "This step uses `android-emulator`." in out


def test_no_footer_without_exclusive(inited):
    write_step(inited.fdir, "plain", {})
    write_pipeline(inited.fdir, {"id": "p", "steps": ["plain"]})
    task_from_pipeline(inited, "p", worktree=str(inited.repo))
    assert "This step uses" not in inited.factory("next", "--task", "t1").stdout


def test_released_line():
    assert render.released_line("emu") == "You released `emu`. Run `factory exclusive acquire emu` before you use it again."


def test_pipeline_check_accepts_exclusive(inited):
    write_step(inited.fdir, "emu", {"exclusive": "android-emulator"})
    write_pipeline(inited.fdir, {"id": "p", "steps": ["emu"]})
    assert "no problem" in inited.factory("pipeline", "check", "p").stdout


def test_step_api_saves_exclusive(inited):
    commit_all(inited.library.parent, "library")
    inited.factory("pipeline", "edit")
    i = info(inited.fdir)
    try:
        manifest = {"id": "emu", "description": "Emu", "category": "test", "type": "ai", "wait_external": True, "exclusive": "emu"}
        status, _ = request(i, "POST", "/api/steps/save", {"manifest": manifest, "body": "Do it.", "level": "local", "mode": "new"})
        assert status == 200
        status, detail = request(i, "GET", "/api/steps/emu")
        assert detail["manifest"]["exclusive"] == "emu"
        text = (inited.fdir / "steps" / "emu.md").read_text()
        assert text.index("wait_external") < text.index("exclusive: emu")
    finally:
        inited.factory("server", "stop", check=False)


def test_editor_has_exclusive_field():
    assert 'field("exclusive"' in EDITOR_PAGE
