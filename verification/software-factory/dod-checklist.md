# Definition Of Done checklist

Source: "Definition Of Done" in `prompts/factory_skill_creation.md`. Test names are in `report.md` (159 pytest tests and 12 e2e checks, all pass).
Legend: PASS = proven by a test, an e2e check or a file. PARTIAL = built and scripted-checked, but a part is not proven. FAIL = not met.

Two PARTIAL reasons recur:
- UI: the scripted check passed (`editor-manual-check.md`, `dashboard-manual-check.md`); human browser check pending.
- Conversation: the orchestrator is a Claude conversation that no test runs end to end. Evidence is the `SKILL.md` line and the CLI tests of the commands it calls.

## Workflow Complete

- PASS: Plan exists under `PLAN_DIR/`, written before the build. Evidence: `plans/2026-10-12-software-factory.md`, `specs/2026-10-12-software-factory-design.md`; git history shows the plan commit before the code commits.
- PASS: The `software-factory` skill exists under `YOUR_WORKING_DIR`. Evidence: `software-factory/skills/software-factory/SKILL.md`, `test_skill::test_skill_frontmatter_and_menu_rule`.
- PASS: `.claude-plugin/marketplace.json` defines marketplace `software-factory` with one plugin pointing to the working dir. Evidence: `.claude-plugin/marketplace.json`, `test_scaffold::test_marketplace_points_to_plugin`.

## Runtime

- PASS: Python 3, one entry script `factory`, run with `uv run --script`, inline dependencies (`pyyaml` only). Evidence: `software-factory/bin/factory` header, `test_scaffold::test_version_prints`.
- PASS: Small modules in `lib/`, one per area, each tested on its own. Evidence: `software-factory/lib/factory/*.py` with matching `tests/test_*.py` (see report milestones).
- PASS: Local server is `factory serve`; `dashboard` and `pipeline edit` start it in the background; server and CLI share functions. Evidence: `test_server::test_server_survives_the_command_and_is_reused`, `test_dashboard_api::test_actions_call_cli_functions`, `test_editor_api::test_cli_lists`.
- PARTIAL: `uv` installs the Python version the scripts need (`requires-python >= 3.12`), machine needs only `uv`. Evidence: `bin/factory` header, `test_scaffold::test_uv_installs_dependencies_on_first_run`. Not proven on a machine without Python 3.12 or without a warm uv cache.
- PARTIAL: Orchestrator starts in the configured terminal, runs `factory terminal check` at start, says why and stops on failure. Evidence: `SKILL.md` lines 16-17, `test_adapters::test_capabilities_and_check`, `test_herdr_adapter::test_check_outside_herdr`, `test_server::test_adapter_check_failure_reported`. Conversation not run end to end.
- PASS: `factory` callable by name in every session (link in `~/.local/bin`, checked at start). Evidence: `test_init_menu::test_link_fixes_wrong_target`, `SKILL.md` line 16, e2e "Claude receives the first prompt and runs factory next".
- PASS: Init writes `.factory/claude-settings.json`; every task session starts with `--settings <main>/.factory/claude-settings.json`; no permission prompt. Evidence: `test_init_menu::test_init_creates_files_and_exclude`, `test_launch` (settings arg assert), e2e "the session never waits on a permission prompt" (14 samples, blocked 0).
- PASS: README lists `git`, `factory` and adapter commands for the Bash allowlist. Evidence: `software-factory/README.md` section "Bash allowlist", `test_docs::test_readme_commands_exist`.

## General concept

