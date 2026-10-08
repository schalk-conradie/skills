---
name: dlx-to-tickets
description: Cut a DLX project's signed-off design handover into tracer-bullet tickets under .scratch/, one delivery phase at a time, each with its blocking edges and handover sources.
argument-hint: "[phase or area]"
disable-model-invocation: true
---

# DLX to tickets

Cut the signed-off handover of a project built from the Dataloop boilerplate into **tickets**: tracer-bullet vertical
slices that each name the tickets that **block** them and the handover sections they implement. Adapted from the
MIT-licensed `to-tickets` skill in mattpocock/skills.

The handover is already the spec. The client signed the functional and technical specifications, so a ticket points into
them and never restates, reinterprets or edits them. This skill decides how to slice the work and in what order. Each
ticket is built afterwards with `/dlx-implement`.

## 1. Check the handover

Run from the project root. Read AGENTS.md and README.md first. The "Signed-off design handover" section of AGENTS.md
governs everything below and wins over anything the pack says.

Confirm `docs/signed-off/` holds `mockup.html`, `design.md`, `functional-spec.md` and `technical-spec.md`, and read
`docs/VERIFY.md`. Stop and report if a document is missing or the verdict is "Not ready". When the verdict is "Ready to
build in part", the screens VERIFY.md names as blocked get `needs-info` tickets. A missing `docs/design/` is a warning;
continue. Without a handover there is nothing for this skill to cut, so say so and stop.

## 2. Read the handover and the repository

Read these in full before drafting, because the cut depends on all of them:

- `design.md`: §1 Authority; §4 Components, each marked `port`, `base-ui`, `rebuild` or `drop`; §5 Screens and the notes
  an implementer must not miss; §6 Permissions, charts, data and print; §7 Decisions and resolutions; §9 Gaps and
  concerns; §10 Accepted deviations; and §11 Accessibility.
- `technical-spec.md`: Delivery Approach for the phases and their exit conditions, Client Responsibilities for what the
  client owes and by when, and Integrations, when the project has any, for each one's failure behaviour.
- `functional-spec.md`: the routes table, the business rules and their worked examples, every screen, the status models,
  the data model, and roles and access.
- `docs/design/`: `permissions.json` for keys, roles and protected permissions, `types.ts` for entity shapes, and
  `tokens.css` with `assets/`.

A pack that leaves out an optional section, such as Integrations, renumbers the sections after it, so find each section
by its name. Do not read `mockup.html` as text. It is large and bundles its own runtime. Refer to its screens by name.

Then read the repository. Know what the boilerplate already provides so no ticket rebuilds it: Entra token validation,
the tenant allowlist, users bound to (tid, oid), role permissions plus grants minus denies, `GET /me`, migrations,
provisioning, health checks, Bicep and pipelines. Read every existing `.scratch/` phase: its `spec.md`, and each
ticket's `Status`, `Blocked by` and `Sources` lines. Work that is already ticketed is not ticketed again.

If `docs/agents/issue-tracker.md` exists, follow it where it differs from the format below on where tickets live and how
they read. A Wayfinding section in it belongs to `/wayfinder` maps and does not apply. If `CONTEXT.md` exists, use its
terms. Otherwise use the functional specification's vocabulary.

When sources disagree:

- `design.md` is canonical for the build. Where it and a client document state different values, the client document was
  signed and wins. Record the difference in the affected ticket.
- AGENTS.md, README.md and `docs/adr/` win over `technical-spec.md` on stack, hosting, identity, networking and the
  delivery pipeline. A requirement the boilerplate cannot meet without an architectural change, such as non-Entra
  sign-in or a different hosting model, is never ticketed around. Stop and report it.

## 3. Pick the scope

Cut one phase of the technical specification's Delivery Approach per run: the phase the user names, or else the earliest
phase with work not yet ticketed. Later phases are cut against the code that exists when they start, because tickets
written too early go stale.

