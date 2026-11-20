import plistlib
from pathlib import Path

from factory import appbuild

OLD_ID = "com.captn.factory.notifications"


def bundle(path, bundle_id):
    (path / "Contents").mkdir(parents=True)
    with open(path / "Contents" / "Info.plist", "wb") as f:
        plistlib.dump({"CFBundleIdentifier": bundle_id}, f)
    return path


def test_old_notifier_is_removed(tmp_path):
    old = bundle(tmp_path / "CAPTN Factory.app", OLD_ID)

    appbuild.remove_old_bundle(old, OLD_ID)

    assert not old.exists()


def test_old_notifier_with_other_id_is_kept(tmp_path):
    other = bundle(tmp_path / "CAPTN Factory.app", "com.example.other")

    appbuild.remove_old_bundle(other, OLD_ID)

    assert other.exists()


def test_lsregister_override_skips(monkeypatch):
    monkeypatch.setenv("FACTORY_LSREGISTER", "")
    assert appbuild.lsregister() is None
    monkeypatch.setenv("FACTORY_LSREGISTER", "/x")
    assert appbuild.lsregister() == Path("/x")
