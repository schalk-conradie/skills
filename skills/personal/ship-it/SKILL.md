---
name: ship-it
description: Carry work that has been settled in the thread (a grilling session, a wayfinder map, a spec, local tickets from to-tickets, Jira issues or Azure DevOps work items, a task or subtask, or the conversation so far) to reviewed, ready-to-commit code. Checks the work is ready, maps its blast radius, breaks it into tracer-bullet vertical slices, gets the slice plan approved, builds and proves every slice, runs an AI review (Claude, plus CodeRabbit when installed), then stops for human review and only afterwards makes one commit per slice. Never pushes, opens a PR or merges. Invoked by name only, with /ship-it (or $ship-it in Codex), once the discussion is done.
disable-model-invocation: true
---

# Ship it

The user has been talking the work through with you, often by being grilled on it. Invoking ship-it means the talking is done. From here you own the work up to a set of local commits: slicing, building, proving and reviewing it.

There are at most two planned stops where you wait for the user: approving the **slice plan**, and the **final review** before anything is committed. The plan stop is skipped when the plan is already settled (see step 3). The final review is never skipped. Between them, make the calls yourself with sensible defaults and keep going. Never push, open a PR, merge or touch a remote. That part stays with the user.

Two wishes pull against each other: nothing enters history until a human has seen the final diff, yet history should read one commit per slice. The bundled script `scripts/ship-it.sh` (next to this file) settles that. It snapshots each slice as you finish it without committing, staging or stashing anything. After approval it turns the snapshots into one commit per slice.

**The session outlives your memory of it.** A long build gets compacted, and only the start of this skill may survive. The script keeps the approved plan and a log of your decisions next to the snapshots. Whenever you are unsure where you are, and always after a compaction, run `bash <skill-dir>/scripts/ship-it.sh recall` and read this file again from `<skill-dir>/SKILL.md`.

## 1. Gather the context

- **Find the right repository.** Run from inside the repository that holds the code. In a hub that clones other repos inside it, such as a planning repo with the code repos as ignored subfolders, `cd` into the child repo first. The hub's own git cannot see the child's changes.
- **The conversation comes first.** Decisions reached while talking outrank the ticket text when they conflict. Note any conflict so it shows up in the plan.
- **Read every source the thread used**, in full. Each kind needs something different:
  - **A grilling session** (`/grill-me`, `/grilling`): the decisions are in the conversation. Collect them, keeping the user's exact words where a value, a message or a rule was settled. `/grill-with-docs` also updates `CONTEXT.md` and ADRs under `docs/adr/`; read the ones it touched.
  - **A wayfinder map:** read its Destination, its Out of scope, and its Decisions so far together with the closed decision tickets they link, which hold the detail. The map lives where the repo's tracker doc says: `.scratch/<effort>/map.md` with tickets in `issues/` for local Markdown, or an issue labelled `wayfinder:map` with child issues on a remote tracker. Open decision tickets mean the way is not clear yet (see "Check it is ready").
  - **A spec and tickets from `/to-spec` or `/to-tickets`:** read `spec.md` and every ticket in its `issues/` folder. Their slices and blocking edges are already agreed, so start the plan from them and change the cut only for a reason you state. Skip tickets that are `built`, `done` or `wontfix`. Put tickets that are `needs-info`, `needs-triage`, `ready-for-human` or `deferred` on the not-covered list.
  - **Jira:** for every issue key, URL or JQL query mentioned, read the whole issue with the Atlassian tools: description, acceptance criteria, comments, subtasks and linked issues. Run a JQL query and read each issue it returns. For an epic or story, read its children too. For a subtask, read its parent for context, but build only the subtask unless the user widened the scope.
  - **Azure DevOps:** read each work item with `az boards work-item show --id <id> --expand all --org https://dev.azure.com/<org>`. Its `relations` list its parent and children; apply the same parent and child rules as for Jira. Read the discussion with `az devops invoke --area wit --resource comments --route-parameters project=<project> workItemId=<id> --org https://dev.azure.com/<org> --api-version 7.1-preview`; the call fails without `--api-version`. Run a WIQL query with `az boards query --wiql "<query>" --org https://dev.azure.com/<org> --project <project>`. If `az` is not signed in to that organisation, say so and work from what the user gave you.
  - **Specs and files** the user pointed at: read them in full.