The build phase usually holds most of the application. When a phase would produce more than about fifteen tickets, cut
it one area at a time, starting with the area the others depend on, which is normally the core records and their
reference data. Tell the user which areas remain. Later runs append to the same phase directory.

If `technical-spec.md` defines no phases, ask the user how to divide the work.

## 4. Draft vertical slices

Break the scope into tracer-bullet tickets.

- Each slice cuts a narrow but complete path through the layers it needs: a forward-only migration, the Zod contract in
  `packages/contracts`, the Express route with its permission and tenant checks, the React screen, and the tests. A
  ticket that delivers one layer for a later ticket to use is a horizontal slice; merge it into the slice that first
  needs it.
- A finished slice is demoable or verifiable on its own. Every ticket answers "what can I demo when this is done?" with
  behaviour.
- Each slice fits one fresh context window. A dense screen becomes several slices: its read path first, then each action
  with its rules.
- Prefactoring goes first. Make the change easy, then make the easy change.

Give each ticket its **blocking edges**: the tickets that must be done before it can start. A ticket with no blockers
can start immediately.

Order the work by the boilerplate's own constraints:

1. Remove the starter widget example before the first feature, if it is still there: its table through a new migration,
   its permissions, endpoints, contract, screen and tests.
2. Seed the permission keys and role mappings from `docs/design/permissions.json` in a new forward-only migration before
   anything checks a permission. Keys live in the database, never in application constants.
3. Build the application shell next: tokens, fonts and assets in place, copied if the import skipped them; navigation
   rendered from the flat permission list in `GET /me`; a placeholder for every route in the functional specification;
   the no-permission message and the no-access screen. Each screen slice then replaces a placeholder.
4. Build Admin → User Management from `design.md` before any feature that depends on user administration. Its API
   enforces that `users:manage` and `roles:manage` cannot leave the administrator role and that the last holder of
   `roles:manage` keeps it.
5. A business table arrives with the first slice that uses it, never in a schema-only ticket. Its reference data arrives
   the same way, seeded by migration with the handover's values.
6. A value that `design.md` §7 classes as `business-data` lives in the database, where its "Where it lives" column says.
   Name that home in the ticket, because a business-data value mistaken for a constant gets hardcoded.
7. A business rule with a worked example goes with the slice that first shows its figure.
8. The first ticket that draws a chart adds Recharts, and the first that needs an icon adds lucide-react. Say so in that
   ticket.
9. An integration is built against its agreed behaviour and failure behaviour, with the external call behind a seam the
   tests can replace. Connecting it to the client's real system waits for the matching item in the technical
   specification's Client Responsibilities.
10. A ticket that introduces an Azure service or architectural element the boilerplate lacks, such as an accepted
    deviation in `design.md` §10, has a criterion to record an ADR.

Some work cannot be done by an agent at a developer machine: Azure portal and tenant configuration, Entra registrations,
Azure DevOps setup, anything the client must supply, and every deployment. That work is a `ready-for-human` ticket. Its
repository side, such as a Bicep parameter file verified with `az bicep build`, can be a separate `ready-for-agent`
ticket. No ticket asks an agent to deploy to production or change production data.

A client responsibility is an external blocker, written after the ticket numbers and a semicolon:
`Blocked by: 04; ViGo: Dirk Vogel's sign-in address (technical-spec §11)`. A ticket that cannot be built until the
client delivers is `needs-info` and says what is missing.

## 5. Write acceptance criteria that can fail

A criterion that is already true before the work starts grades nothing. Write each one so that someone can name the
observation that would prove it false.

- Quote the handover's values: interface copy verbatim, keeping its punctuation even where it breaks house style;
  thresholds; counts; permission keys; and the states each screen has, such as loading, empty, no results, error and no
  permission.
- Use the functional specification's worked examples as expected values.
- Every protected route checks its permission and the tenant scope, and tests prove the 403 and the cross-tenant case.
- A UI ticket keeps every colour in the tokens, with no colour literal in `apps/web/src` outside `tokens.css`, and
  carries the `design.md` §11 accessibility items for its screen. A chart names its type and series tokens from
  `design.md` §6. A printed route carries the `design.md` §6 print rules.
