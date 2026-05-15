---
name: microsoft-exam-docs
description: Downloads Microsoft Learn study material for a Microsoft certification exam code such as AB-620, PL-400, AI-102, AZ-104, or MB-910. Use when the user asks to download offline study material for a Microsoft exam.
---

# Microsoft Exam Docs Downloader

Use this skill when the user gives a Microsoft exam code and wants offline Markdown study material from Microsoft Learn.

## What it does

The helper script:

1. Normalizes an exam code, for example `AB-620` or `PL-400`.
2. Fetches the official Microsoft Learn study guide and the certification page for exam metadata (passing score, duration, level, languages, etc.).
3. Parses the **Skills measured** section (including dated headings like `Skills measured as of ...`) with percentages.
4. Discovers the official Microsoft Learn learning paths for each exam domain by searching Microsoft Learn.
5. Downloads every module and unit under each learning path — the full lesson text, not just index pages.
6. Strips all YAML frontmatter and metadata so files contain clean, readable content.
7. Writes:
   - `SUMMARY.md` — exam details (code, duration, passing score, level, proctored status, languages), skills measured with percentages, useful links, audience profile, detailed objectives, and a table of learning paths.
   - One `.md` file per learning path — all modules and units concatenated with clear headings and source links.
   - `retry-failed.sh` (only if any downloads failed) — a script to re-run the download and recover failed items.

The script uses only Python standard library.

## Usage

From the project directory where the user wants the folder created:

```bash
python3 ~/.pi/agent/skills/microsoft-exam-docs/scripts/download_exam_docs.py AB-620
```

Specify output directory:

```bash
python3 ~/.pi/agent/skills/microsoft-exam-docs/scripts/download_exam_docs.py PL-400 --out microsoft-learn-pl-400
```

Control search breadth for discovering learning paths:

```bash
python3 ~/.pi/agent/skills/microsoft-exam-docs/scripts/download_exam_docs.py PL-400 --training-search 8
```

## Output structure

```
microsoft-learn-pl-900/
├── SUMMARY.md                                           # Exam overview + links
├── 01-describe-the-business-value-of-power-platform.md  # All modules & units for LP 1
├── 02-manage-the-power-platform-environment.md           # All modules & units for LP 2
├── 03-demonstrate-the-capabilities-of-power-apps.md      # All modules & units for LP 3
├── 04-demonstrate-the-capabilities-of-power-automate.md  # All modules & units for LP 4
├── 05-demonstrate-the-capabilities-of-power-pages.md     # All modules & units for LP 5
└── retry-failed.sh                                       # Only if downloads failed
```

**SUMMARY.md** includes:
- Exam details table (code, duration, passing score, proctored, level, languages)
- Useful links (certification page, exam scoring, sandbox, accommodations)
- Audience profile
- Skills measured with percentages (e.g. "Describe the business value of Microsoft Power Platform (15–20%)")
- Learning paths table with modules/units counts and download status (✓ or ⚠ partial)
- Detailed objectives breakdown by domain and sub-objective
- Failed downloads section (if any) with URLs and error messages

Each learning path file contains all modules and units concatenated:

```markdown
# Describe the business value of Microsoft Power Platform
> Source: https://learn.microsoft.com/en-us/training/paths/...

---

## Module 1: Describe the business value of Microsoft Power Platform services
> Source: https://learn.microsoft.com/en-us/training/modules/...

### 1. Introduction
[full lesson text]

---

### 2. Explore Microsoft Power Platform
[full lesson text]
```

## Retry on failure

If any learning paths or units fail to download (network timeout, etc.), the script:

1. Prints each failure to the console with the URL and error.
2. Adds a **⚠ Failed downloads** section to `SUMMARY.md` listing every failed item.
3. Writes a `retry-failed.sh` script that re-runs the full download (which will re-fetch and update all files, including previously failed ones).

To recover:
```bash
bash microsoft-learn-pl-900/retry-failed.sh
```

Or simply re-run the original command — it's idempotent and will update all files:
```bash
python3 ~/.pi/agent/skills/microsoft-exam-docs/scripts/download_exam_docs.py PL-900 --out microsoft-learn-pl-900
```

## Recommended workflow

1. Run the script with the exam code.
2. Read `SUMMARY.md` for a quick overview of exam details and what was downloaded.
3. Check the **Status** column in the learning paths table — ✓ means complete, ⚠ partial means some units failed.
4. If there are failures, run `retry-failed.sh` or re-run the original command.
5. Open the learning path `.md` files to study — they contain all the lesson content.

## Important notes

- Microsoft Learn rendered Markdown for module overview pages only contains an index of unit links, not actual lesson content. The script expands each module into its individual units and concatenates the full text.
- YAML frontmatter is automatically stripped from all downloaded content.
- Exam metadata (duration, passing score, level, proctored status, languages) is fetched from both the study guide and certification detail pages, with the certification page taking priority on conflicts.
- Some Microsoft Learn metadata points to `*-pr` repositories that may be private/inaccessible on GitHub. Content is downloaded directly from Microsoft Learn rendered Markdown endpoints.
- The script can be rerun safely; it recreates/updates files under the selected output directory.