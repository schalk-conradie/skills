#!/usr/bin/env python3
"""Download Microsoft Learn Markdown study material for a Microsoft exam code.

Example:
    python3 download_exam_docs.py AB-620
    python3 download_exam_docs.py PL-400 --out microsoft-learn-pl-400 --objective-search 2
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import re
import shutil
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, quote, urlencode, urljoin, urlparse, urlunparse
from urllib.request import Request, urlopen

LEARN = "https://learn.microsoft.com"
UA = "Mozilla/5.0 (compatible; pi-microsoft-exam-docs-skill/1.0; +https://learn.microsoft.com/)"
MAX_FILES_PER_RUN = 600
DEFAULT_OBJECTIVE_SEARCH = 2


@dataclass
class Item:
    group: str
    section: str
    subsection: str
    title: str
    url: str
    out_path: str
    final_url: Optional[str] = None
    status: Optional[int] = None
    content_type: Optional[str] = None
    bytes: int = 0
    sha256: Optional[str] = None
    error: Optional[str] = None
    source: Optional[str] = None


def fetch(url: str, accept: Optional[str] = None, timeout: int = 40) -> Tuple[int, str, bytes, str]:
    headers = {"User-Agent": UA}
    if accept:
        headers["Accept"] = accept
    req = Request(url, headers=headers)
    with urlopen(req, timeout=timeout) as resp:
        data = resp.read()
        return resp.status, resp.geturl(), data, resp.headers.get("content-type", "")


def normalize_exam_code(code: str) -> str:
    code = code.strip().upper()
    code = re.sub(r"[^A-Z0-9-]", "", code)
    if not re.match(r"^[A-Z]{1,4}-\d{2,4}$", code):
        raise SystemExit(f"Invalid-looking Microsoft exam code: {code!r} (expected like AB-620 or PL-400)")
    return code


def markdown_url(url: str) -> str:
    p = urlparse(url)
    qs = [(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True) if k.lower() != "accept"]
    qs.append(("accept", "text/markdown"))
    return urlunparse((p.scheme, p.netloc, p.path, p.params, urlencode(qs), p.fragment))


def canonical_url(url: str) -> str:
    # Preserve Learn paths exactly except for fragments. Some Learn routes (for example
    # /en-us/users/) depend on the trailing slash for rendered Markdown.
    p = urlparse(url)
    return urlunparse((p.scheme, p.netloc, p.path, p.params, p.query, ""))


def normalize_url(url: str, base: str = LEARN) -> str:
    url = html.unescape(url).strip()
    if not url:
        return url
    if url.startswith("/"):
        url = urljoin(base, url)
    elif url.startswith("http://docs.microsoft.com") or url.startswith("https://docs.microsoft.com"):
        p = urlparse(url)
        url = urlunparse(("https", "learn.microsoft.com", p.path, p.params, p.query, p.fragment))
    return url


def is_learn_url(url: str) -> bool:
    return urlparse(url).netloc.lower() == "learn.microsoft.com"


def slugify(text: str, max_len: int = 88) -> str:
    text = html.unescape(text or "").strip().lower()
    text = re.sub(r"[`'\u2019\u2018\"()]+", "", text)
    text = re.sub(r"&", " and ", text)
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = re.sub(r"-+", "-", text).strip("-")
    return (text[:max_len].strip("-") or "untitled")


def strip_tags(s: str) -> str:
    s = re.sub(r"<script\b.*?</script>", "", s, flags=re.S | re.I)
    s = re.sub(r"<style\b.*?</style>", "", s, flags=re.S | re.I)
    s = re.sub(r"<[^>]+>", " ", s)
    return " ".join(html.unescape(s).split())


def extract_meta(html_text: str) -> Dict[str, str]:
    meta: Dict[str, str] = {}
    patterns = [
        r'<meta\s+[^>]*(?:name|property)=["\']([^"\']+)["\'][^>]*content=["\']([^"\']*)["\'][^>]*>',
        r'<meta\s+[^>]*content=["\']([^"\']*)["\'][^>]*(?:name|property)=["\']([^"\']+)["\'][^>]*>',
    ]
    for idx, pat in enumerate(patterns):
        for m in re.finditer(pat, html_text, re.I):
            if idx == 0:
                key, val = m.group(1), m.group(2)
            else:
                val, key = m.group(1), m.group(2)
            meta[html.unescape(key)] = html.unescape(val)
    return meta


def extract_markdown_links(markdown: str) -> List[Tuple[str, str]]:
    links: List[Tuple[str, str]] = []
    # Inline markdown links. This intentionally ignores image links and refs.
    for text, url in re.findall(r"(?<!!)\[([^\]]+)\]\(([^)\s]+)(?:\s+['\"][^)]+['\"])?\)", markdown):
        url = normalize_url(url)
        if is_learn_url(url):
            links.append((strip_tags(text), url))
    return unique_links(links)


def unique_links(links: Iterable[Tuple[str, str]]) -> List[Tuple[str, str]]:
    seen = set()
    out: List[Tuple[str, str]] = []
    for title, url in links:
        key = canonical_url(url)
        if key in seen:
            continue
        seen.add(key)
        out.append((title or key, url))
    return out


def learn_search(query: str, take: int = 5) -> List[Dict[str, str]]:
    url = f"{LEARN}/api/search?" + urlencode({"search": query, "locale": "en-us", "$top": str(take)})
    try:
        status, _final, data, _ctype = fetch(url, timeout=25)
        if status != 200:
            return []
        raw = json.loads(data.decode("utf-8", "replace"))
    except Exception:
        return []
    results = []
    for item in raw.get("results", [])[:take]:
        item_url = normalize_url(str(item.get("url") or ""))
        if not is_learn_url(item_url):
            continue
        results.append({
            "title": strip_tags(str(item.get("title") or item_url)),
            "url": item_url,
            "category": str(item.get("category") or ""),
            "description": strip_tags(str(item.get("description") or "")),
        })
    return results


def parse_skill_objectives(study_md: str) -> List[Dict[str, str]]:
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
            if level == 2 and lower == "skills measured":
                in_skills = True
                current_domain = ""
                current_objective = ""
                continue
            if in_skills and level == 2 and lower != "skills measured":
                break
            if not in_skills:
                continue
            if level == 3:
                # Skip generic headings. Domains usually include a percentage.
                if "%" in title or re.search(r"\(\d+", title):
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


def infer_product_terms(study_md: str, exam_code: str) -> str:
    # Prefer words from audience profile/resource table that improve Microsoft Learn search relevance.
    terms = []
    candidates = [
        "Microsoft Copilot Studio", "Power Platform", "Dataverse", "Microsoft 365 Copilot",
        "Azure AI", "Azure", "Dynamics 365", "Power Apps", "Power Automate", "Power BI",
        "Microsoft Fabric", "Microsoft Foundry", "Security", "Microsoft Purview",
    ]
    lower = study_md.lower()
    for c in candidates:
        if c.lower() in lower:
            terms.append(c)
    return " ".join(terms[:5]) or exam_code


def save_markdown(root: Path, item: Item, cache: Dict[str, Dict[str, str]]) -> Item:
    out = root / item.out_path
    out.parent.mkdir(parents=True, exist_ok=True)
    base_url = canonical_url(item.url)
    md_url = markdown_url(base_url)
    try:
        if base_url in cache and Path(cache[base_url]["cache_path"]).exists():
            shutil.copyfile(cache[base_url]["cache_path"], out)
            item.final_url = cache[base_url]["final_url"]
            item.status = int(cache[base_url]["status"])
            item.content_type = cache[base_url]["content_type"]
            data = out.read_bytes()
        else:
            status, final_url, data, ctype = fetch(md_url, accept="text/markdown")
            item.status = status
            item.final_url = final_url.replace("?accept=text%2Fmarkdown", "").replace("?accept=text/markdown", "")
            item.content_type = ctype
            out.write_bytes(data)
            cache[base_url] = {
                "cache_path": str(out),
                "final_url": item.final_url or "",
                "status": str(status),
                "content_type": ctype,
            }
            time.sleep(0.12)
        item.bytes = len(data)
        item.sha256 = hashlib.sha256(data).hexdigest()
    except HTTPError as e:
        item.status = e.code
        item.error = f"HTTPError: {e.reason}"
    except (URLError, TimeoutError, OSError) as e:
        item.error = f"{type(e).__name__}: {e}"
    return item


def write_index(root: Path, exam_code: str, items: List[Item]) -> None:
    lines = [f"# {exam_code} Markdown Index\n"]
    groups = [
        "00-study-guide",
        "01-exam-certification-course-pages",
        "02-objective-search-docs",
        "03-official-study-guide-linked-pages",
    ]
    for group in groups:
        lines.append(f"\n## {group}\n")
        if group == "00-study-guide":
            lines.append(f"- [Official {exam_code} study guide](00-study-guide/{exam_code.lower()}-study-guide.md)\n")
            continue
        last_section = last_subsection = None
        for item in [x for x in items if x.group == group and not x.error]:
            if group == "02-objective-search-docs":
                if item.section != last_section:
                    lines.append(f"\n### {item.section}\n")
                    last_section = item.section
                    last_subsection = None
                if item.subsection != last_subsection:
                    lines.append(f"\n#### {item.subsection}\n")
                    last_subsection = item.subsection
            lines.append(f"- [{item.title}]({item.out_path.replace(' ', '%20')}) — {item.url}\n")
    (root / "INDEX.md").write_text("".join(lines), encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Download Microsoft Learn docs for a Microsoft exam code.")
    parser.add_argument("exam_code", help="Microsoft exam code, e.g. AB-620, PL-400, AZ-104")
    parser.add_argument("--out", help="Output directory (default: microsoft-learn-<exam-code-lowercase>)")
    parser.add_argument(
        "--objective-search",
        type=int,
        default=DEFAULT_OBJECTIVE_SEARCH,
        help="Top Microsoft Learn search results to download per skill bullet. Use 0 to disable. Default: 2",
    )
    parser.add_argument("--max-pages", type=int, default=MAX_FILES_PER_RUN, help="Safety cap on pages to attempt. Default: 600")
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    exam_code = normalize_exam_code(args.exam_code)
    exam_slug = exam_code.lower()
    out_root = Path(args.out or f"microsoft-learn-{exam_slug}").expanduser().resolve()
    out_root.mkdir(parents=True, exist_ok=True)
    (out_root / "metadata").mkdir(exist_ok=True)
    (out_root / "00-study-guide").mkdir(exist_ok=True)

    study_url = f"{LEARN}/en-us/credentials/certifications/resources/study-guides/{exam_slug}"
    print(f"Fetching official study guide: {study_url}")
    try:
        _sg_status, _sg_final, sg_html_b, _sg_html_ct = fetch(study_url)
    except HTTPError as e:
        raise SystemExit(f"Could not fetch official study guide for {exam_code}: HTTP {e.code} {e.reason}")
    sg_html = sg_html_b.decode("utf-8", "replace")
    sg_meta = extract_meta(sg_html)
    (out_root / "metadata" / "official-study-guide.html").write_bytes(sg_html_b)

    _md_status, _md_final, sg_md_b, _md_ct = fetch(markdown_url(study_url), accept="text/markdown")
    study_md = sg_md_b.decode("utf-8", "replace")
    study_path = out_root / "00-study-guide" / f"{exam_slug}-study-guide.md"
    study_path.write_bytes(sg_md_b)

    items: List[Item] = []

    # Direct official links from the study guide resource tables.
    direct_links = extract_markdown_links(study_md)
    for idx, (title, url) in enumerate(direct_links, start=1):
        items.append(Item(
            "03-official-study-guide-linked-pages", "", "", title, url,
            f"03-official-study-guide-linked-pages/{idx:02d}-{slugify(title)}.md",
            source="official study guide link",
        ))

    # Learn Search for exam/cert/course pages.
    exam_page_links: List[Tuple[str, str]] = []
    for result in learn_search(f'"{exam_code}" Microsoft Learn certification exam course', take=12):
        title = result["title"]
        url = result["url"]
        if exam_slug in url.lower() or exam_code.lower() in title.lower():
            exam_page_links.append((title, url))
    exam_page_links = unique_links(exam_page_links)
    for idx, (title, url) in enumerate(exam_page_links, start=1):
        items.append(Item(
            "01-exam-certification-course-pages", "", "", title, url,
            f"01-exam-certification-course-pages/{idx:02d}-{slugify(title)}.md",
            source="Microsoft Learn search for exam code",
        ))

    # Objective docs via Microsoft Learn Search.
    if args.objective_search > 0:
        objectives = parse_skill_objectives(study_md)
        product_terms = infer_product_terms(study_md, exam_code)
        per_folder_count: Dict[str, int] = {}
        seen_by_folder_url = set()
        print(f"Discovered {len(objectives)} skill bullets; searching top {args.objective_search} docs per bullet")
        for rec in objectives:
            query = f'{rec["task"]} {product_terms}'
            results = learn_search(query, take=max(1, min(5, args.objective_search)))
            folder = (
                f"02-objective-search-docs/{slugify(rec['domain'], 64)}/"
                f"{slugify(rec['objective'], 64)}/{slugify(rec['task'], 72)}"
            )
            for result in results[: args.objective_search]:
                url = result["url"]
                # Avoid downloading certification/support/Q&A pages as objective docs.
                if "/answers/" in url or "/credentials/" in url:
                    continue
                key = (folder, canonical_url(url))
                if key in seen_by_folder_url:
                    continue
                seen_by_folder_url.add(key)
                per_folder_count[folder] = per_folder_count.get(folder, 0) + 1
                n = per_folder_count[folder]
                title = result["title"]
                items.append(Item(
                    "02-objective-search-docs", rec["objective"], rec["task"], title, url,
                    f"{folder}/{n:02d}-{slugify(title)}.md",
                    source=f"Microsoft Learn Search query: {query}",
                ))
                if len(items) >= args.max_pages:
                    break
            if len(items) >= args.max_pages:
                break

    # Safety cap and de-dupe exact output paths.
    items = items[: args.max_pages]
    out_path_counts: Dict[str, int] = {}
    for item in items:
        if item.out_path not in out_path_counts:
            out_path_counts[item.out_path] = 1
        else:
            out_path_counts[item.out_path] += 1
            p = Path(item.out_path)
            item.out_path = str(p.with_name(f"{p.stem}-{out_path_counts[item.out_path]}{p.suffix}"))

    cache: Dict[str, Dict[str, str]] = {}
    results: List[Item] = []
    for item in items:
        print(f"Downloading {item.url} -> {item.out_path}")
        results.append(save_markdown(out_root, item, cache))

    manifest = {
        "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "exam_code": exam_code,
        "official_study_guide": study_url,
        "identified_repo": {
            "repository_hint": (sg_meta.get("original_content_git_url") or "").split("github.com/")[-1].split("/blob/")[0] or None,
            "source_path": sg_meta.get("source_path"),
            "original_content_git_url": sg_meta.get("original_content_git_url"),
            "gitcommit": sg_meta.get("gitcommit"),
            "git_commit_id": sg_meta.get("git_commit_id"),
            "depot_name": sg_meta.get("depot_name"),
            "access_note": "If the metadata points to a *-pr repository, it may not be publicly accessible. Content was downloaded from learn.microsoft.com rendered Markdown endpoints.",
        },
        "settings": {"objective_search": args.objective_search, "max_pages": args.max_pages},
        "counts": {
            "items_attempted": len(results),
            "items_downloaded": sum(1 for r in results if not r.error),
            "items_failed": sum(1 for r in results if r.error),
            "unique_urls": len(set(canonical_url(r.url) for r in results)),
        },
        "items": [asdict(r) for r in results],
    }
    (out_root / "metadata" / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    fields = list(asdict(results[0]).keys()) if results else ["url", "error"]
    with (out_root / "metadata" / "manifest.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for r in results:
            writer.writerow(asdict(r))

    failures = [r for r in results if r.error]
    with (out_root / "metadata" / "failures.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for r in failures:
            writer.writerow(asdict(r))

    repo = manifest["identified_repo"]
    repo_info = f"""# {exam_code} source repository identification\n\nOfficial Microsoft Learn study guide: {study_url}\n\nMicrosoft Learn metadata identifies:\n\n- Repository hint: `{repo['repository_hint']}`\n- Source path: `{repo['source_path']}`\n- Original content Git URL: {repo['original_content_git_url']}\n- Commit URL: {repo['gitcommit']}\n- Commit ID: `{repo['git_commit_id']}`\n- Depot name: `{repo['depot_name']}`\n\nNote: Microsoft Learn often uses private `*-pr` repos in metadata. Anonymous GitHub access may fail even when the repo/path is identified. This downloader saves rendered Markdown from Microsoft Learn instead.\n"""
    (out_root / "metadata" / "repo-info.md").write_text(repo_info, encoding="utf-8")

    readme = f"""# Microsoft Learn {exam_code} Documentation Download\n\nThis folder contains Markdown downloaded from Microsoft Learn for **{exam_code}**.\n\n## Source repository identified\n\nSee `metadata/repo-info.md`. Repository hint: `{repo['repository_hint']}`.\n\n## Folder structure\n\n- `00-study-guide/` — official {exam_code} study guide Markdown.\n- `01-exam-certification-course-pages/` — exam/certification/course pages found by Microsoft Learn Search.\n- `02-objective-search-docs/` — Microsoft Learn docs discovered by searching each skill bullet from the study guide.\n- `03-official-study-guide-linked-pages/` — direct Microsoft Learn links found in the study guide.\n- `metadata/` — manifest, source metadata, failures, and repo identification.\n- `INDEX.md` — clickable index of downloaded Markdown files.\n\n## Download summary\n\n- Attempted: {manifest['counts']['items_attempted']} pages\n- Downloaded: {manifest['counts']['items_downloaded']} pages\n- Failed: {manifest['counts']['items_failed']} pages\n- Unique URLs: {manifest['counts']['unique_urls']}\n\nSee `metadata/manifest.csv` or `metadata/manifest.json` for source URL to file mappings.\n"""
    (out_root / "README.md").write_text(readme, encoding="utf-8")
    write_index(out_root, exam_code, results)

    print("\nDone.")
    print(json.dumps(manifest["counts"], indent=2))
    print(f"Output: {out_root}")
    if failures:
        print(f"Failures: {out_root / 'metadata' / 'failures.csv'}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
