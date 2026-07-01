# Annotated SVG Workflow Diagram Specification

Use this when converting analyzed Power Automate flow logic into diagrams.

## Mandatory Layout

- One diagram per flow.
- Minimum `viewBox` width: 900.
- Title banner at top using full flow name.
- Directional arrows between every step.
- Yes/No labels on all condition branches.
- Add annotation callouts for complex expressions, dynamic content, loop logic, and filter queries.

## Shape and Color Mapping

- Trigger:
- Shape: parallelogram
- Fill: `#D6EAF8`
- Border: `#2980B9`

- Action:
- Shape: rounded rectangle
- Fill: `#EBF5FB`
- Border: `#2980B9`

- Condition:
- Shape: diamond
- Fill: `#F5CBA7`
- Border: `#E67E22`

- Dataverse operation:
- Shape: cylinder
- Fill: `#D5F5E3`
- Border: `#27AE60`

- Send Email:
- Shape: rounded rectangle
- Fill: `#E8DAEF`
- Border: `#8E44AD`

- Terminate/Error:
- Shape: rounded rectangle
- Fill: `#FADBD8`
- Border: `#E74C3C`

## Validation

Before finalizing, verify:
- Every flow step appears exactly once unless loop repetition is explicitly represented.
- Branch labels are present on each conditional edge.
- Colors and shape categories match the mapping.
- Diagram remains legible when embedded into DOCX.
