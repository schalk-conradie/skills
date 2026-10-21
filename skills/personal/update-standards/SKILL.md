---
name: update-standards
description: Record a coding preference, correction, or review lesson from the current conversation as a durable personal standard in ~/.agents/CODING.md. Use when the user asks to update CODING.md, remember a coding standard, keep a preferred pattern, avoid a disliked pattern, or turn feedback they just gave into a global rule.
---

# Update coding standards

Edit `~/.agents/CODING.md`. It is the canonical file. Any copy under a harness folder is a link to it, so change only this one.

## What qualifies

- Something the user said, approved, or corrected in this conversation. An agent suggestion the user did not endorse is not a standard.
- A durable coding preference. Project conventions belong in that project's instructions. Communication and workflow preferences belong in `~/.agents/AGENTS.md` or `~/.agents/STYLE.md`. When the preference belongs elsewhere, say so in one sentence and do not edit `CODING.md`.

The file's own rule applies to you too: add a rule only for concrete, recurring friction.

An explicit request to use this skill is permission to edit the file. Ask one question only when the rule has materially different readings.

## Editing

Read the whole file first. If an existing rule already covers the lesson, sharpen that rule instead of adding a second one.

Place the rule in the narrowest section. Language-independent rules go under `## General`, TypeScript rules under `## TypeScript`, each under the closest existing `###` heading. Create a subsection only when nothing fits. Preferred TypeScript subsection order: `Types and boundaries`, `Functions and abstractions`, `Error handling`, `Testing`, `Style and syntax`. Dependency rules belong under `## General`.

Write the smallest rule that keeps the lesson. One bullet, concrete and observable, stating the desired behaviour. Add a prohibition or exception only when it prevents likely misuse. No dates, chat history, or rationale paragraphs. Absolute wording only when the preference is absolute.

Add a fenced `ts` snippet under the bullet only when structure says it better than prose. Keep it to a few lines. Label contrasting forms `// Prefer` and `// Avoid` only when both are needed.

Keep the existing heading hierarchy and formatting. Edit in place; do not rewrite the file. Do not touch `AGENTS.md`, commit, or push unless asked.

## Finish

Re-read the changed section and the diff. Check for a duplicate or contradicting rule and that any snippet matches the prose. Report the section and the exact rule text added or changed.
