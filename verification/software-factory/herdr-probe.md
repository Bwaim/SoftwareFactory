# Herdr probe (herdr 0.9.3)

Probe run on 2026-10-12. S1 = trusted folder under the project (`verification/software-factory/work/probe-s1`). S2 = `$TMPDIR/sf-probe-s2-456A64` (outside any project). In both setups Claude stopped at the folder trust dialog, which was NOT accepted, so Claude never started. Q3, Q5 and Q6 (partly) could not be answered the way the brief describes; see each answer.

Note: the `claude` launched in the pane is a shell wrapper that prepends `--append-system-prompt-file .../sr_opus_5_system_prompt.md`. Note also: `herdr agent start` has no `--cwd`; the pane must be at a shell prompt.

## Objects created

- S1: workspace `w1H`, tab `w1H:t1`, pane `w1H:p1`, agent `sf-probe-s1` (closed with `workspace close w1H`)
- S2: workspace `w1K`, tabs `w1K:t1`, `w1K:t2`, panes `w1K:p1`, `w1K:p2`, agents `sf-probe-s2`, `sf-probe-r` (closed with `workspace close w1K`)
- Side effect: `worktree open --cwd <repo>` also created a workspace for the main repo dir, label not `sf-probe`: `w1G` (S1, label SoftwareFactory, 1 pane) and `w1J` (S2, label repo, 1 pane). They are not in any JSON the commands returned. The auto mode classifier refused my `workspace close` on them, so they may still be open.

## Q1: keys of `worktree open`

Yes. `result.root_pane` holds `pane_id` and `workspace_id` (also `tab_id`, `cwd`, `terminal_id`, `agent_status`). Top-level keys of `result`: `already_open, root_pane, tab, type, workspace, worktree`. `result.workspace.workspace_id` and `result.tab.tab_id` exist too. A fixed `--workspace <ID>` option and `--trust-repository` option also exist on `worktree open` (not used).

S1 output:
```json
{"id":"cli:worktree:open","result":{"already_open":false,"root_pane":{"agent_status":"unknown","cwd":"/Users/fabienboismoreau/Documents/Projects/SoftwareFactory/SoftwareFactory/verification/software-factory/work/probe-s1/wt","focused":false,"foreground_cwd":"/Users/fabienboismoreau/Documents/Projects/SoftwareFactory/SoftwareFactory/verification/software-factory/work/probe-s1/wt","pane_id":"w1H:p1","revision":0,"scroll":{"max_offset_from_bottom":0,"offset_from_bottom":0,"viewport_rows":53},"tab_id":"w1H:t1","terminal_id":"term_65da716c8223e1c","workspace_id":"w1H"},"tab":{"agent_status":"unknown","focused":false,"label":"1","number":1,"pane_count":1,"tab_id":"w1H:t1","workspace_id":"w1H"},"type":"worktree_opened","workspace":{"active_tab_id":"w1H:t1","agent_status":"unknown","focused":false,"label":"sf-probe","number":12,"pane_count":1,"tab_count":1,"workspace_id":"w1H","worktree":{"checkout_path":"/Users/fabienboismoreau/Documents/Projects/SoftwareFactory/SoftwareFactory/verification/software-factory/work/probe-s1/wt","is_linked_worktree":true,"repo_key":"/Users/fabienboismoreau/Documents/Projects/SoftwareFactory/SoftwareFactory/verification/software-factory/work/probe-s1/repo/.git","repo_name":"repo","repo_root":"/Users/fabienboismoreau/Documents/Projects/SoftwareFactory/SoftwareFactory/verification/software-factory/work/probe-s1/repo"}},"worktree":{"is_bare":false,"is_detached":true,"is_linked_worktree":true,"is_prunable":false,"label":"repo","open_workspace_id":"w1H","path":"/Users/fabienboismoreau/Documents/Projects/SoftwareFactory/SoftwareFactory/verification/software-factory/work/probe-s1/wt"}}}
```

