# Exam Study Pi Extension

Interactive study assistant for a folder of Markdown exam material, with a persistent overlay UI.

## Command

```text
/study [folder]
```

If no folder is supplied, the extension auto-detects common study folders (`microsoft-learn-ab-620`, `microsoft-learn-pl-900`, `microsoft-learn-pl-400`). If none match, it uses the current working directory.

## Overlay UI

The `/study` command opens a persistent overlay that stays open across interactions, similar to the `/btw` extension. You can:

- **Ask questions** — type any question and press Enter to get an answer from the study material
- **Generate quizzes** — type `/quiz [topic]` to generate an interactive Microsoft-style quiz
- **Switch folders** — type `/topic <path>` to change the study folder
- **Check status** — type `/status` to see file and chunk counts
- **Clear transcript** — type `/clear` to clear the conversation
- **Get help** — type `/help` to see available commands

### Keyboard shortcuts (in overlay)

- `Enter` — submit question or command
- `Escape` — dismiss overlay (transcript is preserved)
- `Alt+S` or `Ctrl+Alt+S` — toggle focus back to overlay
- `PgUp` / `PgDn` — scroll transcript

### Quiz controls (during quiz)

- `↑` / `↓` — move through answer options
- `Enter` / `Space` — toggle selected answer
- `←` / `→` — previous/next question
- `s` — submit quiz
- `q` / `Esc` — return to study overlay (after submission) or cancel

## Persistence

The study overlay transcript is preserved across sessions. Answers are also saved to the main chat as visible study notes.

The command caps generated quizzes at 50 questions to keep model output and the terminal UI manageable.