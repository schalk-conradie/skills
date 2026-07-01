---
name: cleanup-ts
description: Clean up TypeScript, TSX, Node, React, frontend, backend, or shared package code that may contain AI-generated or AI-modified code smells. Use when asked to reduce maintenance risk, remove unsafe TypeScript patterns, simplify redundant abstractions, fix duplicated logic, repair brittle tests, or address architectural drift without changing behavior.
---

# Cleanup TS

## Purpose

Use this skill when cleaning up TypeScript, TSX, Node, React, frontend, backend, or shared package code that may contain AI-generated or AI-modified code smells.

Primary objective: reduce long-term maintenance risk without changing behavior.

Secondary objective: remove unsafe TypeScript patterns, redundant abstractions, duplicated logic, brittle tests, and architectural drift.

## Operating Rules

1. Preserve behavior unless the task explicitly asks for a behavior change.

2. Before editing, inspect nearby code, existing helpers, existing types, existing tests, and project conventions.

3. Prefer deleting code over adding code. A cleanup that increases code size must justify the increase.

4. Do not loosen `tsconfig`, ESLint, test config, build config, or CI config to make cleanup pass.

5. Never add `any`, `as any`, `as unknown as T`, broad type assertions, or non-null assertions to silence errors.

6. Existing `any` must be replaced with a concrete type, a generic constraint, `unknown` plus narrowing, or an isolated boundary adapter.

7. Treat `unknown` as unusable until narrowed by a type guard, schema parser, `instanceof`, discriminant, or explicit runtime check.

8. Replace unsafe object-literal casts like `{ ... } as SomeType` with annotations or `satisfies` where appropriate.

9. Remove unnecessary type assertions that do not change or improve safety.

10. Ban non-null assertion `!` except in rare proven invariants. If kept, add a local explanation or replace with an invariant helper.

11. Do not use `@ts-ignore`. Use `@ts-expect-error` only when unavoidable, with a reason and the smallest possible scope.

12. Do not add broad `eslint-disable` comments. Line-level disables require a reason and must not suppress type-safety rules casually.

13. Public exported functions, package APIs, hooks, service methods, and library utilities should have explicit return types.

14. Runtime inputs are untrusted. Validate or parse `JSON.parse`, `fetch().json()`, request bodies, query params, route params, localStorage, cookies, and environment variables.

15. Do not cast API responses, database rows, or external SDK results directly into domain types. Map and validate them.

16. Separate DTO, database row, form state, API response, domain model, and view model types when their semantics differ.

17. Do not use `Partial<T>` as a substitute for a real draft, patch, update, or form type.

18. Avoid optional booleans. Replace `flag?: boolean` with a required boolean or an explicit union such as `"enabled" | "disabled" | "inherit"`.

19. Replace boolean-state clusters like `isLoading`, `isError`, `isSuccess`, `data?`, `error?` with discriminated unions.

20. Every discriminated union switch must be exhaustive using `never` or an equivalent exhaustiveness helper.

21. Prefer `??` over `||` when defaulting values that may validly be `0`, `false`, or `""`.

22. Avoid truthiness checks for nullable strings, numbers, arrays, and objects when the distinction matters. Use explicit checks.

23. Treat indexed access as possibly missing. Guard `arr[i]`, `record[key]`, `map[id]`, and environment lookups.

24. Avoid `Record<string, T>` unless every possible string key is valid. Prefer narrower key unions, `Partial<Record<K, T>>`, or `Map`.

25. Use `readonly` arrays and readonly object shapes for inputs that should not be mutated.

26. Do not mutate function inputs unless the function name and contract clearly indicate mutation.

27. Avoid hidden shared mutable module state. If state is necessary, make ownership explicit.

28. Search before adding new helpers, utilities, hooks, services, validators, types, or abstractions.

29. Do not duplicate business logic. If two blocks implement the same business rule, extract a shared function or consolidate ownership.

30. Do not extract merely because code looks textually similar. Extract only when the concept is actually shared.

31. Avoid "manager," "handler," "processor," "service," and "utils" sprawl. Use domain-specific names and responsibilities.

32. Keep functions focused. Split functions with excessive branching, nesting, multiple responsibilities, or unclear phases.

