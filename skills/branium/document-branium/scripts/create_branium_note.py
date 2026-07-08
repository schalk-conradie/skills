#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path


DEFAULT_VAULT = Path(r"C:\Users\Schalk\Documents\The Brainium")
REGISTRY_PATH = Path("99 Meta") / "project-registry.json"
NOTE_FOLDERS = {
    "adr": "Decisions",
    "architecture": "Notes",
    "as-built": "Notes",
    "change": "Changes",
    "conversation": "Notes",
    "decision": "Decisions",
    "handoff": "Notes",
    "incident": "Notes",
    "investigation": "Notes",
    "meeting": "Notes",
    "note": "Notes",
    "plan": "Notes",
    "technical-design": "Notes",
}


def normalized_path_key(raw_path: str | Path) -> str:
    return str(Path(raw_path).expanduser().resolve(strict=False)).rstrip("\\/").casefold()


def slug(value: str) -> str:
    text = value.casefold()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-") or "unknown"


def safe_filename(value: str) -> str:
    text = re.sub(r'[<>:"/\\|?*]+', " ", value)
    text = re.sub(r"\s+", " ", text).strip().rstrip(".")
    if not text:
        raise ValueError("Title does not contain a usable filename.")
    return text[:100].rstrip()


def yaml_quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def load_registry(vault: Path) -> list[dict]:
    path = vault / REGISTRY_PATH
    with path.open("r", encoding="utf-8") as handle:
        registry = json.load(handle)
    if not isinstance(registry, list):
        raise ValueError(f"{path} must contain a JSON array.")
    return registry


def find_by_explicit(registry: list[dict], client: str, project: str) -> dict | None:
    client_key = client.casefold()
    project_key = project.casefold()
    for entry in registry:
        if entry.get("client", "").casefold() == client_key and entry.get("project", "").casefold() == project_key:
            return entry
    return None


def find_by_cwd(registry: list[dict], cwd: Path) -> dict | None:
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


def fallback_entry(client: str, project: str) -> dict:
    return {
        "client": client,
        "project": project,
        "projectFolder": f"10 Clients/{client}/Projects/{project}",
        "tags": [
            f"client/{slug(client)}",
            f"project/{slug(project)}",
        ],
    }


def unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    for index in range(2, 1000):
        candidate = path.with_name(f"{path.stem} {index}{path.suffix}")
        if not candidate.exists():
            return candidate
    raise FileExistsError(f"Could not find an available filename for {path}")


def build_content(args: argparse.Namespace, entry: dict, cwd: Path, note_date: str, body: str) -> str:
    client = entry["client"]
    project = entry["project"]
    project_folder = entry["projectFolder"].replace("\\", "/")
    tags = list(dict.fromkeys([f"type/{args.note_type}", *entry.get("tags", [])]))
    client_link = f"[[10 Clients/{client}/{client}|{client}]]"
    project_link = f"[[{project_folder}/{project}|{project}]]"

    frontmatter = [
        "---",
        f"type: {args.note_type}",
        f"client: {yaml_quote(client)}",
        f"project: {yaml_quote(project)}",
        f"status: {yaml_quote(args.status)}",
        f"created: {note_date}",
        f"source_path: {yaml_quote(str(cwd))}",
        "tags:",
    ]
    frontmatter.extend(f"  - {tag}" for tag in tags)
    frontmatter.append("---")

    header = [
        f"# {args.title}",
        "",
        f"Client: {client_link}",
        f"Project: {project_link}",
        f"Source: `{cwd}`",
        "",
    ]

    return "\n".join(frontmatter + [""] + header) + "\n" + body.rstrip() + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a project note in The Brainium vault.")
    parser.add_argument("--vault", default=str(DEFAULT_VAULT), help="Path to The Brainium vault.")
    parser.add_argument("--cwd", default=str(Path.cwd()), help="Current project or repo path.")
    parser.add_argument("--client", help="Client name. Optional when cwd matches the registry.")
    parser.add_argument("--project", help="Project name. Optional when cwd matches the registry.")
    parser.add_argument("--title", required=True, help="Note title.")
    parser.add_argument("--note-type", choices=sorted(NOTE_FOLDERS), default="change")
    parser.add_argument("--status", default="captured")
    parser.add_argument("--date", default=date.today().isoformat(), help="YYYY-MM-DD note date.")
    parser.add_argument("--body", default="", help="Markdown body to append after the generated header.")
    parser.add_argument("--body-file", help="Path to a UTF-8 markdown body file.")
    parser.add_argument("--dry-run", action="store_true", help="Print the destination and content without writing.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    vault = Path(args.vault).expanduser().resolve(strict=False)
    cwd = Path(args.cwd).expanduser().resolve(strict=False)

    if args.body and args.body_file:
        raise ValueError("Use either --body or --body-file, not both.")

    registry = load_registry(vault)
    entry = None
    if args.client and args.project:
        entry = find_by_explicit(registry, args.client, args.project) or fallback_entry(args.client, args.project)
    else:
        entry = find_by_cwd(registry, cwd)

    if entry is None:
        registry_file = vault / REGISTRY_PATH
        raise LookupError(
            f"No Brainium project mapping matched cwd '{cwd}'. "
            f"Add it to '{registry_file}' or pass --client and --project."
        )

    body = args.body
    if args.body_file:
        body = Path(args.body_file).read_text(encoding="utf-8")

    project_folder = Path(vault, *entry["projectFolder"].replace("\\", "/").split("/"))
    note_folder = project_folder / NOTE_FOLDERS[args.note_type]
    note_name = f"{args.date} {safe_filename(args.title)}.md"
    note_path = unique_path(note_folder / note_name)
    content = build_content(args, entry, cwd, args.date, body)

    if args.dry_run:
        print(f"Would write: {note_path}")
        print()
        print(content)
        return 0

    note_folder.mkdir(parents=True, exist_ok=True)
    note_path.write_text(content, encoding="utf-8", newline="\n")
    print(note_path)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"create_branium_note.py: {exc}", file=sys.stderr)
        raise SystemExit(1)
