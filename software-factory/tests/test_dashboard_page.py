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


def test_empty_columns_shrink_and_hide_clean():
    assert ".column.no-tasks { flex: 0 0 auto; min-width: 104px; min-height: 0; padding: 0; background: none; }" in PAGE
    assert '"column" + (empty ? " no-tasks" : "")' in PAGE
    # Only the header shows; screen readers still hear that the column is empty.
    assert 'el("p", { class: "visually-hidden" }, "No tasks here")' in PAGE
    rules = [line for line in PAGE.splitlines() if line.startswith(".column.no-tasks")]
    assert len(rules) == 3 and not any("dashed" in line for line in rules)
    assert 'name === "Done" && !empty' in PAGE
    # `.empty` is the empty board, with a 60vh minimum height.
    assert ".column.empty" not in PAGE and '" empty"' not in PAGE


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
    for text in ["no_factory", "Set up and add", "Library folder", "Choose folder…", "/api/workspaces/pick-folder", "/api/host", "Rename", "In a git repository, the factory adds two lines to .git/info/exclude, so git does not track these files.",
                 "Init keeps files that exist.", "/path/to/folder"]:
        assert text in PAGE
    for text in ["/path/to/repository", "Git does not track these files."]:
        assert text not in PAGE
    assert "Remove ${ws.name} from the dashboard? The repository and its tasks stay on disk. Done checks of this workspace stop. The workspace comes back when a task in this repository waits for a done check, when you resume a task in it, or when you run \\`factory dashboard\\` in it." in PAGE


def test_workspace_menu_reuses_task_menu():
    assert PAGE.count("function closeMenus") == 1
    assert PAGE.count("function menuOpen") == 1


def test_editor_page_uses_workspace_routes():
    editor = (SF / "lib" / "factory" / "web" / "editor.html").read_text()
    assert "GLOBAL_API" in editor and "/api/w/" in editor


def test_refresh_ignores_stale_responses():
    assert "generation: state.generation + 1" in PAGE
    assert PAGE.count("state.generation !== ") == 2


def test_settings_popup():
    for text in ['button("Settings"', "openSettings", "/api/settings", "/api/settings/save", "/api/server-settings",
                 "Repository", "Built-in step settings", "Server", "Add column", "moves_needed", "Unhide",
                 "Create the folder if it is missing", "No hidden steps.", "Used by the built-in step `create-worktree` only.",
                 "Applies to all workspaces.", "Set by FACTORY_POLL_SECONDS (", "https://nextory.atlassian.net/browse/{key}",
                 "Save rewrites .factory/factory.yaml and .factory/config.yaml. Comments in these files are lost."]:
        assert text in PAGE
    assert "server-settings" in PAGE[PAGE.index("const GLOBAL_API"):PAGE.index("\n", PAGE.index("const GLOBAL_API"))]


def test_launch_popup_opens_editor_on_a_new_pipeline():
    assert 'button("Create a pipeline"' in PAGE
    assert 'new_pipeline: "1"' in PAGE and "createPipelineButton, closeButton(\"Cancel\")" in PAGE
    editor = (SF / "lib" / "factory" / "web" / "editor.html").read_text()
    assert 'else if (params.get("new_pipeline")) openModel(emptyModel(), null);' in editor
