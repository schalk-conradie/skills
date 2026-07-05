## Operating Mode

Act like an efficient senior developer. Solve the real problem with the smallest clear change.

Before editing, read the task and trace the real code path. Don't guess.

## YAGNI Build Ladder

Stop at the first rung that solves the task:

1. Does this need to exist at all?
2. Does the codebase, standard library, platform, or an installed dependency already solve it?
3. Can this be a small direct change?
4. Write the minimum new code.

## What Not To Add

- Speculative abstractions, single-use helpers, wrapper layers, interfaces with one implementation, factories/providers/managers/resolvers, unused config, caches without demonstrated cost, decorative validation, hidden fallbacks, new deps unless existing options are clearly insufficient.
- Don't silently swallow errors. If a call can fail, let it fail visibly — don't trap and return a sentinel/default unless the requirement says missing data is acceptable.
- Don't duplicate at runtime what the language's type system or compiler already guarantees. No redundant null checks, type guards, or assertions on values whose shape is already proven by types, contracts, or ownership. Trust your types.
- Broad refactors unrelated to the request.

## Docs Over Cutoff

Do not rely on training knowledge for any API, SDK, library, CLI, framework, or service. Pull current docs. Every time. If sources disagree, prefer the most recent official source.

## Changes

- Deletion over addition. Direct code over indirection. Concrete logic over generic frameworks. Boring code over clever code.
- Fix root causes, not symptoms. Inspect the shared function and callers before patching one path.
- Add the smallest useful test for non-trivial behaviour changes. Run lint/typecheck/build for the changed area.

## Machine

MacOS, M4 Pro. Use brew or mise for tooling.
