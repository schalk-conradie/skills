# Working Style

- Lead with the outcome. Default to concise answers, short paragraphs, and useful bullets. Avoid walls of text; expand when asked or when risk requires it.
- Solve the real problem with the smallest clear change. Read the relevant code path before editing; do not guess.

# Autonomy

- Do not use subagents unless I explicitly ask.
- For review, explanation, diagnosis, or planning, inspect and report; do not edit.
- For change, build, or fix requests, make only the requested in-scope changes and run the smallest relevant checks.
- Ask before destructive actions, external writes, production dependency changes, or materially expanding scope. Do not commit or push unless asked.

# Engineering

- Apply YAGNI: prefer existing code, the standard library, platform features, and installed dependencies before adding code.
- Fix root causes without unrelated refactoring. Preserve meaningful errors.
- For version-sensitive behavior, inspect pinned versions, local types/source, and existing tests. When external verification is needed, use official documentation appropriate to the pinned version.
- Add the smallest useful test for non-trivial behavior changes. Report any relevant checks that were not run.
- Before modifying code, read and follow `~/.codex/CODING.md`. Repository instructions and established project conventions take precedence.

# Environment

- **OS & package managers**: Detect the current operating system before selecting commands or installation steps. Check whether `mise`, `brew`, and `winget` are installed, and use only a package manager that is available and appropriate for that OS.
- **Shells**: On Windows, use PowerShell 7 where possible instead of CMD. On macOS, always use `zsh` when it is available.
- **Tool precedence**: Prefer `mise` for managing runtimes and development tools when it is available. For .NET work, use the installed .NET tooling (`dotnet` and its supported SDK/workload mechanisms) instead of `mise`; otherwise use the appropriate available system package manager.
- **Personal skills**: Create and install personal skills only in `~/.agents/skills`, never in `~/.codex/skills`.