- **Remote tickets are read-only.** Never transition, comment on, edit, assign or log work on Jira issues or Azure DevOps work items; the final report lists what the user should change by hand. Local ticket files in the repo are code: update them only when the repo's tracker doc, such as `docs/agents/issue-tracker.md`, says the person building them does, and then in the slice that completes them. Never mark one `done`; that is the user's call after review.
- **The codebase:** learn its conventions, nearby patterns, test setup and how its checks run. Look at package scripts, the Makefile, CI config, CLAUDE.md / AGENTS.md, CONTRIBUTING, ADRs and glossaries, and `git log` for how commits and branches are named. Use the project's own vocabulary in slice titles.
- **Prefactoring:** look for refactors that would make the change easy. Make the change easy, then make the easy change.

### Check it is ready

List every question the sources leave open, and sort each one:

- **It would change what gets built:** a value, a rule, a message, a screen state, a data shape, or a choice between two behaviours. Don't guess. Put it in the plan with your recommended answer, so approving the plan settles it.
- **The codebase or its conventions answer it:** decide it and log the decision once the session starts.

If the open questions are many, or they reach the goal itself, it is too early to ship. Stop before slicing, list the questions, and suggest `/grill-me` for a few or a wayfinder map for many. Do the same for a wayfinder map that still has open decision tickets between it and its destination: those decisions are the user's, not yours.

## 2. Slice the work

Break the work into **tracer-bullet vertical slices**:

- Each slice cuts a narrow but *complete* path through every layer it needs (schema, API, UI, tests), not one horizontal layer.
- A finished slice works on its own and can be demonstrated or verified by itself.
- Each slice has one reason to exist and reads well as a single commit.
- Prefactoring slices come first.
- Give each slice its **blocking edges**, the slices that must land before it. Order the slices so every one builds and passes on top of those before it, because the commit order is the slice order. Commit hooks check each slice on its own, so a slice that only works with a later one will be rejected.

**Scope is the user's call, not yours.** A small change gets one or two slices. A big one gets as many as it needs, even hundreds. Don't pad small work into ceremony, and don't cap big work.

**Wide refactors are the exception.** This is one mechanical change, such as renaming a column or retyping a shared symbol, that breaks call sites everywhere at once, so no vertical slice can stay green. Sequence it as **expand–contract** instead:

1. Add the new form beside the old.
2. Migrate call sites in batches sized by blast radius, one batch per slice.
3. Delete the old form once nothing uses it.

### Map the blast radius

For each slice, list what it changes that something else depends on: exported functions and types, API routes and response shapes, database tables, columns, views and stored procedures, config keys and environment variables, events, messages and queues, and file formats. Then find every consumer of each one:

- **In this repo:** search, and use find-references where a language server is available. Also look for uses the compiler cannot see, such as names in config files, templates, SQL strings and reflection.
- **In other repos:** sibling repos named in AGENTS.md, CLAUDE.md or a hub's repo list, shared packages, and clients that update later than the server, such as mobile and offline apps. Search them when they are on disk; otherwise name them as unknown.
- **In data:** existing rows a migration must handle, and defaults or meanings that change for stored values.

Each breaking change needs one of three answers in the plan:

1. A slice updates every consumer.
2. The change is sequenced expand–contract, so old consumers keep working.
3. It is marked breaking (`!` in the header) and the user approves it explicitly.

A consumer outside this repo can't be fixed here; flag it in the plan and the final report.

### Grouping tickets onto slices

Tickets are written for planning, not as build units, so map them to slices rather than one-to-one:

- one ticket can be one slice,
- several tickets can share a slice when they are really one behaviour,
- one ticket can be split across several slices.

Every ticket in scope ends up either in at least one slice or on a **not covered** list with its reason: out of scope, already done, blocked, or unclear. Don't add work that neither the tickets nor the discussion asked for. If the work genuinely needs something with no ticket behind it, include it as a slice and flag it.

## 3. Get the plan approved

Present the plan, then ask with the harness's question tool: `AskUserQuestion` in Claude Code, `request_user_input` in Codex, or whatever this harness has. A plain message can look like a finished thread. Show:

| # | Slice | Delivers | Blocked by | Ticket | Blast radius | Commit header | Proof |
|---|-------|----------|------------|--------|--------------|---------------|-------|
| 1 | Reset tokens table | Tokens can be stored and expire | none | DLX-123 | new table, no consumers | `feat(DLX-123): add password reset tokens` | migration test |

Also show:

- the open questions that change what gets built, each with your recommended answer,
- breaking changes and consumers outside this repo,
- the tickets that are not covered,
- the branch you will work on,
- the commit style you will use, and where you found it,
- the assumptions you made,
- the conflicts between tickets and the discussion.

