import shutil
import subprocess
from pathlib import Path

import pytest

ICON = Path(__file__).resolve().parent.parent / "lib" / "factory" / "appicon" / "AppIcon.icns"
SIZES = (16, 32, 128, 256, 512)


@pytest.mark.skipif(shutil.which("iconutil") is None, reason="iconutil needs macOS")
def test_icon_has_all_sizes(tmp_path):
    subprocess.run(["iconutil", "-c", "iconset", str(ICON), "-o", str(tmp_path / "out.iconset")], check=True)
    names = {path.name for path in (tmp_path / "out.iconset").iterdir()}
    expected = {f"icon_{size}x{size}{suffix}.png" for size in SIZES for suffix in ("", "@2x")}
    assert names == expected
