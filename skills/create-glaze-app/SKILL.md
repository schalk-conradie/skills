---
name: create-glaze-app
description: Create custom Glaze desktop apps from Glaze's installed official template, including source trees, Glaze app-folder installs, local macOS .app bundles, and importable .glaze project packages. Use when the user asks to build, scaffold, generate, export, import, package, prototype, or custom-code a Glaze app, Raycast Glaze app, Glaze source tree, Glaze desktop utility, or app backed by local commands such as brew/git/gh.
---

# Create Glaze App

## Overview

Use this skill to create or modify Glaze app source code, install the app into Glaze's local apps folder, package it as a local macOS `.app`, and export it as an importable `.glaze` project package.

Use Glaze's installed assets as the source of truth:

- template source: `/Applications/Glaze.app/Contents/Resources/template-app`
- launcher shell: `/Applications/Glaze.app/Contents/Resources/template-app-shell.app`
- SDK docs: `/Users/schalk/Library/Application Support/app.glaze.macos.main/sdk/current/@glaze/core`
- local app install folder: `/Users/schalk/Library/Application Support/app.glaze.macos.main/apps`

Do not treat the skill's old copied templates as authoritative. Read the installed SDK docs before using unfamiliar APIs or components.

## Quick Start

Prefer the generator script for new apps. By default it creates the source tree, runs install/check/build, and installs the generated app into Glaze's local apps folder so it appears in Glaze:

```bash
python3 /Users/schalk/.agents/skills/create-glaze-app/scripts/create_glaze_app.py \
  --output /path/to/new-app \
  --name brew-packages \
  --product-name "Brew Packages" \
  --description "Inspect installed Homebrew packages"
```

The script copies Glaze's installed official template, rewrites package metadata, runs `npm ci --ignore-scripts`, runs `npm run type-check`, `npm run lint`, runs `npm run build`, then installs this shape:

```text
/Users/schalk/Library/Application Support/app.glaze.macos.main/apps/<name>-local-<id>/
├── .glaze/
├── .glaze-sources/
└── <Product Name>.app/
```

Use `--app-output "/path/to/Product.app"` when the user also wants a standalone app bundle outside Glaze's app folder. Use `--project-output "/path/to/Product.glaze"` when the user wants an importable/exportable Glaze project package.

Use `--no-install-to-glaze` only when the user explicitly wants files but does not want the app added to Glaze. Use `--skip-install` when dependencies are already installed or the user only wants files. Use `--skip-checks` only when the environment cannot run type-check/lint. Use `--skip-build` only when build output already exists and no installed app, `.app`, or `.glaze` package is requested.

## App Anatomy

The official template has the same shape as a Glaze-created app:

- `glaze.ts`: wrapper that finds the installed Glaze SDK CLI.
- `package.json`: app metadata, scripts, dependencies, and Glaze manifest fields.
- `main/index.ts`: backend entry point; creates the main `BrowserWindow`.
- `main/handlers/`: IPC handler registration.
- `main/windows/`: window URL and settings window helpers.
- `renderer/preload.ts`: secure bridge exposed as `window.glazeAPI`.
- `renderer/main/`: React main window.
- `renderer/settings/`: settings window.
- `main-window.html` and `settings-window.html`: renderer entrypoints and CSP.

## App Bundle Packaging

When the user wants a runnable `.app`, pass `--app-output`.

The script:

- copies `/Applications/Glaze.app/Contents/Resources/template-app-shell.app`
- embeds `build/`, a minimized runtime `package.json`, and `app-icon.icns` under `Contents/Resources/glaze-runtime`
- rewrites `CFBundleDisplayName`, `CFBundleExecutable`, `CFBundleIdentifier`, `CFBundleName`, and URL schemes in `Contents/Info.plist`
- renames the launcher executable to the product name
- signs locally with `codesign --sign - --options runtime`
- verifies with `codesign --verify --deep --strict`

Use `--icon /path/to/icon.icns` for a custom icon. Use `--skip-sign` only for debugging, because unsigned modified app bundles usually fail local launch or trigger macOS trust issues.

## Glaze App Folder Install

The default install target is:

```text
/Users/schalk/Library/Application Support/app.glaze.macos.main/apps
```

Install output uses this directory name:

```text
<package-name>-local-<glaze-id>
```

Inside that directory:

- `.glaze/` contains the built runtime payload Glaze launches.
- `.glaze-sources/` contains editable source, local project memory, and a Git repository.
- `<Product Name>.app/` is the signed shell app using the same runtime.

Do not write directly to Glaze's SQLite database. Current local app discovery is represented by the app directories under the apps folder.