Ask whether the granularity is right, whether any slices should merge or split, and whether the blocking edges are right. Only an explicit approval of the plan as shown counts. Treat any other answer, including a partial yes, as a change request: revise the plan and ask again.

After approval the user may step away. Work through to the final review without needing them, except for the cases under "Asking the user".

**Skip this stop when the plan is already settled.** That covers two cases:

- **A single obvious slice:** one fix or one small change that the user has already described and agreed, with no tickets to group and no open choices that would change the result.
- **A plan the user has already approved** in the conversation or in their message.

In either case, say the plan in one or two lines at the top of your work (slice, commit header, branch) and go straight to building. Stopping to ask "yes?" about a one-liner the user already decided on only costs them a round trip. The final review gate in step 8 is never skipped.

## 4. Set up

1. **Uncommitted changes already present?** Ask whether they belong to this work. If they do, start with `--allow-dirty`, which puts them into slice 1. If they don't, the user deals with them first. Don't stash them yourself.
2. **Branch.** Find the base branch, the one pull requests go to: what CLAUDE.md, AGENTS.md or CONTRIBUTING names, else `development` or `develop` when it exists on `origin`, else the branch `origin/HEAD` points to. If you are on the base branch, or on `main` or `master`, create a branch. Name it the way the repo names branches. With no convention, use `<type>/<ticket-lowercase>-<short-slug>`, for example `feat/dlx-123-password-reset`, or `feat/password-reset` with no ticket. On any other branch, stay where you are.
3. **Commit style.** Use the repo's convention (see "Commit messages"). If it is not Conventional Commits, start with `--plain` so the script stops enforcing that format.
4. **Start the session:** `bash <skill-dir>/scripts/ship-it.sh start [--allow-dirty] [--plain]`
5. **Save the plan:** pipe the approved plan table, the answered questions, the blast radius, the not-covered list and the assumptions into `ship-it.sh plan -`.

## 5. Build each slice

Work the slices in order. For each one:

1. **Make the smallest change that delivers the slice.** Fix the case in front of you, not every case that could happen.
2. **Use TDD where there is a clean seam.** Write a failing test first, then make it pass. Where no natural seam exists (glue code, config, layout), don't contort the code to manufacture one.
3. **Keep the loop tight.** Typecheck often and run the single test files you are touching often. Save the full suite for the end, because it is slow and the narrow loop catches most problems.
4. **Prove it** (see "Proof").
5. **Check the reach.** If the slice touched more than its planned blast radius, find the consumers of the extra changes and log them. If it now breaks a consumer that the plan doesn't cover and the slice can't fix without growing its scope, stop and ask.
6. **Check for stray files.** `checkpoint` lists the new files in the slice. Make sure none are `.env` files, logs, build output, screenshots or scratch notes. Keep scratch files outside the repo.
7. **Checkpoint it**, passing the commit message on stdin:

   ```bash
   bash <skill-dir>/scripts/ship-it.sh checkpoint 3 - <<'MSG'
   feat(DLX-123): email the reset link

   Sends the link through the existing mailer queue so retries and
   bounce handling come for free.
   MSG
   ```

**Log each call you make for the user** as you make it, one line each, with `ship-it.sh decision -`. The report draws on this log, and it survives a compaction where your memory does not.

During the session, don't run `git add`, `git commit`, `git stash`, `git reset` or `git checkout`. The script relies on HEAD and the index staying exactly where they are, and refuses to checkpoint or fold if the branch or HEAD has moved. Read-only git, such as `diff`, `log` and `status`, is fine.

**If a later slice shows an earlier one was wrong**, fix it, then run `ship-it.sh fold <n>` so the fix lands in slice *n* and carries forward. `fold` refuses when the fix overlaps code a later slice changed, and when it would leave a slice with nothing of its own. Then fold it into the slice it names, or another that fits, and mention that in the report.

To renumber or restructure the plan mid-build, `abort` and `start` again. That leaves the working tree untouched, and you checkpoint from scratch. Use this only when the plan itself has changed, save the new plan, and say so in the report.

## Proof

Proof is evidence you observed yourself in this session: command output, a reproduction, a screenshot. Use the most direct proof the change allows:

- For a bug, reproduce the failure, apply the fix, then watch the same reproduction pass.
- When a behaviour has no test and the repo has a test setup, add one focused test that fails without the change.
- For UI and runtime behaviour, run the app and look at it in a browser, then take a screenshot when it helps. Green mocked tests don't prove the user experience works.

