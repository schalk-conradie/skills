#!/usr/bin/env python3
"""Download Microsoft Learn study material for a Microsoft certification exam code.

Produces an offline Markdown output:
  - SUMMARY.md  — exam metadata, skills measured, learning path index
  - CONTENT.md  — all learning path modules and unit lesson text
  - media/      — images referenced by CONTENT.md

Example:
    python3 download_exam_docs.py AB-620
    python3 download_exam_docs.py PL-400 --out microsoft-learn-pl-400
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import posixpath
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, unquote, urlencode, urljoin, urlparse, urlunparse
from urllib.request import Request, urlopen

LEARN = "https://learn.microsoft.com"
UA = "Mozilla/5.0 (compatible; pi-microsoft-exam-docs-skill/1.0)"
IMAGE_EXTENSIONS = {".apng", ".bmp", ".gif", ".jpeg", ".jpg", ".png", ".svg", ".webp"}


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


def _without_fragment(url: str) -> str:
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
    if not (_is_learn_url(url) and "/training/modules/" in path):
        return False
    # Exclude unit pages (anything after the module slug).
    return re.fullmatch(r"/en-us/training/modules/[^/]+/?", path) is not None


def _module_url_from_slug(slug: str) -> str:
    return _canonical(f"{LEARN}/en-us/training/modules/{slug}/")


def _extract_module_urls_from_path(path_url: str) -> List[Tuple[str, str]]:
    """Get module URLs from a learning path overview page."""
    overview_md = fetch_markdown(path_url)
    modules: List[Tuple[str, str]] = []
    seen = set()
    for slug in re.findall(r"modules/([a-z0-9-]+)", overview_md):
        if slug in seen:
            continue
        seen.add(slug)
        url = _module_url_from_slug(slug)
        modules.append((_title_from_slug(slug), url))

    if modules:
        return modules

    html_text = fetch_html(path_url)
    return [(t, u) for t, u in _extract_html_links(html_text, path_url) if _is_training_module_url(u)]


def _extract_unit_urls_from_module(module_url: str) -> List[Tuple[str, str]]:
    """Get unit URLs from a module page (supports numbered and slug-based unit links)."""
    module_md = fetch_markdown(module_url)
    unit_links: List[Tuple[str, str]] = []
    seen = set()

    def add_unit(title: str, slug: str) -> None:
        slug = slug.strip()
        if not slug or slug.startswith(("http://", "https://", "/")):
            return
        url = _canonical(urljoin(module_url.rstrip("/") + "/", slug))
        if url in seen:
            return
        seen.add(url)
        unit_links.append((title.strip(), url))

    for match in re.finditer(r"\[([^\]]+)\]\(([^)]+)\)\s*min\b", module_md):
        add_unit(match.group(1), match.group(2))

    if not unit_links:
        for match in re.finditer(r"\[([^\]]+)\]\((\d-[^)]+)\)", module_md):
            add_unit(match.group(1), match.group(2))

    if unit_links:
        return unit_links

    html_text = fetch_html(module_url)
    for match in re.finditer(r'<a\b[^>]*href=["\'](\d-[^"\']+)["\'][^>]*>(.*?)</a>', html_text, re.I | re.S):
        add_unit(_strip_tags(match.group(2)) or _title_from_slug(match.group(1)), match.group(1))

    return unit_links


def _module_title_from_markdown(module_url: str) -> str:
    module_md = fetch_markdown(module_url)
    titles = re.findall(r"^#\s+(.+)$", module_md, re.M)
    if len(titles) >= 2:
        return re.sub(r"\s*\|\s*Microsoft Learn\s*$", "", titles[1]).strip()
    if titles:
        return re.sub(r"\s*\|\s*Microsoft Learn\s*$", "", titles[0]).strip()
    return _title_from_slug(urlparse(module_url).path)

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


# ── Media helpers ──────────────────────────────────────────────────────────

def _is_probable_image_url(url: str) -> bool:
    path = urlparse(url).path.lower()
    return posixpath.splitext(path)[1] in IMAGE_EXTENSIONS


def _safe_path_segment(value: str, fallback: str) -> str:
    value = unquote(value or "")
    value = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip(".-")
    return value or fallback


def _asset_scope_from_base_url(base_url: str) -> str:
    path = urlparse(base_url).path
    module_match = re.search(r"/training/modules/([^/]+)", path, re.I)
    if module_match:
        return _safe_path_segment(module_match.group(1), "module")

    slug = path.strip("/").split("/")[-1]
    return _safe_path_segment(slug, "shared")


def _split_markdown_destination(raw: str) -> Optional[Tuple[str, str, bool]]:
    stripped = raw.strip()
    if not stripped:
        return None
    if stripped.startswith("<"):
        end = stripped.find(">")
        if end == -1:
            return None
        target = stripped[1:end].strip()
        suffix = stripped[end + 1:].strip()
        return target, suffix, True

    parts = stripped.split(maxsplit=1)
    target = parts[0].strip()
    suffix = parts[1].strip() if len(parts) > 1 else ""
    return target, suffix, False


def _format_markdown_destination(target: str, suffix: str, bracketed: bool) -> str:
    if bracketed:
        dest = f"<{target}>"
    else:
        dest = target
    if suffix:
        dest = f"{dest} {suffix}"
    return dest


class AssetDownloader:
    """Download Microsoft Learn images and rewrite Markdown links to local files."""

    def __init__(self, root: Path, failures: List[FailedItem],
                 asset_timeout: int = 20, asset_retries: int = 1,
                 skip_media: bool = False, log_assets: bool = True) -> None:
        self.root = root
        self.failures = failures
        self.asset_timeout = max(1, asset_timeout)
        self.asset_retries = max(0, asset_retries)
        self.skip_media = skip_media
        self.log_assets = log_assets
        self.cache: Dict[str, str] = {}
        self.failed_urls: set = set()
        self.path_sources: Dict[str, str] = {}
        self.seen_count = 0
        self.downloaded_count = 0
        self.reused_count = 0
        self.failed_count = 0

    def rewrite_markdown_assets(self, markdown: str, base_url: str, context: str) -> str:
        def repl_markdown(match: re.Match) -> str:
            parsed = _split_markdown_destination(match.group(1))
            if not parsed:
                return match.group(0)
            target, suffix, bracketed = parsed
            local = self.localize(target, base_url, context)
            if not local:
                return match.group(0)
            return f"]({_format_markdown_destination(local, suffix, bracketed)})"

        def repl_html(match: re.Match) -> str:
            local = self.localize(match.group(2), base_url, context)
            if not local:
                return match.group(0)
            return f"{match.group(1)}{local}{match.group(3)}"

        markdown = re.sub(r"\]\(([^)\n]+)\)", repl_markdown, markdown)
        markdown = re.sub(r"(<img\b[^>]*\bsrc=[\"'])([^\"']+)([\"'])",
                          repl_html, markdown, flags=re.I)
        return markdown

    def localize(self, target: str, base_url: str, context: str) -> Optional[str]:
        asset_url = self._resolve_asset_url(target, base_url)
        if not asset_url or self.skip_media:
            return None
        if asset_url in self.cache:
            return self.cache[asset_url]
        if asset_url in self.failed_urls:
            return None

        rel_path = self._allocate_local_path(asset_url, base_url)
        dest = self.root / rel_path
        local = rel_path.as_posix()
        if dest.exists() and dest.stat().st_size > 0:
            self.cache[asset_url] = local
            self.reused_count += 1
            if self.log_assets:
                print(f"      Media reused: {local}", flush=True)
            return local

        self.seen_count += 1
        attempts = self.asset_retries + 1
        last_error: Optional[Exception] = None
        for attempt in range(1, attempts + 1):
            if self.log_assets:
                retry_note = f" attempt {attempt}/{attempts}" if attempts > 1 else ""
                print(f"      Media {self.seen_count}:{retry_note} {local}", flush=True)
                print(f"        {asset_url}", flush=True)
            try:
                _status, final_url, data, _ctype = fetch(asset_url, accept="image/*", timeout=self.asset_timeout)
                if not data:
                    raise ValueError("empty response")
                dest.parent.mkdir(parents=True, exist_ok=True)
                tmp_dest = dest.with_name(dest.name + ".tmp")
                tmp_dest.write_bytes(data)
                tmp_dest.replace(dest)
                self.cache[asset_url] = local
                if final_url and _without_fragment(final_url) != asset_url:
                    self.cache[_without_fragment(final_url)] = local
                self.downloaded_count += 1
                return local
            except Exception as e:
                last_error = e
                if attempt < attempts:
                    print(f"        retrying after error: {e}", flush=True)
                    time.sleep(min(2 * attempt, 5))

        self.failed_count += 1
        self.failed_urls.add(asset_url)
        error = str(last_error) if last_error else "unknown error"
        print(f"      Media FAILED: {local} — {error}", flush=True)
        self.failures.append(FailedItem(
            url=asset_url,
            context=f"{context} > Asset: {target}",
            error=error,
        ))
        return None

    def _resolve_asset_url(self, target: str, base_url: str) -> Optional[str]:
        target = html.unescape(target.strip())
        if not target or target.startswith("#"):
            return None
        lower = target.lower()
        if lower.startswith(("data:", "javascript:", "mailto:", "tel:")):
            return None
        if target.startswith("//"):
            target = "https:" + target

        target = _without_fragment(target)
        parsed = urlparse(target)
        if parsed.scheme and parsed.scheme not in ("http", "https"):
            return None
        if parsed.scheme:
            asset_url = target
        else:
            asset_url = urljoin(base_url.rstrip("/") + "/", target)

        if not _is_probable_image_url(asset_url):
            return None
        return _without_fragment(asset_url)

    def _allocate_local_path(self, asset_url: str, base_url: str) -> Path:
        scope = _asset_scope_from_base_url(base_url)
        filename = _safe_path_segment(posixpath.basename(urlparse(asset_url).path), "image")
        if posixpath.splitext(filename)[1].lower() not in IMAGE_EXTENSIONS:
            filename = f"{filename}.img"

        rel_path = Path("media") / scope / filename
        rel_key = rel_path.as_posix()
        existing_source = self.path_sources.get(rel_key)
        if existing_source and existing_source != asset_url:
            digest = hashlib.sha1(asset_url.encode("utf-8")).hexdigest()[:8]
            path_obj = Path(filename)
            filename = f"{path_obj.stem}-{digest}{path_obj.suffix}"
            rel_path = Path("media") / scope / filename
            rel_key = rel_path.as_posix()

        self.path_sources[rel_key] = asset_url
        return rel_path


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
              "Power Pages", "Dynamics 365", "Copilot Studio", "Microsoft Fabric", "Azure"]:
        if c.lower() in study_md.lower():
            terms.append(c)
    return " ".join(terms[:5]) or exam_code


def _exam_product_tokens(study_md: str) -> set:
    catalog = [
        "power platform", "dataverse", "power apps", "power automate", "power bi",
        "power pages", "dynamics 365", "copilot studio", "microsoft fabric", "azure",
        "cosmos db", "sql server", "sharepoint", "teams",
    ]
    lower = study_md.lower()
    tokens: set = set()
    for phrase in catalog:
        if phrase in lower:
            tokens.update(_significant_tokens(phrase))
    return tokens


def _path_relevance_score(path_title: str, path_url: str, exam_code: str,
                          product_tokens: set, objective_text: str,
                          path_roles: Optional[set] = None,
                          audience_roles: Optional[set] = None) -> int:
    haystack = f"{path_title} {urlparse(path_url).path.replace('-', ' ')}"
    path_tokens = _significant_tokens(haystack)
    obj_tokens = _significant_tokens(objective_text)
    score = len(path_tokens & obj_tokens)

    if product_tokens and path_tokens & product_tokens:
        score += 2

    developer_terms = {"developer", "extend", "component", "framework", "plugin", "plug",
                       "connector", "scripting", "lifecycle", "integrate", "dataverse", "custom"}
    if path_tokens & developer_terms:
        score += 1

    if audience_roles and path_roles:
        if audience_roles & path_roles:
            score += 3
        elif "developer" in audience_roles and path_roles & {"app-maker", "business-user"} and "developer" not in path_roles:
            score -= 3

    if "azure" in path_tokens and "azure" not in product_tokens:
        score -= 3
    if re.search(r"\baz-\d", path_title.lower()) and not exam_code.lower().startswith("az-"):
        score -= 4
    if re.search(r"\bms-\d", path_title.lower()) and not exam_code.lower().startswith("ms-"):
        score -= 4
    if re.search(r"\bdp-\d", path_title.lower()) and not exam_code.lower().startswith("dp-"):
        score -= 4

    return score


def _audience_roles(study_md: str) -> set:
    roles: set = set()
    match = re.search(r"### Audience profile\s*\n([\s\S]*?)(?=\n###|\n##|\Z)", study_md)
    if not match:
        return roles
    text = match.group(1).lower()
    for role in ["developer", "administrator", "analyst", "architect", "consultant",
                 "engineer", "functional", "admin"]:
        if role in text:
            roles.add(role)
    return roles


def _path_roles(path_url: str) -> set:
    md = fetch_markdown(path_url)
    return set(re.findall(r"roles=([^&\]\)]+)", md))


def _exam_short_name(study_md: str) -> str:
    h1 = re.search(r"^#\s+(.+)$", study_md, re.M)
    if not h1:
        return ""
    name = re.sub(r"\s*\|\s*Microsoft Learn\s*$", "", h1.group(1).strip())
    return re.sub(r"^Study guide for Exam [^:]+:\s*", "", name, flags=re.I).strip()


def _supplement_discovery_queries(objective_text: str, product_terms: str) -> List[str]:
    """Add targeted searches for common technical topics mentioned in exam objectives."""
    lower = objective_text.lower()
    queries: List[str] = []
    supplements = [
        ("component framework", "Power Apps Component Framework"),
        ("custom connector", "custom connectors"),
        ("client scripting", "client scripting command bar"),
        ("lifecycle", "application lifecycle management"),
        ("plug-in", "Dataverse plug-in"),
        ("plugin", "Dataverse plugin"),
        ("custom api", "Dataverse custom API"),
        ("canvas app", "canvas apps developer"),
        ("model-driven", "model-driven apps developer"),
        ("power fx", "Power Fx"),
    ]
    for needle, phrase in supplements:
        if needle in lower:
            queries.append(f'"{phrase}" {product_terms} learning path')
    if re.search(r"\bintegrat", lower) and "azure" in lower:
        queries.append(f'"Integrate with Dataverse and Azure" {product_terms} learning path')
    return queries


def _supplement_path_titles(objective_text: str) -> List[str]:
    """Return likely Microsoft Learn learning path titles to resolve exactly."""
    lower = objective_text.lower()
    titles: List[str] = []
    if "component framework" in lower:
        titles.extend([
            "Build basic code components with the Power Apps Component Framework",
            "Create components with Power Apps Component Framework",
        ])
    if "custom connector" in lower:
        titles.append("Get started with custom connectors for Microsoft Power Platform")
    if "client scripting" in lower:
        titles.append("Extend the user experience with client scripting and command bar customization")
    if "lifecycle" in lower:
        titles.append("Basic application lifecycle management in Microsoft Power Platform")
    if re.search(r"\bintegrat", lower) and "azure" in lower:
        titles.append("Integrate with Dataverse and Azure")
    if "plug-in" in lower or "plugin" in lower or "dataverse" in lower:
        titles.append("Extending Power Platform Dataverse")
    if "canvas app" in lower:
        titles.append("Use advance techniques in canvas apps to perform custom updates and optimization")
    if "model-driven" in lower:
        titles.append("Extend Power Platform user experience with model-driven apps")
    if "developer" in lower:
        titles.append("Introduction to developing with Microsoft Power Platform")
    return titles


def _resolve_exact_path_titles(titles: List[str]) -> Dict[str, str]:
    candidates: Dict[str, str] = {}
    for title in titles:
        for result in _learn_search(f'"{title}"', take=3):
            url = _canonical(result["url"])
            if _is_training_path_url(url):
                candidates[url] = result["title"]
                break
        time.sleep(0.05)
    return candidates


def _discovery_queries(exam_code: str, study_md: str, objectives: List[Dict[str, str]],
                       product_terms: str, exam_name: str) -> List[str]:
    queries: List[str] = [
        f"{exam_code} learning path",
    ]
    if exam_name:
        queries.extend([
            f'"{exam_name}" learning path',
            f'"{exam_name}" developer learning path',
        ])
    if product_terms:
        primary_label = " ".join(product_terms.split()[0:2])
        queries.extend([
            f"{product_terms} developer learning path",
            f"{primary_label} developer extend learning path",
            f"{product_terms} learning path",
        ])

    domain_titles: List[str] = []
    for rec in objectives:
        domain = _clean_skill_title(rec["domain"])
        if domain and domain not in domain_titles:
            domain_titles.append(domain)
            queries.append(f'"{domain}" {product_terms} learning path')

    task_keywords: set = set()
    for rec in objectives:
        task_keywords.update(_significant_tokens(rec["task"] + " " + rec["objective"]))
    for kw in sorted(task_keywords, key=len, reverse=True)[:8]:
        queries.append(f"{kw} {product_terms} developer learning path")

    objective_text = " ".join(
        f"{rec['domain']} {rec['objective']} {rec['task']}" for rec in objectives
    )
    queries.extend(_supplement_discovery_queries(objective_text, product_terms))

    return queries


def _collect_path_candidates(queries: List[str], search_breadth: int) -> Dict[str, str]:
    """Search Microsoft Learn and expand result titles into canonical path URLs."""
    candidates: Dict[str, str] = {}
    titles_to_expand: set = set()
    # Microsoft Learn search returns different result sets below take=25.
    take = min(25, max(25, search_breadth))

    for query in queries:
        for result in _learn_search(query, take=take):
            url = _canonical(result["url"])
            if _is_training_path_url(url):
                candidates[url] = result["title"]
            title = result.get("title", "")
            if " - Training" in title:
                titles_to_expand.add(title.split(" - Training")[0].strip())
        time.sleep(0.1)

    for title in sorted(titles_to_expand):
        for result in _learn_search(f'"{title}"', take=3):
            url = _canonical(result["url"])
            if _is_training_path_url(url):
                candidates[url] = result["title"]
        time.sleep(0.05)

    return candidates


def discover_learning_paths(exam_code: str, study_md: str, search_breadth: int) -> List[str]:
    """Discover relevant Microsoft Learn learning paths for an exam."""
    objectives = _parse_skill_objectives(study_md)
    if not objectives:
        return []

    objective_text = " ".join(
        f"{rec['domain']} {rec['objective']} {rec['task']}" for rec in objectives
    )
    product_terms = _infer_product_terms(study_md, exam_code)
    product_tokens = _exam_product_tokens(study_md)
    exam_name = _exam_short_name(study_md)
    audience_roles = _audience_roles(study_md)

    queries = _discovery_queries(exam_code, study_md, objectives, product_terms, exam_name)
    candidates = _collect_path_candidates(queries, search_breadth)
    candidates.update(_resolve_exact_path_titles(_supplement_path_titles(objective_text)))

    scored: List[Tuple[int, str, set]] = []
    for url, title in candidates.items():
        roles = _path_roles(url)
        score = _path_relevance_score(
            title, url, exam_code, product_tokens, objective_text, roles, audience_roles
        )
        scored.append((score, url, roles))

    if "developer" in audience_roles:
        developer_paths = [
            (score, url, roles) for score, url, roles in scored
            if "developer" in roles and score >= 6
        ]
        if len(developer_paths) >= 5:
            scored = developer_paths

    # Drop clearly off-topic paths when enough exam-aligned content was found.
    if product_tokens & {"power", "platform", "dataverse", "apps", "automate"}:
        off_topic_slugs = (
            "azure-data-fundamentals", "aspnet-core", "microsoft-365",
            "ms-900", "az-400", "ai-fluency", "develop-language-solutions",
            "create-azure-app-service", "introduction-cloud-infrastructure",
        )
        filtered = [
            (score, url, roles) for score, url, roles in scored
            if not (score < 9 and any(token in urlparse(url).path for token in off_topic_slugs))
        ]
        if len(filtered) >= 8:
            scored = filtered

    scored = [(score, url, roles) for score, url, roles in scored if score >= 3]
    if len(scored) < 4:
        scored = [(score, url, roles) for score, url, roles in scored if score >= 2]

    scored.sort(key=lambda item: (-item[0], item[1]))
    return [url for _, url, _ in scored]


# ── Training content download ──────────────────────────────────────────────

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
        mod_title = _module_title_from_markdown(mod_url)
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

def _format_learning_path_content(lp: LearningPathContent,
                                  asset_downloader: Optional[AssetDownloader] = None) -> str:
    """Render one learning path (modules + units) as Markdown."""
    lines: List[str] = []

    lines.append(f"# {lp.title}\n")
    lines.append(f"> Source: [{lp.url}]({lp.url})\n")

    overview_text = lp.overview_markdown
    desc_lines: List[str] = []
    in_description = False
    for line in overview_text.split("\n"):
        stripped = line.strip()
        if stripped.startswith("## At a glance") or stripped.startswith("## Prerequisites"):
            break
        if stripped.startswith("# "):
            continue
        if stripped.startswith("![]"):
            continue
        if stripped and not in_description and len(stripped) > 30:
            in_description = True
        if in_description and stripped:
            desc_lines.append(line)
        elif in_description and not stripped:
            break
    if desc_lines:
        desc_text = "\n".join(desc_lines)
        if asset_downloader:
            desc_text = asset_downloader.rewrite_markdown_assets(
                desc_text, lp.url, f"LP: {lp.title} > Overview"
            )
        lines.append(desc_text + "\n")

    lines.append("\n---\n")

    for mi, mod in enumerate(lp.modules, start=1):
        lines.append(f"\n## Module {mi}: {mod.title}\n")
        lines.append(f"> Source: [{mod.url}]({mod.url})\n")

        for ui, unit in enumerate(mod.units, start=1):
            lines.append(f"\n### {ui}. {unit.title}\n")
            unit_text = unit.markdown
            unit_text = re.sub(r"^#\s+.+\n", "", unit_text, count=1)
            unit_text = re.sub(r"^Completed\s*\n", "", unit_text)
            unit_text = re.sub(r"^\-\s+\d+\s+min(?:utes)?\s*\n", "", unit_text)
            if asset_downloader:
                context = f"LP: {lp.title} > Module: {mod.title} > Unit: {unit.title}"
                unit_text = asset_downloader.rewrite_markdown_assets(unit_text, mod.url, context)
            lines.append(unit_text.rstrip("\n") + "\n")
            if ui < len(mod.units):
                lines.append("\n---\n")

        if mi < len(lp.modules):
            lines.append("\n---\n")

    return "\n".join(lines)


def write_content_file(root: Path, exam_code: str, learning_paths: List[LearningPathContent],
                       failures: List[FailedItem], asset_timeout: int = 20,
                       asset_retries: int = 1, skip_media: bool = False,
                       log_assets: bool = True) -> AssetDownloader:
    """Write all learning path lesson content into a single CONTENT.md."""
    lines: List[str] = []
    asset_downloader = AssetDownloader(
        root,
        failures,
        asset_timeout=asset_timeout,
        asset_retries=asset_retries,
        skip_media=skip_media,
        log_assets=log_assets,
    )
    lines.append(f"# {exam_code} — Microsoft Learn training content\n")
    lines.append("All official learning paths, modules, and units for this exam.\n")

    if skip_media:
        print("Writing CONTENT.md without downloading media assets", flush=True)
    else:
        print(
            f"Writing CONTENT.md and downloading media assets "
            f"(timeout {asset_downloader.asset_timeout}s, retries {asset_downloader.asset_retries})",
            flush=True,
        )

    for idx, lp in enumerate(learning_paths, start=1):
        if idx > 1:
            lines.append("\n\n---\n\n")
        lines.append(_format_learning_path_content(lp, asset_downloader))

    (root / "CONTENT.md").write_text("\n".join(lines), encoding="utf-8")
    return asset_downloader


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
                  learning_paths: List[LearningPathContent],
                  failures: List[FailedItem]) -> None:
    """Write a compact SUMMARY.md with exam metadata and section overview."""
    lines: List[str] = []

    study_meta = _parse_exam_metadata(study_md)
    cert_meta = _fetch_cert_metadata(exam_code.lower())
    merged = {**study_meta, **cert_meta}
    skill_glance: Dict[str, str] = merged.get("skill_glance", {})  # type: ignore[assignment]

    cert_name = merged.get("name", f"Exam {exam_code}")
    lines.append(f"# {cert_name}\n")

    details: List[Tuple[str, str]] = [("Exam code", exam_code)]
    if "duration_minutes" in merged:
        details.append(("Duration", f"{merged['duration_minutes']} minutes"))
    if "pass_score" in merged:
        details.append(("Passing score", f"{merged['pass_score']} / 1000"))
    if merged.get("proctored"):
        details.append(("Proctored", "Yes"))
    if merged.get("level"):
        details.append(("Level", merged["level"]))
    if merged.get("languages"):
        details.append(("Languages", merged["languages"]))

    lines.append("## Exam details\n")
    lines.append("| | |")
    lines.append("|---|---|")
    for label, value in details:
        lines.append(f"| **{label}** | {value} |")
    lines.append("")

    useful_links: Dict[str, str] = merged.get("useful_links", {})  # type: ignore[assignment]
    if useful_links:
        lines.append("## Useful links\n")
        for label, url in useful_links.items():
            lines.append(f"- [{label}]({url})")
        lines.append("")

    lines.append("## Skills measured\n")
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

    lines.append("## Learning paths\n")
    lines.append("Full lesson text is in [CONTENT.md](CONTENT.md).\n")
    lines.append("| # | Learning path | Modules | Units | Status |")
    lines.append("|---|---|---|---|---|")
    for idx, lp in enumerate(learning_paths, start=1):
        n_modules = len(lp.modules)
        n_units = sum(len(m.units) for m in lp.modules)
        has_failure = any(f"LP: {lp.title}" in f.context for f in failures)
        status = "⚠ partial" if has_failure else "✓"
        lines.append(f"| {idx} | {lp.title} | {n_modules} | {n_units} | {status} |")
    lines.append("")

    if failures:
        lines.append("## ⚠ Failed downloads\n")
        lines.append(f"{len(failures)} item(s) failed. Run `retry-failed.sh` to re-download.\n")
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
    lines.append('PYTHON_SCRIPT="$HOME/.agents/skills/microsoft-exam-docs/scripts/download_exam_docs.py"')
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
    p.add_argument("--asset-timeout", type=int, default=20,
                   help="Seconds to wait for each image asset request. Default: 20")
    p.add_argument("--asset-retries", type=int, default=1,
                   help="Retries per image asset before recording a failure. Default: 1")
    p.add_argument("--no-media", action="store_true",
                   help="Skip downloading image assets; CONTENT.md keeps original relative image links.")
    p.add_argument("--quiet-media", action="store_true",
                   help="Do not print one line per media asset while CONTENT.md is written.")
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
        if len(path_urls) > 15:
            print(
                "  Note: this is a large download. Use --paths for a focused run, "
                "--no-media for text-only output, or lower --asset-timeout if image requests are slow.",
                flush=True,
            )

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
    asset_downloader = write_content_file(
        out_root,
        exam_code,
        learning_paths,
        failures,
        asset_timeout=args.asset_timeout,
        asset_retries=args.asset_retries,
        skip_media=args.no_media,
        log_assets=not args.quiet_media,
    )
    content_size = (out_root / "CONTENT.md").stat().st_size
    print(f"Wrote CONTENT.md ({content_size:,} bytes, {len(learning_paths)} learning paths)")
    if args.no_media:
        print("Skipped media/ download")
    else:
        print(
            f"Wrote media/ ({asset_downloader.downloaded_count:,} downloaded, "
            f"{asset_downloader.reused_count:,} reused, {asset_downloader.failed_count:,} failed)"
        )

    objectives = _parse_skill_objectives(study_md)
    write_summary(out_root, exam_code, study_md, objectives, learning_paths, failures)

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
    files_note = "SUMMARY.md + CONTENT.md"
    if not args.no_media and (asset_downloader.downloaded_count or asset_downloader.reused_count):
        files_note += " + media/"
    print(f"  Files: {files_note}")
    print(f"{'='*60}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
