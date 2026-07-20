# Personal Coding Standards

These are personal defaults. Repository instructions and established project conventions take precedence.

Only add a rule after encountering concrete, recurring friction.

## General

### Design

- Prefer direct, concrete code over speculative abstractions.
- Do not add single-use wrappers, factories, managers, providers, or interfaces without a current benefit.
- Prefer deletion when it fully solves the problem while preserving clear behavior.

### Errors and fallbacks

- Do not add hidden fallbacks or silently swallow meaningful errors.

### Dependencies

- Do not add dependencies when the standard library, platform, or an installed dependency adequately solves the problem.

## TypeScript

### Types and boundaries

- Validate data at external or untyped boundaries. Avoid redundant runtime checks for trusted internal values whose ownership and types already establish validity.
