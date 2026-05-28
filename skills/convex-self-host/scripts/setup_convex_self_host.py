#!/usr/bin/env python3
"""Set up Convex self-hosted Docker Compose files in a project."""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path


DEFAULTS = {
    "PORT": "3210",
    "SITE_PROXY_PORT": "3211",
    "DASHBOARD_PORT": "6791",
    "CONVEX_CLOUD_ORIGIN": "http://127.0.0.1:3210",
    "CONVEX_SITE_ORIGIN": "http://127.0.0.1:3211",
    "NEXT_PUBLIC_DEPLOYMENT_URL": "http://127.0.0.1:3210",
    "RUST_LOG": "info",
    "DISABLE_METRICS_ENDPOINT": "true",
}


COMPOSE_TEMPLATE = """services:
  backend:
    image: ghcr.io/get-convex/convex-backend:latest
    stop_grace_period: 10s
    stop_signal: SIGINT
    ports:
      - "${PORT:-3210}:3210"
      - "${SITE_PROXY_PORT:-3211}:3211"
    volumes:
      - data:/convex/data
    environment:
      - ACTIONS_USER_TIMEOUT_SECS
      - APPLICATION_MAX_CONCURRENT_MUTATIONS=${APPLICATION_MAX_CONCURRENT_MUTATIONS:-16}
      - APPLICATION_MAX_CONCURRENT_NODE_ACTIONS=${APPLICATION_MAX_CONCURRENT_NODE_ACTIONS:-16}
      - APPLICATION_MAX_CONCURRENT_QUERIES=${APPLICATION_MAX_CONCURRENT_QUERIES:-16}
      - APPLICATION_MAX_CONCURRENT_V8_ACTIONS=${APPLICATION_MAX_CONCURRENT_V8_ACTIONS:-16}
      - AWS_ACCESS_KEY_ID
      - AWS_REGION
      - AWS_S3_DISABLE_CHECKSUMS
      - AWS_S3_DISABLE_SSE
      - AWS_S3_FORCE_PATH_STYLE
      - AWS_SECRET_ACCESS_KEY
      - AWS_SESSION_TOKEN
      - CONVEX_CLOUD_ORIGIN=${CONVEX_CLOUD_ORIGIN:-http://127.0.0.1:${PORT:-3210}}
      - CONVEX_RELEASE_VERSION_DEV
      - CONVEX_SITE_ORIGIN=${CONVEX_SITE_ORIGIN:-http://127.0.0.1:${SITE_PROXY_PORT:-3211}}
      - DATABASE_URL
      - DISABLE_BEACON
      - DISABLE_METRICS_ENDPOINT=${DISABLE_METRICS_ENDPOINT:-true}
      - DOCUMENT_RETENTION_DELAY=${DOCUMENT_RETENTION_DELAY:-172800}
      - DO_NOT_REQUIRE_SSL
      - HTTP_SERVER_TIMEOUT_SECONDS
      - INSTANCE_NAME
      - INSTANCE_SECRET
      - MYSQL_URL
      - POSTGRES_URL
      - REDACT_LOGS_TO_CLIENT
      - RUST_BACKTRACE
      - RUST_LOG=${RUST_LOG:-info}
      - S3_ENDPOINT_URL
      - S3_STORAGE_EXPORTS_BUCKET
      - S3_STORAGE_FILES_BUCKET
      - S3_STORAGE_MODULES_BUCKET
      - S3_STORAGE_SEARCH_BUCKET
      - S3_STORAGE_SNAPSHOT_IMPORTS_BUCKET
    healthcheck:
      test: curl -f http://localhost:3210/version
      interval: 5s
      start_period: 10s

  dashboard:
    image: ghcr.io/get-convex/convex-dashboard:latest
    stop_grace_period: 10s
    stop_signal: SIGINT
    ports:
      - "${DASHBOARD_PORT:-6791}:6791"
    environment:
      - NEXT_PUBLIC_DEPLOYMENT_URL=${NEXT_PUBLIC_DEPLOYMENT_URL:-http://127.0.0.1:${PORT:-3210}}
      - NEXT_PUBLIC_LOAD_MONACO_INTERNALLY
    depends_on:
      backend:
        condition: service_healthy

volumes:
  data:
"""


