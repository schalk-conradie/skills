---
name: document-branium
description: Create or update project and Home notes in the user's Obsidian vault at `C:\Users\Schalk\Documents\The Brainium`. Use when the user says phrases like "Document this change in the branium", "document this in Brainium", "add this to my second brain", or asks Codex to capture project/client context, Home context, implementation notes, decisions, fixes, todos, shopping lists, documents, maintenance, inventory, or important household information into the vault.
---

# Document Branium

## Overview

Use this skill to turn the current work context into a concise Brainium note under the correct area:

- **Client/project work** goes under the matching client/project folder.
- **Home and household information** goes under `100 Home`.

The vault root is:

```text
C:\Users\Schalk\Documents\The Brainium
```

The project routing registry is used only for client/project notes:

```text
C:\Users\Schalk\Documents\The Brainium\99 Meta\project-registry.json
```

## Home Structure

The Home area is an active household second-brain area, not a client/project.

Use these existing notes first instead of creating duplicates:

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

Home templates live in:

```text
C:\Users\Schalk\Documents\The Brainium\90 Templates\Home
```

Every Home-specific template is prefixed with `Home`, for example `Home Quick Note.md`, `Home Project.md`, and `Home Shopping List.md`.

Do not store passwords, secret recovery codes, or sensitive IDs in Home notes. Refer to a password manager or secure storage location instead.

## Project Folder Naming

Project folders are generally named `Client - Project`, where the leading code maps to a default client context:

| Code | Default client |
| --- | --- |
| AGR | Allan Gray Retail |
| AGI | Allan Gray Institutional |
| E6 | Element 6 |
| EC | Enterprise cloud |
| SBS | SBS |

`SBS` is the canonical client key and folder name; `Stellenbosch Business School` is accepted as a human-readable alias.

When a clear repo, folder, or vault clue reveals a new code mapping, self-heal the convention by updating this section, the matching section in `C:\Users\Schalk\.agents\skills\branium\search-branium\SKILL.md`, and `C:\Users\Schalk\Documents\The Brainium\AGENTS.md`. Do not infer a new mapping from the code alone; ask if the evidence is unclear.

## Workflow

1. Decide whether this is **Home** or **client/project** context.
   - Use **Home** when the user mentions home, household, personal admin, current todo, shopping, documents, important information, maintenance, inventory, service providers, routines, or a path under `100 Home`.
   - Use **client/project** when the context is a repo, client, implementation change, delivery decision, system design, work meeting, or project folder.
   - If both are plausible and the user did not make the target clear, ask one concise question instead of guessing.

2. For Home context, route to the smallest useful existing note.
   - Current task or reminder: update `100 Home/Tasks/Current Todo.md`.
   - Shopping/restock item: update `100 Home/Lists/Shopping List.md`.
   - Household reference detail: update `100 Home/Important Information/Important Information.md`.
   - Document/admin/renewal detail: update `100 Home/Documents/Document Register.md`.
   - Repair, service, or recurring care: update `100 Home/Maintenance/Maintenance Log.md`.
   - Valuable item, warranty, receipt, or serial number: update `100 Home/Inventory/Home Inventory.md`.
   - Multi-step household effort: add/link it from `100 Home/Projects/Home Projects.md` and create a Home Project note if needed.
   - Messy capture with no clear destination yet: add it to `100 Home/Quick Notes/Home Quick Notes.md` or create a Home Quick Note.
   - Prefer updating the active list/register over creating a duplicate dated note.

3. For client/project context, trace the current project before writing a note.
   - Get the current directory and, if available, the git repo root.
   - Inspect the relevant files, changed files, branch, and verification commands from the current task.
   - Use user-provided context first when it is more specific than repo metadata.

4. Resolve the client/project when needed.
   - Prefer the longest matching `repoPath` in `99 Meta/project-registry.json`.
   - If the user explicitly named a client/project, use that and check the registry for the matching `projectFolder`.
   - If a repo or folder name follows `Client - Project`, use the project-folder naming map as the default client context unless stronger observed evidence says otherwise.
   - If the client/project is unclear, ask one concise question instead of guessing.
   - Project writes require an existing entry in `99 Meta\project-registry.json`. Never invent a synthetic route from command-line client/project values.
   - If a new project is obvious but unregistered, update the vault and registry as a separate, deliberate step before creating its project note.

