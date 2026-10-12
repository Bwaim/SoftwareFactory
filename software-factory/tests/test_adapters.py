from conftest import fake_calls, fake_config
from factory import adapters, repo


def test_fake_records_calls(inited):
    ctx = repo.load_ctx(cwd=inited.repo)
    a = adapters.get_adapter(ctx)
    h = a.start_session("t1", inited.repo, "say \"hi\" $HOME `x`", ["--name", "t1"], False)
    a.send_prompt(h, "next")
    calls = fake_calls(inited.fdir)
    assert calls[0]["op"] == "start_session"
    assert calls[0]["prompt"] == "say \"hi\" $HOME `x`"
    assert calls[1] == {"op": "send_prompt", "handle": h, "text": "next"}


def test_capabilities_and_check(inited):
    fake_config(inited.fdir, capabilities=["focus"], check_ok=False, check_message="nope")
    ctx = repo.load_ctx(cwd=inited.repo)
    a = adapters.get_adapter(ctx)
    assert a.capabilities() == {"focus"}
    assert a.check() == (False, "nope")
    r = inited.factory("terminal", "check", check=False)
    assert r.returncode == 1 and "nope" in r.stdout
