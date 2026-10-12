import json
import os
import subprocess
import uuid

from conftest import BIN, PROJECT_ROOT, SF, VERIF


def test_version_prints():
    r = subprocess.run(["uv", "run", "--script", str(BIN), "--version"], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert "factory 0.1.0" in r.stdout


def test_uv_installs_dependencies_on_first_run(tmp_path_factory):
    cache = VERIF / "work" / f"uv-cache-{uuid.uuid4().hex[:6]}"
    env = {**os.environ, "UV_CACHE_DIR": str(cache)}
    r = subprocess.run(["uv", "run", "--script", str(BIN), "--version"], capture_output=True, text=True, env=env)
    subprocess.run(["rm", "-rf", str(cache)])
    assert r.returncode == 0, r.stderr
    assert "pyyaml" in r.stderr.lower() or "installed" in r.stderr.lower()


def test_marketplace_points_to_plugin():
    data = json.loads((PROJECT_ROOT / ".claude-plugin" / "marketplace.json").read_text())
    assert data["name"] == "software-factory"
    assert (PROJECT_ROOT / data["plugins"][0]["source"]).resolve() == SF
    plugin = json.loads((SF / ".claude-plugin" / "plugin.json").read_text())
    assert plugin["name"] == "software-factory"
