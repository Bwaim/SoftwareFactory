import json

import pytest

from conftest import task_from_pipeline, task_json, write_pipeline, write_step


def run(inited, *args, check=True):
    return inited.factory(*args, "--task", "t1", check=check)


@pytest.fixture
def ai(inited):
    write_step(inited.fdir, "plan", {
        "config": {"style": {"description": "Style", "default": "small"}},
        "outputs": {"plan": {"type": "file", "description": "The plan"},
                    "note": {"type": "long-text", "description": "Notes", "optional": True}},
        "done_when": "The plan is written.",
    }, body="Plan {{spec}} for {{task_id}} ({{description}}), style {{config.style}}. Ticket: {{ticket}}.\n")
    write_pipeline(inited.fdir, {"id": "p", "steps": ["plan"]})
    task_from_pipeline(inited, "p", description="Add login", state={"spec": "/tmp/spec.md"})
    return inited


def test_next_prints_exact_prompt_then_footer(ai):
    out = run(ai, "next").stdout
    prompt, footer = out.split("\n---\n", 1)
    assert prompt.rstrip("\n") == "Plan /tmp/spec.md for t1 (Add login), style small. Ticket: (not set)."
    assert footer.splitlines()[0] == "Step 2 of 2: plan"
    assert "- `plan` (file): The plan. Set it with `factory state set plan <path>`. Get a path in the artifacts folder with `factory artifact path <name>`." in footer
    assert "- `note` (long-text, optional): Notes. Set it with `factory state set note <value>`." in footer
    assert "Done when: The plan is written." in footer
    assert footer.rstrip().endswith("When the step is done, run `factory done`.")
    assert "--task" not in out


def test_subagent_prompt_is_the_same_text_with_a_report_line(inited):
    write_step(inited.fdir, "sub", {"run_in": "subagent", "model": "haiku", "effort": "low",
                                    "outputs": {"review": {"type": "file", "description": "Review"}}}, body="Review {{ticket}}.\n")
    write_pipeline(inited.fdir, {"id": "s", "steps": [{"id": "sub", "model": "opus"}]})
    task_from_pipeline(inited, "s", state={"ticket": "ABC-1"})
    out = run(inited, "next").stdout
    inner = out.split("<<<\n", 1)[1].split("\n>>>", 1)[0]
    assert inner.startswith("Review ABC-1.\n\n---\nStep 2 of 2: sub\n")
    assert "- `review` (file): Review." in inner
    assert inner.endswith("End with a short report. If you need an answer from the user, say so in the report and stop.")
    assert "factory done" not in inner
    assert "- model: opus" in out and "- effort: low" in out
    assert out.rstrip().endswith("Otherwise run `factory done`.")


def test_wait_external_ends_with_factory_wait(inited):
    write_step(inited.fdir, "w", {"wait_external": True}, body="Wait.\n")
    write_pipeline(inited.fdir, {"id": "wp", "steps": ["w"]})
    task_from_pipeline(inited, "wp")
    assert run(inited, "next").stdout.rstrip().endswith("The factory tells you when the external event happens.")


def test_group_step_shows_full_path(inited):
    write_step(inited.fdir, "a", {})
    write_step(inited.fdir, "b", {})
    write_step(inited.fdir, "ab", {"type": "group", "steps": ["a", "b"]}, body="")
    write_pipeline(inited.fdir, {"id": "g", "steps": ["ab"]})
    task_from_pipeline(inited, "g")
    run(inited, "next"); run(inited, "done")
    assert "Step 3 of 3: ab > b" in run(inited, "next").stdout


def test_first_prompt_never_adds_task_flag():
    from factory import session
    text = session.first_prompt({"id": "t1", "worktree": "/w"})
    assert "`factory next`" in text and "`factory done`" in text and "--task" not in text


@pytest.fixture
def cmd(inited):
    step = write_step(inited.fdir, "echo", {
        "type": "command", "config": {"word": {"description": "w", "default": "hello"}},
        "outputs": {"echoed": {"type": "file", "description": "Echo file"}},
    }, body='bash "$FACTORY_STEP_DIR/echo.sh"\n')
    (step.parent / "echo.sh").write_text(
        'p="$(factory artifact path echo.txt)"\n'
        'printf "%s|%s|%s|%s" "$FACTORY_KEY_TICKET" "$FACTORY_CONFIG_WORD" "$FACTORY_KEY_TASK_ID" "$FACTORY_STEP_DIR" > "$p"\n'
        'factory state set echoed "$p"\n'
        'exit "${FACTORY_KEY_CODE:-0}"\n')
    write_pipeline(inited.fdir, {"id": "c", "steps": ["echo"]})
    task_from_pipeline(inited, "c", state={"ticket": "T-1"})
    return inited, step


def test_command_next_and_env(cmd):
    inited, step = cmd
    out = run(inited, "next").stdout
    assert "Run `factory run-command`." in out
    assert "- `echoed` (file): Echo file." in out
    r = run(inited, "run-command")
    assert r.stdout.rstrip().endswith("Exit code: 0")
    text = (inited.fdir / "tasks" / "t1" / "artifacts" / "echo.txt").read_text()
    assert text == f"T-1|hello|t1|{step.parent.resolve()}"
    assert "The pipeline is finished" in run(inited, "done").stdout


