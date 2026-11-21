import hashlib
import subprocess
import tarfile

from conftest import PROJECT_ROOT

BUILD = PROJECT_ROOT / "scripts" / "build-release.sh"


def run_build(version, out):
    r = subprocess.run(["sh", str(BUILD), version, str(out)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return out / "software-factory.tar.gz"


def tar_names(archive):
    with tarfile.open(archive) as t:
        return [n.rstrip("/") for n in t.getnames()]


def extract(archive, dest):
    with tarfile.open(archive) as t:
        t.extractall(dest, filter="data")


def test_archive_has_only_runtime_files(work):
    out = run_build("0.2.0", work)
    names = tar_names(out)
    tops = {n.split("/")[1] for n in names if n.count("/") >= 1 and n.split("/")[1]}
    assert tops == {"VERSION", "bin", "lib", "builtin", "catalog", "migrations"}
    assert all(n.startswith("software-factory/") or n == "software-factory" for n in names)
    assert not any("__pycache__" in n for n in names)


def test_digest_file_matches(work):
    out = run_build("0.2.0", work)
    line = (work / "software-factory.tar.gz.sha256").read_text()
    assert line == f"{hashlib.sha256(out.read_bytes()).hexdigest()}  software-factory.tar.gz\n"


def test_archive_version_and_cli(work):
    out = run_build("0.2.0", work)
    extract(out, work)
    assert (work / "software-factory/VERSION").read_text() == "0.2.0\n"
    r = subprocess.run(
        ["uv", "run", "--script", str(work / "software-factory/bin/factory"), "--version"],
        capture_output=True, text=True,
    )
    assert "factory 0.2.0" in r.stdout


def test_version_mismatch_fails(work):
    r = subprocess.run(["sh", str(BUILD), "9.9.9", str(work)], capture_output=True, text=True)
    assert r.returncode == 1
    assert "build-release: version 9.9.9 differs from cli.VERSION 0.2.0." in r.stderr
    assert not list(work.glob("software-factory.tar.gz*"))


def test_release_workflow_attaches_install_script():
    text = (PROJECT_ROOT / ".github" / "workflows" / "release.yml").read_text()
    line = next(l for l in text.splitlines() if "gh release create" in l)
    assert "dist/software-factory.tar.gz.sha256 install.sh" in line