- PARTIAL: `software-factory` skill is an orchestrator launched in the main repository, with the menu actions grouped. Evidence: `SKILL.md` lines 8-57, `test_init_menu::test_menu_before_and_after_init`. Conversation not run end to end.
- PARTIAL: Tasks: launch from scratch or backlog. Evidence: `SKILL.md` line 40, `test_launch::*`, `test_backlog::test_launch_from_backlog`, e2e launch checks. Conversation part not run.
- PASS: Tasks: show tasks with status. Evidence: `SKILL.md` line 41, `test_board::test_block_unblock_and_order`.
- PARTIAL: Tasks: check waiting tasks (`factory poll`, mark manual events done). Evidence: `SKILL.md` line 42, `test_waiting::test_wait_then_poll_ends_on_check`, `test_waiting::test_external_done_manual`. Conversation part not run.
- PASS: Tasks: focus a task. Evidence: `SKILL.md` line 43, `test_session::test_send_prompt_and_focus`.
- PARTIAL: Tasks: send a prompt (wait or send now, offer resume). Evidence: `SKILL.md` lines 44-47, `test_session::test_send_prompt_and_focus`, `test_session::test_deliver_to_gone_session_sends_one_prompt`. Conversation choice not run.
- PARTIAL: Tasks: resume a task (paused or session gone, warning without `state`). Evidence: `SKILL.md` line 48, `test_session::test_resume_restores_status_same_session`, e2e "resume reopens the Claude process with --resume and the same session id". Warning step is conversation only.
- PASS: Tasks: delete a task via `delete-task`. Evidence: `SKILL.md` line 49, `builtin/steps/delete-task.md`, `test_delete::*`, e2e delete checks.
- PASS: Tasks: clean finished tasks whose work is merged. Evidence: `SKILL.md` line 50, `test_clean::test_clean_detects_merge_cases`, `test_dashboard_api::test_clean_and_delete_routes`.
- PARTIAL: Pipelines and steps: create or edit a pipeline opens the editor in the browser. Evidence: `SKILL.md` line 51, `test_editor_api::*`. Editor page: UI-only, scripted check passed; human browser check pending.
- PARTIAL: Pipelines and steps: create a new step runs `new-step-assistant`. Evidence: `SKILL.md` line 52, `builtin/pipelines/new-step-assistant.yaml`, `test_step_assistant::test_builtin_assistant_runs_in_main_repo`. The assistant dialogue is not run by any test.
- PASS: Pipelines and steps: browse the catalog, list and install. Evidence: `SKILL.md` line 53, `test_catalog::test_list_and_install_pipeline_with_missing_steps`, `test_catalog::test_replace_needs_flag_and_shows_diff`.
- PARTIAL: Backlog: add entry via `backlog-add`. Evidence: `SKILL.md` line 54, `builtin/steps/backlog-add.md`, `test_backlog::test_add_list_remove_move`. Conversation not run.
- PARTIAL: Backlog: remove entry via `backlog-remove`. Evidence: `SKILL.md` line 55, `builtin/steps/backlog-remove.md`, `test_backlog::test_add_list_remove_move`. Conversation not run.
- PARTIAL: Factory: open dashboard starts the server if needed and opens the browser. Evidence: `SKILL.md` line 56, `test_server::test_server_survives_the_command_and_is_reused`, `test_dashboard_api::*`. Page: human browser check pending.
- PARTIAL: Factory: Init is the only action before init and never shown after. Evidence: `test_init_menu::test_menu_before_and_after_init`, `SKILL.md` lines 18, 35-39. Init conversation not run.
- PARTIAL: Factory: Exit stops the menu and server, first asks whether to pause all tasks. Evidence: `SKILL.md` line 57, `test_session::test_pause_all`, `test_server::test_stop`. The question is not run by any test.

## Factory elements: Pipelines

- PASS: A pipeline is one YAML file `pipelines/<id>.yaml` with `id`, `description`, `inputs`, `steps`, `claude`, `start_column`, step `with`, `model`, `effort`, `column`. Evidence: `test_registry::test_expand_adds_create_worktree_and_overrides`, `test_pipeline_check::test_each_problem_type`, `test_board::test_launch_uses_start_column`, `test_engine::test_subagent_call_model_effort_precedence`.
- PASS: Pipeline `claude.model` and `claude.effort` passed at launch as `--model` and `--effort`. Evidence: `test_launch` (claude args), `tests/test_launch.py`.
- PASS: Built-in pipeline `new-step-assistant`; other pipelines from catalog or editor. Evidence: `builtin/pipelines/new-step-assistant.yaml`, `catalog/pipelines/`, `test_builtin::test_builtin_steps_parse`.
- PASS: A new pipeline needs only a new file. Evidence: `test_catalog::test_catalog_steps_parse_with_registry`, `test_editor_api::test_load_copy_check_save`.
- PASS: Each pipeline run is a task. Evidence: `test_launch::test_launch_detached`.

## Factory elements: Steps

- PASS: A step is one markdown file with a YAML manifest (all listed fields) and a body per type. Evidence: `test_registry::*`, `test_builtin::test_builtin_steps_parse`, `test_catalog::test_catalog_steps_parse_with_registry`.
- PASS: Composite steps: computed `reads`/`writes`, full path, loop refused, children keep checks. Evidence: `test_registry::test_composite_paths_and_io`, `test_registry::test_composite_loop_refused`, `test_engine::test_skip_refused_for_required_and_composite_path`.
- PASS: Steps that ask the user run in the session; subagent steps print the Agent call with model, effort and full prompt; pipeline value wins. Evidence: `test_engine::test_subagent_call_model_effort_precedence`, `test_pipeline_check::test_each_problem_type`.
- PASS: A step can be used by many pipelines. Evidence: `test_registry::test_local_overrides_generic_overrides_builtin`, catalog pipelines share `commit`, `user-validation`.
- PASS: Built-in steps `create-task`, `create-worktree`, `delete-task`, `backlog-add`, `backlog-remove`, `migrate`, `user-validation`. Evidence: `software-factory/builtin/steps/`, `test_builtin::test_builtin_steps_parse`.
- PASS: Required steps enforced: `factory skip` refuses them, `done` runs `done_check`. Evidence: `test_engine::test_skip_refused_for_required_and_composite_path`, `test_engine::test_next_done_check_fails_then_passes`.

