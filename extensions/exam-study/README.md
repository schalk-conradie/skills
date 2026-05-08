# Exam Study Pi Extension

Interactive study assistant for a folder of Markdown exam material.

## Command

```text
/study [folder]
```

If no folder is supplied, the extension uses `./microsoft-learn-ab-620` when present, otherwise the current working directory.

## Modes

- **Ask a question** — asks the selected model to answer from retrieved Markdown chunks and cite source paths.
- **Generate an interactive quiz** — creates Microsoft-style scenario questions from the material, with configurable question count and answer option count, then opens an interactive quiz UI.
- **Show study folder status** — reports the detected folder, Markdown file count, and searchable chunk count.

## Quiz controls

- `↑` / `↓` — move through answer options
- `Enter` / `Space` — toggle selected answer
- `←` / `→` — previous/next question
- `s` — submit quiz
- `q` / `Esc` — close after submission, or cancel before submission

The command caps generated quizzes at 50 questions to keep model output and the terminal UI manageable.