S2 output:
```json
{"id":"cli:worktree:open","result":{"already_open":false,"root_pane":{"agent_status":"unknown","cwd":"/private/var/folders/hj/g3l2tt954zz3qj2d5r89dgx40000gn/T/sf-probe-s2-456A64/wt","focused":false,"foreground_cwd":"/private/var/folders/hj/g3l2tt954zz3qj2d5r89dgx40000gn/T/sf-probe-s2-456A64/wt","pane_id":"w1K:p1","revision":0,"scroll":{"max_offset_from_bottom":0,"offset_from_bottom":0,"viewport_rows":53},"tab_id":"w1K:t1","terminal_id":"term_65da717bfb2581e","workspace_id":"w1K"},"tab":{"agent_status":"unknown","focused":false,"label":"1","number":1,"pane_count":1,"tab_id":"w1K:t1","workspace_id":"w1K"},"type":"worktree_opened","workspace":{"active_tab_id":"w1K:t1","agent_status":"unknown","focused":false,"label":"sf-probe","number":13,"pane_count":1,"tab_count":1,"workspace_id":"w1K","worktree":{"checkout_path":"/private/var/folders/hj/g3l2tt954zz3qj2d5r89dgx40000gn/T/sf-probe-s2-456A64/wt","is_linked_worktree":true,"repo_key":"/private/var/folders/hj/g3l2tt954zz3qj2d5r89dgx40000gn/T/sf-probe-s2-456A64/repo/.git","repo_name":"repo","repo_root":"/private/var/folders/hj/g3l2tt954zz3qj2d5r89dgx40000gn/T/sf-probe-s2-456A64/repo"}},"worktree":{"is_bare":false,"is_detached":true,"is_linked_worktree":true,"is_prunable":false,"label":"repo","open_workspace_id":"w1K","path":"/private/var/folders/hj/g3l2tt954zz3qj2d5r89dgx40000gn/T/sf-probe-s2-456A64/wt"}}}
```

`tab create` output (S2, `--workspace w1K --cwd ... --label sf-probe-q6 --no-focus`): `result.tab.tab_id` and `result.root_pane.{pane_id,workspace_id,tab_id}`.
```json
{"id":"cli:tab:create","result":{"root_pane":{"agent_status":"unknown","cwd":"/private/var/folders/hj/g3l2tt954zz3qj2d5r89dgx40000gn/T/sf-probe-s2-456A64/wt","focused":false,"foreground_cwd":"/private/var/folders/hj/g3l2tt954zz3qj2d5r89dgx40000gn/T/sf-probe-s2-456A64/wt","pane_id":"w1K:p2","revision":0,"scroll":{"max_offset_from_bottom":0,"offset_from_bottom":0,"viewport_rows":53},"tab_id":"w1K:t2","terminal_id":"term_65da71870ceda1f","workspace_id":"w1K"},"tab":{"agent_status":"unknown","focused":false,"label":"sf-probe-q6","number":2,"pane_count":1,"tab_id":"w1K:t2","workspace_id":"w1K"},"type":"tab_created"}}
```

## Q2: folder trust dialog

Yes, in both S1 and S2. Same text:
```text
fabienboismoreau@MacBook-Pro-de-Fabien wt % claude --name sf-probe-s1 --session-id 880b8d6a-8981-4bf2-bec1-0f20ac29b5c8

─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
 Accessing workspace:

 /Users/fabienboismoreau/Documents/Projects/SoftwareFactory/SoftwareFactory/verification/software-factory/work/probe-s1/wt

 Quick safety check: Is this a project you created or one you trust? (Like your own code, a well-known open source project, or work from your team). If not, take a moment to review what's
 in this folder first.

 Claude Code'll be able to read, edit, and execute files here.

 Security guide

 ❯ No, exit
   Yes, I trust this folder

 Enter to confirm · Esc to cancel
```
`agent start` exits 1 after the timeout window with a JSON error (stdout), code `agent_not_ready`:

S1:
```json
{"error":{"code":"agent_not_ready","message":"agent sf-probe-s1 is blocked during startup and is not ready for prompts"},"id":"cli:agent:start"}
```

S2:
```json
{"error":{"code":"agent_not_ready","message":"agent sf-probe-s2 is blocked during startup and is not ready for prompts"},"id":"cli:agent:start"}
```

