---
name: convex-self-host
description: Set up self-hosted Convex in a project with Docker Compose. Use when a user asks to add, install, configure, or bootstrap Convex self-hosting, Convex backend/dashboard containers, Convex Docker setup, or reusable local Convex development infrastructure. Supports defaulting the Docker Compose project name from the current directory when no project name is specified.
---

# Convex Self-Host

Use this skill to add Convex self-hosted backend and dashboard Docker Compose files to a project. Prefer the bundled script for repeatable setup.

## Workflow

1. If the user names a project, pass it with `--project-name`.
2. If the user does not name a project, let the script derive it from the target directory basename.
3. Run the script from the target project directory, or pass `--target-dir`.
4. Use `--start` when the user wants Docker containers started now.
5. Use `--generate-admin-key` when the user wants `.env.local` populated with `CONVEX_SELF_HOSTED_URL` and `CONVEX_SELF_HOSTED_ADMIN_KEY`. This starts the containers if needed.

## Script

Run:

```sh
python3 ~/.agents/skills/convex-self-host/scripts/setup_convex_self_host.py
```

Common options:

```sh
python3 ~/.agents/skills/convex-self-host/scripts/setup_convex_self_host.py --start --generate-admin-key
python3 ~/.agents/skills/convex-self-host/scripts/setup_convex_self_host.py --target-dir /path/to/project --project-name my-app
python3 ~/.agents/skills/convex-self-host/scripts/setup_convex_self_host.py --force
```

The script creates or updates:

- `docker-compose.yml`
- `.env`
- `.env.example`
- `.gitignore`
- `README.md`
- `.env.local` only when `--generate-admin-key` is used

## Defaults

The setup uses Convex's standard local ports:

- Backend: `http://127.0.0.1:3210`
- HTTP actions: `http://127.0.0.1:3211`
- Dashboard: `http://localhost:6791`

The Docker images are `ghcr.io/get-convex/convex-backend:latest` and `ghcr.io/get-convex/convex-dashboard:latest`.

If the user explicitly asks for the latest upstream instructions, check the official Convex self-hosted README before making changes:

`https://github.com/get-convex/convex-backend/blob/main/self-hosted/README.md`
