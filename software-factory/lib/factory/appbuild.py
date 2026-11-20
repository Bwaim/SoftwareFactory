import os
import plistlib
import shutil
import subprocess
import tempfile
from pathlib import Path

ICON = Path(__file__).resolve().parent / "appicon" / "AppIcon.icns"
STAMP_KEY = "CAPTNBuildStamp"
BUILD_TIMEOUT_SECONDS = 300
SYSTEM_LSREGISTER = Path(
    "/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister"
)


def can_build():
    return bool(shutil.which("swiftc") and shutil.which("codesign"))


def lsregister():
    override = os.environ.get("FACTORY_LSREGISTER")
    if override is not None:
        return Path(override) if override else None
    return SYSTEM_LSREGISTER if SYSTEM_LSREGISTER.exists() else None


def read_info(app):
    try:
        with open(app / "Contents" / "Info.plist", "rb") as f:
            return plistlib.load(f)
    except (OSError, plistlib.InvalidFileException):
        return None


def is_current(app, executable, stamp):
    info = read_info(app)
    return bool(info) and info.get(STAMP_KEY) == stamp and (app / "Contents" / "MacOS" / executable).exists()


def build(app, source, executable, plist):
    app.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=app.parent, prefix=".captn-build-") as work:
        bundle = Path(work) / app.name
        (bundle / "Contents" / "MacOS").mkdir(parents=True)
        (bundle / "Contents" / "Resources").mkdir()
        subprocess.run(["swiftc", "-O", str(source), "-o", str(bundle / "Contents" / "MacOS" / executable)],
                       check=True, capture_output=True, timeout=BUILD_TIMEOUT_SECONDS)
        shutil.copyfile(ICON, bundle / "Contents" / "Resources" / "AppIcon.icns")
        with open(bundle / "Contents" / "Info.plist", "wb") as f:
            plistlib.dump(plist, f)
        subprocess.run(["codesign", "--force", "--sign", "-", str(bundle)], check=True, capture_output=True)
        if app.exists():
            shutil.rmtree(app)
        os.rename(bundle, app)
    register = lsregister()
    if register is not None:
        subprocess.run([str(register), "-f", str(app)], capture_output=True)


def remove_old_bundle(path, bundle_id):
    info = read_info(path)
    if info and info.get("CFBundleIdentifier") == bundle_id:
        shutil.rmtree(path, ignore_errors=True)
