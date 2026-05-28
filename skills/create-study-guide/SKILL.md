---
name: create-study-guide
description: Clean up a Microsoft Learn CONTENT.md (produced by the microsoft-exam-docs skill) into a concise, properly formatted study guide. Removes step-by-step exercise instructions, UI walkthrough screenshots, progress markers, and time estimates while preserving conceptual explanations, learning objectives, knowledge checks, and diagrams. Use when the user wants a readable study guide from raw Microsoft Learn training material.
---

# Create Study Guide

Transforms a raw `CONTENT.md` + `SUMMARY.md` pair (downloaded Microsoft Learn training material) into a clean, exam-focused `STUDY_GUIDE.md`.

## What it does

1. **Prepends exam metadata** from `SUMMARY.md` (exam details, skills measured, useful links).
2. **Strips clutter** from `CONTENT.md`:
   - `Completed` markers
   - Time estimates (`- 10 minutes`)
   - Source URL blocks (`> Source: ...`)
   - Excessive blank lines
3. **Removes step-by-step exercise/simulation instructions** and their associated UI screenshots while keeping:
   - Exercise scenario descriptions
   - Prerequisites
   - Summaries / wrap-ups
   - Conceptual text outside exercises
4. **Preserves knowledge checks** (quiz questions and answer options).
5. **Keeps conceptual images** (diagrams, architecture overviews, conceptual screenshots) and removes trivial UI walkthrough screenshots (button clicks, form fields, parameter panels).

## Usage

```bash
python3 ~/.agents/skills/create-study-guide/scripts/clean_study_guide.py <CONTENT.md> <SUMMARY.md> [OUTPUT.md]
```

If `OUTPUT.md` is omitted, it writes `STUDY_GUIDE.md` in the current directory.

### Example

```bash
cd ./microsoft-learn-pl-900
python3 ~/.agents/skills/create-study-guide/scripts/clean_study_guide.py CONTENT.md SUMMARY.md
```

## Output

A single `STUDY_GUIDE.md` file structured as:

```markdown
# PL-900 — Microsoft Power Platform Fundamentals

## Exam Overview

| **Exam code** | PL-900 |
| **Duration** | 45 minutes |
...

---

# Automate and extend your solutions with AI in Microsoft Power Automate

## Module 1: Get started with Power Automate

### 1. Introducing Power Automate
...
```

## Rules of thumb for manual touch-ups

After running the script, do a quick pass for any remaining artifacts:

- **Empty blockquotes** (`>` on a line by itself) may appear where step instructions were removed. You can delete them.
- **Very large conceptual screenshots** that don't add value can be removed manually.
- **Duplicate knowledge checks** across modules can be consolidated if desired.
- Ensure heading hierarchy is consistent (`#` → `##` → `###`).

## Dependencies

- Python 3 (standard library only)
