# Personal instructions

These are personal defaults. Explicit user instructions take precedence over these defaults and skill guidelines, subject to system and developer requirements. Repository instructions and established conventions take precedence over personal coding defaults.

## Work and authorization

- For review-only, explanation, diagnosis, and planning requests, inspect and report without editing. When the request also asks for changes, make them.
- For implementation requests, inspect the relevant code path, make the smallest complete change, and carry authorized work through verification. Do not stop at a plan or an offer to continue.
- Resolve routine choices from context. Ask only when missing information materially affects correctness, scope, or consequences and cannot be inferred. Continue independent authorized work while waiting.
- Carry out routine in-scope work, including dependency changes, without additional approval. Reuse authorization already given for the same action and scope.
- Obtain explicit confirmation for the target environment and action before changing production systems or data, or triggering a production deployment. A general implementation or fix request does not authorize production changes or deployment. Prepare the concrete change and relevant checks first. Do not ask again when that production action and scope have already been explicitly confirmed.
- Treat follow-up corrections and questions as part of the active task unless the user cancels or replaces it. Preserve completed work and finish the remaining scope.
- Preserve unrelated local changes. Stage only the files or hunks that belong to the requested commit.

## Instructions and evidence

- Read and follow `~/.agents/STYLE.md` for user-facing prose.
- Before implementing, reviewing, diagnosing, or proposing code changes, read and follow `~/.agents/CODING.md`.
- Apply skill rules to their stated scope. If an instruction blocks requested work, link to the exact file, quote the rule, and explain why it applies. Do not turn a guideline into an unstated approval requirement.
- Verify version-sensitive claims against pinned versions, local source or types, and official documentation for that version.
- Run the smallest checks that establish the changed behavior and all repository-required checks. Broaden or repeat them only for new changes, failures, or unresolved concerns. Report what passed, what was not checked, and any remaining blocker.

## Environment

- On macOS, use `zsh` when available.
- Treat `~/.agents` as the canonical location for shared instructions and personal skills. Harness directories contain links into it.
- Keep shared configuration and skill scripts compatible with macOS and Windows. Use platform-appropriate commands and paths.
- Create personal skills under `~/.agents/skills/personal/<name>`, then run `~/.agents/install.sh` or `~/.agents/install.ps1`.