S2 screen text (`agent read`):
```text
fabienboismoreau@MacBook-Pro-de-Fabien wt % claude --name sf-probe-s2 --session-id aa515e14-47d7-4bfb-9941-70a9206226c3

─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
 Accessing workspace:

 /private/var/folders/hj/g3l2tt954zz3qj2d5r89dgx40000gn/T/sf-probe-s2-456A64/wt

 Quick safety check: Is this a project you created or one you trust? (Like your own code, a well-known open source project, or work from your team). If not, take a moment to review what's
 in this folder first.

 Claude Code'll be able to read, edit, and execute files here.

 Security guide

 ❯ No, exit
   Yes, I trust this folder

 Enter to confirm · Esc to cancel
```

A project folder under the repo (S1) is not trusted automatically; S1 and S2 behave identically. The `agent start` error does not contain the screen text, so the adapter must call `agent read` (it works while blocked). Caveat: S1's trust is by the exact folder `.../probe-s1/wt`; a parent folder trusted in `~/.claude.json` was not available to test.

## Q3: key path of the agent status in `agent get`

`result.agent.agent_status` (value `blocked` while on the trust dialog; `launch_pending: true`). `result.agent.agent` is the kind (`claude`), `result.agent.name` the name. Only the blocked value was observed; idle/working values were not (Claude never started).

S1:
```json
{"id":"cli:agent:get","result":{"agent":{"agent":"claude","agent_status":"blocked","cwd":"/Users/fabienboismoreau/Documents/Projects/SoftwareFactory/SoftwareFactory/verification/software-factory/work/probe-s1/wt","focused":false,"foreground_cwd":"/Users/fabienboismoreau/Documents/Projects/SoftwareFactory/SoftwareFactory/verification/software-factory/work/probe-s1/wt","launch_pending":true,"name":"sf-probe-s1","pane_id":"w1H:p1","revision":0,"state_change_seq":413,"tab_id":"w1H:t1","terminal_id":"term_65da716c8223e1c","workspace_id":"w1H"},"type":"agent_info"}}
```

S2:
```json
{"id":"cli:agent:get","result":{"agent":{"agent":"claude","agent_status":"blocked","cwd":"/private/var/folders/hj/g3l2tt954zz3qj2d5r89dgx40000gn/T/sf-probe-s2-456A64/wt","focused":false,"foreground_cwd":"/private/var/folders/hj/g3l2tt954zz3qj2d5r89dgx40000gn/T/sf-probe-s2-456A64/wt","launch_pending":true,"name":"sf-probe-s2","pane_id":"w1K:p1","revision":0,"state_change_seq":414,"tab_id":"w1K:t1","terminal_id":"term_65da717bfb2581e","workspace_id":"w1K"},"type":"agent_info"}}
```

`herdr notification show "Software factory" --body "Probe notification" --sound none`:
```json
{"id":"cli:notification:show","result":{"reason":"shown","shown":true,"type":"notification_show"}}
```

## Q4: Claude process after `workspace close`

No. Before close `pgrep -fl <SID>` listed the claude process (S1 PID 42815, S2 PID 43900, and the Q6 PID 44437). 2 seconds after `workspace close`, `pgrep -fl sf-probe` and `pgrep -fl <SID>` found nothing, so no manual kill was needed. Caveat: Claude was sitting at the trust dialog, not running a task, so a Claude that is working may behave differently; keep `stop_agent` before close to be safe.

S1 before close:
```text
42815 claude --append-system-prompt-file /Users/fabienboismoreau/Documents/Projects/Nextory/NextoryCustomSkills/sr_opus_5_system_prompt.md --name sf-probe-s1 --session-id 880b8d6a-8981-4bf2-bec1-0f20ac29b5c8
```

S1 after close: (empty)

S1 close output:
```json
{"id":"cli:workspace:close","result":{"type":"ok"}}
```

## Q5: resume

Not tested. Claude could not start in either setup because of the trust dialog, so there was no first prompt to remember and no `--session-id X --resume X` error (A5) to record.

## Q6: arguments with spaces and quotes after `--`

Tested on a Claude that stopped at the trust dialog, using the shell command line that Herdr typed into the pane and `pgrep`. Command given:

```
herdr agent start sf-probe-r --kind claude --pane w1K:p2 --timeout 15000 -- --name 'sf-probe r' --append-system-prompt 'say "hi" $HOME `x` it'"'"'s' --session-id <SID>
```

