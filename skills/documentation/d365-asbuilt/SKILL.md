---
name: d365-asbuilt
description: Generate and refine Dynamics 365 as-built technical documentation from exported unmanaged solution metadata and existing DOCX deliverables. Use when extracting chapter-by-chapter architecture details (tables, flows, JavaScript resources, environment variables, security, plugins, custom APIs, integrations) and when cleaning Word output issues such as duplicated heading numbering, template theme reapplication, flow diagram standardization, and repeat table headers.
---

# D365 Asbuilt

Follow this skill when producing or polishing enterprise as-built documentation for Dynamics 365 / Power Platform solutions from unzipped solution metadata.

## Inputs

Require these inputs before writing content:
- Unmanaged solution exported and extracted to a folder.
- Existing as-built DOCX artifact when refinement is requested.
- Optional style template DOCX when theme/style alignment is requested.

If source metadata for a requested section is missing, write exactly:
`Information not available in provided solution metadata`

## Authoring Rules

- Preserve full display names exactly as provided.
- Avoid abbreviations in narrative and headings.
- Document custom components (`ec_`, `ecsm_`) and customized standard components only, unless user explicitly broadens scope.
- Produce only the chapter explicitly requested; do not auto-generate remaining chapters.
- Keep terminology and naming consistent across chapters.

## Delivery Workflow

1. Inspect extracted solution artifacts and identify available component inventories.
2. Draft requested chapter only, using strict chapter scope and required tables.
3. When flows are requested, analyze each flow independently before any grouping.
4. When flow diagrams are requested, render one diagram per flow using the annotation rules in `references/flow-diagram-spec.md`.
5. Apply DOCX cleanup passes in this order unless user specifies otherwise:
- Remove duplicated/manual heading numbering artifacts.
- Reapply template theme/styles from provided template DOCX.
- Enable repeating header rows on all multi-row tables.
6. Re-render and verify final DOCX structure after each cleanup pass.

## Chapter Scope Matrix

Use the detailed chapter prompts in `references/chapter-spec.md`.

Minimum expectations:
- Chapter 1: Executive Summary only.
- Chapter 2: Architecture narrative plus component purpose table.
- Chapter 3: Table inventory and explicit relationships output.
- Chapter 4: Flow analysis first, grouping second, diagrams only when requested.
- Chapter 5-11: Keep to explicit chapter scope and avoid assumptions.

## DOCX Refinement Rules

- If model responds in chat instead of document mode, instruct it to continue writing into the DOCX artifact.
- Keep existing approved content untouched when request is formatting-only.
- If heading numbering duplicates appear, remove manual numbering text and preserve Word multilevel list numbering.
- If style application is lost after structural edits, reapply template styles and confirm heading/body/table styles match template.
- Ensure every table has header row repeat enabled so multi-page tables retain context.

## Verification Checklist

Before completion, verify:
- Requested scope only (no extra chapters).
- Exact fallback sentence used for missing metadata.
- Flow diagrams comply with mandated shapes/colors/labels when requested.
- No duplicate heading numbers in visible output.
- Template styling preserved in final document.
- Table header repetition enabled across all tables.
