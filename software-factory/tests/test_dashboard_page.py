from conftest import SF

PAGE = (SF / "lib" / "factory" / "web" / "dashboard.html").read_text()


def test_modal_has_fixed_bar_and_scrolling_content():
    assert "#modal .bar" in PAGE and "#modal .content" in PAGE
    assert "max-height: calc(100vh - 2rem)" in PAGE


def test_artifact_viewer_is_dismissable():
    assert "dismissable: true" in PAGE
    assert 'e.key !== "Escape"' in PAGE
    assert "Discard the typed text?" in PAGE
    assert "pressedOnBackdrop" in PAGE


def test_card_has_countdown_and_check_now():
    assert "data-next-check" in PAGE and "Next check in" in PAGE
    assert "Check now" in PAGE and "Checking…" in PAGE
    assert "/check`" in PAGE


def test_focus_asks_terminal_app():
    assert "terminal_app" in PAGE and "Which terminal app shows Herdr?" in PAGE