Herdr typed this into the pane shell (shell-quoted, so the shell decodes it back to the exact original):
```text
fabienboismoreau@MacBook-Pro-de-Fabien wt % claude --name 'sf-probe r' --append-system-prompt 'say "hi" $HOME `x` it'\''s' --session-id 2253ff04-e40a-4ed1-9ba5-19fd856f6488
```

The running process argv (from `pgrep -fl`) holds the original values unchanged: `--name`, `sf-probe r`, `--append-system-prompt`, `say "hi" $HOME `x` it's` (no expansion of `$HOME`, no backtick execution). Answer: yes, arguments are preserved unchanged.


## Second probe: worktrees of a trusted repo (T1, T2)

Setup: R = `/Users/fabienboismoreau/Documents/Projects/SoftwareFactory/SoftwareFactory` (the repo the user already trusts). Worktrees created with `git worktree add --detach <path> HEAD` under `$TMPDIR`: T1 `/private/var/folders/hj/g3l2tt954zz3qj2d5r89dgx40000gn/T/sf-probe-t1-18208`, T2 `.../sf-probe-t2-5343`. `herdr workspace list` / `tab list` were saved before; compared before and after, `worktree open --cwd R --path <wt>` created only the one workspace named in its JSON (no extra workspace for R this time, because R already has workspace `w1F`).

Result: NO trust dialog in T1 (no flag) and NO trust dialog in T2 (`--trust-repository`). Claude started directly at its prompt in both. The worktree of an already trusted repo inherits trust. T2 therefore does not show whether `--trust-repository` has an effect, since T1 without it already worked.

### T1 `worktree open` (no extra flag)
```json
{"id":"cli:worktree:open","result":{"already_open":false,"root_pane":{"agent_status":"unknown","cwd":"/private/var/folders/hj/g3l2tt954zz3qj2d5r89dgx40000gn/T/sf-probe-t1-18208","focused":false,"foreground_cwd":"/private/var/folders/hj/g3l2tt954zz3qj2d5r89dgx40000gn/T/sf-probe-t1-18208","pane_id":"w1M:p1","revision":0,"scroll":{"max_offset_from_bottom":0,"offset_from_bottom":0,"viewport_rows":53},"tab_id":"w1M:t1","terminal_id":"term_65da7c066ebcc20","workspace_id":"w1M"},"tab":{"agent_status":"unknown","focused":false,"label":"1","number":1,"pane_count":1,"tab_id":"w1M:t1","workspace_id":"w1M"},"type":"worktree_opened","workspace":{"active_tab_id":"w1M:t1","agent_status":"unknown","focused":false,"label":"sf-probe-t1","number":13,"pane_count":1,"tab_count":1,"workspace_id":"w1M","worktree":{"checkout_path":"/private/var/folders/hj/g3l2tt954zz3qj2d5r89dgx40000gn/T/sf-probe-t1-18208","is_linked_worktree":true,"repo_key":"/Users/fabienboismoreau/Documents/Projects/SoftwareFactory/SoftwareFactory/.git","repo_name":"SoftwareFactory","repo_root":"/Users/fabienboismoreau/Documents/Projects/SoftwareFactory/SoftwareFactory"}},"worktree":{"is_bare":false,"is_detached":true,"is_linked_worktree":true,"is_prunable":false,"label":"SoftwareFactory","open_workspace_id":"w1M","path":"/private/var/folders/hj/g3l2tt954zz3qj2d5r89dgx40000gn/T/sf-probe-t1-18208"}}}
```
`agent start` T1 (exit 0, `agent_status` idle, `interactive_ready` true):
```json
{"id":"cli:agent:start","result":{"agent":{"agent":"claude","agent_status":"idle","cwd":"/private/var/folders/hj/g3l2tt954zz3qj2d5r89dgx40000gn/T/sf-probe-t1-18208","focused":false,"foreground_cwd":"/private/var/folders/hj/g3l2tt954zz3qj2d5r89dgx40000gn/T/sf-probe-t1-18208","interactive_ready":true,"name":"sf-probe-t1","pane_id":"w1M:p1","revision":1,"state_change_seq":430,"tab_id":"w1M:t1","terminal_id":"term_65da7c066ebcc20","terminal_title":"✳ sf-probe-t1","terminal_title_stripped":"sf-probe-t1","workspace_id":"w1M"},"argv":["claude","--name","sf-probe-t1","--session-id","66d7108c-8bc7-4486-b954-e2763883bb0a"],"type":"agent_started"}}
```
Screen after start (`agent read`): Claude Code v2.1.296 banner, cwd line, prompt `❯ Try "fix typecheck errors"`, status lines; no dialog text.

