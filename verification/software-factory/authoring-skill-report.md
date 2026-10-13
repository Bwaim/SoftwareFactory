# Authoring skill verification report

Date: 2026-10-13 21:41

## Milestone 1. Authoring skill

14 of 14 tests pass.

| Test | Result |
|---|---|
| `test_authoring_skill::test_skill_file_and_frontmatter` | PASS |
| `test_authoring_skill::test_skill_commands_exist` | PASS |
| `test_authoring_skill::test_fallback_factory_path_exists` | PASS |
| `test_authoring_skill::test_examples_load_and_check_clean` | PASS |
| `test_authoring_skill::test_example_command_step_runs` | PASS |
| `test_authoring_skill::test_every_field_is_described` | PASS |
| `test_authoring_skill::test_named_builtin_steps_exist` | PASS |
| `test_authoring_skill::test_readme_describes_authoring_skill` | PASS |
| `test_docs::test_readme_commands_exist` | PASS |
| `test_docs::test_skill_and_builtin_commands_exist` | PASS |
| `test_docs::test_readme_sections` | PASS |
| `test_docs::test_checker_scans_fenced_blocks_and_inline_spans_but_not_prose` | PASS |
| `test_docs::test_readme_describes_step_editor` | PASS |
| `test_skill::test_skill_frontmatter_and_menu_rule` | PASS |

## Full test suite

357 of 357 tests pass.

## Orchestrator skill

`git diff master -- software-factory/skills/software-factory/SKILL.md` is empty. The menu is unchanged.

## Updated tests


None. No existing test changed.

## Definition Of Done

### Workflow Complete

- The plan exists under `plans/2026-10-13-authoring-skill.md`. It was committed before the implementation, in the first commit of the branch.
- The work is on the branch `authoring-skill`. `master` is unchanged.
- Every existing test still passes: see "Full test suite" above. Updated tests: see "Updated tests" above.

### Skill

- The skill file is `skills/factory-authoring/SKILL.md`. The plugin finds every `skills/<name>/SKILL.md`, so `plugin.json` is unchanged: covered by `test_authoring_skill::test_skill_file_and_frontmatter`.
- The description names pipelines, steps and the "Implement" example: covered by `test_skill_file_and_frontmatter`. Loading it from a request: manual check 1.
- Direct call `/factory-authoring <file or request>`: `argument-hint` and `$ARGUMENTS` in the skill. Manual check 5.
- No orchestrator, server or browser: the workflow uses only CLI commands. The fallback path to `bin/factory`: covered by `test_fallback_factory_path_exists`.

### Format reference

- Where files go, levels, override of built-in steps: the "Where files go" section of the skill.
- Ids and key names, key types, factory keys with "maybe set": the "Ids and key names" and "Key types" sections.
- Every step manifest field and every pipeline field: covered by `test_every_field_is_described`.
- The three step types, outputs, `done_when`, `done_check`, the order of the checks of `factory done`, `config` and `with`, typed `inputs`, the `create-worktree` rule: the sections of the same names in the skill.
- One example of each type and one pipeline with an input, an output used later and a config value: covered by `test_examples_load_and_check_clean` and `test_example_command_step_runs`.

### Workflow of the skill

- Steps 1 to 9 of the prompt: the "Workflow" section of the skill. Every `factory` command in it exists: covered by `test_skill_commands_exist`. Behavior with an agent: manual checks 1 to 4.

### Rules of the skill

- Built-in files, task files, unfinished tasks (with `path`), generic pipelines use generic or built-in steps, steps that call a skill: the "Rules" section of the skill.

### Orchestrator and documentation

- The `software-factory` skill is unchanged: see "Orchestrator skill" above.
- The README section and its example: covered by `test_readme_describes_authoring_skill`. No tutorial step: the same test.

### Verification

- This report, the CLI tests above, and the manual check list `authoring-skill-manual-check.md`.
- Built-in step ids named in the skill exist: covered by `test_named_builtin_steps_exist`.