## Factory elements: Step creation

- PARTIAL: `new-step-assistant` runs as a task in the main repository without a worktree, with `--add-dir <library>`, asks where to save, the goal, type, category, reads/writes, done condition, where it runs, config, required; checks for similar steps; shows the file before writing; offers to add to pipelines; local beats generic. Evidence: `builtin/steps/new-step.md`, `test_step_assistant::test_builtin_assistant_runs_in_main_repo`, `test_registry::test_local_overrides_generic_overrides_builtin`. The dialogue itself is not run by any test.

## Factory elements: Step configuration

- PASS: Config in `.factory/config.yaml`; order `with`, `config.yaml`, default; missing value makes `factory next` ask; `factory config set` saves it. Evidence: `test_config_state::test_config_order`, `test_config_state::test_cli_config_set_get`, `test_engine::test_missing_config_asks`.
- PASS: `factory next` prints resolved config values with the instructions. Evidence: `test_engine::test_run_script_gets_config_and_task`, `test_engine::test_missing_config_asks`.
- PASS: No secrets in config files. Evidence: no secret keys in `builtin/` or `catalog/` config; `test_catalog::test_catalog_is_generic`.

## Factory elements: Pipeline editor

- PARTIAL: Editor is a plain HTML/CSS/JS page on the local server, no external library, started by `factory pipeline edit`, with start options, drag and drop, forms, filters, reload, level and run-in display, read-only detail panel. Evidence: `test_editor_api::test_steps_list_and_detail`, `test_editor_api::test_load_copy_check_save`, `test_editor_api::test_cli_lists`, `editor-manual-check.md` (`node --check` pass). Scripted check passed; human browser check pending (items 1 to 8).
- PASS: Live pipeline checks via the server, every error and warning type; save with warnings, never with errors. Evidence: `test_pipeline_check::test_each_problem_type`, `test_editor_api::test_load_copy_check_save`. Live timing and disabled button: browser check pending (see above).
- PASS: On save, asks level (generic or local); a generic pipeline can be saved as a local override. Evidence: `test_editor_api::test_load_copy_check_save`, `test_editor_api::test_save_drops_empty_nested_fields`. Dialog look: browser check pending.

## Factory elements: Local server

- PASS: One stdlib `http.server`, serves editor, dashboard and API; writes port, token and pid to `.factory/server.json`; reused. Evidence: `test_server::test_server_survives_the_command_and_is_reused`, `test_server::test_server_info_file_is_private`.
- PASS: API covers steps, pipelines, tasks, backlog and one route per dashboard action; routes call the CLI functions. Evidence: `test_editor_api::*`, `test_dashboard_api::test_actions_call_cli_functions`.
- PASS: Server runs `factory poll` every `poll_minutes`. Evidence: `software-factory/lib/factory/server.py` (poll loop uses `poll_minutes`, default 5), `test_waiting::test_wait_then_poll_ends_on_check`. The timer itself has no dedicated test.
- PASS: Security: `127.0.0.1` only, random token, Origin check. Evidence: `test_server::test_security_checks`, `test_server::test_non_ascii_token_is_refused`, `test_server::test_shutdown_needs_token_and_safe_origin`.
- PASS: Stops on Exit or after 30 min idle. Evidence: `test_server::test_stop`, `test_server::test_idle_stop`, `server.py` `IDLE_SECONDS = 1800`.

## Factory elements: Dashboard

- PARTIAL: Tasks and Backlog views, plain HTML, refresh every 5 s, errors in the page. Evidence: `dashboard-manual-check.md` (page served, `node --check` pass, all API routes 200), `test_dashboard_api::test_missing_body_field_is_400`. Scripted check passed; human browser check pending.
- PARTIAL: Tasks view columns plus Done, hide/show saved in browser, no drag between columns, cards with ticket link, status text, icon, time in status, tint colors, `gone` marker, artifact list. Evidence: `test_board::test_session_state_column`, `test_dashboard_api::test_artifact_and_errors`, `dashboard-manual-check.md`. Scripted check passed; human browser check pending (layout, colors, localStorage).
- PARTIAL: Card buttons (Focus, Show MR, Approve, Request changes with Open in IDE, Mark done, Send prompt, Pause with wait-idle, Resume). Evidence: `test_dashboard_api::test_actions_call_cli_functions`, `test_dashboard_api::test_approve_from_card`, `test_approval::*`, `test_waiting::test_external_done_manual`. Scripted check passed; human browser check pending.
- PARTIAL: Launch form shows the dry-run result and launches after confirmation. Evidence: `test_dashboard_api::test_launch_dry_run_then_launch`. Scripted check passed; human browser check pending.
- PARTIAL: Done column Clean button shows the report and deletes selected tasks via `delete-task`. Evidence: `test_dashboard_api::test_clean_and_delete_routes`, `test_dashboard_api::test_confirm_unpushed_must_be_true`. Scripted check passed; human browser check pending (unpushed-work dialog).
- PARTIAL: Backlog view: priority order, drag to move, Add, Delete with confirmation, Start with `--from-backlog`. Evidence: `test_dashboard_api::test_backlog_routes`, `test_backlog::test_add_list_remove_move`. Scripted check passed; drag and drop and dialog look need a human browser check.

