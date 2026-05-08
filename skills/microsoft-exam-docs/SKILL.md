---
name: microsoft-exam-docs
description: Downloads Microsoft Learn study material for a Microsoft certification exam code such as AB-620, PL-400, AI-102, AZ-104, or MB-910. Use when the user asks to identify the Microsoft Learn source repo for an exam study guide and save related Microsoft Learn Markdown into a structured local folder.
---

# Microsoft Exam Docs Downloader

Use this skill when the user gives a Microsoft exam code and wants offline Markdown study material from Microsoft Learn.

## What it does

The helper script:

1. Normalizes an exam code, for example `AB-620` or `PL-400`.
2. Fetches the official Microsoft Learn study guide page:
   `https://learn.microsoft.com/en-us/credentials/certifications/resources/study-guides/<exam-code-lowercase>`
3. Reads Microsoft Learn metadata to identify the source repo/path/commit.
4. Downloads the official study guide through Microsoft Learn rendered Markdown (`?accept=text/markdown`).
5. Downloads direct Microsoft Learn links from the study guide.
6. Uses Microsoft Learn Search API to discover exam/certification/course pages and objective-related docs from the study-guide skill bullets.
7. Saves everything into a structured folder with README, INDEX, manifest CSV/JSON, repo info, and failures.

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

Control objective search breadth:

```bash
python3 ~/.pi/agent/skills/microsoft-exam-docs/scripts/download_exam_docs.py PL-400 --objective-search 2
```

Disable objective search and download only official/direct links:

```bash
python3 ~/.pi/agent/skills/microsoft-exam-docs/scripts/download_exam_docs.py PL-400 --objective-search 0
```

## Recommended workflow

1. Run the script with the exam code.
2. Check the final summary for failures.
3. Read `<output>/metadata/repo-info.md` to report the identified repo, path, and commit.
4. Read `<output>/README.md` and `<output>/INDEX.md` to summarize what was downloaded.
5. If the user wants broader coverage, rerun with `--objective-search 3`; if results are too noisy, rerun with `--objective-search 1` or `0`.

## Important notes

- Some Microsoft Learn metadata points to `*-pr` repositories that may be private/inaccessible on GitHub. In that case, the source repo can still be identified from page metadata, but content should be downloaded from Microsoft Learn rendered Markdown.
- Do not clone or scrape an entire MicrosoftDocs repo unless the user explicitly asks; these repos can be very large and include far more than exam study material.
- The generated `metadata/manifest.csv` is the source-of-truth mapping from source URL to local Markdown file.
- The script can be rerun safely; it recreates/updates files under the selected output directory.
