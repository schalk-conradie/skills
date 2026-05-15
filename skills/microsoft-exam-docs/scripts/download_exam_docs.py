#!/usr/bin/env python3
"""Download Microsoft Learn study material for a Microsoft certification exam code.

Produces a clean output with:
  - SUMMARY.md   — exam overview, objectives, links to each learning path
  - One .md file per learning path with all modules and unit content concatenated

Example:
    python3 download_exam_docs.py AB-620
    python3 download_exam_docs.py PL-400 --out microsoft-learn-pl-400
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse
from urllib.request import Request, urlopen

LEARN = "https://learn.microsoft.com"
UA = "Mozilla/5.0 (compatible; pi-microsoft-exam-docs-skill/1.0)"


# ── Data structures ──────────────────────────────────────────────────────────

@dataclass
class UnitContent:
    title: str
    url: str
    markdown: str


@dataclass
class ModuleContent:
    title: str
    url: str
    units: List[UnitContent] = field(default_factory=list)


@dataclass
class LearningPathContent:
    title: str
    url: str
    overview_markdown: str
    modules: List[ModuleContent] = field(default_factory=list)


@dataclass
class FailedItem:
    """Track a failed download for retry."""
    url: str
    context: str  # e.g. "LP: Business Value > Module: Services > Unit: Introduction"
    error: str


# ── Network helpers ─────────────────────────────────────────────────────────

def fetch(url: str, accept: Optional[str] = None, timeout: int = 40) -> Tuple[int, str, bytes, str]:
    headers = {"User-Agent": UA}
    if accept:
        headers["Accept"] = accept
    req = Request(url, headers=headers)
    with urlopen(req, timeout=timeout) as resp:
        data = resp.read()
        return resp.status, resp.geturl(), data, resp.headers.get("content-type", "")


def fetch_markdown(url: str) -> str:
    """Fetch a Microsoft Learn page as rendered Markdown, with frontmatter stripped."""
    md_url = _add_accept(url, "text/markdown")
    _status, _final, raw_data, _ctype = fetch(md_url, timeout=35)
    text = raw_data.decode("utf-8", "replace")
    return _clean_markdown(text)


def fetch_html(url: str) -> str:
    _status, _final, data, _ctype = fetch(url, timeout=35)
    return data.decode("utf-8", "replace")


def _add_accept(url: str, value: str) -> str:
    p = urlparse(url)
    qs = [(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True) if k.lower() != "accept"]
    qs.append(("accept", value))
    return urlunparse((p.scheme, p.netloc, p.path, p.params, urlencode(qs), p.fragment))


def _canonical(url: str) -> str:
    p = urlparse(url)
    return urlunparse((p.scheme, p.netloc, p.path, p.params, p.query, ""))


def _normalize_url(url: str, base: str = LEARN) -> str:
    url = html.unescape(url).strip()
    if url.startswith("/"):
        return urljoin(base, url)
    return url


# ── Text helpers ────────────────────────────────────────────────────────────

def _clean_markdown(text: str) -> str:
    """Strip YAML frontmatter and clean up Microsoft Learn rendered Markdown."""
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            text = text[end + 4:].lstrip("\n")
    text = text.replace("\u00a0", " ")
    text = re.sub(r"\n{4,}", "\n\n\n", text)
    text = "\n".join(line.rstrip() for line in text.split("\n"))
    return text.rstrip("\n") + "\n"


def _strip_tags(s: str) -> str:
    s = re.sub(r"<script\b.*?</script>", "", s, flags=re.S | re.I)
    s = re.sub(r"<style\b.*?</style>", "", s, flags=re.S | re.I)
    s = re.sub(r"<[^>]+>", " ", s)
    return " ".join(html.unescape(s).split())


def _slugify(text: str, max_len: int = 80) -> str:
    text = html.unescape(text or "").strip().lower()
    text = re.sub(r"[`'\u2019\u2018\"()]+", "", text)
    text = re.sub(r"&", " and ", text)
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = re.sub(r"-+", "-", text).strip("-")
    return (text[:max_len].strip("-") or "untitled")


def _title_from_slug(slug: str) -> str:
    slug = slug.strip("/").split("/")[-1]
    slug = re.sub(r"^\d+-", "", slug)
    return re.sub(r"-+", " ", slug).strip().title() or slug


# ── URL classification ──────────────────────────────────────────────────────

def _is_learn_url(url: str) -> bool:
    return urlparse(url).netloc.lower() == "learn.microsoft.com"


def _is_training_path_url(url: str) -> bool:
    return _is_learn_url(url) and "/training/paths/" in urlparse(url).path.lower()


def _is_training_module_url(url: str) -> bool:
    path = urlparse(url).path.lower()
    return _is_learn_url(url) and "/training/modules/" in path and not re.search(r"/training/modules/[^/]+/\d-", path)


# ── HTML link extraction ────────────────────────────────────────────────────

def _extract_html_links(html_text: str, base_url: str) -> List[Tuple[str, str]]:
    links: List[Tuple[str, str]] = []
    seen = set()
    for m in re.finditer(r'<a\b[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', html_text, re.I | re.S):
        href, body = m.group(1), m.group(2)
        url = _normalize_url(urljoin(base_url, html.unescape(href)))
        if not _is_learn_url(url):
            continue
        key = _canonical(url)
        if key in seen:
            continue
        seen.add(key)
        title = _strip_tags(body) or _title_from_slug(urlparse(url).path)
        links.append((title, key))
    return links


# ── Microsoft Learn Search API ─────────────────────────────────────────────

def _learn_search(query: str, take: int = 5) -> List[Dict[str, str]]:
    url = f"{LEARN}/api/search?" + urlencode({"search": query, "locale": "en-us", "$top": str(take)})
    try:
        status, _, data, _ = fetch(url, timeout=25)
        if status != 200:
            return []
        raw = json.loads(data.decode("utf-8", "replace"))
    except Exception:
        return []
    results = []
    for item in raw.get("results", [])[:take]:
        item_url = _normalize_url(str(item.get("url") or ""))
        if not _is_learn_url(item_url):
            continue
        results.append({
            "title": _strip_tags(str(item.get("title") or item_url)),
            "url": item_url,
        })
    return results


# ── Study guide parsing ────────────────────────────────────────────────────

def _parse_skill_objectives(study_md: str) -> List[Dict[str, str]]:
    """Parse headings and bullet tasks under the Skills measured section."""
    lines = study_md.splitlines()
    in_skills = False
    current_domain = ""
    current_objective = ""
    records: List[Dict[str, str]] = []

    for line in lines:
        heading = re.match(r"^(#{2,5})\s+(.+?)\s*$", line)
        if heading:
            level = len(heading.group(1))
            title = heading.group(2).strip()
            lower = title.lower()
            if level == 2 and lower.startswith("skills measured"):
                in_skills = True
                current_domain = ""
                current_objective = ""
                continue
            if in_skills and level == 2 and not lower.startswith("skills measured"):
                break
            if not in_skills:
                continue
            if level == 3 and ("%" in title or re.search(r"\(\d+", title)):
                current_domain = title
                current_objective = ""
            elif level == 4:
                current_objective = title
            continue

        if in_skills:
            bullet = re.match(r"^\s*[-*]\s+(.+?)\s*$", line)
            if bullet and current_domain and current_objective:
                task = re.sub(r"\s+", " ", bullet.group(1).strip())
                if task and not re.search(r"\b\d+\s*[–-]\s*\d+%", task):
                    records.append({"domain": current_domain, "objective": current_objective, "task": task})
    return records


def _clean_skill_title(title: str) -> str:
    title = re.sub(r"\s*\(\s*\d+\s*[–-]\s*\d+%\s*\)\s*$", "", title).strip()
    title = re.sub(r"\s+as of\s+.+$", "", title, flags=re.I).strip()
    return title


def _significant_tokens(text: str) -> set:
    words = re.findall(r"[a-z0-9]+", html.unescape(text or "").lower())
    stop = {"the", "and", "with", "using", "use", "for", "from", "into", "your", "learn", "training", "microsoft"}
    return {w for w in words if len(w) >= 4 and w not in stop}


def _training_title_matches(expected: str, result_title: str, result_url: str) -> bool:
    expected_tokens = _significant_tokens(expected)
    haystack = f"{result_title} {urlparse(result_url).path.replace('-', ' ')}"
    result_tokens = _significant_tokens(haystack)
    if not expected_tokens:
        return True
    return expected_tokens.issubset(result_tokens)


# ── Training path discovery ────────────────────────────────────────────────

def _infer_product_terms(study_md: str, exam_code: str) -> str:
    terms = []
    for c in ["Power Platform", "Dataverse", "Power Apps", "Power Automate", "Power BI",
              "Power Pages", "Dynamics 365", "Copilot Studio", "Azure"]:
        if c.lower() in study_md.lower():
            terms.append(c)
    return " ".join(terms[:5]) or exam_code


def _title_variants(title: str) -> List[str]:
    vals = [title]
    for old, new in [("Power Apps", "Microsoft Power Apps"), ("Power Automate", "Microsoft Power Automate"),
                     ("Power Pages", "Microsoft Power Pages"), ("Power Platform", "Microsoft Power Platform")]:
        if old in title and new not in title:
            vals.append(title.replace(old, new))
    seen = []
    return [v for v in vals if v not in seen and not seen.append(v)]


def discover_learning_paths(exam_code: str, study_md: str, search_breadth: int) -> List[str]:
    """Discover official learning path URLs from exam domain headings via Microsoft Learn Search."""
    objectives = _parse_skill_objectives(study_md)
    if not objectives:
        return []

    domain_titles: List[str] = []
    for rec in objectives:
        domain = _clean_skill_title(rec["domain"])
        if domain and domain not in domain_titles:
            domain_titles.append(domain)

    found_urls: List[str] = []
    seen = set()

    for title in domain_titles:
        for variant in _title_variants(title):
            for query in [f'"{variant}" Microsoft Learn training learning path',
                          f'"{variant}" {exam_code} Microsoft Learn training learning path']:
                for result in _learn_search(query, take=max(8, search_breadth)):
                    url = _canonical(result["url"])
                    if _is_training_path_url(url) and url not in seen and _training_title_matches(variant, result["title"], url):
                        seen.add(url)
                        found_urls.append(url)
                        break
                else:
                    continue
                break
            else:
                continue
            break
    return found_urls


# ── Training content download ──────────────────────────────────────────────

def _extract_module_urls_from_path(path_url: str) -> List[Tuple[str, str]]:
    """Get module URLs from a learning path page's HTML."""
    html_text = fetch_html(path_url)
    return [(t, u) for t, u in _extract_html_links(html_text, path_url) if _is_training_module_url(u)]