def test_command_sets_wrong_key(inited):
    write_step(inited.fdir, "wrong", {
        "type": "command",
        "outputs": {"out": {"type": "file", "description": "Out file"},
                    "extra": {"type": "text", "description": "Extra", "optional": True}},
    }, body="factory state set result 1\n")
    write_pipeline(inited.fdir, {"id": "w", "steps": ["wrong"]})
    task_from_pipeline(inited, "w")
    out = run(inited, "next").stdout
    assert "factory state set" not in out and "factory artifact path" not in out
    assert ("The command sets these outputs. Never set them yourself and never write their files. "
            "If one is missing, run `factory block` and tell the user that the step command did not set it.") in out
    assert "- `out` (file): Out file." in out and "- `extra` (text, optional): Extra." in out
    r = run(inited, "run-command")
    assert "The command did not set the output `out`." in r.stdout
    assert "`extra`" not in r.stdout
    assert task_json(inited.fdir, "t1")["state"]["result"] == "1"


def test_done_refused_until_command_exits_0(cmd):
    inited, _ = cmd
    run(inited, "next")
    r = run(inited, "done", check=False)
    assert r.returncode == 1 and "The output `echoed` is not set" in r.stderr
    run(inited, "state", "set", "echoed", str(inited.repo / "README.md"))
    r = run(inited, "done", check=False)
    assert r.returncode == 1 and "Run `factory run-command` first." in r.stderr
    run(inited, "state", "set", "code", "3")
    assert run(inited, "run-command", check=False).returncode == 3
    r = run(inited, "done", check=False)
    assert r.returncode == 1 and "exited with code 3" in r.stderr
    assert json.loads((inited.fdir / "tasks" / "t1" / "events.jsonl").read_text().splitlines()[-1])["type"] == "done_check_failed"
    run(inited, "state", "set", "code", "0")
    run(inited, "run-command")
    run(inited, "done")


def test_goto_clears_command_result(cmd):
    inited, _ = cmd
    write_step(inited.fdir, "after", {})
    write_pipeline(inited.fdir, {"id": "c2", "steps": ["echo", "after"]})
    task_from_pipeline(inited, "c2", tid="t2", state={"ticket": "T-1"})
    r2 = lambda *a, check=True: inited.factory(*a, "--task", "t2", check=check)
    r2("next"); r2("run-command"); r2("done"); r2("next")
    r2("goto", "echo", "--reason", "again")
    assert task_json(inited.fdir, "t2")["command_result"] is None
    r = r2("done", check=False)
    assert r.returncode == 1 and "Run `factory run-command` first." in r.stderr


def test_command_key_value_is_never_run(inited):
    write_step(inited.fdir, "safe", {"type": "command"}, body='printf "%s" "$FACTORY_KEY_EVIL" > "$(factory artifact path out.txt)"\n')
    write_pipeline(inited.fdir, {"id": "s", "steps": ["safe"]})
    evil = '$(touch pwned) `touch pwned2` "quote\nline'
    task_from_pipeline(inited, "s", state={"evil": evil})
    run(inited, "next"); run(inited, "run-command")
    assert (inited.fdir / "tasks" / "t1" / "artifacts" / "out.txt").read_text() == evil
    assert not (inited.repo / "pwned").exists() and not (inited.repo / "pwned2").exists()


def test_file_output_must_exist(ai):
    run(ai, "next")
    run(ai, "state", "set", "note", "free text, not checked")
    r = run(ai, "state", "set", "plan", "missing.md", check=False)
    assert r.returncode == 1 and "The path does not exist" in r.stderr
    task = task_json(ai.fdir, "t1")
    task["state"]["plan"] = "/nowhere/plan.md"
    (ai.fdir / "tasks" / "t1" / "task.json").write_text(json.dumps(task))
    r = run(ai, "done", check=False)
    assert r.returncode == 1 and "The output `plan` points to a path that does not exist: /nowhere/plan.md" in r.stderr


def test_state_set_file_relative_to_caller(ai):
    run(ai, "next")
    sub = ai.repo / "docs"
    sub.mkdir()
    (sub / "plan.md").write_text("x")
    ai.factory("state", "set", "plan", "plan.md", "--task", "t1", cwd=sub)
    assert task_json(ai.fdir, "t1")["state"]["plan"] == str((sub / "plan.md").resolve())
    run(ai, "state", "set", "free_key", "anything")
    run(ai, "done")


def test_run_script_is_gone(inited):
    r = inited.factory("run-script", "--task", "t1", check=False)
    assert r.returncode != 0


def test_subagent_wait_external_ends_with_factory_wait(inited):
    write_step(inited.fdir, "sw", {"run_in": "subagent", "wait_external": True}, body="Wait.\n")
    write_pipeline(inited.fdir, {"id": "swp", "steps": ["sw"]})
    task_from_pipeline(inited, "swp")
    out = run(inited, "next").stdout
    inner = out.split("<<<\n", 1)[1].split("\n>>>", 1)[0]
    assert inner.endswith("End with a short report. If you need an answer from the user, say so in the report and stop.")
    assert out.rstrip().endswith("The factory tells you when the external event happens.")
    assert "Otherwise run `factory done`" not in out