### T2 `worktree open --trust-repository`
```json
{"id":"cli:worktree:open","result":{"already_open":false,"root_pane":{"agent_status":"unknown","cwd":"/private/var/folders/hj/g3l2tt954zz3qj2d5r89dgx40000gn/T/sf-probe-t2-5343","focused":false,"foreground_cwd":"/private/var/folders/hj/g3l2tt954zz3qj2d5r89dgx40000gn/T/sf-probe-t2-5343","pane_id":"w1N:p1","revision":0,"scroll":{"max_offset_from_bottom":0,"offset_from_bottom":0,"viewport_rows":53},"tab_id":"w1N:t1","terminal_id":"term_65da7c06799f821","workspace_id":"w1N"},"tab":{"agent_status":"unknown","focused":false,"label":"1","number":1,"pane_count":1,"tab_id":"w1N:t1","workspace_id":"w1N"},"type":"worktree_opened","workspace":{"active_tab_id":"w1N:t1","agent_status":"unknown","focused":false,"label":"sf-probe-t2","number":14,"pane_count":1,"tab_count":1,"workspace_id":"w1N","worktree":{"checkout_path":"/private/var/folders/hj/g3l2tt954zz3qj2d5r89dgx40000gn/T/sf-probe-t2-5343","is_linked_worktree":true,"repo_key":"/Users/fabienboismoreau/Documents/Projects/SoftwareFactory/SoftwareFactory/.git","repo_name":"SoftwareFactory","repo_root":"/Users/fabienboismoreau/Documents/Projects/SoftwareFactory/SoftwareFactory"}},"worktree":{"is_bare":false,"is_detached":true,"is_linked_worktree":true,"is_prunable":false,"label":"SoftwareFactory","open_workspace_id":"w1N","path":"/private/var/folders/hj/g3l2tt954zz3qj2d5r89dgx40000gn/T/sf-probe-t2-5343"}}}
```
`agent start` T2 (exit 0, idle):
```json
{"id":"cli:agent:start","result":{"agent":{"agent":"claude","agent_status":"idle","cwd":"/private/var/folders/hj/g3l2tt954zz3qj2d5r89dgx40000gn/T/sf-probe-t2-5343","focused":false,"foreground_cwd":"/private/var/folders/hj/g3l2tt954zz3qj2d5r89dgx40000gn/T/sf-probe-t2-5343","interactive_ready":true,"name":"sf-probe-t2","pane_id":"w1N:p1","revision":1,"state_change_seq":431,"tab_id":"w1N:t1","terminal_id":"term_65da7c06799f821","terminal_title":"✳ sf-probe-t2","terminal_title_stripped":"sf-probe-t2","workspace_id":"w1N"},"argv":["claude","--name","sf-probe-t2","--session-id","e5c830c0-8e1d-4ebe-b063-301d69264b74"],"type":"agent_started"}}
```
Screen after start: same banner, prompt `❯ Try "fix lint errors"`; no dialog text.