def _extract_unit_urls_from_module(module_url: str) -> List[Tuple[str, str]]:
    """Get unit URLs from a module page's HTML (relative hrefs like 1-introduction)."""
    html_text = fetch_html(module_url)
    unit_links: List[Tuple[str, str]] = []
    seen = set()
    for m in re.finditer(r'<a\b[^>]*href=["\'](\d-[^"\']+)["\'][^>]*>(.*?)</a>', html_text, re.I | re.S):
        href, body = m.group(1), m.group(2)
        title = _strip_tags(body) or _title_from_slug(href)
        url = _canonical(urljoin(module_url.rstrip('/') + '/', href))
        if url not in seen:
            seen.add(url)
            unit_links.append((title, url))
    return unit_links


def download_learning_path(path_url: str, failures: List[FailedItem]) -> LearningPathContent:
    """Download a full learning path with all modules and their unit content."""
    overview_md = fetch_markdown(path_url)

    # Extract title from first H1 in the cleaned markdown
    # The overview page often has two H1s; the second one is the human-friendly title.
    title_hits = re.findall(r"^#\s+(.+)$", overview_md, re.M)
    title = title_hits[1].strip() if len(title_hits) >= 2 else (title_hits[0].strip() if title_hits else _title_from_slug(urlparse(path_url).path))

    lp = LearningPathContent(title=title, url=path_url, overview_markdown=overview_md)

    print(f"  Learning path: {title}")
    module_urls = _extract_module_urls_from_path(path_url)
    for mod_title, mod_url in module_urls:
        mod = ModuleContent(title=mod_title, url=mod_url)
        print(f"    Module: {mod_title}")

        # Download each unit's full content
        unit_urls = _extract_unit_urls_from_module(mod_url)
        for unit_title, unit_url in unit_urls:
            ctx = f"LP: {title} > Module: {mod_title} > Unit: {unit_title}"
            try:
                unit_md = fetch_markdown(unit_url)
                mod.units.append(UnitContent(title=unit_title, url=unit_url, markdown=unit_md))
                print(f"      Unit: {unit_title} ({len(unit_md):,} chars)")
                time.sleep(0.15)
            except Exception as e:
                print(f"      Unit: {unit_title} — FAILED: {e}")
                failures.append(FailedItem(url=unit_url, context=ctx, error=str(e)))

        lp.modules.append(mod)

    return lp


