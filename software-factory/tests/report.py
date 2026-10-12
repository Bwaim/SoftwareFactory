import json
import sys
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

SF = Path(__file__).resolve().parents[1]
VERIF = SF.parent / "verification" / "software-factory"
MILESTONES = {
    "1. Core": ["test_scaffold", "test_fsio", "test_repo_version", "test_registry", "test_pipeline_check", "test_config_state",
                "test_adapters", "test_engine", "test_builtin", "test_herdr_adapter", "test_launch", "test_delete",
                "test_init_menu", "test_skill"],
    "2. Task life": ["test_board", "test_session", "test_approval", "test_waiting", "test_goto", "test_clean", "test_backlog",
                     "test_event_log"],
    "3. Authoring": ["test_server", "test_editor_api", "test_catalog", "test_library", "test_step_assistant"],
    "4. Lifecycle and docs": ["test_migrate", "test_docs"],
    "5. Dashboard": ["test_dashboard_api"],
}


def cases(junit):
    out = []
    for case in ET.parse(junit).getroot().iter("testcase"):
        module = case.get("classname", "").split(".")[-1]
        failure = case.find("failure") if case.find("failure") is not None else case.find("error")
        skipped = case.find("skipped") is not None
        status = "FAIL" if failure is not None else "SKIP" if skipped else "PASS"
        out.append({"module": module, "name": case.get("name"), "status": status,
                    "message": (failure.get("message") or "")[:300] if failure is not None else ""})
    return out


def table(rows):
    lines = ["| Test | Result |", "|---|---|"]
    for r in rows:
        extra = f" ({r['message']})" if r["message"] else ""
        lines.append(f"| `{r['module']}::{r['name']}` | {r['status']}{extra} |")
    return lines


def main():
    rows = cases(VERIF / "junit.xml")
    e2e = json.loads((VERIF / "e2e-results.json").read_text()) if (VERIF / "e2e-results.json").exists() else []
    lines = ["# Software factory verification report", "", f"Date: {datetime.now():%Y-%m-%d %H:%M}", ""]
    total = len(rows) + len(e2e)
    passed = sum(r["status"] == "PASS" for r in rows) + sum(r["ok"] for r in e2e)
    lines += [f"Total: {passed} of {total} checks pass.", ""]
    known = set()
    for title, modules in MILESTONES.items():
        known |= set(modules)
        lines += [f"## Milestone {title}", ""] + table([r for r in rows if r["module"] in modules]) + [""]
    other = [r for r in rows if r["module"] not in known]
    if other:
        lines += ["## Other tests", ""] + table(other) + [""]
    lines += ["## End-to-end (Herdr and Claude)", "", "| Check | Result |", "|---|---|"]
    lines += [f"| {r['name']} | {'PASS' if r['ok'] else 'FAIL'}{(' (' + r['detail'] + ')') if r['detail'] else ''} |" for r in e2e]
    if not e2e:
        lines.append("| e2e not run | FAIL |")
    (VERIF / "report.md").write_text("\n".join(lines) + "\n")
    return 0 if passed == total and e2e else 1


if __name__ == "__main__":
    sys.exit(main())
