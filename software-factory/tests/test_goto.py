from conftest import events, task_from_pipeline, task_json, write_pipeline, write_step


def setup(inited):
    for sid in ("a", "rebase", "commit", "b"):
        write_step(inited.fdir, sid, {"writes": [f"{sid}_out"]})
    write_step(inited.fdir, "rebase-and-commit", {"type": "composite", "steps": ["rebase", "commit"]}, body="")
    write_pipeline(inited.fdir, {"id": "g", "steps": ["a", "rebase-and-commit", "b"]})
    task_from_pipeline(inited, "g")
    run = lambda *x, check=True: inited.factory(*x, "--task", "t1", check=check)
    for _ in range(3):
        run("next"); run("done")
    run("state", "set", "a_out", "kept")
    return run


def test_goto_back_into_composite(inited):
    run = setup(inited)
    run("goto", "rebase-and-commit > commit", "--reason", "fix commit")
    t = task_json(inited.fdir, "t1")
    assert t["position"] == 3 and t["state"]["a_out"] == "kept"
    goto = [e for e in events(inited.fdir, "t1") if e["type"] == "step_goto"][0]
    assert (goto["from"], goto["to"], goto["reason"]) == ("b", "rebase-and-commit > commit", "fix commit")


def test_goto_forward_refused(inited):
    run = setup(inited)
    run("goto", "a", "--reason", "x")
    r = run("goto", "b", "--reason", "x", check=False)
    assert r.returncode == 1 and "skip" in r.stderr


def test_third_jump_blocks(inited):
    run = setup(inited)
    for i in range(3):
        run("goto", "a", "--reason", f"try {i}")
        for _ in range(3):
            if task_json(inited.fdir, "t1")["status"] == "blocked":
                break
            run("next"); run("done")
    t = task_json(inited.fdir, "t1")
    assert t["status"] == "blocked" and t["status_reason"] == "loop on a"
