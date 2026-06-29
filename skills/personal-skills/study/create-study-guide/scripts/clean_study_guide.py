#!/usr/bin/env python3
"""Clean up Microsoft Learn CONTENT.md into a concise STUDY_GUIDE.md."""
import re
import sys
from pathlib import Path


def is_exercise_heading(text: str) -> bool:
    lower = text.lower()
    return bool(re.search(
        r'\b(exercise|simulation|walkthrough|lab|practice|step-by-step|hands-on)\b',
        lower,
    ) or re.search(r'\btask\b', lower))


def is_knowledge_check_heading(text: str) -> bool:
    lower = text.lower()
    return ("knowledge check" in lower or "check your knowledge" in lower
            or "answer the following" in lower)


def looks_like_numbered_step(line: str) -> bool:
    return bool(re.match(r'^\s*\d+\.\s+', line))


def is_image_line(line: str) -> bool:
    return bool(re.search(r'!\[.*?\]\(.*?\)', line))


def extract_alt_text(line: str) -> str:
    m = re.search(r'!\[(.*?)\]', line)
    return m.group(1) if m else ""


def looks_like_ui_screenshot_alt(text: str) -> bool:
    lower = text.lower()
    if "screenshot of the" in lower or "screenshot of a" in lower:
        return True
    ui_words = ["button", "dropdown", "pane", "panel", "dialog", "window",
                "menu", "toolbar", "tab ", "text box", "checkbox", "field",
                "screenshot showing", "image of the", "image showing"]
    return any(w in lower for w in ui_words)


def is_unit_heading(text: str) -> bool:
    """Matches '### 1. Title' or '## Module 1: Title' or '# Learning Path Title'"""
    return bool(re.match(r'^### \d+\.', text)) or bool(re.match(r'^## Module \d+:', text))


def clean_content(content_path: Path, summary_path: Path, output_path: Path):
    content_lines = content_path.read_text(encoding="utf-8").splitlines(keepends=True)
    summary_lines = summary_path.read_text(encoding="utf-8").splitlines(keepends=True)

    title = content_lines[0].strip().lstrip("#").strip() if content_lines else "Study Guide"

    out = []
    out.append(f"# {title}\n\n")

    # Exam overview from SUMMARY.md
    out.append("## Exam Overview\n\n")
    capture = False
    for line in summary_lines:
        stripped = line.strip()
        if stripped.startswith("## Exam details") or stripped.startswith("## Useful links") or stripped.startswith("## Skills measured"):
            capture = True
        elif stripped.startswith("## ") and capture:
            capture = False
        if capture:
            out.append(line)

    out.append("\n---\n\n")

    n = len(content_lines)
    i = 0

    in_exercise = False
    in_knowledge_check = False
    blank_run = False

    while i < n:
        line = content_lines[i]
        stripped = line.strip()

        if i == 0:
            i += 1
            continue

        # Remove source URL blocks
        if stripped.startswith("> Source:"):
            i += 1
            while i < n and content_lines[i].strip() == "":
                i += 1
            continue

        # Remove "Completed"
        if stripped == "Completed":
            i += 1
            while i < n and content_lines[i].strip() == "":
                i += 1
            continue

        # Remove time estimates
        if re.match(r'^- \d+\s*minutes?$', stripped):
            i += 1
            while i < n and content_lines[i].strip() == "":
                i += 1
            continue

        # Heading handling
        if line.startswith("#"):
            heading_text = line.lstrip("#").strip()

            # Knowledge checks are quiz content, not theory. Drop the entire
            # section until the next major/module/unit heading.
            if in_knowledge_check:
                if is_unit_heading(line) or line.startswith("# ") or line.startswith("## "):
                    in_knowledge_check = False
                else:
                    i += 1
                    blank_run = False
                    continue

            # Determine if this heading ends the current exercise/lab.
            if in_exercise:
                if is_unit_heading(line) or is_exercise_heading(heading_text) or line.startswith("# "):
                    in_exercise = False
                else:
                    i += 1
                    blank_run = False
                    continue

            if is_exercise_heading(heading_text):
                in_exercise = True
                in_knowledge_check = False
                i += 1
                blank_run = False
                continue
            elif is_knowledge_check_heading(heading_text):
                in_knowledge_check = True
                in_exercise = False
                i += 1
                blank_run = False
                continue

            out.append(line)
            i += 1
            blank_run = False
            continue

        # Knowledge checks: drop everything until the next major heading.
        if in_knowledge_check:
            i += 1
            blank_run = False
            continue

        # Inside an exercise/lab: drop everything until the next unit/module.
        if in_exercise:
            i += 1
            blank_run = False
            continue

        # Collapse multiple blank lines
        if stripped == "":
            if not blank_run:
                out.append(line)
                blank_run = True
            i += 1
            continue
        else:
            blank_run = False

        out.append(line)
        i += 1

    text = "".join(out)
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = text.rstrip() + "\n"

    output_path.write_text(text, encoding="utf-8")
    print(f"Study guide written to {output_path}")
    print(f"Original lines: {len(content_lines)}")
    print(f"Output lines:   {len(text.splitlines())}")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python3 clean_study_guide.py <content.md> <summary.md> [output.md]")
        sys.exit(1)
    clean_content(Path(sys.argv[1]), Path(sys.argv[2]),
                  Path(sys.argv[3]) if len(sys.argv) > 3 else Path("STUDY_GUIDE.md"))
