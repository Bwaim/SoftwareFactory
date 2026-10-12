import os
import shutil
from pathlib import Path


def claude_home():
    return Path(os.environ.get("FACTORY_CLAUDE_HOME", "~/.claude")).expanduser()


def skill_present(name, main):
    plugin, _, skill = name.lstrip("/").rpartition(":")
    if not plugin:
        for root in (claude_home() / "skills", Path(main) / ".claude" / "skills"):
            if (root / skill / "SKILL.md").exists():
                return True
    plugins = claude_home() / "plugins"
    if not plugins.exists():
        return False
    pattern = f"**/{plugin}/**/skills/{skill}/SKILL.md" if plugin else f"**/skills/{skill}/SKILL.md"
    return next(plugins.glob(pattern), None) is not None


def missing(items, main):
    out = []
    for item in items:
        present = skill_present(item, main) if item.startswith("/") else shutil.which(item) is not None
        if not present:
            out.append(item)
    return out