# ── Output generation ──────────────────────────────────────────────────────

def _build_path_filename(index: int, title: str) -> str:
    slug = _slugify(title, 60)
    return f"{index:02d}-{slug}.md"


def write_learning_path_file(root: Path, index: int, lp: LearningPathContent) -> str:
    """Write a single .md file containing all modules and units for a learning path."""
    lines: List[str] = []

    lines.append(f"# {lp.title}\n")
    lines.append(f"> Source: [{lp.url}]({lp.url})\n")

    # Add a concise overview from the learning path page (skip the verbose "At a glance" section)
    # Extract just the description paragraph(s) from the overview
    overview_text = lp.overview_markdown
    # Find the first paragraph after the H1s that looks like a description (not "At a glance" metadata)
    desc_lines: List[str] = []
    in_description = False
    past_at_a_glance = False
    for line in overview_text.split("\n"):
        stripped = line.strip()
        if stripped.startswith("## At a glance") or stripped.startswith("## Prerequisites"):
            break
        if stripped.startswith("# "):
            continue
        if stripped.startswith("![]"):
            continue
        if stripped and not past_at_a_glance:
            # Skip metadata-like lines (single words or very short lines)
            if len(stripped) > 30:
                in_description = True
        if in_description and stripped:
            desc_lines.append(line)
        elif in_description and not stripped:
            break
    if desc_lines:
        lines.append("\n".join(desc_lines) + "\n")

    lines.append("\n---\n")

    for mi, mod in enumerate(lp.modules, start=1):
        lines.append(f"\n## Module {mi}: {mod.title}\n")
        lines.append(f"> Source: [{mod.url}]({mod.url})\n")

        for ui, unit in enumerate(mod.units, start=1):
            lines.append(f"\n### {ui}. {unit.title}\n")
            # Strip the H1 from unit content (it duplicates our ### heading)
            unit_text = unit.markdown
            unit_text = re.sub(r"^#\s+.+\n", "", unit_text, count=1)
            # Remove "Completed" / duration artifacts at the top
            unit_text = re.sub(r"^Completed\s*\n", "", unit_text)
            unit_text = re.sub(r"^\-\s+\d+\s+min(?:utes)?\s*\n", "", unit_text)
            lines.append(unit_text.rstrip("\n") + "\n")
            if ui < len(mod.units):
                lines.append("\n---\n")

        if mi < len(lp.modules):
            lines.append("\n---\n")

    filename = _build_path_filename(index, lp.title)
    (root / filename).write_text("\n".join(lines), encoding="utf-8")
    return filename


