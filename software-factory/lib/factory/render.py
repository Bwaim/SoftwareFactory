from . import keys

NOT_SET = "(not set)"
IF_NEEDED = [
    "If needed:",
    '- If you cannot continue without the user, run `factory block "<question>"`, ask the user, then run `factory unblock` when the user answers.',
    "- Only after the user approves: skip this step with `factory skip`, or go back to an earlier step with `factory goto <step path> --reason \"<why>\"`.",
]
SESSION_END = "When the step is done, run `factory done`."
WAIT_END = "When the actions of this step are done, run `factory wait`. The factory tells you when the external event happens."
SUBAGENT_END = "End with a short report. If you need an answer from the user, say so in the report and stop."
SUBAGENT_AFTER = "When the subagent ends, read its report. If it needs the user, ask the user, then run `factory next` again. Otherwise run `factory done`."
COMMAND_RUN = "Run `factory run-command`. It runs the step command and prints its output and its exit code."
COMMAND_OUTPUTS = "The command sets these outputs. Never set them yourself and never write their files. If one is missing, run `factory block` and tell the user that the step command did not set it."
COMMAND_RETRY = "If the exit code is not 0, fix the cause or ask the user, then run `factory run-command` again."
SEPARATOR = "---"


def fill(text, values, config_values):
    def sub(m):
        inner = m.group(1)
        if inner.startswith(keys.CONFIG_PREFIX):
            value = config_values.get(inner[len(keys.CONFIG_PREFIX):])
        else:
            value = values.get(inner)
        return NOT_SET if value is None or value == "" else str(value)
    return keys.PLACEHOLDER_RE.sub(sub, text or "")


def show_names(text):
    return keys.PLACEHOLDER_RE.sub(lambda m: f"<{m.group(1)}>", text or "")


def output_name_line(name, out):
    flag = ", optional" if out["optional"] else ""
    desc = out["description"].strip().rstrip(".")
    return f"- `{name}` ({out['type']}{flag})" + (f": {desc}." if desc else ".")


def output_line(name, out):
    line = output_name_line(name, out) + " "
    if out["type"] == "file":
        return line + f"Set it with `factory state set {name} <path>`. Get a path in the artifacts folder with `factory artifact path <name>`."
    return line + f"Set it with `factory state set {name} <value>`."


def output_lines(outputs, title):
    if not outputs:
        return []
    return [title] + [output_line(name, out) for name, out in outputs.items()]


def end_line(step):
    return WAIT_END if step.wait_external else SESSION_END


def loop_lines(step, loop_keys):
    if step.type == "command":
        return [f"This step controls a loop. The command sets `{key}` to `none` when nothing is left." for key in loop_keys]
    return [f"This step controls a loop. Set `{key}` to `none` when nothing is left." for key in loop_keys]


def footer(step_line, step, outputs, last, help_lines, extra=()):
    lines = [SEPARATOR, step_line] + output_lines(outputs, "Outputs to set:") + list(extra)
    if step.done_when:
        lines.append(f"Done when: {step.done_when}")
    if help_lines:
        lines += IF_NEEDED
    return lines + [last]


def prompt_with_footer(prompt, step_line, step, outputs, last, help_lines, extra=()):
    return "\n".join([prompt.rstrip("\n"), ""] + footer(step_line, step, outputs, last, help_lines, extra))


def subagent_text(prompt, step_line, step, outputs, model, effort, extra=()):
    inner = prompt_with_footer(prompt, step_line, step, outputs, SUBAGENT_END, False, extra)
    return "\n".join([step_line, "Run this step in a subagent. Call the Agent tool with:",
                      f"- model: {model or 'inherit'}", f"- effort: {effort or 'inherit'}",
                      "- prompt:", "<<<", inner, ">>>", WAIT_END if step.wait_external else SUBAGENT_AFTER])


def command_text(step_line, step, outputs, extra=()):
    lines = [step_line, COMMAND_RUN]
    if outputs:
        lines += [COMMAND_OUTPUTS] + [output_name_line(name, out) for name, out in outputs.items()]
    lines += list(extra)
    if step.done_when:
        lines.append(f"Done when: {step.done_when}")
    return "\n".join(lines + [COMMAND_RETRY] + IF_NEEDED + [end_line(step)])


def step_text(step, prompt, step_line, outputs, model=None, effort=None, loop_keys=()):
    extra = loop_lines(step, loop_keys)
    if step.type == "command":
        return command_text(step_line, step, outputs, extra)
    if step.run_in == "subagent":
        return subagent_text(prompt, step_line, step, outputs, model, effort, extra)
    return prompt_with_footer(prompt, step_line, step, outputs, end_line(step), True, extra)
