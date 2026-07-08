---
name: document-branium
description: Create or update project notes in the user's Obsidian vault at `C:\Users\Schalk\Documents\The Brainium`. Use when the user says phrases like "Document this change in the branium", "document this in Brainium", "add this to my second brain", or asks Codex to capture project/client context, implementation notes, decisions, fixes, webresource work, integrations, or verification details into the vault.
---

# Document Branium

## Overview

Use this skill to turn the current work context into a concise Brainium note under the correct client and project.

The vault root is:

```text
C:\Users\Schalk\Documents\The Brainium
```

The routing registry is:

```text
C:\Users\Schalk\Documents\The Brainium\99 Meta\project-registry.json
```

## Project Folder Naming

Project folders are generally named `Client - Project`, where the leading code maps to a default client context:

| Code | Default client |
| --- | --- |
| AGR | Allan Gray Retail |
| AGI | Allan Gray Institutional |
| E6 | Element 6 |
| EC | Enterprise cloud |
| SBS | Stellenbosch Business School |

When a clear repo, folder, or vault clue reveals a new code mapping, self-heal the convention by updating this section, the matching section in `C:\Users\Schalk\.agents\skills\branium\search-branium\SKILL.md`, and `C:\Users\Schalk\Documents\The Brainium\AGENTS.md`. Do not infer a new mapping from the code alone; ask if the evidence is unclear.

## Workflow

1. Trace the current project before writing a note.
   - Get the current directory and, if available, the git repo root.
   - Inspect the relevant files, changed files, branch, and verification commands from the current task.
   - Use user-provided context first when it is more specific than repo metadata.

2. Resolve the client/project.
   - Prefer the longest matching `repoPath` in `99 Meta/project-registry.json`.
   - If the user explicitly named a client/project, use that and check the registry for the matching `projectFolder`.
   - If a repo or folder name follows `Client - Project`, use the project-folder naming map as the default client context unless stronger observed evidence says otherwise.
   - If the client/project is unclear, ask one concise question instead of guessing.
   - If a new project is obvious, add the project to the vault and registry with the same folder pattern.

3. Choose the note type.
   - Default to `change`.
   - Use `decision` only for an architectural, delivery, or business decision.
   - Use `note` for general project context that is not tied to a change.

4. Write a compact note.
   - Include what changed, why, files touched, verification, and follow-up.
   - Include failed or skipped verification explicitly.
   - Link to the client and project pages.
   - Do not invent Dataverse, client, or repo facts that were not observed in the current task.

5. Create the note with `scripts/create_branium_note.py`.

## Script Usage

Use the bundled script from this skill folder:

```powershell
python .\scripts\create_branium_note.py `
  --cwd "C:\Users\Schalk\Code\AGR - SWOT Rewrite" `
  --title "Fix rich text field save binding" `
  --note-type change `
  --body "## Context`n- ...`n`n## What Changed`n- ...`n`n## Verification`n- npm run build"
```

The script reads the Brainium registry, creates the destination folder if needed, writes a dated markdown note, and prints the created path. Use `--dry-run` before writing if the route looks uncertain.

## Note Quality

Prefer this shape:

```markdown
## Context
- What triggered the work.

## What Changed
- The concrete behavior or implementation change.

## Files Touched
- `path/to/file`

## Verification
- Command or manual check.

## Follow Up
- Anything unresolved.
```

Keep notes factual and short. A good Brainium note should be useful six months later without becoming a duplicate code review.
