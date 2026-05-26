---
name: exam-qa-generator
description: Generates multiple-choice and multiple-select question and answer banks from Microsoft Learn training data. Use when the user wants to create exam practice questions from downloaded Microsoft Learn study material.
---

# Exam Q&A Generator

Generates a JSON question-and-answer bank from Microsoft Learn training material (Markdown files produced by the `microsoft-exam-docs` skill).

## Artifact policy

Create exactly one file: the final question-and-answer JSON file named `{exam-code}.json` in the training directory.

Do not create helper scripts, scratch files, intermediate JSON/Markdown files, manifests, logs, caches, or generated tooling. Do not scaffold a generator. If validation or analysis needs code, use inline shell commands only (for example `node -e`, `python -c`, `jq`, `rg`, `awk`) and do not write those commands to disk.

## Efficiency guidelines

- Build a quick content outline from headings before generating questions. Use it to identify learning paths, modules, units, and sections with enough body content.
- Allocate question counts per section before generation starts. This avoids over-generating and then discarding large batches.
- Generate in section-sized batches instead of repeatedly prompting over the entire `CONTENT.md`.
- When using subagents, pass only the relevant source section(s), the allocated question count, and the schema rules. Do not pass the entire exam content to every subagent unless the file is small.
- Prefer exact JSON arrays from generation batches so the coordinator can merge them directly with minimal rewriting.
- Do one final global pass for duplicates, topic consistency, answer/option integrity, IDs, and `questionCount`.
- Use inline validation commands where useful, but keep all intermediate state in memory and write only the final JSON file.

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
  "questionCount": 50,
  "questions": [
    {
      "id": 1,
      "topic": "Configure message formatting in agent topics",
      "type": "single",
      "question": "In Microsoft Copilot Studio, which feature allows you to define multiple phrasings for a single message node so the experience feels different on repeated visits?",
      "answers": ["Message variations"],
      "options": [
        "Message variations",
        "Quick replies",
        "Adaptive Cards",
        "Topic branching"
      ],
      "WrongAnswerHint": "Review the module **Configure message formatting in agent topics** in the *Build chatbots with Copilot Studio* learning path."
    },
    {
      "id": 2,
      "topic": "Manage environment variables",
      "type": "multiple",
      "question": "Which of the following are valid ways to store environment-specific configuration in a Power Platform solution? (Choose all that apply.)",
      "answers": [
        "Environment variables",
        "Custom connectors"
      ],
      "options": [
        "Environment variables",
        "Custom connectors",
        "Business rules",
        "Workflow processes",
        "Plugin assemblies"
      ],
      "WrongAnswerHint": "Review the module **Manage environment variables** in the *Implement Power Platform solutions* learning path."
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
| `questions[].type` | Either `single` (multiple choice — one correct answer) or `multiple` (multiple select — 1–5 correct answers). |
| `questions[].question` | Clear, specific question. No tricks — test real knowledge. |
| `questions[].answers` | Array of correct option strings. For `single` type, exactly **1** element. For `multiple` type, **1–5** elements. Every element must appear verbatim in the `options` array. |
| `questions[].options` | Array of all plausible options. For `single` type, exactly **4** options. For `multiple` type, exactly **5** options. Distractors must be realistic and relate to the domain. |
| `questions[].WrongAnswerHint` | A short, actionable pointer to the relevant learning-path or module title in `CONTENT.md` the question came from, so a user can quickly re-study the material when they answer incorrectly. Must not contain the correct answer itself. Example: "Review the module **Configure message formatting in agent topics** in the *Build chatbots with Copilot Studio* learning path." |

## Generation process

Follow these steps **in order**. Do not skip any step.

### Step 1 — Identify the training directory

The user provides a path to a directory containing:
- `SUMMARY.md` — exam metadata (extract `exam` object from here)
- `CONTENT.md` — all training lesson content for the exam

If no path is given, use the current working directory.

### Step 2 — Read the exam metadata

Read `SUMMARY.md`. Extract **only** the exam info fields for the `exam` object in the output JSON:
- `code` — from the exam code field
- `title` — from the exam title / study guide heading
- `duration` — from the duration field
- `passingScore` — from the passing score field
- `level` — from the level field

Ignore all other content in SUMMARY.md (skills measured, objectives, audience profile, links, etc.).

### Step 3 — Read training content

Read `CONTENT.md` completely — it contains all learning paths, modules, and units for the exam. Do not truncate or skip sections.

For very large files, read in chunks using offset/limit until you have consumed the entire file.

### Step 4 — Generate questions

Generate questions distributed across the training content. If the user specifies a number, generate exactly that many questions. If no number is given, generate **50** questions. Follow these guidelines:

**Parallel generation when available:**
- When subagent tools are available, use them by default for multi-module content, large `CONTENT.md` files, or requested question counts of 30 or more. Skip subagents only when the source material is small enough that delegation overhead would dominate.
- Spawn a small number of independent workers, usually 2-6, based on coherent content partitions. Do not spawn one worker per question.
- The main agent is the coordinator. It remains responsible for reading `SUMMARY.md`, determining the requested question count, computing the section/module allocation, merging output, validating the final JSON, and writing the only output file.
- Split work by learning path, module, or coherent content ranges. Give each subagent only the source sections it needs, the exact number of questions to generate, the required single/multiple mix, and the schema rules.
- Require each subagent to return only an in-memory JSON array of question objects without top-level `exam`, `generatedAt`, `questionCount`, or file-writing instructions.
- Do not let subagents create files, scripts, or tool scaffolding. They generate question objects only.
- After subagents return, the coordinator deduplicates, normalizes topic labels, assigns final sequential IDs, verifies answer/option consistency, and writes `{exam-code}.json`.
- If subagents are unavailable, continue in a single agent using the same section allocation and validation rules.

**Distribution:**
- Spread questions proportionally across learning paths and modules based on content depth.
- If a section has very little content (e.g., only headings with no body), skip it and redistribute to sections with real content.
- Each distinct module/section should have at least a few questions.
- Question type mix: aim for roughly **70% `single`** and **30% `multiple`**, but adjust based on the material. If the content naturally lends itself to many multi-select scenarios, go up to 40% `multiple`.

**Quality guidelines:**
- Questions should test **understanding and application**, not just recall of exact phrases.
- **Never reference images, diagrams, figures, or visual examples.** Questions and answers must be purely based on text content. Do not include phrasing such as "as shown in the image", "refer to the diagram", or "based on the figure above". If a section relies heavily on images and lacks sufficient explanatory text, skip it and redistribute the questions to sections with adequate text content.
- Include a mix of question types:
  - Conceptual understanding ("What is the purpose of…?")
  - Feature identification ("Which feature allows you to…?")
  - Scenario-based ("A company wants to… Which approach should they use?")
  - Comparison ("What is the difference between X and Y?")
  - Configuration ("How do you configure…?")
  - Best practice ("What is the recommended approach for…?")
- Avoid trivial questions that can be answered by a single word from a heading.
- Avoid negative questions ("Which of the following is NOT…") — use them sparingly at most.
- Do **not** invent features, facts, or concepts that are not present in the training material.

**Single-choice (`single`) questions:**
- Exactly **4 options**.
- Exactly **1 correct answer**.
- Distractors must be plausible and come from related concepts in the material — not obviously wrong.

**Multiple-select (`multiple`) questions:**
- Exactly **5 options** total.
- **1–5 correct answers**.
- Use these when the material describes:
  - A list of valid steps, requirements, or prerequisites.
  - Multiple features that apply to a scenario.
  - Several configuration options that must all be selected.
- Distractors must be plausible — they can be real concepts from the material that do **not** apply to the specific question.
- Phrase the question clearly so the user knows to select all that apply (e.g., "Which of the following…? (Choose all that apply.)").

**Topic assignment:**
- Derive the `topic` from the nearest module or section heading.
- Keep topic labels concise (3–6 words).
- Use consistent topic labels for questions from the same section.

### Step 5 — Write the output file

Write the complete JSON to a file named `{exam-code}.json` (e.g., `pl-400.json`, `pl-900.json`) in the training directory.

This is the only file that may be created or modified. Do not leave behind generated scripts, temporary files, partial question banks, analysis notes, or other artifacts.

Validate the JSON:
- `questionCount` must equal `questions.length`
- Every element in `answers` must appear verbatim in its corresponding `options` array
- For `single` type: `answers.length === 1` and `options.length === 4`
- For `multiple` type: `answers.length` is between 1 and 5, and `options.length === 5`
- No duplicate questions
- All `id` values are sequential from 1

Report the total questions generated and the file path to the user.

## Example invocation

When the user says:

- "Generate a Q&A bank from this material"
- "Create practice questions for my exam"
- "Build a question bank from the training data in ./microsoft-learn-ab-620"
- "Generate 80 practice questions for PL-400"

Then follow the process above. The user may optionally specify a number of questions (e.g., "Generate 80 questions"). If no number is given, default to 50.

## Usage from command line

If invoked via `/skill:exam-qa-generator /path/to/training/dir`, use the provided path as the training directory.

If invoked via `/skill:exam-qa-generator` with no arguments, use the current working directory.