5. Choose the note type.
   - For client/project notes, default to `change`.
   - Use `decision` only for an architectural, delivery, or business decision.
   - Use `note` for general project context that is not tied to a change.
   - Use the specialized project types when the request is clearly one of them: `meeting`, `adr`, `investigation`, `incident`, `plan`, `architecture`, `technical-design`, `as-built`, `handoff`, or `conversation`.
   - File client/project `adr` and `decision` notes under `Decisions`; file the other specialized project note types under `Notes` unless the script's existing folder map says otherwise.
   - For Home notes, use Home types such as `home-note`, `home-quick-note`, `home-project`, `home-service-provider`, `home-routine`, `home-shopping-list`, `home-document-register`, `home-important-information`, `home-maintenance-log`, `home-inventory`, or `home-todo`.
   - `home-todo` is canonical. The script accepts legacy `home-current-todo` input but writes `type: home-todo`.

6. Write compact, factual content.
   - For project changes, include what changed, why, files touched, verification, and follow-up.
   - For Home, include only the information needed to act later: task, item, date, provider, location, renewal, cost, status, and links where useful.
   - Include failed or skipped verification explicitly for project work.
   - Link to the relevant client/project pages or the Home dashboard.
   - Do not invent Dataverse, client, repo, household, provider, warranty, or document facts that were not observed or supplied.

7. Create or update the note.
   - For active Home lists/registers, edit the existing Home note directly.
   - For new Home notes, use the matching `90 Templates/Home/Home ...` template shape.
   - For scripted creation, use `scripts/create_branium_note.py`.

## Script Usage

Use the bundled script from this skill folder.

Client/project example:

```powershell
python .\scripts\create_branium_note.py `
  --cwd "C:\Users\Schalk\Code\AGR - SWOT Rewrite" `
  --title "Fix rich text field save binding" `
  --note-type change `
  --body "## Context`n- ...`n`n## What Changed`n- ...`n`n## Verification`n- npm run build"
```

Home example for a new quick note:

```powershell
python .\scripts\create_branium_note.py `
  --area home `
  --note-type home-quick-note `
  --title "Garage shelf measurements" `
  --body "## Note`n- ...`n`n## Next Action`n- [ ] ..."
```

The script requires the Brainium registry for project routing, creates the destination note-type folder if needed, writes a dated markdown note, and prints the created path. It derives folder, default status, and tags from the matching vault template; `--status` overrides that default. Home routing does not require the project registry.

Source provenance records an external `--cwd` unchanged. When `--cwd` is inside the Brainium vault, a project note uses the registered `repoPath` if one exists and otherwise omits `source_path` and `Source`; a Home note created from inside the vault also omits them. Use `--dry-run` before writing if the route looks uncertain.

## Templates

Reusable Obsidian templates live in:

```text
C:\Users\Schalk\Documents\The Brainium\90 Templates
```

Use the closest template shape when creating a body for a specialized project note:

- `Change Note.md` for implementation notes and fixes.
- `Decision.md` for short delivery or design decisions.
- `ADR.md` for architectural decision records.
- `Meeting Note.md` for meeting notes and action capture.
- `Investigation Note.md` for debugging, discovery, and evidence trails.
- `Incident RCA.md` for incidents and root-cause analysis.
- `Implementation Plan.md` for scoped plans.
- `Architecture Note.md` for system or integration overviews.
- `Technical Design.md` for proposed technical designs before or during implementation.
- `As Built.md` for the implemented state after delivery.
- `Handoff Note.md` for work transfer notes.
- `Client Conversation.md` for stakeholder conversations.

Use the Home-prefixed templates for Home content:

- `Home Current Todo.md` for household action lists.
- `Home Shopping List.md` for shopping/restock lists.
- `Home Document Register.md` for documents, locations, and renewals.
- `Home Important Information.md` for household reference information.
- `Home Maintenance Log.md` for service history and recurring maintenance.
- `Home Inventory.md` for valuables, serial numbers, receipts, and warranties.
- `Home Project.md` for multi-step household work.
- `Home Service Provider.md` for plumbers, electricians, insurance contacts, and similar providers.
- `Home Routine.md` for repeatable household checklists.
- `Home Quick Note.md` for temporary household capture.

## Note Quality

For project changes, prefer this shape:

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

For Home notes, prefer this shape:

```markdown
## Context
- What this is about.

## Details
- The useful facts, dates, locations, costs, or provider information.

## Next Action
- [ ] The next household action, if any.

## Links
- [[100 Home/00 Home Dashboard|Home Dashboard]]
```

Keep notes factual and short. A good Brainium note should be useful six months later without becoming a duplicate code review or an overgrown household database.
