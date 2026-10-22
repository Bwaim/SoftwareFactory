import subprocess
import sys
from datetime import datetime

from report import SF, VERIF, cases, table

MASTER = "f8ee5474c500d51f1b080a83daf3350e4ca9fe3b"
MILESTONES = {
    "1. Merged branch check": ["test_merge_check", "test_squash_merge", "test_clean", "test_delete", "test_removal_failures",
                               "test_herdr_adapter"],
    "2. Cancel in the CLI": ["test_no_recreate", "test_cancel", "test_cancel_races"],
    "3. Dashboard and docs": ["test_cancel_api", "test_dashboard_page", "test_docs"],
}
JUNIT = VERIF / "task-cancel-junit.xml"
REPORT = VERIF / "task-cancel-report.md"
UPDATED = [
    "`tests/test_squash_merge.py::test_later_change_of_same_lines_is_not_merged` is renamed to "
    "`test_later_change_of_same_lines_is_merged_by_patch_id`. It checked the old bug: a later change of the same lines "
    "hid a squash merge. It now expects \"merged (squash)\". The user approved the change.",
]


def master():
    out = subprocess.run(["git", "rev-parse", "master"], cwd=SF, capture_output=True, text=True)
    return out.stdout.strip()


def main():
    rows = cases(JUNIT)
    lines = ["# Task cancel verification report", "", f"Date: {datetime.now():%Y-%m-%d %H:%M}", ""]
    for title, modules in MILESTONES.items():
        mine = [r for r in rows if r["module"] in modules]
        passed = sum(r["status"] == "PASS" for r in mine)
        lines += [f"## Milestone {title}", "", f"{passed} of {len(mine)} tests pass.", ""] + table(mine) + [""]
    passed = sum(r["status"] == "PASS" for r in rows)
    failed = [r for r in rows if r["status"] != "PASS"]
    lines += ["## Full test suite", "", f"{passed} of {len(rows)} tests pass.", ""]
    if failed:
        lines += table(failed) + [""]
    lines += ["## Updated tests", ""] + UPDATED + [""]
    head = master()
    state = "unchanged" if head == MASTER else "CHANGED"
    lines += ["## Master", "", f"`git rev-parse master` is `{head}`: {state} (expected `{MASTER}`).", ""]
    REPORT.write_text("\n".join(lines))
    return 0 if rows and passed == len(rows) and head == MASTER else 1


if __name__ == "__main__":
    sys.exit(main())
