# Static shadcn Registry Workflow

Use this reference when building a static registry for create-ec-app.

## URL Model

Publish static JSON files under `/r`:

- Catalog URL for discovery and create-ec-app: `https://<owner>.github.io/<repo>/r/registry.json`
- Item URL template for namespaces: `https://<owner>.github.io/<repo>/r/{name}.json`
- Concrete item URL: `https://<owner>.github.io/<repo>/r/button.json`

The `{name}` placeholder is correct for `shadcn registry add`; it is not the URL to pass to create-ec-app.

## Source Layout

Use nested manifests for anything larger than a tiny registry:

```txt
registry.json
src/
  components/ui/
    registry.json
    button.tsx
  hooks/
    registry.json
    use-mobile.ts
  lib/
    registry.json
    utils.ts
  theme/
    registry.json
    <slug>-theme.css
public/r/
  registry.json
  button.json
  <slug>-theme.json
```

The shadcn build command resolves includes and writes static output:

```bash
npx shadcn@latest build registry.json --output public/r
```

## Root Manifest

```json
{
  "$schema": "https://ui.shadcn.com/schema/registry.json",
  "name": "<slug>",
  "homepage": "https://<owner>.github.io/<repo>",
  "include": [
    "src/lib/registry.json",
    "src/hooks/registry.json",
    "src/theme/registry.json",
    "src/components/ui/registry.json"
  ]
}
```

## Component Import Rule

For a new registry, always pull in every shadcn component from a temporary shadcn app:

```bash
npx shadcn@latest add --all
```

Copy the resulting `components/ui`, `lib/utils.ts`, and any generated hooks into the registry source tree. Do not create a new registry from a manually selected subset of components.

## Theme Item

Use a separate CSS file so installing a registry component adds the registry theme without overwriting the consumer app's base shadcn CSS.

```json
{
  "$schema": "https://ui.shadcn.com/schema/registry.json",
  "items": [
    {
      "name": "<slug>-theme",
      "type": "registry:theme",
      "title": "<Title> Theme",
      "description": "<Title> theme tokens and base Tailwind CSS for registry components.",
      "dependencies": [
        "tw-animate-css@^1.4.0"
      ],
      "css": {
        "@import \"tw-animate-css\"": {},
        "@import \"./<slug>-theme.css\"": {}
      },
      "files": [
        {
          "path": "<slug>-theme.css",
          "type": "registry:file",
          "target": "src/<slug>-theme.css"
        }
      ]
    }
  ]
}
```

The CSS file should include the Tailwind v4 layer, not import itself:

```css
@custom-variant dark (&:is(.dark *));

@theme inline {
  --color-background: var(--background);
  --color-foreground: var(--foreground);
  --color-primary: var(--primary);
  --color-primary-foreground: var(--primary-foreground);
  --color-border: var(--border);
  --color-ring: var(--ring);
  --radius-lg: var(--radius);
}

:root:root {
  --background: #ffffff;
  --foreground: #111827;
  --primary: #2563eb;
  --primary-foreground: #ffffff;
  --border: #e5e7eb;
  --ring: #2563eb;
  --radius: 0.5rem;
}

.dark.dark {
  --background: #111827;
  --foreground: #f9fafb;
  --primary: #60a5fa;
  --primary-foreground: #0f172a;
  --border: rgb(255 255 255 / 14%);
  --ring: #60a5fa;
}

@layer base {
  * {
    @apply border-border outline-ring/50;
  }

  body {
    @apply bg-background text-foreground;
  }
}
```

## Utility Item

```json
{
  "$schema": "https://ui.shadcn.com/schema/registry.json",
  "items": [
    {
      "name": "utils",
      "type": "registry:lib",
      "title": "Utils",
      "description": "Class name merge utility used by registry components.",
      "files": [
        {
          "path": "utils.ts",
          "type": "registry:lib",
          "target": "@lib/utils.ts"
        }
      ],
      "dependencies": [
        "clsx@^2.1.1",
        "tailwind-merge@^3.6.0"
      ]
    }
  ]
}
```

## UI Item Pattern

Use full public URLs for same-registry dependencies:

```json
{
  "name": "button",
  "type": "registry:ui",
  "title": "Button",
  "description": "<Title> Button component.",
  "files": [
    {
      "path": "button.tsx",
      "type": "registry:ui",
      "target": "@ui/button.tsx"
    }
  ],
  "dependencies": [
    "class-variance-authority@^0.7.1",
    "radix-ui@^1.6.0"
  ],
  "registryDependencies": [
    "https://<owner>.github.io/<repo>/r/<slug>-theme.json",
    "https://<owner>.github.io/<repo>/r/utils.json"
  ]
}
```

Bare names such as `"button"` or `"utils"` resolve against the built-in shadcn registry unless they are full namespace/GitHub/URL addresses.

## GitHub Pages Workflow

Use this only when the project does not already have a Pages workflow:

```yaml
name: Pages

on:
  push:
    branches: ["main"]
  workflow_dispatch:

permissions:
  contents: read
  pages: write
  id-token: write

concurrency:
  group: "pages"
  cancel-in-progress: false

jobs:
  deploy:
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: 22
          cache: npm
      - run: npm ci
      - run: npm run build:registry
      - run: npm run build
        if: ${{ hashFiles('src/main.tsx', 'app/**') != '' }}
      - uses: actions/configure-pages@v5
      - uses: actions/upload-pages-artifact@v3
        with:
          path: ./dist
      - id: deployment
        uses: actions/deploy-pages@v4
```

If `public/r` is not copied into `dist` by the app build, either configure the build to include it or upload the directory that contains `/r/registry.json`.

## Verification

From outside the registry repo:

```bash
npx shadcn@latest list https://<owner>.github.io/<repo>/r/registry.json
npx shadcn@latest registry add @<namespace>=https://<owner>.github.io/<repo>/r/{name}.json
npx shadcn@latest list @<namespace>
npx shadcn@latest add @<namespace>/button
```

For create-ec-app, create a fresh project under `/tmp` and pass the catalog URL:

```bash
npx create-ec-app@latest /tmp/<slug>-consumer --shadcn-registry https://<owner>.github.io/<repo>/r/registry.json
```

Then verify:

- The installed component exists under the consumer's configured UI alias.
- `src/<slug>-theme.css` exists.
- The app CSS imports `./<slug>-theme.css`.
- `tw-animate-css` and component package dependencies are installed.
- The app builds and rendered components are styled.
