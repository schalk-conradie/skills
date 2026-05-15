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

## Install Specific Resources

`pi install git:` clones the whole repo. To load only certain extensions or skills, install the collection and filter in `~/.pi/agent/settings.json`:

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

Omit a key (`"extensions"`, `"skills"`) to load all of that type. Use `[]` to load none. You can also use glob patterns and `!` exclusions.

### Local install of a single extension

If you've cloned the repo locally, you can install a subdirectory directly:

```bash
pi install /path/to/ai-collection/extensions/tokens-per-second
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
pi list                               # show installed packages
pi update                             # update all packages
pi update git:github.com/schalk-conradie/ai-collection  # update just this one
pi remove git:github.com/schalk-conradie/ai-collection  # remove it
```
