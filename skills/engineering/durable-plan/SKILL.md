---
name: durable-plan
description: Create durable, resumable repository plans and architectural decision records after rigorous one-question-at-a-time scope interrogation. Use when planning a multi-step task, designing work that may span sessions, working in plan mode, or when the user asks to create/design a plan, wants architectural decisions captured, mentions "durable plan", or needs a future agent to resume from a written source of truth.
---

# Durable Plan

Turn planning into durable repository documentation. The plan file, not the
conversation, is the source of truth: it records the agreed scope, phased work,
verification, completion state, handoff context, architectural decisions, and a
deployment plan.

Do not execute deployments, publish releases, run production migrations, or make
live-environment changes unless the user explicitly asks for that action. Writing
a deployment plan is expected; performing the deployment is not.

## 1. Reach Shared Understanding First

Do not write the plan until the scope is fully understood. Interview the user
relentlessly, using the `grill-me` pattern:

- Ask one question at a time.
- Provide a recommended answer with each question.
- If a question can be answered by exploring the codebase and documentation, inspect the repo
  instead of asking.
- Continue until there are no open assumptions, ambiguities, or unmade decisions.

Probe these areas as needed:

- Goal, non-goals, and success criteria
- Users, workflows, and expected behavior
- Technical constraints, dependencies, and integration boundaries
- Data shape, state transitions, permissions, and failure cases
- Environments, verification commands, rollout risks, and deployment expectations
- Architectural decisions that should be recorded separately from the plan

When the scope is clear, summarize the full agreement back to the user and wait
for confirmation before writing the plan.

## 2. Locate Documentation Folders

Create the plan in the current repository root:

```text
docs/plans/<descriptive-name>.md
```

Create architectural decision records in an architecture documentation folder
under `docs/`. Prefer an existing folder if one is already present, such as:

```text
docs/architecture/
docs/adr/
docs/decisions/
```

If no architecture folder exists, create:

```text
docs/architecture/
```

Name decision files descriptively, for example:

```text
docs/architecture/adr-001-auth-boundary.md
```

## 3. Write The Plan

Use concrete checkbox items. Each item must describe a specific change or
investigation, not a vague theme.

Use this template:

```markdown
# <Work Title>

<1-2 sentence goal and scope.>

## For Future Agents
As work proceeds: mark checkboxes `- [x]` as items complete; when a phase is done,
set its status to `Complete` and write its **Phase Summary** with what changed,
key decisions, verification results, and anything needed to continue with zero
conversation context. Run the phase's **Verification Plan** before moving on.
When all phases are done, fill in **Final Recap** and **Deployment Plan**.

Do not perform deployment steps unless the user explicitly asks. The deployment
section is an instruction plan only.

## Scope
- In:
- Out:
- Success criteria:

## Architectural Decisions
- [ ] <decision to record in docs/architecture or link to existing ADR>

## Phase 1: <Title>
Status: Not started

- [ ] <concrete, actionable item>
- [ ] <concrete, actionable item>

### Verification Plan
- `<command/check>` - expected result: <expected result>

### Phase Summary
_(write when phase completes)_

## Phase 2: <Title>
Status: Not started

- [ ] <concrete, actionable item>

### Verification Plan
- `<command/check>` - expected result: <expected result>

### Phase Summary
_(write when phase completes)_

## Final Recap
_(write when all phases complete: summary of the entire piece of work)_

## Deployment Plan
_(write when all phases complete: step-by-step deployment instructions only; do
not execute unless the user explicitly asks)_
```

## 4. Record Architectural Decisions

When the plan depends on a meaningful architectural decision, write an ADR-style
document in the architecture docs folder. Keep each decision focused.

Use this template:

```markdown
# <Decision Title>

Date: <YYYY-MM-DD>
Status: Proposed

## Context
<What forces, constraints, or requirements made this decision necessary?>

## Decision
<What was decided?>

## Consequences
- <Positive or neutral consequence>
- <Tradeoff or risk>

## Alternatives Considered
- <Alternative>: <why it was not chosen>
```

Do not invent architectural decisions just to fill the folder. If the work has
no architectural decisions, say so in the plan.

## Common Mistakes

- Writing the plan before the user confirms the shared understanding.
- Asking the user questions that can be answered from the repository.
- Asking multiple questions at once.
- Saving plans outside `docs/plans/`.
- Saving ADRs outside an architecture folder under `docs/`.
- Treating copied deployment instructions as permission to deploy.
- Using vague checklist items or non-autonomous verification.
- Pre-filling phase summaries, final recap, or deployment plan before the work is
  actually complete.
