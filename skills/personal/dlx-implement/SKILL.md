---
name: dlx-implement
description: Build one .scratch ticket in a DLX project to the signed-off handover, verify it with the repository's checks and mark it done, leaving every change uncommitted for the user to review.
argument-hint: "[ticket number or path]"
disable-model-invocation: true
---

# DLX implement

Build one ticket that `/dlx-to-tickets` cut from the signed-off handover and close it, then hand the change to the user
for review. Adapted from the MIT-licensed `implement` skill in mattpocock/skills.

The work is already decided. The client signed the handover and the ticket names the slice of it to build, so do not
reopen either: no interview, no redesign, no extra scope. Where the handover is silent, or cannot be built on the
boilerplate, stop and say so instead of inventing an answer.

Never commit. The user reviews and tests each ticket's change and commits it themselves, so leave the code, the tests
and the ticket file in the working tree, unstaged. Do not push or open a pull request.

## 1. Pick the ticket

Tickets live at `.scratch/<phase>/issues/<NN>-<slug>.md`. If `docs/agents/issue-tracker.md` exists, follow it for where
tickets live and which strings the `Status` line uses. A Wayfinding section in that file belongs to `/wayfinder` maps,
and its claim, resolve and frontier rules do not apply here.

Resolve the argument against the tickets: `03`, `phase-2-build/03`, a path, or a title. A bare number that exists in
more than one phase is ambiguous, so ask which. With no argument, take the frontier: searching the phases in order, the
lowest-numbered `ready-for-agent` ticket whose blockers are all `done`. Listing every ticket's `Status` and `Blocked by`
lines shows the board quickly.

The `Blocked by` line lists ticket numbers, with the phase directory for a ticket in another phase, such as
`phase-1-foundation/04`. Text after the numbers, such as `ViGo: Dirk Vogel's sign-in address`, is a client blocker. It
names something the client still owes and stays open until the user says it has arrived. `None (can start immediately)`
means the ticket has no blockers.

State the ticket's path and title before anything else, so a wrong pick is caught early. Then check that an agent can
build it now:

| Ticket                                    | Do                                                                                                      |
| ----------------------------------------- | ------------------------------------------------------------------------------------------------------- |
| `ready-for-agent`, every blocker `done`   | Continue                                                                                                |
| A blocker not `done`, or a client blocker | Stop and list the blockers, unless the user explicitly says to go ahead                                 |
| `ready-for-human`                         | Stop. Say what the person has to do, citing the README section, and offer only the repository-side work |
| `needs-info`                              | Stop and say what is missing                                                                            |
| `done` or `wontfix`                       | Stop and say so                                                                                         |

A ticket can match more than one stop row, such as `needs-info` with open blockers, so name every reason. A stop reads
only what it needs to give its reasons, changes no file and goes straight to the report in step 8.

When the user supplies what a `needs-info` ticket or a client blocker is waiting for, record the answer and who gave it
under the ticket's `## Comments`, remove the client blocker, set the ticket to `ready-for-agent` and check it again.

Work on the current branch. Run `git status` before step 2. If the working tree already has changes, list them and ask
whether to build on top of them, because the user reviews each ticket's change on its own and mixed changes are hard to
separate. When the user says to go ahead, leave those changes alone and name them again in the report.

## 2. Load what the ticket points at

1. AGENTS.md and README.md: the rules, the handover authority and the commands.
2. The ticket, and its phase's `spec.md`, whose "How the phase was cut" records decisions the handover does not make.
3. Every section on the ticket's `Sources` line, in full, or the sections its body names when it has no `Sources` line.
   Also `design.md` §1 Authority, the rows of §7 Decisions and resolutions for the values the ticket uses, with their
   class and where they live, and the notes in §9 Gaps and concerns and §11 Accessibility for the screens involved. A
   pack that leaves out an optional section renumbers the sections after it, so find each one by its name.
4. The extracts the ticket touches: `docs/design/permissions.json` for keys and roles, `docs/design/types.ts` for entity
   shapes, and `apps/web/src/tokens/tokens.css` for the semantic utilities.
5. For a screen, its layout in `docs/signed-off/mockup.html`. Open it in a browser, using any browser tool you have or a
   throwaway Playwright script kept outside the repository, and reach the screen through the mockup's own navigation,
   since it keeps screens in local state. Do not read the file as text; it is large and bundles its runtime. The mockup
   keeps the design's original palette, and `tokens.css` wins on colour.
6. The code the slice passes through, and what the tickets this one depends on built, which sets the patterns to follow.
   `git log` on a blocker's ticket file finds the commit that closed it.

When sources disagree, `design.md` is canonical for the build, except that a value a client document states differently
was signed and wins. Build to the client document and record the difference under the ticket's `## Comments`. AGENTS.md,
README.md and `docs/adr/` win over `technical-spec.md` on stack, hosting, identity, networking and delivery. A
requirement that needs an architectural change, such as non-Entra sign-in, stops the run before any code is written.