### Q3 (run on T1)
`agent prompt sf-probe-t1 "Reply with the word OK only." --wait --timeout 120000` (exit 0):
```json
{"id":"cli:agent:prompt","result":{"agent":{"agent":"claude","agent_status":"done","completion_seq":433,"cwd":"/private/var/folders/hj/g3l2tt954zz3qj2d5r89dgx40000gn/T/sf-probe-t1-18208","focused":false,"foreground_cwd":"/private/var/folders/hj/g3l2tt954zz3qj2d5r89dgx40000gn/T/sf-probe-t1-18208","interactive_ready":true,"name":"sf-probe-t1","pane_id":"w1M:p1","revision":1,"state_change_seq":433,"tab_id":"w1M:t1","terminal_id":"term_65da7c066ebcc20","terminal_title":"✳ sf-probe-t1","terminal_title_stripped":"sf-probe-t1","workspace_id":"w1M"},"type":"agent_prompted"}}
```
`agent get sf-probe-t1`:
```json
{"id":"cli:agent:get","result":{"agent":{"agent":"claude","agent_status":"done","completion_seq":433,"cwd":"/private/var/folders/hj/g3l2tt954zz3qj2d5r89dgx40000gn/T/sf-probe-t1-18208","focused":false,"foreground_cwd":"/private/var/folders/hj/g3l2tt954zz3qj2d5r89dgx40000gn/T/sf-probe-t1-18208","interactive_ready":true,"name":"sf-probe-t1","pane_id":"w1M:p1","revision":1,"state_change_seq":433,"tab_id":"w1M:t1","terminal_id":"term_65da7c066ebcc20","terminal_title":"✳ sf-probe-t1","terminal_title_stripped":"sf-probe-t1","workspace_id":"w1M"},"type":"agent_info"}}
```
Key path `result.agent.agent_status`; value `done` after the prompt finished (it was `idle` right after start; `done` carries `completion_seq`). Claude answered `OK`.

