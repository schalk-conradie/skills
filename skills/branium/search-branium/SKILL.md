---
name: search-branium
description: Search and retrieve relevant context from the user's Obsidian vault at `C:\Users\Schalk\Documents\The Brainium`. Use when the user asks to reference, look up, retrieve, search, recall, or find notes from Brainium or "branium", especially while working in a client/project repo and needing prior project context, decisions, change notes, webresource notes, integration notes, or verification history.
---

# Search Branium

## Overview

Use this skill to find useful Brainium notes before answering a project question or making a change.

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

When a clear repo, folder, or vault clue reveals a new code mapping, self-heal the convention by updating this section, the matching section in `C:\Users\Schalk\.agents\skills\branium\document-branium\SKILL.md`, and `C:\Users\Schalk\Documents\The Brainium\AGENTS.md`. Do not infer a new mapping from the code alone; ask if the evidence is unclear.

## Workflow

1. Understand what the user is trying to recall.
   - Extract concrete search terms from repo names, client names, feature names, table/entity names, file names, errors, routes, and business terms.
   - If the user is currently inside a repo, use the current directory as a routing clue.
   - If a repo or folder name follows `Client - Project`, use the project-folder naming map as a default client clue unless stronger observed evidence says otherwise.

2. Search the narrowest useful scope first.
   - If `cwd` maps to a registry `repoPath`, search that project folder first.
   - If that is too narrow, search the client folder.
   - If still weak, search the whole vault.
   - Do not ask the user to choose a project when the registry can infer it.

3. Use `scripts/search_branium.py` for the first pass.

```powershell
python .\scripts\search_branium.py `
  --cwd "C:\Users\Schalk\Code\AGR - SWOT Rewrite" `
  --query "audit history rich text field"
```

Useful options:

```powershell
python .\scripts\search_branium.py --query "PRP2 Product Group" --scope all
python .\scripts\search_branium.py --client "Element 6" --query "JDE" --scope client
python .\scripts\search_branium.py --cwd "C:\repo" --query "payment bypass" --scope project --json
```

4. Read the top matching notes before answering.
   - Open full files for any result you rely on.
   - Cite local file paths and line numbers in the final answer when useful.
   - Say when no Brainium note was found, then continue from repo evidence if needed.

## Search Behavior

Default `--scope auto` means:

- Search the current project folder when `cwd` matches the registry.
- Search the whole vault when no project mapping exists.

Do not treat the first match as truth. Use the snippets as a locator, then inspect the note itself if the answer depends on exact wording.
