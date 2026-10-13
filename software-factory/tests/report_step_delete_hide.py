import sys
from datetime import datetime

from report import VERIF, cases, table

MILESTONES = {"1. Delete a step": ["test_step_delete"], "2. Hide a step": ["test_step_hide"]}
JUNIT = VERIF / "step-delete-hide-junit.xml"
REPORT = VERIF / "step-delete-hide-report.md"


def main():
    rows = cases(JUNIT)
    lines = ["# Step delete and hide verification report", "", f"Date: {datetime.now():%Y-%m-%d %H:%M}", ""]
    for title, modules in MILESTONES.items():
        mine = [r for r in rows if r["module"] in modules]
        passed = sum(r["status"] == "PASS" for r in mine)
        lines += [f"## Milestone {title}", "", f"{passed} of {len(mine)} tests pass.", ""] + table(mine) + [""]
    passed = sum(r["status"] == "PASS" for r in rows)
    failed = [r for r in rows if r["status"] != "PASS"]
    lines += ["## Full test suite", "", f"{passed} of {len(rows)} tests pass.", ""]
    if failed:
        lines += table(failed) + [""]
    REPORT.write_text("\n".join(lines) + "\n")
    return 0 if rows and passed == len(rows) else 1


if __name__ == "__main__":
    sys.exit(main())