README_SECTION = """## Convex Self-Host

This project includes a Docker Compose setup for the Convex backend and dashboard.

Start:

```sh
docker compose up -d
```

Dashboard: http://localhost:6791

Backend: http://127.0.0.1:3210

HTTP actions: http://127.0.0.1:3211

Generate an admin key:

```sh
docker compose exec backend ./generate_admin_key.sh
```

For Convex CLI commands, put these values in `.env.local`:

```sh
CONVEX_SELF_HOSTED_URL='http://127.0.0.1:3210'
CONVEX_SELF_HOSTED_ADMIN_KEY='<your admin key>'
```
"""


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", value.strip()).strip("-_").lower()
    return slug or "convex-self-host"


def run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, check=False)


def write_file(path: Path, content: str, force: bool) -> bool:
    if path.exists() and not force:
        return False
    path.write_text(content, encoding="utf-8")
    return True


def upsert_env(path: Path, values: dict[str, str]) -> None:
    existing: list[str] = []
    seen: set[str] = set()
    if path.exists():
        existing = path.read_text(encoding="utf-8").splitlines()

    next_lines: list[str] = []
    for line in existing:
        match = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)=", line)
        if match and match.group(1) in values:
            key = match.group(1)
            next_lines.append(f"{key}={values[key]}")
            seen.add(key)
        else:
            next_lines.append(line)

    if next_lines and next_lines[-1] != "":
        next_lines.append("")

    for key, value in values.items():
        if key not in seen:
            next_lines.append(f"{key}={value}")

    path.write_text("\n".join(next_lines).rstrip() + "\n", encoding="utf-8")


def append_missing_lines(path: Path, lines: list[str]) -> None:
    current = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    next_lines = list(current)
    for line in lines:
        if line not in current:
            next_lines.append(line)
    path.write_text("\n".join(next_lines).rstrip() + "\n", encoding="utf-8")


def update_readme(path: Path, project_name: str) -> None:
    if path.exists():
        content = path.read_text(encoding="utf-8")
        if "## Convex Self-Host" in content:
            return
        content = content.rstrip() + "\n\n" + README_SECTION
    else:
        title = project_name.replace("-", " ").replace("_", " ").title()
        content = f"# {title}\n\n{README_SECTION}"
    path.write_text(content.rstrip() + "\n", encoding="utf-8")


def generate_admin_key(target_dir: Path) -> str:
    result = run(["docker", "compose", "exec", "-T", "backend", "./generate_admin_key.sh"], target_dir)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())
    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    for line in reversed(lines):
        if line.startswith("convex-self-hosted|"):
            return line
    raise RuntimeError("Could not find generated Convex admin key in command output.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target-dir", default=".", help="Project directory to configure.")
    parser.add_argument("--project-name", help="Docker Compose project name. Defaults to target folder name.")
    parser.add_argument("--force", action="store_true", help="Overwrite docker-compose.yml if it exists.")
    parser.add_argument("--start", action="store_true", help="Run docker compose up -d after writing files.")
    parser.add_argument(
        "--generate-admin-key",
        action="store_true",
        help="Start services if needed, generate an admin key, and write .env.local.",
    )
    args = parser.parse_args()

    target_dir = Path(args.target_dir).expanduser().resolve()
    target_dir.mkdir(parents=True, exist_ok=True)
    project_name = slugify(args.project_name or target_dir.name)

    env_values = {"COMPOSE_PROJECT_NAME": project_name, **DEFAULTS}
    compose_written = write_file(target_dir / "docker-compose.yml", COMPOSE_TEMPLATE, args.force)
    upsert_env(target_dir / ".env", env_values)
    upsert_env(target_dir / ".env.example", env_values)
    append_missing_lines(target_dir / ".gitignore", [".env.local", ".DS_Store", "node_modules/"])
    update_readme(target_dir / "README.md", project_name)

    print(f"Configured Convex self-hosting in {target_dir}")
    print(f"Project name: {project_name}")
    if not compose_written:
        print("Skipped existing docker-compose.yml. Re-run with --force to overwrite it.")

    if args.start or args.generate_admin_key:
        result = run(["docker", "compose", "up", "-d"], target_dir)
        if result.returncode != 0:
            sys.stderr.write(result.stderr or result.stdout)
            return result.returncode
        print("Docker services started.")

    if args.generate_admin_key:
        key = generate_admin_key(target_dir)
        local_env = (
            "CONVEX_SELF_HOSTED_URL='http://127.0.0.1:3210'\n"
            f"CONVEX_SELF_HOSTED_ADMIN_KEY='{key}'\n"
        )
        (target_dir / ".env.local").write_text(local_env, encoding="utf-8")
        print("Generated admin key and wrote .env.local.")

    print("Dashboard: http://localhost:6791")
    print("Backend: http://127.0.0.1:3210")
    print("HTTP actions: http://127.0.0.1:3211")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