## Factory elements: Catalog

- PASS: Catalog in `catalog/`, items are templates installed by copy to generic or local. Evidence: `test_catalog::test_list_and_install_pipeline_with_missing_steps`.
- PASS: Browse shows category, description, status (not installed, installed, installed and changed since) and missing `requires`. Evidence: `test_catalog::test_list_and_install_pipeline_with_missing_steps`, `test_catalog::test_missing_requires`.
- PASS: Installing a pipeline lists missing steps and installs them after approval; replacing needs the diff and approval. Evidence: `test_catalog::test_list_and_install_pipeline_with_missing_steps`, `test_catalog::test_replace_needs_flag_and_shows_diff`.
- PARTIAL: Init offers the starter pack (`quick-task` and its steps). Evidence: `SKILL.md` line 38, `test_catalog::test_list_and_install_pipeline_with_missing_steps` (installs `quick-task` with steps). The offer is conversation only.
- PASS: Catalog is generic, no project-specific skill or tool. Evidence: `test_catalog::test_catalog_is_generic`.
- PASS: Catalog content matches the list: pipelines `quick-task`, `plan-and-build`; steps `implement`, `commit`, `rebase`, `push`, `run-tests`, `create-pr`, `review`, `address-review-comments`, `brainstorm`, `write-plan`, `execute-plan`, `wait-review`, `wait-qa`. Evidence: `software-factory/catalog/`, `test_catalog::test_catalog_steps_parse_with_registry`.
- PASS: `config.forge` asked once per repository like any config key. Evidence: `catalog/steps/create-pr.md`, `wait-review.md`, `test_config_state::test_config_order`.

## Factory elements: Library commits

- PASS: After a library write, offers a commit with files and message `Factory library: <action> <kind> <id>`; pathspec only; disabled outside git; never pushes. Evidence: `test_library::test_commit_only_given_files`, `test_library::test_refuses_paths_outside_library`, `test_library::test_disabled_without_git`, `SKILL.md` lines 63-69. The approval prompt is conversation only.

## Factory elements: Tasks

