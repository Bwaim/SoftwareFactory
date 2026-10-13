import sys
from datetime import datetime

from report import VERIF, cases, table

MILESTONES = {
    "1. Step format and runtime": ["test_keys", "test_step_format", "test_builtin", "test_catalog", "test_registry",
                                   "test_runtime_v2", "test_engine", "test_step_assistant", "test_migrate_v2", "test_migrate"],
    "2. Available keys": ["test_pipeline_keys", "test_pipeline_check", "test_typed_inputs"],
    "3. Step editor": ["test_step_editor_api", "test_docs"],
}
JUNIT = VERIF / "step-editor-junit.xml"
REPORT = VERIF / "step-editor-report.md"
UPDATED = VERIF / "step-editor-updated-tests.md"


def main():
    rows = cases(JUNIT)
    lines = ["# Step editor verification report", "", f"Date: {datetime.now():%Y-%m-%d %H:%M}", ""]
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
    lines += UPDATED.read_text().splitlines() if UPDATED.exists() else ["None."]
    REPORT.write_text("\n".join(lines) + "\n")
    return 0 if rows and passed == len(rows) else 1


if __name__ == "__main__":
    sys.exit(main())
