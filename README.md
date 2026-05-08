# ai-collection

A collection of [Pi](https://github.com/earendil-works/pi) extensions and skills.

## Install the Whole Collection

Install all extensions and skills at once from this repo:

```bash
# From GitHub (SSH)
pi install git:git@github.com:schalk-conradie/ai-collection

# From GitHub (HTTPS)
pi install git:github.com/schalk-conradie/ai-collection

# From a local clone
pi install /path/to/ai-collection
```

## Install Individual Extensions

### tokens-per-second

Rich multi-line footer showing live tokens-per-second, context usage, API cost, git branch, and model info.

```bash
# Standalone install
pi install git:github.com/schalk-conradie/ai-collection#main --filter extensions/tokens-per-second

# Or install the whole collection and disable what you don't need
pi install git:github.com/schalk-conradie/ai-collection
```

### exam-study

Interactive study assistant for Markdown exam notes. Ask questions from your material or generate Microsoft-style practice quizzes with a full terminal UI.

```bash
# Standalone install
pi install git:github.com/schalk-conradie/ai-collection#main --filter extensions/exam-study
```

## Install Individual Skills

Skills are auto-loaded when relevant. Install the whole collection and pick what you use:

```bash
pi install git:github.com/schalk-conradie/ai-collection
```

## Included

### Extensions

| Extension | Description |
|-----------|-------------|
| [tokens-per-second](extensions/tokens-per-second/) | Live TPS, context %, cost, git branch in the footer |
| [exam-study](extensions/exam-study/) | Study assistant: ask questions & generate quizzes from Markdown notes |

### Skills

| Skill | Description |
|-------|-------------|
| [blueprint](skills/blueprint/) | Creates technical design blueprint DOCX files from Markdown |
| [d365-asbuilt](skills/d365-asbuilt/) | Generate Dynamics 365 as-built technical documentation |
| [dynamics-365](skills/dynamics-365/) | Read-only access to Dynamics 365 WebAPI / Dataverse |
| [microsoft-exam-docs](skills/microsoft-exam-docs/) | Download Microsoft Learn study material for certification exams |

## Managing Installed Packages

```bash
# List installed packages
pi list

# Update all packages
pi update

# Remove the collection
pi remove git:github.com/schalk-conradie/ai-collection
```

## Filtering Resources

If you only want specific extensions or skills from the collection, use package filtering in your settings:

```json
{
  "packages": [
    {
      "source": "git:github.com/schalk-conradie/ai-collection",
      "extensions": ["extensions/tokens-per-second/src/index.ts"],
      "skills": []
    }
  ]
}
```
