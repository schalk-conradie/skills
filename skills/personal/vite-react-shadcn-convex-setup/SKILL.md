---
name: vite-react-shadcn-convex-setup
description: Initialize the current folder as a Vite React TypeScript app with Tailwind CSS, shadcn/ui, Zod, Zustand, TanStack Query, Convex AI project files, and optional Convex self-hosting. Use when the user asks for this stack to be installed in-place, especially when the folder name should become the npm project name and existing Convex/self-hosting files must be preserved or created.
---

# Vite React Shadcn Convex Setup

Use this workflow to set up the same stack in an existing folder without creating
a nested project directory.

## Workflow

1. Inspect the directory first:
   - Run `pwd`, `rg --files -uu -g '!*node_modules*' -g '!*.git*'`, and `git status --short`.
   - Read existing `README.md`, `.env.example`, `docker-compose.yml`, and Convex files before scaffolding.
   - Preserve user files. If Vite overwrites `README.md`, restore the useful existing notes afterward.

2. Scaffold Vite React TypeScript in the current folder:
   - Run `npm create vite@latest . -- --template react-ts` from the target root.
   - If the directory is not empty, use a TTY and choose `Ignore files and continue`.
   - Do not choose the option that removes existing files.
   - Decline "install and start now"; run installs explicitly afterward.
   - The npm package name should default to `basename "$PWD"`. Verify it in `package.json`.

3. Install dependencies:

```sh
npm install
npm install tailwindcss @tailwindcss/vite zod zustand @tanstack/react-query convex
```

4. Configure Tailwind and imports before running shadcn:
   - In `vite.config.ts`, add `@tailwindcss/vite`, React, and the `@` alias.
   - In `tsconfig.json` and `tsconfig.app.json`, add:

```json
"paths": {
  "@/*": ["./src/*"]
}
```

   - With TypeScript 6+, avoid adding `baseUrl`; it is deprecated and can fail the build.
   - Replace `src/index.css` temporarily with `@import "tailwindcss";`.

5. Initialize shadcn/ui non-interactively:

```sh
npx shadcn@latest init --template vite --base radix --preset nova --no-monorepo --css-variables --no-rtl --pointer
```

   - This should create `components.json`, `src/lib/utils.ts`, shadcn theme CSS, and at least `src/components/ui/button.tsx`.
   - If ESLint flags the shadcn `buttonVariants` export, add this rule override:

```js
'react-refresh/only-export-components': [
  'error',
  { allowConstantExport: true, allowExportNames: ['buttonVariants'] },
]
```

6. Add starter integration files:
   - `src/components/providers.tsx` should create a `QueryClient` and wrap children with `QueryClientProvider`.
   - Add a Zod schema file under `src/lib/` and export inferred types.
   - Add a Zustand store under `src/store/`.
   - Update `src/main.tsx` to wrap `<App />` in `<Providers>`.
   - Replace the Vite starter `App.tsx` with a small screen that imports the shadcn `Button`, reads/writes the Zustand store, validates data with Zod, and uses `useQuery` from TanStack Query.
   - Remove unused starter CSS imports/files if the new app uses Tailwind only.

7. Handle Convex self-hosting only when requested:
   - If the user asks to add, bootstrap, initialize, start, or configure a self-hosted Convex backend, use the `convex-self-host` skill at `~/.agents/skills/convex-self-host/SKILL.md`.
   - Prefer that skill's bundled script instead of writing Docker Compose files by hand:

```sh
python3 ~/.agents/skills/convex-self-host/scripts/setup_convex_self_host.py
```

   - Run it from the project root, or pass `--target-dir`.
   - Add `--start` when the user wants containers started now.
   - Add `--generate-admin-key` when the user wants `.env.local` populated with `CONVEX_SELF_HOSTED_URL` and `CONVEX_SELF_HOSTED_ADMIN_KEY`.
   - If self-hosting files already exist, read them first and preserve local choices unless the user asks to replace them.

8. Install Convex AI files exactly from the project root:

```sh
npx convex ai-files install
```

   - Expect `AGENTS.md`, `CLAUDE.md`, `convex/_generated/ai/guidelines.md`, `skills-lock.json`, and local `.agents/skills/*` files.
   - Keep existing self-hosting environment files and Docker Compose config.

9. Audit and verify:

```sh
npm run lint
npm run build
npm audit --omit=dev
```

   - If `convex` pins a vulnerable `ws` version and no patched Convex release is available, add a top-level npm override such as:

```json
"overrides": {
  "ws": "8.21.0"
}
```

   - Run `npm install` again after adding an override.
   - Start `npm run dev` and verify the local app in the browser when doing frontend work.

## Notes

- Use current package manager behavior and CLI help if a prompt or flag changes.
- Prefer the latest official shadcn, Tailwind, Vite, and Convex commands, but keep this ordering: Vite scaffold, Tailwind/alias config, shadcn init, app wiring, optional Convex self-hosting, Convex AI files, verification.
- Do not leak `.env.local` secrets in the final response.
