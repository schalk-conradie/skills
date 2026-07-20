---
name: update-standards
description: Capture explicit coding likes, dislikes, corrections, and review feedback from the current conversation as durable personal standards in ~/.agents/CODING.md. Use when the user asks to update CODING.md, add or remember a coding standard, preserve a preferred pattern, avoid a disliked pattern, or turn the current TypeScript discussion into a global coding rule.
---

# Update Coding Standards

Update `~/.agents/CODING.md`, the canonical file linked from `~/.codex/CODING.md`.

## Workflow

1. Extract the preference from the current conversation.
   - Use explicit user feedback, approval, or correction. Do not promote an unendorsed agent suggestion into a standard.
   - Separate durable coding preferences from project-specific conventions, communication preferences, and workflow instructions. Do not edit `CODING.md` when the preference belongs elsewhere; explain the mismatch briefly.
   - Treat an explicit request to use this skill as authorization to edit the standards file. Ask one concise question only when the intended rule has materially different interpretations.

2. Read the complete standards file before editing.
   - Search the relevant headings and existing rules for overlap, conflict, or a useful nearby example.
   - Update or refine an existing rule instead of adding a duplicate.

3. Place the rule in the narrowest applicable section.
   - Put language-independent rules under `## General` and the closest existing `###` subsection.
   - Put TypeScript-specific rules under `## TypeScript` and the closest existing `###` subsection.
   - Create a missing subsection only when the new rule needs it. Prefer these TypeScript subsection names and order: `Types and boundaries`, `Functions and abstractions`, `Error handling`, `Dependencies`, `Testing`, `Style and syntax`, `Tooling`.

4. Write the smallest rule that preserves the lesson.
   - Make each bullet concrete, observable, and scoped. Prefer stating the desired behavior; include a prohibition or exception when it prevents likely misuse.
   - Avoid chat history, dates, lengthy rationale, and absolute language unless the preference is genuinely absolute.
   - Add a fenced `ts` snippet directly below its rule only when syntax or structure communicates the standard better than prose. Keep it minimal; label contrasting forms with `// Prefer` and `// Avoid` when both are necessary.
   - Preserve the file's heading hierarchy and formatting. Use `apply_patch` for the edit.
   - Do not modify `AGENTS.md`, commit, or push unless the user separately asks.

5. Verify the result.
   - Re-read the changed section and inspect the diff for `CODING.md` only.
   - Confirm there is no duplicate or contradictory rule and that any snippet matches the prose.
   - Report the section and exact rule added or changed in a concise summary.