- PASS: Task properties (id, ticket, description, pipeline, inputs, step path, status, column, branch, worktree, session id, terminal handle, dates). Evidence: `test_launch::test_launch_detached`, `test_config_state::test_state_set_get_and_artifact_path`.
- PASS: Task launch with `factory launch` and `--dry-run`, no Claude, id slug and suffix, rollback on failure, backlog entry removed only on success, session started with `--name`, `--session-id`, `--settings`, `--add-dir`. Evidence: `test_launch::test_slug_rules`, `test_launch::test_dry_run_changes_nothing_and_reports`, `test_launch::test_taken_id_gets_suffix`, `test_launch::test_failed_start_rolls_back_but_keeps_existing_branch`, `test_backlog::test_failed_launch_keeps_entry`, e2e "Claude runs in Herdr named with the task id, with the factory settings".
- PASS: Worktree creation: fetch `origin`, new branch, existing local branch fast-forwarded, remote-only branch, diverged branch stops, branch in another worktree stops, detached without branch input, git only. Evidence: `test_launch::test_new_branch`, `test_launch::test_existing_local_branch_behind_is_fast_forwarded`, `test_launch::test_remote_only_branch`, `test_launch::test_diverged_branch_stops`, `test_launch::test_branch_in_other_worktree_stops`, `test_launch::test_launch_detached`, e2e "launch fetches origin and creates the worktree from origin/main".
- PASS: `create-worktree` added automatically, refused when not first; `new-step-assistant` runs without a worktree. Evidence: `test_launch::test_create_worktree_listed_late_refused`, `test_registry::test_expand_adds_create_worktree_and_overrides`, `test_step_assistant::test_builtin_assistant_runs_in_main_repo`.
- PASS: Task delete with `--dry-run` and `--confirm-unpushed`, local branch deleted only if pushed or merged, never a remote branch, terminal closed, worktree removed, folder archived. Evidence: `test_delete::*`, e2e "delete asks for approval when there are uncommitted changes", "delete closes the terminal, removes the worktree and archives the task".
- PASS: Event log: JSON lines written by the CLI, all event types. Evidence: `test_event_log::test_all_event_types`, `test_config_state::test_events_append`.
- PASS: Task execution: first prompt, `factory next`/`done` loop, finish sets `finished` with `task_finished` and notification, skip needs approval, goto rules. Evidence: `test_engine::test_last_done_finishes`, `test_engine::test_next_tells_session_about_block_skip_and_goto`, `test_goto::*`, e2e "first script step runs with factory next and factory done", "the resumed session continues the pipeline to the end".
- PASS: `factory goto` back only, into composites, blocks on 3rd jump. Evidence: `test_goto::test_goto_back_into_composite`, `test_goto::test_goto_forward_refused`, `test_goto::test_third_jump_blocks`.
- PASS: Task list shows id, pipeline, step path, status with reason, live session state; blocked then awaiting approval first. Evidence: `test_board::test_block_unblock_and_order`, `test_board::test_session_state_column`.
- PASS: Focus and send prompt call the adapter and are hidden when unsupported. Evidence: `test_session::test_send_prompt_and_focus`, `test_adapters::test_capabilities_and_check`, `test_init_menu::test_menu_before_and_after_init`.
- PASS: Clean: merged, pushed-and-remote-deleted (squash), no-branch cases; merged selected by default; each via `delete-task`. Evidence: `test_clean::test_clean_detects_merge_cases`, `SKILL.md` line 50.
- PASS: Blocked status with `block`/`unblock`, notify. Evidence: `test_board::test_block_unblock_and_order`, `test_event_log::test_all_event_types`.
- PASS: Board columns from `.factory/factory.yaml`, Done last, `start_column`, step column (pipeline over manifest), unknown column is a check error. Evidence: `test_board::test_columns_follow_steps`, `test_board::test_launch_uses_start_column`, `test_pipeline_check::test_each_problem_type`.
- PASS: Approval: `awaiting_approval`, `approve`, `request-changes`, `open-ide`, message to session via adapter. Evidence: `test_approval::test_awaiting_approval_then_approve`, `test_approval::test_request_changes`, `test_approval::test_open_ide_needs_command`.
- PASS: External waiting: `wait`, `poll` with 60 s timeout, `external-done`, resume of a gone session, paused tasks not polled. Evidence: `test_waiting::*`, `test_engine::test_done_check_timeout`.
- PASS: Pause and resume: saves status, waits for idle or stops, closes terminal, resume with `--resume <session-id>`, restores status, pause all. Evidence: `test_session::test_pause_saves_status_and_closes`, `test_session::test_pause_wait_uses_wait_idle`, `test_session::test_resume_restores_status_same_session`, `test_session::test_pause_all`, e2e "pause closes the task terminal", "resume reopens the Claude process with --resume and the same session id", "the same Claude transcript file exists and grew after resume".
- PARTIAL: Pause and resume at orchestrator level: Exit asks to pause all; start offers to resume all, some or none; resume of a task without the `state` capability warns first. Evidence: `SKILL.md` lines 23, 48, 57. Conversation not run end to end.
- PASS: Artifacts in `.factory/tasks/<id>/artifacts/`, `factory artifact path` creates the folder, works from a worktree, archived tasks keep them. Evidence: `test_config_state::test_state_set_get_and_artifact_path`, `test_config_state::test_artifact_name_must_be_simple`, `test_delete::test_delete_refuses_without_confirm_then_archives`.

## Backlog

- PASS: `.factory/backlog.md` entry format (heading, id line, optional pipeline, summary), file order is priority, stable id, hand-written entries get an id. Evidence: `test_backlog::test_add_list_remove_move`, `test_backlog::test_hand_written_file_is_kept`.
- PARTIAL: Built-in steps `backlog-add` and `backlog-remove` run in the orchestrator. Evidence: `builtin/steps/backlog-add.md`, `backlog-remove.md`, `test_backlog::test_add_list_remove_move`. Conversation not run.
- PASS: Launch from a backlog entry: title becomes description, summary saved in state, entry removed after success. Evidence: `test_backlog::test_launch_from_backlog`, `test_backlog::test_failed_launch_keeps_entry`.
- PARTIAL: End of Init asks for backlog import, parses and adds after approval. Evidence: `SKILL.md` line 39, `test_backlog::test_import`. The question is conversation only.

## Orchestrator

- PASS: Menu is shown with the available actions, always, after each action. Evidence: `SKILL.md` lines 25-29, `test_init_menu::test_menu_before_and_after_init`. Whether Claude follows it in a live run is not tested.
- PASS: Menu is a numbered text list, one heading per group, one number sequence; `AskUserQuestion` is not used. Evidence: `SKILL.md` lines 27-28, `test_skill::test_skill_frontmatter_and_menu_rule`. The rule is in the skill and checked by a test; a live Claude run is not tested.

## Init