def _parse_exam_metadata(study_md: str) -> Dict[str, str]:
    """Extract key exam metadata from the study guide markdown."""
    meta: Dict[str, str] = {}

    # Certification / exam name from the H1
    h1 = re.search(r"^#\s+(.+)$", study_md, re.M)
    if h1:
        name = h1.group(1).strip()
        # Remove the " | Microsoft Learn" suffix that appears on rendered pages
        name = re.sub(r"\s*\|\s*Microsoft Learn\s*$", "", name)
        meta["name"] = name

    # Pass score
    pass_m = re.search(r"score of (\d+) or greater", study_md, re.I)
    if pass_m:
        meta["pass_score"] = pass_m.group(1)

    # Exam duration
    dur_m = re.search(r"(\d+)\s+minutes? to complete", study_md, re.I)
    if dur_m:
        meta["duration_minutes"] = dur_m.group(1)

    # Skills at a glance (domain → percentage)
    skill_glance = {}
    for m in re.finditer(r"^[-*]\s+(.+?)\s*\((\d+[–\\-]\d+)%\)\s*$", study_md, re.M):
        skill_glance[m.group(1).strip()] = m.group(2) + "%"
    meta["skill_glance"] = skill_glance  # type: ignore[assignment]

    # Useful links from the table
    links: Dict[str, str] = {}
    for m in re.finditer(r"\[([^\]]+)\]\(([^)]+)\)", study_md):
        label = m.group(1).strip()
        href = m.group(2).strip()
        if label in ("How to earn the certification", "Exam scoring and score reports",
                     "Exam sandbox", "Request accommodations"):
            if not href.startswith("http"):
                href = LEARN + href
            links[label] = href
    if links:
        meta["useful_links"] = links  # type: ignore[assignment]

    return meta


