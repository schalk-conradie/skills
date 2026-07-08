#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path


DEFAULT_VAULT = Path("/Users/schalk/Documents/The Brainium")
REGISTRY_PATH = Path("99 Meta") / "project-registry.json"
HOME_ROOT = Path("100 Home")
SKIP_DIRS = {".obsidian", ".git", ".codex", ".agents", "90 Templates"}


@dataclass
class SearchResult:
    path: Path
    score: int
    title: str
    snippets: list[str]


def normalized_path_key(raw_path: str | Path) -> str:
    return str(Path(raw_path).expanduser().resolve(strict=False)).rstrip("\\/").casefold()


def is_under(path: Path, root: Path) -> bool:
    path_key = normalized_path_key(path)
    root_key = normalized_path_key(root)
    return path_key == root_key or path_key.startswith(root_key + "\\") or path_key.startswith(root_key + "/")


def load_registry(vault: Path) -> list[dict]:
    path = vault / REGISTRY_PATH
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as handle:
        registry = json.load(handle)
    if not isinstance(registry, list):
        raise ValueError(f"{path} must contain a JSON array.")
    return registry


def find_project_by_cwd(registry: list[dict], cwd: Path) -> dict | None:
    cwd_key = normalized_path_key(cwd)
    matches: list[tuple[int, dict]] = []
    for entry in registry:
        repo_path = entry.get("repoPath")
        if not repo_path:
            continue
        repo_key = normalized_path_key(repo_path)
        if cwd_key == repo_key or cwd_key.startswith(repo_key + "\\") or cwd_key.startswith(repo_key + "/"):
            matches.append((len(repo_key), entry))
    if not matches:
        return None
    return sorted(matches, key=lambda item: item[0], reverse=True)[0][1]


def find_project_by_name(registry: list[dict], client: str | None, project: str | None) -> dict | None:
    if not client and not project:
        return None
    client_key = client.casefold() if client else None
    project_key = project.casefold() if project else None
    for entry in registry:
        if client_key and entry.get("client", "").casefold() != client_key:
            continue
        if project_key and entry.get("project", "").casefold() != project_key:
            continue
        return entry
    return None


def client_folder(vault: Path, client: str) -> Path:
    return vault / "10 Clients" / client


def home_folder(vault: Path) -> Path:
    return vault / HOME_ROOT


def project_folder(vault: Path, entry: dict) -> Path:
    return Path(vault, *entry["projectFolder"].replace("\\", "/").split("/"))


def existing_scope_roots(vault: Path, registry: list[dict], args: argparse.Namespace) -> tuple[str, list[Path], dict | None]:
    entry = find_project_by_name(registry, args.client, args.project) if args.project else None
    if entry is None and args.cwd and not args.client:
        entry = find_project_by_cwd(registry, Path(args.cwd))

    scope = args.scope
    client_is_home = bool(args.client and args.client.casefold() == "home")
    cwd_is_home = bool(args.cwd and is_under(Path(args.cwd), home_folder(vault)))

    if scope == "auto":
        if client_is_home or cwd_is_home:
            scope = "home"
        elif entry:
            scope = "project"
        elif args.client:
            scope = "client"
        else:
            scope = "all"

    if scope == "home":
        roots = [home_folder(vault)]
        entry = None
    elif scope == "project":
        if entry is None:
            raise LookupError("Project scope requested, but no registry project matched --cwd/--client/--project.")
        roots = [project_folder(vault, entry)]
    elif scope == "client":
        if client_is_home:
            roots = [home_folder(vault)]
            scope = "home"
            entry = None
        else:
            client = args.client or (entry.get("client") if entry else None)
            if not client:
                raise LookupError("Client scope requested, but no client matched --cwd/--client.")
            roots = [client_folder(vault, client)]
    else:
        roots = [vault]

    return scope, [root for root in roots if root.exists()], entry


def tokenize(query: str) -> list[str]:
    return [term.casefold() for term in re.findall(r"[A-Za-z0-9_./:-]{2,}", query)]


def term_pattern(term: str) -> re.Pattern[str]:
    if re.fullmatch(r"[A-Za-z0-9_]+", term):
        return re.compile(rf"(?<![A-Za-z0-9_]){re.escape(term)}(?![A-Za-z0-9_])", re.IGNORECASE)
    return re.compile(re.escape(term), re.IGNORECASE)


def count_term(text: str, term: str) -> int:
    return len(term_pattern(term).findall(text))


