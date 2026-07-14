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
HOME_ROOT = Path("100 Home")
NOTE_TYPES = {
    "adr": {"area": "project", "folder": "Decisions", "status": "proposed", "tags": ("type/adr",)},
    "architecture": {"area": "project", "folder": "Notes", "status": "current", "tags": ("type/architecture",)},
    "as-built": {"area": "project", "folder": "Notes", "status": "current", "tags": ("type/as-built",)},
    "change": {"area": "project", "folder": "Changes", "status": "captured", "tags": ("type/change",)},
    "conversation": {"area": "project", "folder": "Notes", "status": "captured", "tags": ("type/conversation",)},
    "decision": {"area": "project", "folder": "Decisions", "status": "proposed", "tags": ("type/decision",)},
    "handoff": {"area": "project", "folder": "Notes", "status": "ready", "tags": ("type/handoff",)},
    "incident": {"area": "project", "folder": "Notes", "status": "open", "tags": ("type/incident",)},
    "investigation": {"area": "project", "folder": "Notes", "status": "in-progress", "tags": ("type/investigation",)},
    "meeting": {"area": "project", "folder": "Notes", "status": "captured", "tags": ("type/meeting",)},
    "note": {"area": "project", "folder": "Notes", "status": "captured", "tags": ("type/note",)},
    "plan": {"area": "project", "folder": "Notes", "status": "draft", "tags": ("type/plan",)},
    "technical-design": {"area": "project", "folder": "Notes", "status": "draft", "tags": ("type/technical-design",)},
    "home-todo": {
        "area": "home",
        "folder": "Tasks",
        "status": "active",
        "tags": ("area/home", "type/home-todo"),
        "index_link": "[[100 Home/Tasks/Current Todo|Current Todo]]",
    },
    "home-document-register": {
        "area": "home",
        "folder": "Documents",
        "status": "active",
        "tags": ("area/home", "type/home-document-register"),
        "index_link": "[[100 Home/Documents/Document Register|Document Register]]",
    },
    "home-important-information": {
        "area": "home",
        "folder": "Important Information",
        "status": "active",
        "tags": ("area/home", "type/home-important-information"),
        "index_link": "[[100 Home/Important Information/Important Information|Important Information]]",
    },
    "home-inventory": {
        "area": "home",
        "folder": "Inventory",
        "status": "active",
        "tags": ("area/home", "type/home-inventory"),
        "index_link": "[[100 Home/Inventory/Home Inventory|Home Inventory]]",
    },
    "home-maintenance-log": {
        "area": "home",
        "folder": "Maintenance",
        "status": "active",
        "tags": ("area/home", "type/home-maintenance-log"),
        "index_link": "[[100 Home/Maintenance/Maintenance Log|Maintenance Log]]",
    },
    "home-note": {
        "area": "home",
        "folder": "Quick Notes",
        "status": "inbox",
        "tags": ("area/home", "type/home-note"),
        "index_link": "[[100 Home/Quick Notes/Home Quick Notes|Quick Notes]]",
    },
    "home-project": {
        "area": "home",
        "folder": "Projects",
        "status": "idea",
        "tags": ("area/home", "type/home-project"),
        "index_link": "[[100 Home/Projects/Home Projects|Home Projects]]",
    },
    "home-quick-note": {
        "area": "home",
        "folder": "Quick Notes",
        "status": "inbox",
        "tags": ("area/home", "type/home-quick-note"),
        "index_link": "[[100 Home/Quick Notes/Home Quick Notes|Quick Notes]]",
    },
    "home-routine": {
        "area": "home",
        "folder": "Maintenance",
        "status": "active",
        "tags": ("area/home", "type/home-routine"),
        "index_link": "[[100 Home/Maintenance/Maintenance Log|Maintenance Log]]",
    },
    "home-service-provider": {
        "area": "home",
        "folder": "Important Information",
        "status": "active",
        "tags": ("area/home", "type/home-service-provider"),
        "index_link": "[[100 Home/Important Information/Important Information|Important Information]]",
    },
    "home-shopping-list": {
        "area": "home",
        "folder": "Lists",
        "status": "active",
        "tags": ("area/home", "type/home-shopping-list"),
        "index_link": "[[100 Home/Lists/Shopping List|Shopping List]]",
    },
}
NOTE_TYPE_ALIASES = {"home-current-todo": "home-todo"}
CLIENT_ALIASES = {"stellenbosch business school": "sbs"}