33. Prefer early returns over deeply nested conditionals.

34. Avoid type gymnastics. Replace deeply nested conditional/mapped utility types with named intermediate types or simpler domain types.

35. Do not introduce generics unless the implementation truly works for multiple caller-supplied types.

36. A generic function must not simply return `T` from unvalidated data. `function parse<T>(x): T` is a cast factory and should be replaced.

37. Avoid wrapper abstractions around existing APIs unless they enforce a real invariant, simplify repeated use, or isolate a dependency.

38. Do not introduce a new library, framework, state manager, validator, test tool, or build plugin without explicit approval.

39. Preserve architectural boundaries. Domain code must not import UI, HTTP, framework, database-client, or infrastructure-specific code unless that is already the project pattern.

40. Prevent circular dependencies. If cleanup creates a cycle, stop and refactor the dependency direction.

41. Use `import type` for type-only imports when the project supports it.

42. Do not expand barrel files casually. Prefer explicit exports when broad barrels obscure dependency graphs.

43. Async work must be owned. No floating promises. Use `await`, `return`, `.catch`, or intentional `void` with a reason.

44. Do not use `array.forEach(async ...)`. Use `for...of` for sequencing or `Promise.all` / controlled concurrency for parallel work.

45. External I/O should have timeout, cancellation, or lifecycle handling when the surrounding codebase supports it.

46. Do not swallow errors with empty `catch` blocks. Handle, wrap, log through the project logger, or return a typed failure.

47. Preserve error context. When wrapping errors, include `cause` where supported.

48. Do not add console logging in production code unless the project uses console logging intentionally. Use the project logger.

49. For React, do not create contexts with `{ } as ContextType`. Use `ContextType | null` and a safe hook that throws if the provider is missing.

50. For React, avoid impossible component state. Use discriminated union state for loading/error/success/empty flows.

51. For React, type event handlers precisely. Do not use `any` for DOM or React events.

52. For React, keep props explicit. Large prop bags signal a component that may need splitting.

53. For React, do not use `useRef`, `useMemo`, or `useCallback` just to silence dependency or lifecycle problems.

54. Tests must not be deleted, skipped, weakened, or rewritten merely to pass.

55. Avoid excessive mocks. Mock external boundaries, not the behavior under test.

56. If fixing a bug, add or update a test that would have failed before the fix.

57. If refactoring, keep or improve test coverage around the changed behavior.

58. Do not hardcode special cases to satisfy the current tests. Implement the general behavior.

59. Run the relevant checks after cleanup: typecheck, lint, unit tests, integration tests, formatting, and build as applicable.

60. If checks cannot be run, report exactly which checks were not run and why.

61. Review the final diff for unrelated changes. Revert unrelated formatting, churn, renamed symbols, or broad rewrites.

62. Every cleanup summary must include: files changed, smells removed, behavior impact, tests/checks run, and remaining risks.

63. For audit findings, do not report speculative issues as facts. Each finding needs a code location, impact, and verification path.

64. For duplicate-code audits, identify semantic duplication, not just repeated syntax. Prefer "same business rule repeated" over "same five lines repeated."

65. For large cleanup tasks, work in small commits or patches by smell category: type safety, runtime validation, state modeling, async, duplication, tests, architecture.

66. If a change crosses architectural boundaries or affects public API, stop and ask for approval before proceeding.

67. Never claim cleanup is complete unless the diff was inspected and relevant checks passed.

## Cleanup Priority Order

1. Remove unsafe type escape hatches.
2. Validate runtime boundaries.
3. Restore strict compiler/lint compliance.
4. Fix async hazards.
5. Replace invalid state shapes with discriminated unions.
6. Remove duplication and helper sprawl.
7. Simplify over-generic or over-abstracted code.
8. Repair tests and remove brittle mocks.
9. Check architecture boundaries.
10. Run verification and report residual risk.

## Definition of Done

A cleanup is done only when:

- TypeScript passes.
- Lint passes or remaining failures are unrelated and documented.
- Relevant tests pass.
- No new `any`, unsafe assertions, skipped tests, broad disables, or config relaxations were introduced.
- The diff is smaller, simpler, or demonstrably safer.
- Remaining risks are explicitly listed.