### Q5 resume (T1 session 66d7108c-8bc7-4486-b954-e2763883bb0a)
`workspace close w1M` returned `{"id":"cli:workspace:close","result":{"type":"ok"}}`; 3 seconds later `pgrep -fl <session id>` was empty (Claude stopped). Note: `herdr tab create --cwd <wt> --label sf-probe-r --no-focus` WITHOUT `--workspace` created the tab in the focused workspace `w1F` (the user's SoftwareFactory workspace), not in a new one. Use `--workspace` in the adapter.
```json
{"id":"cli:tab:create","result":{"root_pane":{"agent_status":"unknown","cwd":"/private/var/folders/hj/g3l2tt954zz3qj2d5r89dgx40000gn/T/sf-probe-t1-18208","focused":false,"foreground_cwd":"/private/var/folders/hj/g3l2tt954zz3qj2d5r89dgx40000gn/T/sf-probe-t1-18208","pane_id":"w1F:p4","revision":0,"scroll":{"max_offset_from_bottom":0,"offset_from_bottom":0,"viewport_rows":53},"tab_id":"w1F:t4","terminal_id":"term_65da7c200503d22","workspace_id":"w1F"},"tab":{"agent_status":"unknown","focused":false,"label":"sf-probe-r","number":4,"pane_count":1,"tab_id":"w1F:t4","workspace_id":"w1F"},"type":"tab_created"}}
```
`agent start sf-probe-r ... -- --name sf-probe-r --resume <id>` (exit 0, idle):
```json
{"id":"cli:agent:start","result":{"agent":{"agent":"claude","agent_status":"idle","cwd":"/private/var/folders/hj/g3l2tt954zz3qj2d5r89dgx40000gn/T/sf-probe-t1-18208","focused":false,"foreground_cwd":"/private/var/folders/hj/g3l2tt954zz3qj2d5r89dgx40000gn/T/sf-probe-t1-18208","interactive_ready":true,"name":"sf-probe-r","pane_id":"w1F:p4","revision":1,"state_change_seq":434,"tab_id":"w1F:t4","terminal_id":"term_65da7c200503d22","terminal_title":"✳ sf-probe-r","terminal_title_stripped":"sf-probe-r","workspace_id":"w1F"},"argv":["claude","--name","sf-probe-r","--resume","66d7108c-8bc7-4486-b954-e2763883bb0a"],"type":"agent_started"}}
```
Prompt "What word did you reply with before? Answer in one word." with `--wait` (exit 0, `agent_status` done):
```json
{"id":"cli:agent:prompt","result":{"agent":{"agent":"claude","agent_status":"done","completion_seq":436,"cwd":"/private/var/folders/hj/g3l2tt954zz3qj2d5r89dgx40000gn/T/sf-probe-t1-18208","focused":false,"foreground_cwd":"/private/var/folders/hj/g3l2tt954zz3qj2d5r89dgx40000gn/T/sf-probe-t1-18208","interactive_ready":true,"name":"sf-probe-r","pane_id":"w1F:p4","revision":1,"state_change_seq":436,"tab_id":"w1F:t4","terminal_id":"term_65da7c200503d22","terminal_title":"✳ sf-probe-r","terminal_title_stripped":"sf-probe-r","workspace_id":"w1F"},"type":"agent_prompted"}}
```
Screen shows the previous exchange restored (`❯ Reply with the word OK only.` / `⏺ OK`) and the answer `⏺ OK`. Claude remembers: yes.

### A5 (`--session-id <id> --resume <id>`, tab label sf-probe-a5)
```json
{"id":"cli:tab:create","result":{"root_pane":{"agent_status":"unknown","cwd":"/private/var/folders/hj/g3l2tt954zz3qj2d5r89dgx40000gn/T/sf-probe-t1-18208","focused":false,"foreground_cwd":"/private/var/folders/hj/g3l2tt954zz3qj2d5r89dgx40000gn/T/sf-probe-t1-18208","pane_id":"w1F:p5","revision":0,"scroll":{"max_offset_from_bottom":0,"offset_from_bottom":0,"viewport_rows":53},"tab_id":"w1F:t5","terminal_id":"term_65da7c2ca5f7d23","workspace_id":"w1F"},"tab":{"agent_status":"unknown","focused":false,"label":"sf-probe-a5","number":5,"pane_count":1,"tab_id":"w1F:t5","workspace_id":"w1F"},"type":"tab_created"}}
```
`agent start` exit 1, stdout:
```json
{"error":{"code":"timeout","message":"timed out waiting for agent startup"},"id":"cli:agent:start"}
```
The `agent start` error is only a generic timeout (no Claude error text); a following `agent read` fails with `agent_not_found`. The real error is on the pane screen (read with `herdr pane read w1F:p5 --source recent-unwrapped --lines 30`):
```text
fabienboismoreau@MacBook-Pro-de-Fabien sf-probe-t1-18208 % claude --name sf-probe-a5 --session-id 66d7108c-8bc7-4486-b954-e2763883bb0a --resume 66d7108c-8bc7-4486-b954-e2763883bb0a
Error: --session-id can only be used with --continue or --resume if --fork-session is also specified.
```

### Objects created and cleanup
Created: workspaces `w1M` (T1, closed by `workspace close`), `w1N` (T2, closed); tabs `w1F:t4` (sf-probe-r) and `w1F:t5` (sf-probe-a5), both closed with `tab close`; agents sf-probe-t1, sf-probe-t2, sf-probe-r; worktrees T1 and T2 removed with `worktree remove --force` and `worktree prune`. After cleanup `git worktree list` shows only R, and workspace and tab ids match the "before" lists exactly. Earlier-probe leftovers `w1G` and `w1J` (see above) are still open and untouched.

## Decision

- User rule: try T1 and T2 first. Use `--trust-repository` (O1) only if both showed the trust dialog. Never use O3.
- Result: T1 showed no dialog, so the setup is T1. A worktree of a repo the user already trusts inherits trust. The adapter runs plain `herdr worktree open` with no `--trust-repository` and never answers the dialog. It only detects the dialog (markers "is this a project you created or one you trust" and "yes, i trust this folder", compared in lower case). If `agent start` fails and the screen shows the dialog, it closes what it opened and raises: "Claude asks to trust the folder <cwd>. Open Claude once in the main repository and trust it, then launch again."
- R1: `worktree open --cwd <main>` can auto-create a workspace for the main repo folder that is not in its JSON. The adapter takes `workspace list` before and after. A workspace present only after, different from the returned workspace id, whose `worktree.checkout_path` is exactly the main repo folder (not a linked worktree), is "created by us". It is stored as `extra_workspace` in the handle and closed by `close`. A workspace that existed before is never closed.
- Main-repo sessions: `tab create` without `--workspace` lands in the focused workspace. The adapter finds the workspace whose folder is the main repo folder and passes `--workspace <id>`. If none exists it runs `workspace create --cwd <main> --label <name> --no-focus`, stores `workspace` and `created_workspace: true`, and closes that workspace on close.
- Q4: Claude stops when the workspace closes. `stop_agent` (ctrl+c twice) is still sent before closing.
- A5: resume uses `--resume <id>` only.
- Status values of `result.agent.agent_status`: idle, done, working, blocked, unknown. `state()` returns the value, or `gone` when `agent get` fails.
