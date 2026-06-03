# Skills

A collection of [Agent Skills](https://agentskills.io) for Cursor, Claude Code, Codex, and [other supported agents](https://github.com/vercel-labs/skills#supported-agents). Skills are grouped by domain under [`skills/`](skills/).

Browse and discover skills on [skills.sh](https://skills.sh). Install and manage them with the [`skills` CLI](https://github.com/vercel-labs/skills).

## Install

### Whole collection

```bash
# Interactive (choose agents and install method)
npx skills add schalk-conradie/skills

# List skill names in this repo without installing
npx skills add schalk-conradie/skills --list

# Install everything, globally, non-interactive
npx skills add schalk-conradie/skills --all -g -y
```

### Specific skills

Use the skill `name` from each skill’s `SKILL.md` frontmatter (see table below):

```bash
npx skills add schalk-conradie/skills --skill dynamics-webapi --skill generate-visual

# Shorthand: repo@skill
npx skills add schalk-conradie/skills@microsoft-exam-docs

# Target one agent (e.g. Cursor)
npx skills add schalk-conradie/skills --skill create-study-guide -a cursor -y
```

### Local clone

```bash
git clone https://github.com/schalk-conradie/skills.git
cd skills

npx skills add .
npx skills add ./skills/study/microsoft-exam-docs
```

### Install scope

| Scope | Flag | Location | Use case |
|-------|------|----------|----------|
| Project | (default) | `./.agents/skills/` (agent-specific; see [CLI docs](https://github.com/vercel-labs/skills#installation-scope)) | Shared with the repo / team |
| Global | `-g` | `~/.agents/skills/` (and agent-specific global paths) | Available across all projects |

Symlink installs are recommended when the CLI prompts you; they keep a single copy easy to update with `npx skills update`.

## Skills layout

```
skills/
├── documentation/   # D365 as-built, HTML visuals
├── dynamics/        # Dataverse / Dynamics 365 Web API
├── personal/        # Convex self-host, Vite + shadcn stack bootstrap
├── study/           # Microsoft Learn exam material and study tools
└── engineering/     # (reserved)
```

## Available skills

### Documentation

| Skill | Path | Description |
|-------|------|-------------|
| [d365-asbuilt](skills/documentation/d365-asbuilt/SKILL.md) | `documentation/d365-asbuilt` | Dynamics 365 as-built documentation from solution exports; chapter extraction, flow diagrams, Word cleanup |
| [generate-visual](skills/documentation/generate-visual/SKILL.md) | `documentation/generate-visual` | Self-contained single-file HTML artifacts (decks, reports, diagrams, prototypes) instead of markdown |

### Dynamics

| Skill | Path | Description |
|-------|------|-------------|
| [dynamics-webapi](skills/dynamics/dynamics-webapi/SKILL.md) | `dynamics/dynamics-webapi` | Read-only Dynamics 365 / Dataverse Web API queries (requires `token.json`) |

### Personal

| Skill | Path | Description |
|-------|------|-------------|
| [convex-self-host](skills/personal/convex-self-host/SKILL.md) | `personal/convex-self-host` | Bootstrap self-hosted Convex with Docker Compose |
| [vite-react-shadcn-convex-setup](skills/personal/vite-react-shadcn-convex-setup/SKILL.md) | `personal/vite-react-shadcn-convex-setup` | In-place Vite + React + TypeScript + Tailwind + shadcn/ui + Zod + Zustand + TanStack Query + Convex |

### Study

| Skill | Path | Description |
|-------|------|-------------|
| [microsoft-exam-docs](skills/study/microsoft-exam-docs/SKILL.md) | `study/microsoft-exam-docs` | Download Microsoft Learn training material for a certification exam code |
| [create-study-guide](skills/study/create-study-guide/SKILL.md) | `study/create-study-guide` | Turn downloaded `CONTENT.md` into a concise `STUDY_GUIDE.md` |
| [exam-qa-generator](skills/study/exam-qa-generator/SKILL.md) | `study/exam-qa-generator` | Generate multiple-choice / multiple-select practice Q&A JSON from Learn material |

Typical study workflow: `microsoft-exam-docs` → `create-study-guide` → `exam-qa-generator`.

## Managing installed skills

```bash
npx skills list
npx skills find microsoft
npx skills update
npx skills update dynamics-webapi
npx skills remove dynamics-webapi
```

## Publishing

There is no separate publish step for [skills.sh](https://skills.sh): host skills in this git repo and share the repo URL. Installs via `npx skills add schalk-conradie/skills` register usage on the skills directory over time.