If the ticket needs something the handover leaves unsettled, such as a value, a message or a state, do not invent it.
Check `design.md` §7 and the phase `spec.md`. If neither settles it, set the ticket to `needs-info` with the question
under `## Comments`, and stop.

## 3. Name the seams

Before writing code, state the seams you will test and what each one catches. Prefer the highest existing seam that
observes the behaviour:

- **HTTP**: `node:test` files under `tests/` that start `createApp` with replaced dependencies and call the API. They
  catch validation, the 403 for a missing permission, cross-tenant isolation and response contracts.
- **Rules**: business rules and calculations as plain functions, tested with the handover's worked examples.
- **SQL**: `tests/integration/` against a dedicated, migrated test database with `SQL_INTEGRATION=1`. They catch
  migrations, queries and tenant predicates, and run only where that database is configured.
- **Browser**: Playwright under `tests/e2e/` against local servers. Without Entra settings they prove unauthenticated
  behaviour only, never a live sign-in.

Confirm with the user before adding a new seam, such as a new test harness or a new injected dependency. A ticket with
no code behaviour, such as a Bicep parameter file, is verified by the checks its criteria name.

## 4. Build it test-first

Work through the acceptance criteria one red-green cycle at a time: write a failing test at the agreed seam, watch it
fail for the right reason, then write the least code that passes. Take expected values from the handover, such as its
worked examples, thresholds, counts and verbatim copy, and never by recomputing them the way the code does. Tidy after
green.

When the ticket adds or changes an API or React feature, call the Skill tool with "add-feature", the project's own
conventions for contracts, migrations, permissions and UI. Keep to the handover rules in AGENTS.md throughout. These are
the ones most often broken:

- `docs/signed-off/` and `docs/design/` are never edited, and no application code imports from `docs/`. Entity shapes
  become Zod schemas in `packages/contracts`.
- No colour literal appears in `apps/web/src` outside `tokens.css`. Use its semantic utilities.
- A `business-data` value from `design.md` §7 lives in the database, seeded by a new forward-only migration, never in a
  constant. An applied migration is never edited.
- Interface copy is the handover's, verbatim.
- Recharts and lucide-react are added only by the first ticket that needs them.

If a criterion asks for an ADR, call the Skill tool with "record-adr".

Typecheck with `npm run typecheck` and run single test files with `npx tsx --test tests/<file>.test.ts` as you go. After
changing `packages/contracts`, rebuild it with `npm run build -w @app/contracts` before the API and web code see the
change.

If the ticket turns out to be two tickets' worth of work, or a horizontal slice, stop and propose the split instead of
building half of it.

## 5. Verify

Run `npm run format`, then `npm run check`. For a UI change, run `npm run test:e2e`, installing Chromium once with
`npx playwright install chromium`. For a SQL change, run `npm run test:integration` only against a dedicated test
database configured with `SQL_INTEGRATION=1`, never a shared or production database. Say which of these could not run
and why.

Signed-in screens cannot be rendered locally without a live sign-in. When none is available, say that the screen was not
compared with the mockup.

## 6. Review the change

Review every changed and new file on two axes and fix what you find:

- **Spec**: every acceptance criterion is met, nothing the ticket did not ask for was added, and every value, message
  and state matches the cited section.
- **Standards**: AGENTS.md, the coding standards your instructions name, and the rules in step 4. Every new protected
  route has its permission check, its tenant predicate and tests for both.

An agent that did not write the code reviews it with less bias. When the harness has subagents or a code-review skill,
run the spec review there.

## 7. Close the ticket

In the ticket file, tick each criterion that a test, a check or a direct observation proved. A conditional criterion
whose condition does not hold here, such as the SQL suite with no test database, stays unticked with a `## Comments`
line saying it was not run; it does not hold the ticket open. Set `Status: done` when every other criterion is ticked.
Add to `## Comments` only what the next person needs: checks not run, handover differences, and follow-up work the
ticket did not cover.

If an unconditional criterion cannot be met, do not mark the ticket done. Report what was built and what blocks the
rest.

Either way, stage and commit nothing. The ticket file goes into the user's commit with the code, so `git log` on it
later finds the work that closed it.

## 8. Report

Give the ticket, the checks that passed and those that did not run, any handover differences, and the next tickets on
the frontier. List the changed files, and the new ones separately, because `git diff` does not show untracked files.
Suggest a commit message with the ticket's title as the subject, in the repository's commit style. When this ticket
completes a phase, quote the phase's exit condition and say who proves it.

After a stop, give the reasons, what would unblock the ticket, any handover difference noticed on the way, and the
frontier.

One ticket per run. Tell the user to review and commit this ticket, then clear context before the next one.
