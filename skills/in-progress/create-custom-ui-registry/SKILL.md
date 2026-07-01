---
name: create-custom-ui-registry
description: Create and publish a custom shadcn/ui registry for create-ec-app. Use when Codex needs to scaffold a registry from a registry name, clone or copy every shadcn component with the --all flag, add a theme/global CSS registry item, publish static registry JSON publicly with GitHub Pages and gh, or verify consumption from create-ec-app.
---

# Create Custom UI Registry

## Overview

Create a static shadcn/ui registry that publishes a catalog at `https://<owner>.github.io/<repo>/r/registry.json` and item files at `https://<owner>.github.io/<repo>/r/{name}.json`.

The create-ec-app integration consumes the catalog URL. shadcn namespace setup consumes the `{name}` template URL.

## Required Inputs

Before mutating files or GitHub state, know:

- Registry name or slug.
- GitHub owner and repository name.
- Theme source: existing CSS, copied registry theme, or new token values.
- Component source: existing registry template, official shadcn registry template, or a fresh app where shadcn components are installed and copied.
- Component scope is fixed for new registries: install every shadcn component with `npx shadcn@latest add --all`.

If the registry name is present but owner/repo is missing, derive a proposal with `scripts/derive-registry-config.mjs` and confirm before publishing.

## Workflow

1. Derive names and URLs:

   ```bash
   node ~/.agents/skills/create-custom-ui-registry/scripts/derive-registry-config.mjs \
     --name "Acme UI" \
     --owner acme \
     --repo acme-ui-registry
   ```

2. Check current shadcn registry docs before relying on CLI or schema details. Prefer official docs and the local working registry pattern over memory.

3. Bootstrap the registry project:

   - Prefer the current proven registry template when the user asks for another registry like the existing EC registry.
   - Otherwise clone `https://github.com/shadcn-ui/registry-template` or create a small Vite/Storybook static site if that better matches the target repo.
   - Keep `shadcn` as a project dependency or dev dependency and add a `build:registry` script that runs `shadcn build registry.json --output public/r`.

4. Bring in components:

   - Use shadcn CLI in a temporary app and run `npx shadcn@latest add --all`, then copy `components/ui`, `lib/utils.ts`, and needed hooks into the registry source tree.
   - Do not hand-pick a smaller component set when creating a new registry. The registry should start with every shadcn component, even if the user only names one example component.
   - Keep component internals close to shadcn defaults unless the user requests branded behavior.
   - Preserve `@ui`, `@lib`, and `@hooks` target placeholders in registry manifests so installs follow the consumer project's `components.json`.

5. Define registry manifests:

   - Use a root `registry.json` with `name`, `homepage`, and `include`.
   - Put nested `registry.json` files beside the files they publish because paths are relative to the declaring manifest.
   - Build static output to `public/r`; do not hand-edit generated files except to inspect them.

6. Publish theme CSS as a registry item:

   - Add a `registry:theme` item such as `<slug>-theme`.
   - Include `tw-animate-css@^1.4.0` when the theme uses shadcn/Tailwind v4 animation styles.
   - In the item `css`, import `tw-animate-css` and `./<slug>-theme.css`.
   - In the item `files`, target the real CSS file to `src/<slug>-theme.css`.
   - Put the actual theme layer in that CSS file with `@custom-variant`, `@theme inline`, `:root:root`, `.dark.dark`, and `@layer base`.
   - Do not overwrite a consumer app's existing global CSS. The theme item should add imports and a separate CSS file.

7. Wire registry dependencies:

   - For items in the same public static registry, use full item URLs like `https://<owner>.github.io/<repo>/r/<item>.json`.
   - Do not use bare names for same-registry dependencies; bare names resolve to the built-in shadcn registry.
   - UI items should depend on the theme item and `utils` when they use theme tokens or `cn`.

8. Publish with gh:

   - Run the smallest local checks first: `npm run validate:registry`, `npm run build:registry`, then the repo's build/check script if present.
   - Create or connect the public GitHub repo with `gh repo create <owner>/<repo> --public --source . --remote origin --push` when publishing a new repo.
   - Use GitHub Pages from Actions or a static hosting target that serves `public/r/registry.json` and `public/r/*.json`.

9. Verify from a clean project:

   - Test the shadcn catalog URL with `npx shadcn@latest list https://<owner>.github.io/<repo>/r/registry.json`.
   - Test namespace installation with `npx shadcn@latest registry add @<namespace>=https://<owner>.github.io/<repo>/r/{name}.json`, then `npx shadcn@latest add @<namespace>/<component>`.
   - Test create-ec-app in `/tmp` with the public catalog URL, for example `--shadcn-registry https://<owner>.github.io/<repo>/r/registry.json`.
   - Confirm the generated app has the theme CSS file, imports it from app CSS, installs dependencies, and builds styled output.

## create-ec-app Contract

Use the catalog URL for create-ec-app:

```txt
https://<owner>.github.io/<repo>/r/registry.json
```

Use the template URL for a shadcn namespace:

```txt
https://<owner>.github.io/<repo>/r/{name}.json
```

The registry must publish both `registry.json` and individual item JSON files under the same `/r/` directory.

## References

Load `references/static-registry-workflow.md` when creating or reviewing manifests, theme items, GitHub Pages publishing, or clean-project verification.
