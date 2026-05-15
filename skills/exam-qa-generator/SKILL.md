---
name: exam-qa-generator
description: Generates multiple-choice question and answer banks from Microsoft Learn training data. Use when the user wants to create exam practice questions from downloaded Microsoft Learn study material.
---

# Exam Q&A Generator

Generates a JSON question-and-answer bank from Microsoft Learn training material (Markdown files produced by the `microsoft-exam-docs` skill).

## Output format

A single JSON file structured as:

```json
{
  "exam": {
    "code": "AB-620",
    "title": "Designing and Building Integrated AI Solutions in Copilot Studio",
    "duration": "100 minutes",
    "passingScore": "700 / 1000",
    "level": "Intermediate"
  },
  "generatedAt": "2025-05-15T12:00:00Z",
  "questionCount": 100,
  "questions": [
    {
      "id": 1,
      "topic": "Configure message formatting in agent topics",
      "question": "In Microsoft Copilot Studio, which feature allows you to define multiple phrasings for a single message node so the experience feels different on repeated visits?",
      "answer": "Message variations",
      "options": [
        "Message variations",
        "Quick replies",
        "Adaptive Cards",
        "Topic branching"
      ]
    }
  ]
}
```

### Schema rules

| Field | Rules |
|---|---|
| `exam` | Populated from `SUMMARY.md` only (code, title, duration, passingScore, level). Ignore all other SUMMARY.md content. |
| `generatedAt` | ISO 8601 timestamp of generation. |
| `questionCount` | Must match the actual length of the `questions` array. |
| `questions[].id` | Sequential integer starting at 1. |
| `questions[].topic` | Short label derived from the module/section heading the question covers. Used to group related questions. |
| `questions[].question` | Clear, specific question. No tricks — test real knowledge. |
| `questions[].answer` | Must be **exactly** one of the option strings. |
| `questions[].options` | Array of **4** plausible options (A–D style). Exactly one correct. Distractors must be realistic and relate to the domain. |

## Generation process

Follow these steps **in order**. Do not skip any step.

### Step 1 — Identify the training directory

The user provides a path to a directory containing:
- `SUMMARY.md` — exam metadata (extract `exam` object from here)
- One or more numbered `.md` files (e.g. `01-*.md`, `02-*.md`, …) — the actual training content

If no path is given, use the current working directory.

### Step 2 — Read the exam metadata

Read `SUMMARY.md`. Extract **only** the exam info fields for the `exam` object in the output JSON:
- `code` — from the exam code field
- `title` — from the exam title / study guide heading
- `duration` — from the duration field
- `passingScore` — from the passing score field
- `level` — from the level field

Ignore all other content in SUMMARY.md (skills measured, objectives, audience profile, links, etc.).

### Step 3 — Read all training content files

Read **every** `.md` file in the directory **except** `SUMMARY.md`, in numerical order. These files contain the full course material. Read each file completely — do not truncate or skip sections.

For very large files, read in chunks using offset/limit until you have consumed the entire file.

### Step 4 — Generate questions

Generate approximately **100 questions** distributed across the training content. Follow these guidelines:

**Distribution:**
- Spread questions proportionally across all training files based on their content depth.
- If a file has very little content (e.g., only headings with no body), skip it and redistribute to files with real content.
- Each distinct module/section should have at least a few questions.

**Quality guidelines:**
- Questions should test **understanding and application**, not just recall of exact phrases.
- Include a mix of question types:
  - Conceptual understanding ("What is the purpose of…?")
  - Feature identification ("Which feature allows you to…?")
  - Scenario-based ("A company wants to… Which approach should they use?")
  - Comparison ("What is the difference between X and Y?")
  - Configuration ("How do you configure…?")
  - Best practice ("What is the recommended approach for…?")
- Avoid trivial questions that can be answered by a single word from a heading.
- Avoid negative questions ("Which of the following is NOT…") — use them sparingly at most.
- Each question must have exactly **4 options**.
- The correct answer must be unambiguously correct based on the training material.
- Distractors must be plausible and come from related concepts in the material — not obviously wrong.
- Do **not** invent features, facts, or concepts that are not present in the training material.

**Topic assignment:**
- Derive the `topic` from the nearest module or section heading.
- Keep topic labels concise (3–6 words).
- Use consistent topic labels for questions from the same section.

### Step 5 — Write the output file

Write the complete JSON to a file named `{exam-code}.json` (e.g., `pl-400.json`, `pl-900.json`) in the training directory.

Validate the JSON:
- `questionCount` must equal `questions.length`
- Every `answer` must appear verbatim in its corresponding `options` array
- No duplicate questions
- All `id` values are sequential from 1

Report the total questions generated and the file path to the user.

## Example invocation

When the user says:

- "Generate a Q&A bank from this material"
- "Create practice questions for my exam"
- "Build a question bank from the training data in ./microsoft-learn-ab-620"

Then follow the process above.

## Usage from command line

If invoked via `/skill:exam-qa-generator /path/to/training/dir`, use the provided path as the training directory.

If invoked via `/skill:exam-qa-generator` with no arguments, use the current working directory.