Without proof you don't have confidence, and the report must not present that work as done. Either ask the user or flag it plainly as unproven.

## 6. Run the full checks

Once every slice is built, run the full test suite once, plus whatever the repo's CI runs: typecheck, lint, format check and build. Fix each failure in the slice it belongs to, using `fold`, and re-run until green.

When something fails that you didn't cause, confirm it also fails on the base commit. Do that in a temporary `git worktree add`, not by stashing. Then record it as pre-existing.

## 7. AI review

Run this before the human sees anything, so their time goes on judgement rather than on catching slips.

- **Claude review, always.** Use a fresh reviewer that didn't watch you build it: a subagent through the Agent or Task tool.
  - Give it the full diff (`ship-it.sh diff all`), the slice plan, the tickets' acceptance criteria and the repo's conventions.
  - Ask for findings, most important first, each with file:line. Have it look for bugs, missed acceptance criteria, security problems, unhandled edge cases, tests that don't prove what they claim, and convention breaks.
  - Give it the plan's blast radius. Have it check every changed signature, route, response shape, schema and config key against its consumers, and flag any breaking change that the plan neither handles nor marks as breaking.
  - Have it check every changed test for **weakening**: an assertion loosened or removed, a test deleted or skipped, or an expected value changed. Each one needs a reason in the spec or the discussion, such as the specified behaviour changing. Making a red test pass is never that reason.
  - If a code-review skill is available, the reviewer can use it.
  - With no subagents, do a deliberate separate review pass yourself and say so in the report.
- **CodeRabbit, when it is available.**
  - Check `command -v coderabbit || command -v cr`, then `cr auth status`.
  - If installed and signed in, run `cr review --agent --uncommitted --include-untracked`. Uncommitted against HEAD is exactly this session's work.
  - Otherwise skip it and note why in the report.
- **Triage.**
  - Fix real findings in the right slice and re-prove them.
  - Dismiss the rest with a one-line reason each.
  - Don't churn on suggestions that contradict the repo's own conventions.

## 8. Human review: the gate

Stop here. **Do not commit.** Run `ship-it.sh recall` first, then give the user everything needed to review quickly:

- **Summary:** what was built, and on which branch.
- **Slices:** number, commit header, tickets, what it delivers, size, and its proof (`ship-it.sh list` gives the sizes).
- **Ticket coverage:** each ticket and the slices it landed in, plus anything not covered and why.
- **Blast radius:** what each slice reaches, the consumers updated, any breaking change, and the consumers outside this repo that someone still has to update.
- **Checks:** results for tests, typecheck, lint and build, including anything pre-existing.
- **AI review:** which reviewers ran, what they found, what you fixed and what you dismissed, with reasons.
- **Decisions** you made for them, from the decision log, and anything unproven or risky that needs their eyes.
- **How to look:** `bash <skill-dir>/scripts/ship-it.sh diff all` shows the whole session's work, new files included; plain `git diff` misses untracked files. `ship-it.sh diff <n>` shows one slice's own changes. Their editor's git view works too.

Then ask with the question tool: **approve and commit**, **request changes**, or **edit commit messages**. If no question tool exists, end your turn with the report and put the question at the top.

When changes are requested:

1. Make them and prove them.
2. Fold each one into the slice it belongs to, or add a new slice if it is new behaviour.
3. Re-run the affected checks, and re-review if the change is substantial.
4. Come back to the gate.

Approval covers the exact state the user saw. Anything you change afterwards needs a fresh yes.

For message edits, use `ship-it.sh msg <n> -` with the new message on stdin.

## 9. Commit

Only after explicit approval of the current state, run `bash <skill-dir>/scripts/ship-it.sh commit`. It builds the commits in a temporary worktree whose files match each slice exactly, so the repo's hooks check every slice on its own. It moves the branch only once every slice has committed: it is all or nothing. It uses git's normal hooks and signing. Never bypass hooks with `--no-verify`.

- **A hook rejects a slice.** Nothing is committed and the branch has not moved. The hook saw that slice exactly as it would be committed, so the failure is real for that slice.
  - If the fix is purely mechanical (formatter output, a lint autofix), make it in the working tree, fold it into that slice, run `commit` again, and mention it.
  - If it changes behaviour, or the slice needs code from a later slice, go back to the gate.
