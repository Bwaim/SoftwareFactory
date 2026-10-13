import json
import shutil
import subprocess

import pytest

from conftest import SF, task_from_pipeline, write_pipeline, write_step
from factory import board, repo, state
from serverutil import info, request

LOOP = {"back_to": "write", "while": "findings", "max": 2}
EDITOR = SF / "lib" / "factory" / "web" / "editor.html"
ROUND_TRIP = ["emptyModel", "isMap", "loopOf", "loopData", "entryOf", "modelOf", "parseValue", "dataOf"]


@pytest.fixture
def ed(inited):
    write_step(inited.fdir, "write", {})
    write_step(inited.fdir, "review", {"outputs": {"findings": {"type": "long-text", "description": "Findings"}}})
    write_step(inited.fdir, "after", {})
    inited.factory("pipeline", "edit")
    yield inited, info(inited.fdir)
    inited.factory("server", "stop", check=False)


def test_editor_api_saves_and_loads_loop_unchanged(ed):
    inited, i = ed
    data = {"id": "rl", "description": "Review loop", "steps": ["write", {"id": "review", "loop": LOOP}, "after"]}
    status, saved = request(i, "POST", "/api/pipelines/save", {"data": data, "level": "local"})
    assert status == 200, saved
    status, loaded = request(i, "GET", "/api/pipelines/rl")
    assert loaded["data"]["steps"] == ["write", {"id": "review", "loop": LOOP}, "after"]
    status, problems = request(i, "POST", "/api/pipelines/check", {"data": {**data, "steps": ["write", {"id": "review", "loop": {**LOOP, "max": 0}}, "after"]}, "level": "local"})
    assert {"level": "error", "message": "Step `review`: `loop.max` must be an integer from 1 to 20."} in problems


def test_editor_page_has_loop_controls(ed):
    inited, i = ed
    status, page = request(i, "GET", "/editor")
    for text in ("(no loop)", "↺ ${s.loop.back_to} ×${s.loop.max}", "datalist", "keysAt(i + 2)", "loopBlock(s, i, loopTag)"):
        assert text in page, text


def extract(source, name):
    start = source.index(f"function {name}(")
    end = source.index("\n}\n", start) + 2
    return source[start:end]


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_editor_model_keeps_loop_on_load_and_save(work):
    source = EDITOR.read_text()
    consts = "const DEFAULT_LOOP_MAX = 2;\nconst LOOP_MAX_LIMIT = 20;\n"
    functions = "\n".join(extract(source, n) for n in ROUND_TRIP)
    data = {"id": "rl", "description": "d", "steps": [
        "write", {"id": "review", "loop": LOOP}, {"id": "odd", "loop": {"back_to": "write", "until": 1}}, {"id": "bad", "loop": "write"}]}
    script = consts + functions + f"\nconst m = modelOf({json.dumps(data)});\nconsole.log(JSON.stringify(dataOf(m).steps.map((s) => s.loop)));\n"
    path = work / "roundtrip.js"
    path.write_text(script)
    out = subprocess.run(["node", str(path)], capture_output=True, text=True, check=True).stdout
    assert json.loads(out) == [None, LOOP, {"back_to": "write", "until": 1}, "write"]


def test_task_row_shows_loop_count(inited):
    write_step(inited.fdir, "write", {})
    write_step(inited.fdir, "review", {"outputs": {"findings": {"type": "long-text", "description": "Findings"}}})
    write_step(inited.fdir, "after", {})
    write_pipeline(inited.fdir, {"id": "rl", "steps": ["write", {"id": "review", "loop": LOOP}, "after"]})
    task_from_pipeline(inited, "rl")
    ctx = repo.load_ctx(cwd=inited.repo)
    assert board.task_row(ctx, state.load(ctx, "t1"))["loop"] is None
    run = lambda *a: inited.factory(*a, "--task", "t1")
    run("next"); run("done"); run("next")
    run("state", "set", "findings", "bugs")
    run("done")
    assert board.task_row(ctx, state.load(ctx, "t1"))["loop"] == {"n": 1, "max": 2, "entry": "review"}
    page = (SF / "lib" / "factory" / "web" / "dashboard.html").read_text()
    assert "` · loop ${t.loop.n} of ${t.loop.max}`" in page


def test_readme_documents_loops():
    text = (SF / "README.md").read_text()
    fields = text.split("### Pipeline fields\n", 1)[1].split("\n### ", 1)[0]
    for needle in ("`loop`", "`back_to`", "`while`", "`max`", "back_to: write-spec", "while: findings"):
        assert needle in fields, needle
    for needle in ("### Loops", "Loop <n> of <max>: back to `<step>`", "`loop_back`", "`loop_limit`", "↺ write-spec ×2"):
        assert needle in text, needle