def normalized_path_key(raw_path: str | Path) -> str:
    return str(Path(raw_path).expanduser().resolve(strict=False)).rstrip("\\/").casefold()


def is_under(path: Path, root: Path) -> bool:
    path_key = normalized_path_key(path)
    root_key = normalized_path_key(root)
    return path_key == root_key or path_key.startswith(root_key + "\\") or path_key.startswith(root_key + "/")


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
    if not path.exists():
        raise FileNotFoundError(f"Brainium project registry not found: {path}")
    with path.open("r", encoding="utf-8") as handle:
        registry = json.load(handle)
    if not isinstance(registry, list):
        raise ValueError(f"{path} must contain a JSON array.")
    return registry


def canonical_client_key(client: str) -> str:
    key = client.strip().casefold()
    return CLIENT_ALIASES.get(key, key)


def find_by_explicit(registry: list[dict], client: str, project: str) -> dict | None:
    client_key = canonical_client_key(client)
    project_key = project.casefold()
    for entry in registry:
        if canonical_client_key(entry.get("client", "")) == client_key and entry.get("project", "").casefold() == project_key:
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


def resolve_source_path(vault: Path, cwd: Path, entry: dict | None = None) -> Path | None:
    if not is_under(cwd, vault):
        return cwd
    repo_path = entry.get("repoPath") if entry else None
    return Path(repo_path).expanduser().resolve(strict=False) if repo_path else None


def unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    for index in range(2, 1000):
        candidate = path.with_name(f"{path.stem} {index}{path.suffix}")
        if not candidate.exists():
            return candidate
    raise FileExistsError(f"Could not find an available filename for {path}")


def frontmatter_status(status: str | None) -> list[str]:
    return [f"status: {yaml_quote(status)}"] if status is not None else []


def build_project_content(
    args: argparse.Namespace,
    entry: dict,
    config: dict,
    status: str | None,
    source_path: Path | None,
    note_date: str,
    body: str,
) -> str:
    client = entry["client"]
    project = entry["project"]
    project_folder = entry["projectFolder"].replace("\\", "/")
    tags = list(dict.fromkeys([*config["tags"], *entry.get("tags", [])]))
    client_link = f"[[10 Clients/{client}/{client}|{client}]]"
    project_link = f"[[{project_folder}/{project}|{project}]]"

    frontmatter = [
        "---",
        f"type: {args.note_type}",
        f"client: {yaml_quote(client)}",
        f"project: {yaml_quote(project)}",
        *frontmatter_status(status),
        f"created: {note_date}",
        *([f"source_path: {yaml_quote(str(source_path))}"] if source_path else []),
        "tags:",
    ]
    frontmatter.extend(f"  - {tag}" for tag in tags)
    frontmatter.append("---")

    header = [
        f"# {args.title}",
        "",
        f"Client: {client_link}",
        f"Project: {project_link}",
        *([f"Source: `{source_path}`"] if source_path else []),
        "",
    ]

    return "\n".join(frontmatter + [""] + header) + "\n" + body.rstrip() + "\n"


def build_home_content(
    args: argparse.Namespace,
    config: dict,
    status: str | None,
    source_path: Path | None,
    note_date: str,
    body: str,
) -> str:
    tags = list(config["tags"])
    filed_under = config["index_link"]

    frontmatter = [
        "---",
        f"type: {args.note_type}",
        "area: home",
        *frontmatter_status(status),
        f"created: {note_date}",
        *([f"source_path: {yaml_quote(str(source_path))}"] if source_path else []),
        "tags:",
    ]
    frontmatter.extend(f"  - {tag}" for tag in tags)
    frontmatter.append("---")

    header = [
        f"# {args.title}",
        "",
        "Home: [[100 Home/00 Home Dashboard|Home Dashboard]]",
        f"Filed under: {filed_under}",
        *([f"Source: `{source_path}`"] if source_path else []),
        "",
    ]

    return "\n".join(frontmatter + [""] + header) + "\n" + body.rstrip() + "\n"


