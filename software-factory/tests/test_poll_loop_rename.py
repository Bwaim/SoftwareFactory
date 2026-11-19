import pytest

from factory import rename, repo, server


class StopLoop(Exception):
    pass


def test_poll_loop_applies_pending_renames(inited, monkeypatch, capsys):
    ctx = repo.load_ctx(cwd=inited.repo)
    srv = server.Server()
    sleeps = []
    applied = []

    def fake_wait(seconds):
        sleeps.append(seconds)
        if len(sleeps) == 2:
            raise StopLoop
        return False

    monkeypatch.setattr(srv.wake, "wait", fake_wait)
    monkeypatch.setattr("factory.engine.poll", lambda c: None)
    monkeypatch.setattr(rename, "apply_all_pending", lambda c: applied.append(c))
    try:
        with pytest.raises(StopLoop):
            srv.poll_loop()
    finally:
        srv.httpd.server_close()
    assert applied == [ctx]
    assert "poll failed" not in capsys.readouterr().err