def iter_markdown_files(roots: list[Path]) -> list[Path]:
    files: list[Path] = []
    for root in roots:
        if root.is_file() and root.suffix.casefold() == ".md":
            files.append(root)
            continue
        for path in root.rglob("*.md"):
            if any(part in SKIP_DIRS for part in path.parts):
                continue
            files.append(path)
    return sorted(set(files), key=lambda item: str(item).casefold())


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def title_from_text(path: Path, text: str) -> str:
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return path.stem


def line_snippets(lines: list[str], terms: list[str], max_snippets: int) -> list[str]:
    snippets: list[str] = []
    for index, line in enumerate(lines):
        if not any(count_term(line, term) for term in terms):
            continue
        start = max(index - 1, 0)
        end = min(index + 2, len(lines))
        snippet_lines = []
        for line_no in range(start, end):
            snippet_lines.append(f"{line_no + 1}: {lines[line_no].rstrip()}")
        snippets.append("\n".join(snippet_lines))
        if len(snippets) >= max_snippets:
            break
    return snippets


def score_note(path: Path, text: str, query: str, terms: list[str]) -> int:
    haystack = text.casefold()
    path_text = str(path)
    score = 0
    exact_phrase = False
    if query and query.casefold() in haystack:
        exact_phrase = True
        score += haystack.count(query.casefold()) * 20
    matched_terms = 0
    for term in terms:
        text_count = count_term(text, term)
        path_count = count_term(path_text, term)
        if text_count or path_count:
            matched_terms += 1
        score += text_count * 5
        score += path_count * 8
    if any(count_term(path.stem, term) for term in terms):
        score += 20
    if len(terms) > 1 and matched_terms < 2 and not exact_phrase:
        return 0
    return score


def search_files(files: list[Path], query: str, limit: int, max_snippets: int) -> list[SearchResult]:
    terms = tokenize(query)
    results: list[SearchResult] = []
    for path in files:
        text = read_text(path)
        if query:
            score = score_note(path, text, query, terms)
            if score <= 0:
                continue
            snippets = line_snippets(text.splitlines(), terms or [query], max_snippets)
        else:
            score = 0
            snippets = []
        results.append(SearchResult(path=path, score=score, title=title_from_text(path, text), snippets=snippets))
    results.sort(key=lambda item: (item.score, item.path.stat().st_mtime), reverse=True)
    return results[:limit]


def print_text(results: list[SearchResult], vault: Path, scope: str, entry: dict | None, query: str) -> None:
    if entry:
        print(f"Scope: {scope} ({entry.get('client')} / {entry.get('project')})")
    else:
        print(f"Scope: {scope}")
    if query:
        print(f"Query: {query}")
    if not results:
        print("No matching Brainium notes found.")
        return
    print()
    for index, result in enumerate(results, start=1):
        rel = result.path.relative_to(vault)
        print(f"{index}. {result.title}")
        print(f"   Path: {rel}")
        print(f"   Score: {result.score}")
        for snippet in result.snippets:
            indented = "\n".join(f"   {line}" for line in snippet.splitlines())
            print(indented)
        print()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Search The Brainium Obsidian vault.")
    parser.add_argument("--vault", default=str(DEFAULT_VAULT), help="Path to The Brainium vault.")
    parser.add_argument("--cwd", default=str(Path.cwd()), help="Current repo/project/vault path for routing.")
    parser.add_argument("--client", help="Restrict or resolve by client name. Use Home for the Home area.")
    parser.add_argument("--project", help="Restrict or resolve by project name.")
    parser.add_argument("--query", default="", help="Search query. If omitted, returns recent notes in scope.")
    parser.add_argument("--scope", choices=["auto", "project", "client", "home", "all"], default="auto")
    parser.add_argument("--limit", type=int, default=8)
    parser.add_argument("--snippets", type=int, default=2)
    parser.add_argument("--json", action="store_true", help="Emit JSON results.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    vault = Path(args.vault).expanduser().resolve(strict=False)
    registry = load_registry(vault)
    scope, roots, entry = existing_scope_roots(vault, registry, args)
    if not roots:
        raise FileNotFoundError("No existing Brainium search roots matched the requested scope.")
    files = iter_markdown_files(roots)
    results = search_files(files, args.query.strip(), args.limit, args.snippets)

    if args.json:
        payload = {
            "scope": scope,
            "entry": entry,
            "query": args.query,
            "results": [
                {
                    "path": str(result.path),
                    "relativePath": str(result.path.relative_to(vault)),
                    "title": result.title,
                    "score": result.score,
                    "snippets": result.snippets,
                }
                for result in results
            ],
        }
        print(json.dumps(payload, indent=2))
    else:
        print_text(results, vault, scope, entry, args.query.strip())
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"search_branium.py: {exc}", file=sys.stderr)
        raise SystemExit(1)