def _fetch_cert_metadata(exam_slug: str) -> Dict[str, str]:
    """Fetch certification page for level, proctored status, duration, languages."""
    meta: Dict[str, str] = {}
    try:
        study_page_url = f"{LEARN}/en-us/credentials/certifications/resources/study-guides/{exam_slug}"
        study_html = fetch_html(study_page_url)
        cert_url = None
        for m in re.finditer(r'href="([^"]+/credentials/certifications/[^"/]+(?:/[^"]*?)?)"', study_html, re.I):
            href = m.group(1)
            if "/resources/study-guides" not in href and "/exams/" not in href:
                cert_url = _normalize_url(href)
                if _is_learn_url(cert_url):
                    break
        if not cert_url:
            return meta

        cert_md = fetch_markdown(cert_url)

        # Level (Beginner / Intermediate / Advanced)
        for level in ["Beginner", "Intermediate", "Advanced"]:
            if f"[{level}]" in cert_md or f"({level.lower()})" in cert_md:
                meta["level"] = level
                break

        # Duration
        dur_m = re.search(r"(\d+)\s+minutes? to complete", cert_md, re.I)
        if dur_m:
            meta["duration_minutes"] = dur_m.group(1)

        # Proctored
        if "proctored" in cert_md.lower():
            meta["proctored"] = "Yes"

        # Languages
        lang_m = re.search(r"offered in the following languages:?\s*(.+?)\n", cert_md, re.I)
        if lang_m:
            meta["languages"] = lang_m.group(1).strip().rstrip(".")

    except Exception:
        pass  # Best-effort; certification page is supplementary
    return meta


