# Real attention check

Date: 2026-10-16T15:29:21+02:00
Claude version: 2.1.301 (Claude Code)
Result: PASS

## Commands

- `factory init --library <lib> --create-library`
- `factory config set create-worktree worktree_root <work>/worktrees`
- `factory launch plain --description "real check"`
- `claude -p 'Ask me which color I prefer, in plain text. Do not use any tool. Then stop.' --session-id <task session_id> --settings <repo>/.factory/claude-settings.json --model haiku`

Environment: FACTORY_TERMINAL=fake, FACTORY_ATTENTION_DELAY=2, temp repo, temp library, task `real-check`.

Claude exit code: 0, duration 6.9 s.

Claude output:

```
Which color do you prefer?
```

## Attention in task.json

```json
{
  "at": "2026-10-16T13:29:15.979427+00:00",
  "message": "Which color do you prefer?"
}
```

## Notify calls on the fake adapter

- real-check may wait for you: Which color do you prefer?

## Task events about attention

```json
{"ts": "2026-10-16T13:29:15+00:00", "type": "attention", "step": null, "message": "Which color do you prefer?"}
```
