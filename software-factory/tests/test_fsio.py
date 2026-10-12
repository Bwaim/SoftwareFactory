import subprocess
import sys

from conftest import SF
from factory import fsio


def test_atomic_write_creates_parents_and_leaves_no_temp(tmp_path):
    p = tmp_path / "a" / "b.json"
    fsio.write_json(p, {"x": 1})
    assert fsio.read_json(p) == {"x": 1}
    assert [f.name for f in p.parent.iterdir()] == ["b.json"]


def test_update_yaml_returns_fn_result(tmp_path):
    p = tmp_path / "c.yaml"
    r = fsio.update_yaml(p, lambda d: d.setdefault("k", "v"))
    assert r == "v"
    assert fsio.read_yaml(p) == {"k": "v"}


def test_lock_file_is_separate(tmp_path):
    p = tmp_path / "d.json"
    with fsio.locked(p):
        assert (tmp_path / "d.json.lock").exists()


WRITER = """
import sys
sys.path.insert(0, sys.argv[1])
from pathlib import Path
from factory import fsio
p = Path(sys.argv[2])
for i in range(200):
    fsio.update_yaml(p, lambda d: d.setdefault("items", []).append(sys.argv[3] + str(i)))
"""


def test_two_processes_lose_no_write(tmp_path):
    p = tmp_path / "shared.yaml"
    procs = [subprocess.Popen([sys.executable, "-c", WRITER, str(SF / "lib"), str(p), tag]) for tag in "ab"]
    assert all(proc.wait(timeout=120) == 0 for proc in procs)
    assert len(fsio.read_yaml(p)["items"]) == 400