def write_summary(root: Path, exam_code: str, study_md: str, objectives: List[Dict[str, str]],
                  path_files: List[Tuple[str, LearningPathContent]],
                  failures: List[FailedItem]) -> None:
    """Write SUMMARY.md with exam overview, objectives, and links to learning path files."""
    lines: List[str] = []

    study_meta = _parse_exam_metadata(study_md)
    cert_meta = _fetch_cert_metadata(exam_code.lower())
    # Merge: cert page values fill in gaps not already in study_meta
    merged = {**study_meta, **cert_meta}  # cert_meta wins on overlap (e.g. duration from cert page)
    skill_glance: Dict[str, str] = merged.get("skill_glance", {})  # type: ignore[assignment]

    # ── Header with exam name ──────────────────────────────────────────
    cert_name = merged.get("name", f"Exam {exam_code}")
    lines.append(f"# {cert_name}\n")

    # ── Exam details table ─────────────────────────────────────────────
    details: List[Tuple[str, str]] = []
    details.append(("Exam code", exam_code))
    if "duration_minutes" in merged:
        details.append(("Duration", f"{merged['duration_minutes']} minutes"))
    if "pass_score" in merged:
        details.append(("Passing score", f"{merged['pass_score']} / 1000"))
    if merged.get("proctored"):
        details.append(("Proctored", "Yes"))
    if merged.get("level"):
        details.append(("Level", merged["level"]))
    if merged.get("price"):
        details.append(("Price", merged["price"]))
    if merged.get("languages"):
        details.append(("Languages", merged["languages"]))

    if details:
        lines.append("## Exam details\n")
        lines.append("| | |")
        lines.append("|---|---|")
        for label, value in details:
            lines.append(f"| **{label}** | {value} |")
        lines.append("")

    # ── Useful links ────────────────────────────────────────────────────
    useful_links: Dict[str, str] = merged.get("useful_links", {})  # type: ignore[assignment]
    if useful_links:
        lines.append("\n## Useful links\n")
        for label, url in useful_links.items():
            lines.append(f"- [{label}]({url})")
        lines.append("")

    # ── Audience profile ───────────────────────────────────────────────
    audience_match = re.search(r"### Audience profile\s*\n([\s\S]*?)(?=\n###|\n##|\Z)", study_md)
    if audience_match:
        lines.append("\n## Audience profile\n")
        lines.append(audience_match.group(1).strip() + "\n")

    # ── Skills at a glance ─────────────────────────────────────────────
    lines.append("\n## Skills measured\n")
    seen_domains: List[str] = []
    domain_percentages: Dict[str, str] = {}
    for rec in objectives:
        domain = _clean_skill_title(rec["domain"])
        if domain not in seen_domains:
            seen_domains.append(domain)
            for glance_name, pct in skill_glance.items():
                if _significant_tokens(domain) & _significant_tokens(glance_name):
                    domain_percentages[domain] = pct
                    break

    for i, domain in enumerate(seen_domains, start=1):
        pct = domain_percentages.get(domain, "")
        pct_str = f" ({pct})" if pct else ""
        lines.append(f"{i}. **{domain}**{pct_str}")
    lines.append("")

    # ── Learning paths ──────────────────────────────────────────────────
    lines.append("\n## Learning paths\n")
    lines.append("| # | Learning path | Modules | Units | Status | File |")
    lines.append("|---|---|---|---|---|---|")
    for idx, (filename, lp) in enumerate(path_files, start=1):
        n_modules = len(lp.modules)
        n_units = sum(len(m.units) for m in lp.modules)
        has_failure = any(f"LP: {lp.title}" in f.context for f in failures)
        status = "⚠ partial" if has_failure else "✓"
        lines.append(f"| {idx} | {lp.title} | {n_modules} | {n_units} | {status} | [{filename}]({filename}) |")
    lines.append("")

    # ── Detailed objectives ─────────────────────────────────────────────
    lines.append("\n## Detailed objectives\n")
    current_domain = ""
    current_objective = ""
    for rec in objectives:
        domain = _clean_skill_title(rec["domain"])
        objective = _clean_skill_title(rec["objective"])
        if domain != current_domain:
            lines.append(f"\n### {domain}\n")
            current_domain = domain
            current_objective = ""
        if objective != current_objective:
            lines.append(f"\n#### {objective}\n")
            current_objective = objective
        lines.append(f"- {rec['task']}")
    lines.append("")

    # ── Failures section ────────────────────────────────────────────────
    if failures:
        lines.append("\n## ⚠ Failed downloads\n")
        lines.append(f"{len(failures)} item(s) failed to download. Run `retry-failed.sh` to re-download them.\n")
        for f in failures:
            lines.append(f"- {f.context} — {f.error}")
            lines.append(f"  `{f.url}`")
        lines.append("")

    (root / "SUMMARY.md").write_text("\n".join(lines), encoding="utf-8")


# ── Main ───────────────────────────────────────────────────────────────────