- PASS: Init checks prerequisites and reports each as OK or failing with the fix (terminal check, git repo with `origin`, `uv`). Evidence: `test_init_menu::test_init_reports_failed_prerequisite`, `test_init_menu::test_init_creates_files_and_exclude`.
- PASS: Saves `terminal: herdr` without asking, saves `library`, creates the library with `factory.yaml`, `steps/`, `pipelines/` when asked, warns when not in git. Evidence: `test_init_menu::test_init_creates_files_and_exclude`, `test_init_menu::test_init_needs_existing_library_or_flag`, `test_library::test_disabled_without_git`.
- PASS: Creates `.factory/` with files and empty folders; never overwrites. Evidence: `test_init_menu::test_init_creates_files_and_exclude`, `test_init_menu::test_init_never_overwrites`.
- PASS: Adds `.factory/` and `.factory.backup-*/` to `.git/info/exclude`; `.gitignore` unchanged. Evidence: `test_init_menu::test_init_creates_files_and_exclude`.
- PARTIAL: Init offers the starter pack and ends with backlog import. Evidence: `SKILL.md` lines 35-39, `test_catalog::test_list_and_install_pipeline_with_missing_steps`, `test_backlog::test_import`. The Init conversation is not run end to end.

## Factory CLI

- PASS: `factory` CLI is the only way to read and write `.factory/`; finds the main repo from any worktree with `git rev-parse --git-common-dir`; finds the task from the worktree path. Evidence: `test_repo_version::test_main_repo_from_worktree`, `test_repo_version::test_current_task_matches_symlinked_path`.
- PASS: Task without worktree uses `--task <id>` in prompts, `next` output and subagent prompt; a missing flag fails with a message. Evidence: `test_launch::test_no_worktree_pipeline_uses_task_flag`, `test_repo_version::test_unknown_task_says_add_task`, `test_engine::test_next_tells_session_about_block_skip_and_goto`.
- PASS: Atomic writes and locking, no lost write from two processes. Evidence: `test_fsio::test_atomic_write_creates_parents_and_leaves_no_temp`, `test_fsio::test_two_processes_lose_no_write`, `test_backlog::test_two_processes_lose_no_write`.
- PASS: Three levels merged, first wins (local, generic, built-in). Evidence: `test_registry::test_local_overrides_generic_overrides_builtin`.
- PASS: Every listed command exists. Evidence: `test_docs::test_readme_commands_exist`, `test_docs::test_skill_and_builtin_commands_exist`.

## Terminal adapter

- PASS: All terminal actions go through `factory terminal`; launch and delete call only the adapter, never `herdr`. Evidence: `test_delete::test_launch_and_delete_never_call_herdr`, `test_adapters::test_fake_records_calls`.
- PASS: Adapter interface (`check`, `start-session`, `close`; optional `send-prompt`, `focus`, `state`, `wait-idle`, `notify`) with unsupported actions hidden; adding a terminal means one adapter. Evidence: `test_adapters::test_capabilities_and_check`, `software-factory/lib/factory/adapters/`.
- PASS: Herdr adapter: `check` is `HERDR_ENV=1`; worktree open or tab create; `agent start` and `agent prompt`; pane id from JSON; handle; `close` stops Claude and closes workspace or tab; other commands. Evidence: `test_herdr_adapter::*`, `herdr-probe.md`, e2e "Claude runs in Herdr named with the task id", "pause closes the task terminal", "no Herdr workspace or tab is left open after the run".

## Versioning and migration

- PASS: Data format version (integer from 1) in `.factory/factory.yaml` and `<library>/factory.yaml`; every command refuses a different version. Evidence: `test_repo_version::test_version_mismatch_refused`, `test_repo_version::test_version_report_states`, `test_migrate::test_newer_refused`.
- PASS: Migration mechanism for scripts `migrations/<from>-to-<to>`; test migration 1 to a fake 2 runs and creates the backup. Evidence: `test_migrate::test_older_refused_then_migrated`. `software-factory/migrations/` is empty on purpose: this build is version 1, so no real migration exists yet.
- PARTIAL: At start the orchestrator compares versions: same shows menu, older runs `migrate` first, newer stops. Evidence: `SKILL.md` lines 19-22, `test_repo_version::test_version_report_states`, `test_migrate::test_older_refused_then_migrated`. Conversation not run.
- PASS: `migrate` backs up `.factory/`, requires a clean library git status (else backs up the library), runs scripts on repository data, active tasks and library, shows a summary. Evidence: `test_migrate::test_dirty_library_refused`, `test_migrate::test_shared_library_migrated_once`, `builtin/steps/migrate.md`.

## Rebuild

- PASS: `FACTORY_SOURCE` holds no user data; a rebuild never changes a library or `.factory/` except through a migration. Evidence: `software-factory/` contains only code, builtin, catalog, migrations, tests, README (no `.factory/`); `test_migrate::*`.

## File organization

- PASS: `.factory/` layout (factory.yaml, config.yaml, claude-settings.json, backlog.md, server.json, pipelines/, steps/, tasks/<id>/{task.json, events.jsonl, artifacts/}, tasks/archive/). Evidence: `test_init_menu::test_init_creates_files_and_exclude`, `test_server::test_server_info_file_is_private`, `test_delete::test_delete_refuses_without_confirm_then_archives`.
- PASS: `FACTORY_SOURCE` layout (`builtin/{pipelines,steps}`, `catalog/{pipelines,steps}`, `migrations/`) and the library layout. Evidence: `ls software-factory/`, `test_init_menu::test_init_needs_existing_library_or_flag`.

