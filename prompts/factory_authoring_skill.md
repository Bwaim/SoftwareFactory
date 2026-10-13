# Software factory: authoring skill

## Problem

To create a pipeline and its steps with an AI agent, I must open the factory first:
- The agent does not know the step and pipeline formats. The format reference is in the README of the plugin, and the agent does not read it.
- The only safe way to create a step is the step form in the pipeline editor.
- I want to write a prompt file that describes a pipeline, give it to an agent, and get the files, like a normal feature in code.

## Solution

- A second skill in the factory plugin: `factory-authoring`.
- It loads in any Claude session, without the factory orchestrator, when the user asks to create or change factory pipelines or steps.
- The agent writes the step and pipeline files directly. It checks them with `factory pipeline check`, the same way code is checked with tests, and fixes them until the check passes.
- No new CLI command. No change to the step and pipeline formats.

## Variables

- `PROJECT_ROOT: /Users/fabienboismoreau/Documents/Projects/SoftwareFactory/SoftwareFactory`
- `SPEC_DIR: <PROJECT_ROOT>/specs/`
    - Save your own spec here.
- `PLAN_DIR: <PROJECT_ROOT>/plans/`
    - Save your own plan here.
- `YOUR_WORKING_DIR: <PROJECT_ROOT>/software-factory/`
    - The existing factory. Save your work here.
- `VERIFICATION_DIR: <PROJECT_ROOT>/verification/software-factory/`
    - Save your verification artifacts here.
- `MAIN_PROMPT: <PROJECT_ROOT>/prompts/factory_skill_creation.md`
    - The full factory requirements. Read it for context. It already contains these changes.

## Workflow

1. Read. Read `MAIN_PROMPT`, `YOUR_WORKING_DIR/README.md`, `YOUR_WORKING_DIR/skills/software-factory/SKILL.md` and the factory code that loads and checks steps and pipelines, so the skill matches the real rules.
2. Brainstorm. Use the `/superpowers:brainstorming` skill to create a specification file from these requirements. Save the specification file in `SPEC_DIR/` before writing the plan.
3. Ask validation. Ask the user to validate the specification file.
4. Plan. After specification validation, use the `/superpowers:writing-plans` skill to create an implementation plan from the specification file. Save the plan file in `PLAN_DIR/` before writing implementation code. One milestone is enough.
5. Ask validation. Ask the user to validate the plan file.
6. Build. After plan validation, create the branch `authoring-skill` from `master`. Use the `/superpowers:subagent-driven-development` skill to implement the plan inside `YOUR_WORKING_DIR`. Run the full test suite of the factory, fix the failures, and commit. Do not skip straight from this prompt to implementation.
7. Verify. Check every item in Definition Of Done, fix failures, and rerun the affected checks. Keep final verification artifacts inside `VERIFICATION_DIR` and report actual results and any remaining blockers.

## Definition Of Done

### Workflow Complete

- Your completed implementation plan exists under `PLAN_DIR/`
    - It was written before implementation, and the build followed its build step.
- The work is on the branch `authoring-skill`. `master` is unchanged.
- Every existing test still passes, or is updated because its behavior changed on purpose. The report lists each updated test and why.

### Skill

- The skill file is `YOUR_WORKING_DIR/skills/factory-authoring/SKILL.md`. The plugin loads it next to the `software-factory` skill.
- Its description makes Claude load it when the user asks to create or change software factory pipelines or steps, or gives a file that describes them. Example: "Implement `prompts/crash-pipeline.md`".
- The user can also call it directly: `/factory-authoring <file or request>`.
- It works without the factory orchestrator, the local server or the browser.

### Format reference

The skill contains everything the agent needs to write valid files, without reading the README:
- Where files go:
  - Local: `.factory/steps/<id>.md` and `.factory/pipelines/<id>.yaml` in the main repository.
  - Generic: `<library>/steps/<id>.md` and `<library>/pipelines/<id>.yaml`. The library path is the `library` key of `.factory/factory.yaml`.
  - Built-in steps are never changed. To change one, write a local step with the same id.
  - Local wins over generic, and generic wins over built-in.
- Ids and key names, with their rules and examples.
- Key types `text`, `long-text`, `file`, and the factory keys `task_id`, `description`, `summary`, with "maybe set" for `summary`.
- Every step manifest field, with its allowed values, and the fields that apply only to `ai` steps or only to `group` steps.
- The three step types:
  - `ai`: the exact prompt, `{{<key>}}` and `{{config.<key>}}` placeholders, single braces stay text, the outputs footer added by the factory.
  - `command`: a shell command run with `bash` in the task worktree, `"$FACTORY_KEY_<KEY>"`, `"$FACTORY_CONFIG_<KEY>"` and `"$FACTORY_STEP_DIR"` always in double quotes, no `{{...}}`, a script file next to the step, and the command sets its own outputs with `factory state set`.
  - `group`: a `steps` list of child step ids, no body, no loop.