def _write_retry_script(root: Path, exam_slug: str, learning_paths: List[LearningPathContent],
                         failures: List[FailedItem], failed_path_urls: List[str]) -> None:
    """Write a retry script for any learning paths or units that failed to download."""
    lines: List[str] = []
    lines.append("#!/bin/bash")
    lines.append("# Retry failed downloads for the " + exam_slug.upper() + " exam study material.")
    lines.append("# Generated by download_exam_docs.py")
    lines.append("#")
    lines.append("# Usage: bash retry-failed.sh [--out <output-dir>]")
    lines.append("#   --out  Output directory (default: same as original download)")
    lines.append("set -euo pipefail")
    lines.append("")
    lines.append(f'OUT_DIR="{root}"')
    lines.append('for arg in "$@"; do')
    lines.append('  case "$arg" in')
    lines.append('    --out=*) OUT_DIR="${arg#*=}";;')
    lines.append('    --out)   shift; OUT_DIR="${1:-$OUT_DIR}";;')
    lines.append('  esac')
    lines.append('done')
    lines.append("")
    lines.append('PYTHON_SCRIPT="$HOME/.pi/agent/skills/microsoft-exam-docs/scripts/download_exam_docs.py"')
    lines.append("")
    lines.append(f'EXAM_CODE="{exam_slug.upper()}"')
    lines.append('echo "Retrying failed downloads for $EXAM_CODE..."')
    lines.append('echo "Output directory: $OUT_DIR"')
    lines.append('echo')
    lines.append("")
    lines.append('# Re-run the full download; the script will re-download and update files.')
    lines.append('python3 "$PYTHON_SCRIPT" "$EXAM_CODE" --out "$OUT_DIR"')

    (root / "retry-failed.sh").write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser():
    p = argparse.ArgumentParser(description="Download Microsoft Learn study material for an exam code.")
    p.add_argument("exam_code", help="Microsoft exam code, e.g. AB-620, PL-400, AZ-104")
    p.add_argument("--out", help="Output directory (default: microsoft-learn-<exam-code-lowercase>)")
    p.add_argument("--training-search", type=int, default=8,
                   help="Max search results to inspect per domain when discovering learning paths. Default: 8")
    p.add_argument("--paths", nargs="*", default=None,
                   help="One or more learning path URLs to download (skips auto-discovery)")
    return p


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    exam_code = args.exam_code.strip().upper()
    exam_code = re.sub(r"[^A-Z0-9-]", "", exam_code)
    if not re.match(r"^[A-Z]{1,4}-\d{2,4}$", exam_code):
        raise SystemExit(f"Invalid exam code: {exam_code!r}")
    exam_slug = exam_code.lower()

    out_root = Path(args.out or f"microsoft-learn-{exam_slug}").expanduser().resolve()
    out_root.mkdir(parents=True, exist_ok=True)

    # ── Step 1: Fetch study guide ──────────────────────────────────────
    study_url = f"{LEARN}/en-us/credentials/certifications/resources/study-guides/{exam_slug}"
    print(f"Fetching study guide: {study_url}")
    try:
        study_md = fetch_markdown(study_url)
    except HTTPError as e:
        raise SystemExit(f"Could not fetch study guide for {exam_code}: HTTP {e.code} {e.reason}")

    # ── Step 2: Discover learning paths ─────────────────────────────────
    if args.paths:
        path_urls = args.paths
        print(f"Using {len(path_urls)} explicitly provided learning path URL(s)")
    else:
        print(f"Discovering official learning paths for {exam_code}...")
        path_urls = discover_learning_paths(exam_code, study_md, args.training_search)
        print(f"Found {len(path_urls)} learning path(s)")

    # ── Step 3: Download all content ────────────────────────────────────
    failures: List[FailedItem] = []
    learning_paths: List[LearningPathContent] = []
    failed_path_urls: List[str] = []
    for path_url in path_urls:
        try:
            lp = download_learning_path(path_url, failures)
            learning_paths.append(lp)
            time.sleep(0.3)
        except Exception as e:
            print(f"  FAILED: {path_url} — {e}")
            failed_path_urls.append(path_url)
            failures.append(FailedItem(url=path_url, context=f"Learning path: {path_url}", error=str(e)))

    # ── Step 4: Write output files ──────────────────────────────────────
    path_files: List[Tuple[str, LearningPathContent]] = []
    for idx, lp in enumerate(learning_paths, start=1):
        filename = write_learning_path_file(out_root, idx, lp)
        path_files.append((filename, lp))
        print(f"Wrote {filename} ({len(lp.modules)} modules, {sum(len(m.units) for m in lp.modules)} units)")

    objectives = _parse_skill_objectives(study_md)
    write_summary(out_root, exam_code, study_md, objectives, path_files, failures)

    # ── Step 5: Write retry script for failures ─────────────────────────
    total_failed = len(failures)
    if total_failed > 0:
        _write_retry_script(out_root, exam_slug, learning_paths, failures, failed_path_urls)
        print(f"  Wrote retry-failed.sh ({total_failed} failed item(s))")

    total_units = sum(len(m.units) for lp in learning_paths for m in lp.modules)
    total_modules = sum(len(lp.modules) for lp in learning_paths)
    print(f"\n{'='*60}")
    print(f"{exam_code} study material saved to {out_root}")
    print(f"  {len(learning_paths)} learning paths  •  {total_modules} modules  •  {total_units} units")
    if total_failed:
        print(f"  ⚠ {total_failed} download(s) failed — run retry-failed.sh to re-download")
    else:
        print(f"  ✓ All downloads successful")
    print(f"  Files: SUMMARY.md + {len(path_files)} learning-path .md files")
    print(f"{'='*60}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
