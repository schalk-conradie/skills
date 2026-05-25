---
name: microsoft-exam-docs
description: Downloads Microsoft Learn study material for a Microsoft certification exam code such as AB-620, PL-400, AI-102, AZ-104, or MB-910. Use when the user asks to download offline study material for a Microsoft exam.
---

# Microsoft Exam Docs Downloader

Use this skill when the user gives a Microsoft exam code and wants offline Markdown study material from Microsoft Learn.

## Microsoft Learn exam structure

Microsoft certification exams on Learn follow a consistent hierarchy:

1. **Study guide** (`/credentials/certifications/resources/study-guides/{exam}`) — exam metadata, audience profile, **skills measured** (domains with weight percentages and detailed task bullets), study resource links, and change log.
2. **Learning paths** (`/training/paths/...`) — curated collections aligned to exam domains. Each path has an overview and ordered modules.
3. **Modules** (`/training/modules/...`) — multi-unit lessons on a single topic. Module overview pages are indexes only.
4. **Units** (`/training/modules/{module}/{n-unit-slug}`) — individual lesson pages with the actual teaching content.

This skill downloads the study guide metadata and the full unit-level lesson text from every discovered learning path.

## What it does

The helper script:

1. Normalizes an exam code, for example `AB-620` or `PL-400`.
2. Fetches the official Microsoft Learn study guide and certification page for exam metadata (passing score, duration, level, languages, etc.).
3. Parses the **Skills measured** section (including dated headings like `Skills measured as of ...`) with percentages.
4. Discovers official Microsoft Learn learning paths for each exam domain via Microsoft Learn Search.
5. Downloads every module and unit under each learning path — full lesson text, not just index pages.
6. Strips YAML frontmatter and metadata so files contain clean, readable content.
7. Writes exactly two Markdown files:
   - `SUMMARY.md` — compact exam overview: details, useful links, skills measured (domain names + weights), learning path index with download status.
   - `CONTENT.md` — all learning paths, modules, and units concatenated with headings and source links.
   - `retry-failed.sh` (only if downloads failed) — re-runs the download to recover failed items.

The script uses only Python standard library.

## Usage

From the project directory where the user wants the folder created:

```bash
python3 ~/.agents/skills/microsoft-exam-docs/scripts/download_exam_docs.py AB-620
```

Specify output directory:

```bash
python3 ~/.agents/skills/microsoft-exam-docs/scripts/download_exam_docs.py PL-400 --out microsoft-learn-pl-400
```

Control search breadth for discovering learning paths:

```bash
python3 ~/.agents/skills/microsoft-exam-docs/scripts/download_exam_docs.py PL-400 --training-search 8
```

Provide learning path URLs manually (skips auto-discovery):

```bash
python3 ~/.agents/skills/microsoft-exam-docs/scripts/download_exam_docs.py PL-400 --paths \
  https://learn.microsoft.com/en-us/training/paths/power-platform-developer
```

## Output structure

```
microsoft-learn-pl-400/
├── SUMMARY.md       # Exam metadata + skills measured + learning path index
├── CONTENT.md       # All learning path lesson content
└── retry-failed.sh  # Only if downloads failed
```

**SUMMARY.md** includes:
- Exam details (code, duration, passing score, proctored, level, languages)
- Useful links (certification page, exam scoring, sandbox, accommodations)
- Skills measured — domain names with weight percentages only
- Learning paths table (title, module/unit counts, download status)
- Failed downloads section (if any)

**CONTENT.md** includes all lesson text, structured as:

```markdown
# PL-400 — Microsoft Learn training content

# Create a technical design
> Source: https://learn.microsoft.com/en-us/training/paths/...

---

## Module 1: Design technical architecture
> Source: https://learn.microsoft.com/en-us/training/modules/...

### 1. Introduction
[full lesson text]

---

### 2. Analyze solution components
[full lesson text]
```

## Retry on failure

If any learning paths or units fail to download (network timeout, etc.), the script:

1. Prints each failure to the console with the URL and error.
2. Adds a **Failed downloads** section to `SUMMARY.md`.
3. Writes a `retry-failed.sh` script that re-runs the full download.

To recover:

```bash
bash microsoft-learn-pl-400/retry-failed.sh
```

Or re-run the original command — it is idempotent:

```bash
python3 ~/.agents/skills/microsoft-exam-docs/scripts/download_exam_docs.py PL-400 --out microsoft-learn-pl-400
```

## Recommended workflow

1. Run the script with the exam code.
2. Read `SUMMARY.md` for exam details and what was downloaded.
3. Use `CONTENT.md` as source material for downstream skills (e.g. `exam-qa-generator`).
4. If there are failures, run `retry-failed.sh` or re-run the original command.

## Important notes

- Microsoft Learn rendered Markdown for module overview pages only contains a unit index, not lesson content. The script expands each module into its individual units.
- YAML frontmatter is stripped from all downloaded content.
- Exam metadata is fetched from both the study guide and certification pages; the certification page takes priority on conflicts.
- Some metadata points to private `*-pr` GitHub repos. Content is downloaded from Microsoft Learn rendered Markdown endpoints instead.
- The script can be rerun safely; it recreates/updates files under the output directory.
- Unit links on newer modules use slug-based URLs (e.g. `/modules/foo/introduction`) rather than numbered paths (`/1-introduction`). Both formats are supported.
- Learning path discovery uses Microsoft Learn Search with exact-title backfill and role-aware filtering. For developer exams, paths tagged with the Developer role are preferred.