- **A hook changed a slice while committing it.** Nothing is committed. The script saves the hook's change as a patch and names the file. Show it to the user. To keep it, make the same change in the working tree (`git apply <patch>` works when the later slices did not touch those lines), fold it into that slice and run `commit` again.
- **Hooks that need installed packages:** the script links the repo's `node_modules` into the temporary worktree. A hook that needs other untracked files, such as a virtual environment or a build output, will fail there. Report that rather than bypassing the hook.

Finish with a short report: `git log --oneline <base>..HEAD`, the branch, and a note that nothing was pushed. End it with an **Action items** list of what is now the user's, most urgent first, one line each starting with a verb:

- push the branch and open the pull request against the base branch,
- each ticket change to make by hand, such as moving DLX-123 to In Review or linking work item 4512 to the pull request,
- each consumer outside this repo that needs updating,
- each migration to apply, and each check that could not run,
- anything left unproven.

## Commit messages

**The repo's own convention wins.** Look for it in CLAUDE.md, AGENTS.md, CONTRIBUTING, a commitlint config, and the recent `git log`. Follow it exactly, including how it names tickets. When it is not Conventional Commits, start the session with `--plain`. When the repo has no convention, use Conventional Commits:

```
type(scope): description

Optional body: why the change was made and anything a reviewer should
know, wrapped at about 72 characters.
```

- **type**, always lowercase:
  - `feat`: new behaviour
  - `fix`: a bug fix (there is no `bug` type)
  - `refactor`: no behaviour change
  - `test`
  - `docs`
  - `perf`
  - `build`
  - `ci`
  - `style`: formatting only
  - `chore`: upkeep that fits nowhere else
  - `revert`

  Pick the type by what the slice does as a whole. Prefactoring slices are `refactor`.
- **scope:**
  - Use the Jira key when the slice has a ticket: `feat(DLX-123): …`.
  - Use `#<id>` for an Azure DevOps work item: `fix(#4512): …`. Azure Repos links `#<id>` mentions in commits to the work item when the repo has commit mention linking turned on.
  - Comma-separate several tickets: `feat(DLX-123,DLX-124): …`.
  - With no ticket, use a short code area (`fix(auth): …`) or leave the scope out.
- **description:** imperative mood, starting lowercase, no full stop. Keep the whole header at 72 characters or fewer.
- **body:** optional for trivial slices. Otherwise explain *why*, because the diff already shows what.
- **breaking changes:** add `!` before the colon and a `BREAKING CHANGE:` footer.

Examples:

- `refactor(DLX-120): extract mailer queue from signup flow`
- `feat(DLX-123): add password reset request form`
- `fix(#4512): stop duplicate reset emails on double submit`
- `test(api): cover expired reset tokens`

## Asking the user

Always use the question tool, and put all the context into the question itself, with options and your recommendation first. Ask only when:

- it is one of the two planned stops (the plan, or the final gate),
- uncommitted changes were already present at the start,
- you can't prove a change,
- the goal is ambiguous in a way that changes the result,
- a slice breaks a consumer the plan doesn't cover,
- the next step is destructive or reaches outside the repo: deleting data, touching production or shared databases, or changing other branches.

Decide everything else yourself and log the decision with `ship-it.sh decision -`.

## Script reference

`<skill-dir>` is the folder holding this SKILL.md. Every command runs from anywhere inside the repo.

| Command | Does |
|---------|------|
| `start [--allow-dirty] [--plain]` | begin a session at the current HEAD; `--plain` drops the Conventional Commits check |
| `plan -` | save the approved plan (stdin), replacing any earlier one |
| `decision -` | append one decision to the log (stdin) |
| `recall` | print the plan, the decision log and the slices |
| `checkpoint <n> -` | snapshot the working tree as slice *n* (message on stdin); re-running on the last slice replaces it |
| `msg <n> -` | replace slice *n*'s commit message |
| `fold <n>` | move changes made since the last snapshot into slice *n* and every slice after it |
| `status` | show changes that are not in any slice yet |
| `list` | slices, headers and sizes |
| `diff <n>` / `diff all` | one slice's own diff, or the whole session's (extra `git diff` options pass through) |
| `commit` | one commit per slice in a temporary worktree, then move the branch; all or nothing |
| `abort` | forget the session; files and branch stay as they are |

The script checks each header and warns on a long header, a trailing full stop or a missing blank second line. Without `--plain` it also requires the Conventional Commits format and warns on a capitalised description. Each session keeps its snapshots under its own `refs/ship-it/<id>/`, so sessions in different worktrees of one repo don't touch each other.