- Every criterion on a `ready-for-agent` ticket can be verified at a developer machine. Phrase checks that need an
  environment conditionally, as in "the SQL integration suite passes where a test database is configured". Anything
  needing Azure, a live tenant or the client belongs on a `ready-for-human` ticket.
- End with the repository's checks: `npm run check` always, `npm run test:e2e` for UI changes, and the SQL integration
  suite for SQL changes.

## 6. Quiz the user

Present the breakdown as a numbered list before writing any file. For each ticket show its title, status, blockers, what
it delivers and its sources. Then show:

- the phase's exit condition and the ticket that proves it;
- every handover section in this scope that no ticket cites, which should be none, each with its reason;
- the areas left for later runs.

Ask whether the granularity is right, whether each blocking edge is real, and whether any ticket should merge or split.
Iterate until the user approves.

## 7. Write the tickets

Each phase has one directory, `.scratch/phase-<n>-<slug>/`, for example `.scratch/phase-1-foundation/`. It holds
`spec.md` and one file per ticket at `issues/<NN>-<slug>.md`, never a combined tickets file. Number from `01` in
dependency order, blockers first, continuing after the highest existing number in that phase. A blocker in another phase
is written with its directory: `phase-1-foundation/04`.

Write `spec.md` with the first tickets of a phase:

<spec-template>

# Phase <n>: <Name>

The <name> phase of the <application> build, as defined in technical-spec §<n>. The handover is the spec; this file
points into it and records only how the phase was cut.

Exit condition: <verbatim from the Delivery Approach>

## Sources

- [technical-spec §<n>](../../docs/signed-off/technical-spec.md): <what it covers>
- [functional-spec §<n>](../../docs/signed-off/functional-spec.md): <what it covers>

## How the phase was cut

<Only the decisions the handover does not make, and where the boilerplate overrides the technical specification.>

</spec-template>

<ticket-template>

# <NN>: <Title>

Status: ready-for-agent

Blocked by: None (can start immediately)

Sources: functional-spec §6.2, §5.2; design.md §5 (Pipeline); permissions.json

**What to build:** <the end-to-end behaviour this ticket makes work, from the user's point of view, in the handover's
vocabulary>

- [ ] <criterion>
- [ ] `npm run check` passes

</ticket-template>

`Status` is one of `ready-for-agent`, `ready-for-human`, `needs-info`, `done` or `wontfix`, or the strings
`docs/agents/triage-labels.md` maps them to. The `Sources` line lists the handover sections the ticket implements, in
plain text. `/dlx-implement` reads exactly those sections, and the next run of this skill uses the lines to see what is
covered.

Point to handover sections instead of copying their rules, and put values only where a criterion needs them to be
testable. Use plain markdown and repo-relative paths. Leave file paths and code out of ticket bodies, except paths that
AGENTS.md or the handover fixes, because the rest go stale.

Format only the files you wrote, for example `npx prettier --write .scratch/phase-1-foundation`, and commit them on
their own with a message such as `Add phase 1 foundation tickets`. Do not push.

## 8. Report

List the tickets with their status, the frontier of tickets an agent can start now, the `ready-for-human` tickets, the
client blockers, and what remains unticketed. Tell the user to run `/dlx-implement <NN>` in a fresh session for each
ticket. It leaves each ticket uncommitted, so they review and commit one before starting the next.

## A revised handover

A scope change arrives as a new handover and is never an edit to the old one. When `docs/signed-off/` has changed since
the tickets were cut, ticket the difference. Read the functional specification's revision summary and the `git diff` of
`docs/signed-off/` and `docs/design/` since the commit that added the tickets. Update the open tickets the change
touches and note why under `## Comments`. A `done` ticket is never reopened; the change becomes a new ticket. A rename
that fans out across the codebase is sequenced expand, migrate, contract: add the new form beside the old one, move the
callers in batches, then delete the old form.
