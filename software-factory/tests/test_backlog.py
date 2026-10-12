import subprocess
import sys

import pytest

from conftest import SF, task_json, write_pipeline, write_step
from factory import backlog, config, launch, repo
from factory.errors import FactoryError


def ctx_of(inited):
    return repo.load_ctx(cwd=inited.repo)


def test_add_list_remove_move(inited):
    inited.factory("backlog", "add", "First", "--summary", "One")
    inited.factory("backlog", "add", "Second", "--pipeline", "quick-task")
    inited.factory("backlog", "add", "Third")
    ids = [e["id"] for e in inited.factory.json("backlog", "list")]
    assert ids == ["b1", "b2", "b3"]
    inited.factory("backlog", "move", "b3", "--to", "1")
    assert [e["title"] for e in inited.factory.json("backlog", "list")] == ["Third", "First", "Second"]
    inited.factory("backlog", "remove", "b1")
    assert [e["id"] for e in inited.factory.json("backlog", "list")] == ["b3", "b2"]
    text = (inited.fdir / "backlog.md").read_text()
    assert "## Second\n<!-- id: b2 -->\npipeline: quick-task\n" in text


def test_hand_written_file_is_kept(inited):
    (inited.fdir / "backlog.md").write_text(
        "# Backlog\n\nNotes before entries.\n\n## Hand entry\nSome text\n\nmore text\n\n## With id\n<!-- id: b7 -->\nX\n"
    )
    entries = inited.factory.json("backlog", "list")
    assert entries[0]["id"] == "b8" and entries[0]["summary"] == "Some text\n\nmore text"
    assert entries[1]["id"] == "b7"
    text = (inited.fdir / "backlog.md").read_text()
    assert text.startswith("# Backlog\n\nNotes before entries.\n")
    assert "<!-- id: b8 -->" in text


def test_launch_from_backlog(inited):
    write_step(inited.fdir, "w", {"reads": ["summary"]})
    write_pipeline(inited.fdir, {"id": "p", "steps": ["w"]})
    e = backlog.add(ctx_of(inited), "Dark mode", "Settings screen only.", "p")
    task = launch.launch(ctx_of(inited), "p", "", {}, from_backlog=e.id)
    t = task_json(inited.fdir, task["id"])
    assert t["description"] == "Dark mode" and t["state"]["summary"] == "Settings screen only."
    assert backlog.list_entries(ctx_of(inited)) == []


def test_failed_launch_keeps_entry(inited):
    from conftest import fake_config
    write_step(inited.fdir, "w", {})
    write_pipeline(inited.fdir, {"id": "p", "steps": ["w"]})
    e = backlog.add(ctx_of(inited), "Keep", "", None)
    fake_config(inited.fdir, fail_start=True)
    with pytest.raises(FactoryError):
        launch.launch(ctx_of(inited), "p", "", {}, from_backlog=e.id)
    assert [x.id for x in backlog.list_entries(ctx_of(inited))] == [e.id]


def test_import(inited):
    out = inited.factory.json("backlog", "import", "--dry-run", input="- One\n2. Two\n\n* Three\n")
    assert out == ["One", "Two", "Three"]
    inited.factory("backlog", "import", input="- One\n2. Two\n")
    assert [e["title"] for e in inited.factory.json("backlog", "list")] == ["One", "Two"]


WRITER = """
import sys
sys.path.insert(0, sys.argv[1])
from factory import backlog, config, repo
ctx = repo.load_ctx(cwd=sys.argv[2])
for i in range(50):
    config.set_value(ctx, "s" + sys.argv[3], "k" + str(i), i)
    backlog.add(ctx, sys.argv[3] + str(i))
"""


def test_two_processes_lose_no_write(inited):
    procs = [subprocess.Popen([sys.executable, "-c", WRITER, str(SF / "lib"), str(inited.repo), tag]) for tag in "ab"]
    assert all(p.wait(timeout=300) == 0 for p in procs)
    ctx = ctx_of(inited)
    assert len(backlog.list_entries(ctx)) == 100
    assert len({e.id for e in backlog.list_entries(ctx)}) == 100
    for tag in "ab":
        assert all(config.get_value(ctx, "s" + tag, f"k{i}") == i for i in range(50))