- Outputs, `optional`, `done_when` and `done_check`, and the order of the checks of `factory done`.
- `config` with descriptions and defaults, and `with` in a pipeline entry.
- Every pipeline field and typed `inputs`.
- The `create-worktree` rule: the factory adds it as the first step. A pipeline lists it only to set `with` values, and only as its first step.
- One complete example of each step type and one complete example pipeline that uses them, with an input, an output used by a later step and a config value.

### Workflow of the skill

1. Find the main repository and check that `.factory/factory.yaml` exists. If not, stop and tell the user to add the factory to the repository first.
2. Read the request or the prompt file. Ask the user only what the file does not say. When the level is not given, use local.
3. List the existing steps with `factory step list --all --json` and the pipelines with `factory pipeline list --json`. Reuse an existing step when it does the job. Never create a step with the id of an existing step at the same level.
4. Plan the key flow: each key a step uses comes from an input, an output of an earlier step or a factory key.
5. Write the step files, then the pipeline files.
6. Check:
   - Run `factory pipeline check <id>` for each new or changed pipeline, and for each pipeline that uses a changed step.
   - An error names the file and the problem. Fix the file and run the check again, until there is no error.
   - Read each warning. Fix it, or tell the user why it stays.
   - Run `factory pipeline keys <id>` and check that every key a step uses is available at its position.
7. For a changed generic step or pipeline, tell the user that other repositories that use the library are not checked.
8. For new or changed generic files, offer the library commit with `factory library commit "<message>" <paths...>`. The message follows the existing rule, for example `Factory library: add step <id>`. Local files are never committed: `.factory/` is excluded from git.
9. Report the files created or changed, their level, and the check results. Tell the user they can review them with `factory pipeline edit <id>`.

### Rules of the skill

- Never edit a built-in step or pipeline file.
- Never edit task files under `.factory/tasks/`.
- Never change a step that an unfinished task uses without telling the user. Unfinished tasks are listed by `factory tasks`.
- A step that calls a skill is an `ai` step whose prompt calls the skill. `requires` lists the skill.

### Orchestrator and documentation

- The `software-factory` skill menu is unchanged.
- The README describes the `factory-authoring` skill: what it does, how to call it, and an example request with a prompt file.
- The README tutorial gets no new step.
- The README and the skill use simple English and short sentences.

### Verification

- The build is verified with an automated test run. Its report goes to `VERIFICATION_DIR/authoring-skill-report.md`, with the tests run, their results and the result of the full test suite.
- Test setup: the same as the existing factory tests. A test repository, a test library in its own test git repository, never a real library or a real `.factory/`.
- CLI tests, without Herdr or Claude:
  - The skill file exists, and its frontmatter has `name: factory-authoring` and a `description`.
  - Every `factory` command written in the skill exists in the CLI.
  - The example steps and the example pipeline of the skill, copied into a test repository, load with the factory code, and `factory pipeline check` on the example pipeline gives no error and no warning.
  - Every step manifest field and pipeline field that the factory code accepts is described in the skill.
  - Every built-in step id named in the skill exists.
- Manual check list in `VERIFICATION_DIR/authoring-skill-manual-check.md`, for the user to run in a test repository:
  - In a normal Claude session, ask "Implement `<prompt file>`" with a prompt file that describes a pipeline with one `ai` step, one `command` step with a `file` output, and a pipeline input. The skill loads, the files are written, and `factory pipeline check` passes.
  - Launch that pipeline and run it to the end.
  - Ask for a generic step. The library commit is offered.
  - Ask to change a step that a pipeline uses. The agent checks that pipeline too.

## How You're Graded

- You'll be graded on a continuous basis based on every completed bullet in the Definition Of Done.
- Every step of Workflow must be fully accomplished: plan, build and verify.
- Instant failure if you write project deliverables outside `YOUR_WORKING_DIR` with the exception of `SPEC_DIR`, `PLAN_DIR` and `VERIFICATION_DIR`.
- Instant failure if you read any part of any file inside `<PROJECT_ROOT>/specs/*` that isn't your own spec.
- Instant failure if you change a real library or a real `.factory/` folder. Tests use test repositories only.
- Instant failure if you close a Herdr workspace, tab, pane or session you did not create.
- Running tools outside these directories is allowed. Temporary files and tool-managed runtime data (caches, logs, browser profiles, updater logs) may use their normal locations and are not grading failures.
- If you find you've mistakenly caused a failure, stop immediately and report your failure.
