---
name: generate-visual
description: Create self-contained single-file HTML visual artifacts instead of markdown. Use when the user invokes /generate-visual or asks for a polished HTML slide deck, visual document, explainer, report, diagram, code review artifact, design system sheet, prototype, implementation plan, or custom mini-editor based on bundled HTML examples.
---

# Generate Visual

## Core Rule

Produce exactly one final `.html` file unless the user explicitly asks for something else. The file must be self-contained: no Tailwind, no CDN scripts, no external stylesheets, no remote images, and no required companion assets. Inline all CSS, JavaScript, SVG, and data needed to render the artifact.

## Workflow

1. Classify the requested artifact type.
2. Read `references/templates.md` and choose the closest bundled example from `assets/examples/`.
3. Read only the selected example plus `assets/base-site.css`.
4. Create a new HTML file in the user's requested location, or in the current workspace when no location is given.
5. Inline `assets/base-site.css` into the output before any page-specific CSS. Remove `<link rel="stylesheet" href="assets/site.css">` or any other external dependency.
6. Replace the template content with the user's subject matter. Keep the visual structure and interaction pattern, but rewrite titles, labels, data, diagrams, and narrative for the actual request.
7. Verify the result by opening it in a browser or local HTTP server when available. Also grep the output for external dependency markers before delivering.

## Template Starter

Use the helper script when it saves time:

```bash
python <skill-dir>/scripts/prepare_template.py 09-slide-deck.html output.html
```

The script copies a bundled example and embeds the shared CSS. It is only a starting point; still edit the generated file so the final artifact directly answers the user's prompt.

## Design Standards

- Keep the restrained editorial style from the examples: light neutral background, dark text, teal accent, muted brass secondary accent.
- Prefer spatial layouts over linear prose: side-by-side panels, timelines, callout rows, cards, diagrams, charts, tabs, accordions, or slide sections.
- Use inline SVG for diagrams and icons when possible.
- For slide decks, make arrow-key navigation work and keep each slide readable at common laptop viewport sizes.
- For custom editors, include useful state, controls, and an export/copy path when relevant.
- Avoid explanatory meta-text about the page's features. The artifact itself should be the deliverable.

## Verification

Before final response:

```bash
rg -n "<link|cdn\\.tailwindcss|tailwind|https?://|src=|url\\(" output.html
```

Investigate any hit. Links in visible content can be acceptable, but rendering must not depend on external files. If browser verification is unavailable, state that and report the static checks performed.
