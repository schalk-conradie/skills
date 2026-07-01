# Template Selection

All examples live in `assets/examples/`. The shared visual tokens live in `assets/base-site.css`.

Choose the closest starting point:

| Request type | Start from |
|---|---|
| Gallery, index, catalog, grouped examples | `index.html` |
| Compare technical approaches | `01-exploration-code-approaches.html` |
| Explore visual directions or layout options | `02-exploration-visual-designs.html` |
| Annotated code review or PR risk view | `03-code-review-pr.html` |
| Module map, architecture orientation, code understanding | `04-code-understanding.html` |
| Design tokens or design system reference | `05-design-system.html` |
| Component states, variants, contact sheets | `06-component-variants.html` |
| Motion, timing, animation sandbox | `07-prototype-animation.html` |
| Click-through prototype or interaction flow | `08-prototype-interaction.html` |
| Slide deck or presentation | `09-slide-deck.html` |
| SVG illustration sheet or article figures | `10-svg-illustrations.html` |
| Weekly status, project update, progress report | `11-status-report.html` |
| Incident review, postmortem, timeline | `12-incident-report.html` |
| Flowchart, pipeline, decision tree | `13-flowchart-diagram.html` |
| Feature explainer for a repo or system | `14-research-feature-explainer.html` |
| Concept explainer with an interactive model | `15-research-concept-explainer.html` |
| Implementation plan, rollout plan, architecture plan | `16-implementation-plan.html` |
| PR writeup for reviewers | `17-pr-writeup.html` |
| Triage board or prioritization editor | `18-editor-triage-board.html` |
| Feature flag or configuration editor | `19-editor-feature-flags.html` |
| Prompt tuner or templated text editor | `20-editor-prompt-tuner.html` |

For mixed requests, choose the dominant user workflow. For example, a presentation about agent harnesses should start from `09-slide-deck.html`; an architecture briefing with a sequence diagram should usually start from `16-implementation-plan.html` or `13-flowchart-diagram.html`.

Final HTML requirements:

- Inline `assets/base-site.css`.
- Keep or adapt the template's page-specific CSS inline.
- Keep any JavaScript inline.
- Convert external visual assets to inline SVG, CSS, or data URIs.
- Remove Tailwind, CDN, and external stylesheet references.
