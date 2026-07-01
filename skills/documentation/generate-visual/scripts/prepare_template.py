#!/usr/bin/env python3
"""Create a self-contained starter HTML file from a bundled visual template."""

from __future__ import annotations

import argparse
import re
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[1]
EXAMPLES_DIR = SKILL_DIR / "assets" / "examples"
BASE_CSS = SKILL_DIR / "assets" / "base-site.css"


def resolve_template(name: str) -> Path:
    candidate = Path(name)
    if candidate.is_file():
        return candidate

    if candidate.suffix != ".html":
        candidate = candidate.with_suffix(".html")

    bundled = EXAMPLES_DIR / candidate.name
    if bundled.is_file():
        return bundled

    matches = sorted(EXAMPLES_DIR.glob(f"*{name}*.html"))
    if len(matches) == 1:
        return matches[0]

    available = ", ".join(path.name for path in sorted(EXAMPLES_DIR.glob("*.html")))
    raise SystemExit(f"Template not found or ambiguous: {name}\nAvailable templates: {available}")


def inline_base_css(html: str, base_css: str) -> str:
    html = re.sub(r'(?m)^\s*<link rel="stylesheet" href="assets/site\.css">\s*\n?', "", html)
    html = re.sub(r'(?m)^\s*<script src="https://cdn\.tailwindcss\.com"></script>\s*\n?', "", html)
    html = re.sub(r'(?m)^\s*<script src="assets/tailwind\.config\.js"></script>\s*\n?', "", html)

    shared_style = f"<style>\n/* Shared visual base */\n{base_css.rstrip()}\n</style>\n"
    if "<style>" in html:
        return html.replace("<style>", shared_style + "<style>", 1)
    return html.replace("</title>", "</title>\n" + shared_style, 1)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("template", help="Bundled template filename or unique substring")
    parser.add_argument("output", help="Output HTML path")
    args = parser.parse_args()

    template = resolve_template(args.template)
    output = Path(args.output).resolve()
    base_css = BASE_CSS.read_text(encoding="utf-8")
    html = template.read_text(encoding="utf-8")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(inline_base_css(html, base_css), encoding="utf-8", newline="\n")
    print(output)


if __name__ == "__main__":
    main()