## Importable `.glaze` Project Packages

When the user wants an importable project, pass `--project-output`.

The script creates a macOS package directory with this structure:

```text
Example.glaze/
├── manifest.json
├── chat/sessions.json
├── data/logs/
└── project/
    ├── .glaze/
    │   ├── package.json
    │   ├── app-icon.icns
    │   └── build/
    └── .glaze-sources/
        ├── package.json
        ├── .git/
        ├── .glaze_memory/
        ├── main/
        └── renderer/
```

`manifest.json` uses `format: "app.glaze.project-package"` and points to the source, runtime, chat, and logs paths. `project/.glaze` is the built runtime payload. `project/.glaze-sources` is the editable source tree without `node_modules`, `build`, or `.build`; the generator initializes a Git repository in that copied source tree if one does not already exist.

The root `.glaze` extension is what gives the package its Glaze project UTI when Glaze is installed. The root `Icon\r` resource from Glaze exports is Finder decoration, not required for the project structure.

## Implementation Workflow

1. Generate or locate the app source tree.
2. Read the relevant existing files before editing: `package.json`, `main/handlers/index.ts`, `renderer/preload.ts`, `renderer/main/router.tsx`, and the target view files.
3. Keep backend work in `main/`, renderer work in `renderer/`, and shared frontend API types next to the renderer client that calls IPC.
4. Add backend services for local command work. Use `execFile` or `spawn` with explicit argv; do not use shell interpolation for user-controlled paths or package names.
5. Expose narrow IPC handlers through `ipcMain.handle("domain:method", ...)`. Validate only trust-boundary inputs that the backend uses for filesystem or command execution.
6. From the renderer, call custom handlers through `window.glazeAPI.glaze.ipc.invoke`. Avoid exposing new preload APIs unless the renderer needs a native capability that is not already exposed.
7. Render with `@glaze/core/components` and existing template patterns. Read the exact component docs under the installed SDK before using an unfamiliar Glaze component.
8. Run the smallest relevant checks, normally:

```bash
npm run type-check
npm run lint
npm run build
```

## Local Command Apps

For app ideas like Homebrew, Git, GitHub CLI, or system inventory:

- Query read-only data first and cache it in React Query if multiple views share it.
- Prefer machine-readable command output, especially JSON flags such as `brew info --json=v2 --installed`.
- Keep modifying actions explicit, named, and button-driven. Examples: `brew upgrade <name>`, `git push`, `gh issue close`.
- Re-read state after a modifying action instead of guessing local state changes.
- Return typed result objects from IPC, for example `{ success: boolean; output: string }` for actions and concrete arrays for scans.
- Do not hide command failures. Surface stderr/stdout in a toast or detail panel.

## UI Guidelines

Use the installed component docs as the detailed source of truth. Common rules from the Glaze SDK:

- Prefer Glaze native components over custom UI.
- Use tables for structured multi-column data and lists for simple rows.
- Use toolbars, icon buttons, and tooltips for command-heavy utility apps.
- Use empty states that are text-first, specific, and limited to one or two actions.
- Use switches for immediate binary settings; do not require a Save button for switch-only settings.
- Use alert dialogs only for blocking or destructive confirmations.
- Use custom menus only when the native menu cannot express the needed interaction.
- Avoid adding renderer access to sensitive native APIs unless the current app needs it.

## Glaze SDK Reference

Before using unfamiliar Glaze APIs or components, inspect the installed SDK reference:

- `/Users/schalk/Library/Application Support/app.glaze.macos.main/sdk/current/@glaze/core/GLAZE-SDK-API-REFERENCE/INDEX.md`
- Component docs live under `/Users/schalk/Library/Application Support/app.glaze.macos.main/sdk/current/@glaze/core/src/components/`

The reference is generated from the installed SDK's Node/TypeScript declaration sources. Use it before guessing API shape:

- exact symbol lookup: `GLAZE-SDK-API-REFERENCE/symbols.json` or `symbols.ndjson`
- package imports: `GLAZE-SDK-API-REFERENCE/entrypoints/*.md`
- `window.glazeAPI.*`: `GLAZE-SDK-API-REFERENCE/window-glaze-api/*.md`
- full declaration context: `GLAZE-SDK-API-REFERENCE/declarations/**/*.md`
- component usage examples: `src/components/<component>.md`

Do not crawl the whole SDK. Read only the exact entrypoint, symbol, or component doc needed for the current app. Remember that `@glaze/core` is not installed into the app's `node_modules`; the template resolves it through TypeScript paths to `/Users/schalk/Library/Application Support/app.glaze.macos.main/sdk/current/@glaze/core`.
