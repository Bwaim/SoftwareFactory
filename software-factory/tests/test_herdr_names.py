import json
import os
import stat

import pytest

from conftest import SF, fake_calls
from factory import repo
from factory.adapters.base import HERDR_NAME_RE, herdr_name
from factory.adapters.fake import FakeAdapter
from factory.adapters.herdr import HerdrAdapter

LONG = "library-following-opening-the-review-mr"


def test_long_name_is_valid_and_short():
    name = herdr_name(LONG)
    assert HERDR_NAME_RE.fullmatch(name) and len(name) <= 32
    assert name.startswith("library-following-opening")


def test_names_that_differ_after_32_characters_stay_different():
    a = "a" * 32 + "-first"
    b = "a" * 32 + "-second"
    assert herdr_name(a) != herdr_name(b)
    assert len(herdr_name(a)) <= 32 and len(herdr_name(b)) <= 32


@pytest.mark.parametrize("raw, expected", [
    ("HT-4549 Fix", "ht-4549-fix"),
    ("4549", "t-4549"),
    ("ht-4549", "ht-4549"),
    ("", "t"),
    ("Été!!", "t"),
])
def test_rule(raw, expected):
    assert herdr_name(raw) == expected


def test_fake_adapter_returns_the_real_name(inited):
    adapter = FakeAdapter(repo.load_ctx(cwd=inited.repo))
    handle = adapter.start_session(LONG, inited.repo, "p", [])
    assert handle["agent"] == herdr_name(LONG)
    call = [c for c in fake_calls(inited.fdir) if c["op"] == "start_session"][-1]
    assert call["name"] == LONG and call["herdr_name"] == herdr_name(LONG)


def test_herdr_adapter_starts_with_the_real_name(tmp_path, monkeypatch, origin_repo):
    bindir = tmp_path / "bin"
    bindir.mkdir()
    exe = bindir / "herdr"
    exe.write_text(f"#!/bin/sh\nexec python3 {SF / 'tests' / 'fake_herdr.py'} \"$@\"\n")
    exe.chmod(exe.stat().st_mode | stat.S_IEXEC)
    log = tmp_path / "herdr.log"
    monkeypatch.setenv("PATH", f"{bindir}:{os.environ['PATH']}")
    monkeypatch.setenv("FAKE_HERDR_LOG", str(log))
    monkeypatch.setenv("FAKE_HERDR_MAIN", str(origin_repo))
    adapter = HerdrAdapter(repo.load_ctx(cwd=origin_repo))
    handle = adapter.start_session(LONG, origin_repo / "wt", "p", [])
    real = herdr_name(LONG)
    assert handle["agent"] == real
    calls = [json.loads(line) for line in log.read_text().splitlines()]
    assert any(c[:3] == ["agent", "start", real] for c in calls)
    opened = [c for c in calls if c[:2] == ["worktree", "open"]][0]
    assert opened[opened.index("--label") + 1] == real
    assert not any(LONG in c for c in calls)
