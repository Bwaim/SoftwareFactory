import subprocess
import sys
from datetime import datetime

from report import SF, VERIF, cases, table

JUNIT = VERIF / "authoring-skill-junit.xml"
REPORT = VERIF / "authoring-skill-report.md"
UPDATED = VERIF / "authoring-skill-updated-tests.md"
DOD = VERIF / "authoring-skill-dod.md"
MODULES = ["test_authoring_skill", "test_docs", "test_skill"]
ORCHESTRATOR_SKILL = "software-factory/skills/software-factory/SKILL.md"


def orchestrator_skill_diff():
    r = subprocess.run(["git", "diff", "master", "--", ORCHESTRATOR_SKILL], cwd=SF.parent, capture_output=True, text=True)
    return r.stdout.strip()


def main():
    rows = cases(JUNIT)
    lines = ["# Authoring skill verification report", "", f"Date: {datetime.now():%Y-%m-%d %H:%M}", ""]
    mine = [r for r in rows if r["module"] in MODULES]
    passed = sum(r["status"] == "PASS" for r in mine)
    lines += ["## Milestone 1. Authoring skill", "", f"{passed} of {len(mine)} tests pass.", ""] + table(mine) + [""]
    total = sum(r["status"] == "PASS" for r in rows)
    failed = [r for r in rows if r["status"] != "PASS"]
    lines += ["## Full test suite", "", f"{total} of {len(rows)} tests pass.", ""]
    if failed:
        lines += table(failed) + [""]
    diff = orchestrator_skill_diff()
    lines += ["## Orchestrator skill", "",
              "`git diff master -- " + ORCHESTRATOR_SKILL + "` is empty. The menu is unchanged." if not diff
              else "The orchestrator skill changed. This breaks the Definition Of Done.", ""]
    lines += ["## Updated tests", ""]
    updated = UPDATED.read_text().splitlines() if UPDATED.exists() else []
    updated = [line for line in updated if line != "# Updated tests"]
    lines += updated or ["None."]
    if DOD.exists():
        lines += [""] + DOD.read_text().splitlines()
    REPORT.write_text("\n".join(lines) + "\n")
    return 0 if rows and total == len(rows) and not diff else 1


if __name__ == "__main__":
    sys.exit(main())