## Documentation

- PASS: `README.md` has what it does, concepts, install and prerequisites, a 6-step tutorial with expected results, reference (menu actions, commands, step and pipeline fields), troubleshooting; simple English. Evidence: `software-factory/README.md`, `test_docs::test_readme_sections`. Tutorial steps were not followed by hand.

## Verification

- PASS: Automated test run with report in `VERIFICATION_DIR`, one section per milestone. Evidence: `verification/software-factory/report.md`, `junit.xml`, `software-factory/tests/report.py`.
- PASS: Test setup in `VERIFICATION_DIR`: test repo with local bare `origin`, test library in its own git repo, `worktree_root` inside `VERIFICATION_DIR`. Evidence: `software-factory/tests/conftest.py`, `tests/e2e_herdr.py`, `verification/software-factory/work/e2e/`.
- PASS: CLI: init, exclude entries, `.gitignore` unchanged. Evidence: `test_init_menu::test_init_creates_files_and_exclude`.
- PASS: CLI: local overrides generic overrides built-in. Evidence: `test_registry::test_local_overrides_generic_overrides_builtin`.
- PASS: CLI: config order and ask when missing. Evidence: `test_config_state::test_config_order`, `test_engine::test_missing_config_asks`.
- PASS: CLI: `next`, `done`, `skip`; `done_check` pass and fail; required skip refused. Evidence: `test_engine::test_next_done_check_fails_then_passes`, `test_engine::test_skip_refused_for_required_and_composite_path`.
- PASS: CLI: composite steps. Evidence: `test_registry::test_composite_paths_and_io`, `test_registry::test_composite_loop_refused`.
- PASS: CLI: `create-worktree` not first is refused. Evidence: `test_launch::test_create_worktree_listed_late_refused`.
- PASS: CLI: backlog add, list, remove, move; hand-written entry gets an id; launch from entry saves summary and removes entry. Evidence: `test_backlog::test_add_list_remove_move`, `test_backlog::test_hand_written_file_is_kept`, `test_backlog::test_launch_from_backlog`.
- PASS: CLI: event log has the expected events. Evidence: `test_event_log::test_all_event_types`.
- PASS: CLI: version refusal and test migration with backup. Evidence: `test_repo_version::test_version_mismatch_refused`, `test_migrate::test_older_refused_then_migrated`.
- PASS: CLI: `pipeline check` reports each error and warning type. Evidence: `test_pipeline_check::test_each_problem_type`.
- PASS: CLI: editor server API without a browser; missing token or wrong Origin rejected. Evidence: `test_editor_api::*`, `test_server::test_security_checks`.
- PASS: CLI: dashboard API without a browser (task list with column, status, session state; actions call the CLI functions with the fake adapter; backlog move; launch dry run). Evidence: `test_dashboard_api::*`, `test_board::test_session_state_column`.
- PASS: CLI: second `factory dashboard` reuses the running server. Evidence: `test_server::test_server_survives_the_command_and_is_reused`.
- PASS: CLI: with a fake adapter, launch and delete call only the adapter. Evidence: `test_delete::test_launch_and_delete_never_call_herdr`.
- PASS: CLI: block, unblock, tasks list order. Evidence: `test_board::test_block_unblock_and_order`.
- PASS: CLI: pause saves status and closes; resume restores status with the same session id. Evidence: `test_session::test_pause_saves_status_and_closes`, `test_session::test_resume_restores_status_same_session`.
- PASS: CLI: worktree creation cases (new, behind, remote only, diverged, in use). Evidence: `test_launch::test_new_branch`, `test_launch::test_existing_local_branch_behind_is_fast_forwarded`, `test_launch::test_remote_only_branch`, `test_launch::test_diverged_branch_stops`, `test_launch::test_branch_in_other_worktree_stops`.
- PASS: CLI: goto back, forward refused, 3rd jump blocks. Evidence: `test_goto::*`.
- PASS: CLI: `artifact path` from main repo and worktree. Evidence: `test_config_state::test_state_set_get_and_artifact_path`.
- PASS: CLI: subagent step prints the Agent call; pipeline value wins. Evidence: `test_engine::test_subagent_call_model_effort_precedence`.
- PASS: CLI: `pipeline check` warns about `model`/`effort` on a session step. Evidence: `test_pipeline_check::test_each_problem_type`.
- PASS: CLI: catalog install and status. Evidence: `test_catalog::test_list_and_install_pipeline_with_missing_steps`.
- PASS: CLI: every README `factory` command exists. Evidence: `test_docs::test_readme_commands_exist`.
- PASS: CLI: no catalog file refers to a project-specific skill or tool. Evidence: `test_catalog::test_catalog_is_generic`.
- PASS: CLI: `catalog list` shows missing `requires`. Evidence: `test_catalog::test_missing_requires`.
- PARTIAL: CLI runs on a machine with only `uv` installed. Evidence: `test_scaffold::test_uv_installs_dependencies_on_first_run`. Run on a machine that has other tools; a bare machine was not available.
- PASS: CLI: `start_column`, column move, pipeline wins, unknown column error. Evidence: `test_board::test_columns_follow_steps`, `test_board::test_launch_uses_start_column`, `test_pipeline_check::test_each_problem_type`.
- PASS: CLI: approval flow. Evidence: `test_approval::test_awaiting_approval_then_approve`, `test_approval::test_request_changes`.
- PASS: CLI: `wait`, `poll`, `external-done`. Evidence: `test_waiting::*`.
- PASS: CLI: `launch --dry-run` reports id, worktree path, branch case, changes nothing; taken id gets suffix. Evidence: `test_launch::test_dry_run_changes_nothing_and_reports`, `test_launch::test_taken_id_gets_suffix`.
- PASS: CLI: failed session start rolls back worktree, branch and task folder. Evidence: `test_launch::test_failed_start_rolls_back_but_keeps_existing_branch`.
- PASS: CLI: `delete --dry-run` and `--confirm-unpushed`. Evidence: `test_delete::test_dry_run_shows_changes_and_changes_nothing`, `test_delete::test_delete_refuses_without_confirm_then_archives`.
- PASS: CLI: two processes write `config.yaml` and `backlog.md` without loss. Evidence: `test_fsio::test_two_processes_lose_no_write`, `test_backlog::test_two_processes_lose_no_write`.
- PASS: CLI: task without worktree prints `--task <id>`. Evidence: `test_launch::test_no_worktree_pipeline_uses_task_flag`, `test_repo_version::test_unknown_task_says_add_task`.
- PASS: CLI: last `done` sets `finished` and logs `task_finished`. Evidence: `test_engine::test_last_done_finishes`.
- PASS: CLI: focus and send prompt call the adapter; hidden when unsupported. Evidence: `test_session::test_send_prompt_and_focus`, `test_adapters::test_capabilities_and_check`.
- PASS: CLI: `clean` merge cases. Evidence: `test_clean::test_clean_detects_merge_cases`.
- PASS: CLI: `library commit` commits only the given files, other staged file stays staged. Evidence: `test_library::test_commit_only_given_files`.
- PASS: E2E: launch fetches `origin`, creates worktree from `origin/main`, opens it in Herdr, starts Claude named with the task id, first prompt received. Evidence: e2e checks 1 to 3 in `e2e-results.json`.
- PASS: E2E: two `script` steps run to the end with `factory next` and `factory done`. Evidence: e2e "first script step runs with factory next and factory done", "the resumed session continues the pipeline to the end".
- PASS: E2E: Claude starts with `.factory/claude-settings.json`, never waits on a permission prompt. Evidence: e2e "the session never waits on a permission prompt" (14 samples, blocked 0, error 0).
- PASS: E2E: pause closes the terminal; resume reopens the same Claude session, which continues. Evidence: e2e pause, resume, transcript-grew checks.
- PASS: E2E: delete asks approval with uncommitted changes, closes terminal, removes worktree, archives the task folder. Evidence: e2e delete checks.
- PASS: Tests close only the Herdr workspaces, tabs and panes they created. Evidence: `test_herdr_adapter::test_preexisting_workspace_never_closed`, `test_herdr_adapter::test_workspace_with_other_tab_only_our_tab_closed`, e2e "no Herdr workspace or tab is left open after the run".
- PARTIAL: At the end, the tests remove the test repositories; the report stays. Evidence: pytest repos are in temp folders and removed. The e2e keeps `verification/software-factory/work/e2e/repo` on purpose (Claude trust is per path; `clear_root_keeping_repo` in `tests/e2e_herdr.py`). It is git-ignored and untracked.

## Remaining blockers and open items

No FAIL items. PARTIAL items:

1. Editor page: human browser check pending (`editor-manual-check.md` items 1 to 8, dark and light mode).
2. Dashboard page: human browser check pending (`dashboard-manual-check.md`, section "Still needs a human browser check"): cards and tint colors, hidden columns saved in the browser, 5 s refresh keeping an open form, Herdr-off banner, backlog drag and drop, launch form states, Clean dialog with unpushed work, Pause dialog.
3. Orchestrator conversation behaviour (menu shown as numbered text, Init flow, Exit asks to pause, resume-at-start question, migrate-at-start, new-step-assistant dialogue, backlog import question) is not run end to end by any test. The `SKILL.md` text and the CLI tests cover it.
4. `uv` on a bare machine (no Python 3.12, no other tools) was not tested.
5. The e2e keeps `verification/software-factory/work/e2e/repo`, because the user trusted that folder once in Claude (the Claude trust dialog). Deleting it means trusting a new folder on the next e2e run. The folder is git-ignored.
