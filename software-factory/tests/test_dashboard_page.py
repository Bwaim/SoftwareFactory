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


def test_card_shows_display_name_and_rename_error():
    assert "t.display_name" in PAGE and "Rename failed" in PAGE


def test_cancel_button_and_dialog():
    for text in ["Cancel task", "Keep task", "Cancelling…", "Loading…", "/cancel/dry-run", "openCancel", "state.removed"]:
        assert text in PAGE
    assert "confirm(" not in PAGE


def test_workspace_sidebar_and_routes():
    for text in ['id="sidebar"', "Workspaces", "GLOBAL_API", "/api/w/", "selectWorkspace", "factory.hiddenColumns.", "renderSidebar", "startRename", "openDeleteWorkspace", "openAddWorkspace"]:
        assert text in PAGE
    assert "No workspace. Click + to add a factory." in PAGE


def test_workspace_add_flow_texts():
    for text in ["no_factory", "Set up and add", "Library folder", "Choose folder…", "/api/workspaces/pick-folder", "/api/host", "Rename", "two lines in .git/info/exclude", "Git does not track these files. Init keeps files that exist."]:
        assert text in PAGE
    assert "Remove ${ws.name} from the dashboard? The repository and its tasks stay on disk. Done checks of this workspace stop. The workspace comes back when a task in this repository waits for a done check, when you resume a task in it, or when you run \\`factory dashboard\\` in it." in PAGE


def test_workspace_menu_reuses_task_menu():
    assert PAGE.count("function closeMenus") == 1
    assert PAGE.count("function menuOpen") == 1


def test_editor_page_uses_workspace_routes():
    editor = (SF / "lib" / "factory" / "web" / "editor.html").read_text()
    assert "GLOBAL_API" in editor and "/api/w/" in editor
