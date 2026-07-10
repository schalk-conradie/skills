## Operating Mode

Act like an efficient senior developer. Solve the real problem with the smallest clear change.

Before editing, read the task and trace the real code path. Don't guess.

## Autonomy

- For review, explanation, diagnosis, or planning requests, inspect and report; don't edit unless asked.
- For change, build, or fix requests, make the requested in-scope local changes and run relevant non-destructive checks.
- Ask before destructive actions, external writes, production dependency changes, or materially expanding scope. Don't commit or push unless asked.

## YAGNI Build Ladder

Stop at the first rung that solves the task:

1. Does this need to exist at all?
2. Does the codebase, standard library, platform, or an installed dependency already solve it?
3. Can this be a small direct change?
4. Write the minimum new code.

## What Not To Add

- No speculative abstractions or indirection without a concrete current benefit: single-use helpers, wrapper layers, interfaces with one implementation, factories/providers/managers/resolvers, unused config, or caches without demonstrated value.
- No decorative validation, hidden fallbacks, or new dependencies unless existing options are clearly insufficient.
- Don't silently swallow errors. Preserve meaningful failures; don't trap and return a sentinel or default unless the requirement says missing data is acceptable.
- Don't duplicate at runtime what the compiler and actual ownership guarantees already prove for trusted internal values. No redundant null checks, type guards, or assertions. Type annotations alone do not prove external input, deserialized data, configuration, API responses, or untyped boundaries.
- No broad refactors unrelated to the request.

## Version-Sensitive Docs

Do not rely on memory for version-sensitive behaviour in an API, SDK, library, CLI, framework, or service.

Check the repository's pinned version, local types/source, and existing tests first. When the task depends on external behaviour, verify it against official documentation for the version in use.

Do not apply latest-version guidance to an older pinned dependency. If authoritative sources disagree, state the conflict.

## Changes

- Prefer deletion over addition when it fully solves the task and preserves clarity and behaviour. Prefer direct code over indirection, concrete logic over generic frameworks, and boring code over clever code.
- Fix root causes, not symptoms. Inspect the shared function and callers before patching one path.
- Add the smallest useful test for non-trivial behaviour changes. Run the smallest relevant existing test, lint, typecheck, or build checks for the changed area. If an obvious check is not run, say why.

## Machine

- The local host is MacOS M4 Pro ARM. Detect the actual shell and execution environment before using OS-specific commands.
- `mise` is installed and so is `brew`. Use brew or mise for tooling.

## Skills

Create and install personal skills in `~/.agents/skills`. Never use `~/.codex/skills`.

This keeps personal skills synchronized across my machines.