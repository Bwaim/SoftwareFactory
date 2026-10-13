import sys
from datetime import datetime

from report import VERIF, cases, table

MILESTONES = {
    "1. Loop runtime": ["test_loops"],
    "2. Loop authoring": ["test_loop_authoring", "test_authoring_skill", "test_docs"],
}
JUNIT = VERIF / "pipeline-loop-junit.xml"
REPORT = VERIF / "pipeline-loop-report.md"
UPDATED = VERIF / "pipeline-loop-updated-tests.md"
DOD = VERIF / "pipeline-loop-dod.md"


def main():
    rows = cases(JUNIT)
    lines = ["# Pipeline loop verification report", "", f"Date: {datetime.now():%Y-%m-%d %H:%M}", ""]
    for title, modules in MILESTONES.items():
        mine = [r for r in rows if r["module"] in modules]
        passed = sum(r["status"] == "PASS" for r in mine)
        lines += [f"## Milestone {title}", "", f"{passed} of {len(mine)} tests pass.", ""] + table(mine) + [""]
    passed = sum(r["status"] == "PASS" for r in rows)
    failed = [r for r in rows if r["status"] != "PASS"]
    lines += ["## Full test suite", "", f"{passed} of {len(rows)} tests pass.", ""]
    if failed:
        lines += table(failed) + [""]
    lines += ["## Updated tests", ""]
    updated = UPDATED.read_text().splitlines() if UPDATED.exists() else []
    updated = [line for line in updated if line.strip() and line != "# Updated tests"]
    lines += updated or ["None."]
    if DOD.exists():
        lines += [""] + DOD.read_text().splitlines()
    REPORT.write_text("\n".join(lines) + "\n")
    return 0 if rows and passed == len(rows) else 1


if __name__ == "__main__":
    sys.exit(main())
