---
name: search-branium
description: Search and retrieve relevant context from the user's Obsidian vault at `/Users/schalk/Documents/The Brainium`. Use when the user asks to reference, look up, retrieve, search, recall, or find notes from Brainium or "branium", especially while working in a client/project repo or needing prior Home context such as todos, shopping lists, documents, maintenance, inventory, important household information, decisions, change notes, integration notes, or verification history.
---

# Search Branium

## Overview

Use this skill to find useful Brainium notes before answering a project or Home question, or before making a change.

The vault root is:

```text
/Users/schalk/Documents/The Brainium
```

The project routing registry is used only for client/project search:

```text
/Users/schalk/Documents/The Brainium/99 Meta/project-registry.json
```

## Home Structure

The Home area lives under:

```text
/Users/schalk/Documents/The Brainium/100 Home
```

Important Home entry points:

| Need | Note |
| --- | --- |
| Home dashboard / index | `100 Home/00 Home Dashboard.md` |
| Current household actions | `100 Home/Tasks/Current Todo.md` |
| Shopping and restock list | `100 Home/Lists/Shopping List.md` |
| Important household reference info | `100 Home/Important Information/Important Information.md` |
| Document locations and renewals | `100 Home/Documents/Document Register.md` |
| Repairs, service history, recurring care | `100 Home/Maintenance/Maintenance Log.md` |
| Valuables, serial numbers, warranties | `100 Home/Inventory/Home Inventory.md` |
| Multi-step household efforts | `100 Home/Projects/Home Projects.md` |
| Temporary household inbox | `100 Home/Quick Notes/Home Quick Notes.md` |
| Completed or stale Home notes | `100 Home/Archive/Home Archive.md` |

Search `100 Home` directly when the user asks about home, household, personal admin, current todo, shopping, documents, important information, maintenance, inventory, routines, service providers, or quick notes.

## Project Folder Naming

Project folders are generally named `Client - Project`, where the leading code maps to a default client context:

| Code | Default client |
| --- | --- |
| AGR | Allan Gray Retail |
| AGI | Allan Gray Institutional |
| E6 | Element 6 |
| EC | Enterprise cloud |
| SBS | Stellenbosch Business School |

When a clear repo, folder, or vault clue reveals a new code mapping, self-heal the convention by updating this section, the matching section in `/Users/schalk/.agents/skills/branium/document-branium/SKILL.md`, and `/Users/schalk/Documents/The Brainium/AGENTS.md`. Do not infer a new mapping from the code alone; ask if the evidence is unclear.

## Workflow

1. Understand what the user is trying to recall.
   - Extract concrete search terms from repo names, client names, feature names, table/entity names, file names, errors, routes, business terms, household areas, document names, provider names, maintenance items, inventory items, and shopping/task wording.
   - If the user is currently inside a repo, use the current directory as a project routing clue.
   - If the user mentions Home or household terms, search `100 Home` first.
   - If a repo or folder name follows `Client - Project`, use the project-folder naming map as a default client clue unless stronger observed evidence says otherwise.

2. Search the narrowest useful scope first.
   - If this is Home context, search the Home scope first.
   - If `cwd` maps to a registry `repoPath`, search that project folder first.
   - If that is too narrow, search the client folder.
   - If still weak, search the whole vault.
   - Do not ask the user to choose a project when the registry can infer it.

3. Use `scripts/search_branium.py` for the first pass.

Client/project example:

```bash
python scripts/search_branium.py \
  --cwd "/Users/schalk/Code/AGR - SWOT Rewrite" \
  --query "audit history rich text field"
```

Home examples:

```bash
python scripts/search_branium.py --scope home --query "insurance renewal"
python scripts/search_branium.py --scope home --query "shopping"
python scripts/search_branium.py --scope home --query ""
```

Useful options:

```bash
python scripts/search_branium.py --query "PRP2 Product Group" --scope all
python scripts/search_branium.py --client "Element 6" --query "JDE" --scope client
python scripts/search_branium.py --cwd "/Users/schalk/Code/repo" --query "payment bypass" --scope project --json
python scripts/search_branium.py --scope home --query "geyser" --json
```

4. Read the top matching notes before answering.
   - Open full files for any result you rely on.
   - For Home questions, prefer the active register/list note over an old archived or dated note when both match.
   - Cite local file paths and line numbers in the final answer when useful.
   - Say when no Brainium note was found, then continue from repo evidence or current Home structure if needed.

## Search Behavior

Default `--scope auto` means:

- Search Home when `cwd` is inside `100 Home` or `--client Home` is passed.
- Search the current project folder when `cwd` matches the registry.
- Search the client folder when only `--client` is supplied.
- Search the whole vault when no project, client, or Home mapping exists.

Explicit `--scope home` searches only `100 Home` and skips template/config folders.

Do not treat the first match as truth. Use the snippets as a locator, then inspect the note itself if the answer depends on exact wording.