def parse_args() -> argparse.Namespace:
    note_type_choices = sorted(set(NOTE_TYPES) | set(NOTE_TYPE_ALIASES))
    parser = argparse.ArgumentParser(description="Create a note in The Brainium vault.")
    parser.add_argument("--vault", default=str(DEFAULT_VAULT), help="Path to The Brainium vault.")
    parser.add_argument("--cwd", default=str(Path.cwd()), help="Current project, repo, or vault path.")
    parser.add_argument("--area", choices=["auto", "project", "home"], default="auto", help="Route as a project note or Home note.")
    parser.add_argument("--client", help="Client name. Optional when cwd matches the registry.")
    parser.add_argument("--project", help="Project name. Optional when cwd matches the registry.")
    parser.add_argument("--title", required=True, help="Note title.")
    parser.add_argument("--note-type", choices=note_type_choices, default="change")
    parser.add_argument("--status", help="Override the selected note type's template default status.")
    parser.add_argument("--date", default=date.today().isoformat(), help="YYYY-MM-DD note date.")
    parser.add_argument("--body", default="", help="Markdown body to append after the generated header.")
    parser.add_argument("--body-file", help="Path to a UTF-8 markdown body file.")
    parser.add_argument("--dry-run", action="store_true", help="Print the destination and content without writing.")
    return parser.parse_args()


def resolve_area(args: argparse.Namespace, vault: Path, cwd: Path) -> str:
    if args.area != "auto":
        return args.area
    if NOTE_TYPES[NOTE_TYPE_ALIASES.get(args.note_type, args.note_type)]["area"] == "home":
        return "home"
    if args.client and args.client.casefold() == "home":
        return "home"
    if is_under(cwd, vault / HOME_ROOT):
        return "home"
    return "project"


def main() -> int:
    args = parse_args()
    vault = Path(args.vault).expanduser().resolve(strict=False)
    cwd = Path(args.cwd).expanduser().resolve(strict=False)

    if args.body and args.body_file:
        raise ValueError("Use either --body or --body-file, not both.")

    body = args.body
    if args.body_file:
        body = Path(args.body_file).read_text(encoding="utf-8")

    area = resolve_area(args, vault, cwd)
    args.note_type = NOTE_TYPE_ALIASES.get(args.note_type, args.note_type)
    if area == "home":
        if args.note_type == "change":
            args.note_type = "home-note"
        config = NOTE_TYPES.get(args.note_type)
        if config is None or config["area"] != "home":
            raise ValueError(f"Note type '{args.note_type}' is not a Home note type.")
        status = args.status if args.status is not None else config["status"]
        note_folder = vault / HOME_ROOT / config["folder"]
        note_name = f"{args.date} {safe_filename(args.title)}.md"
        note_path = unique_path(note_folder / note_name)
        content = build_home_content(args, config, status, resolve_source_path(vault, cwd), args.date, body)
    else:
        config = NOTE_TYPES.get(args.note_type)
        if config is None or config["area"] != "project":
            raise ValueError(f"Note type '{args.note_type}' is not a project note type.")
        registry = load_registry(vault)
        if bool(args.client) != bool(args.project):
            raise ValueError("Project notes require both --client and --project when either is supplied.")
        if args.client:
            entry = find_by_explicit(registry, args.client, args.project)
            if entry is None:
                raise LookupError(
                    f"No Brainium project registry entry matched --client '{args.client}' "
                    f"and --project '{args.project}'."
                )
        else:
            entry = find_by_cwd(registry, cwd)

        if entry is None:
            registry_file = vault / REGISTRY_PATH
            raise LookupError(
                f"No Brainium project mapping matched cwd '{cwd}'. "
                f"Add it to '{registry_file}' or pass --client and --project for an existing registry entry. "
                "For Home notes, pass --area home."
            )

        project_folder = Path(vault, *entry["projectFolder"].replace("\\", "/").split("/"))
        status = args.status if args.status is not None else config["status"]
        note_folder = project_folder / config["folder"]
        note_name = f"{args.date} {safe_filename(args.title)}.md"
        note_path = unique_path(note_folder / note_name)
        content = build_project_content(
            args,
            entry,
            config,
            status,
            resolve_source_path(vault, cwd, entry),
            args.date,
            body,
        )

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
