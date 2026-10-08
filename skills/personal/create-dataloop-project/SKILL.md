---
name: create-dataloop-project
description:
    Create a new local Dataloop application from the private Azure DevOps boilerplate in Claude Code, including
    dependency installation and build verification. Use for new projects, not updates to an existing application.
---

Run on the developer's machine in Claude Code. This skill needs Node 24, npm, Git, and the developer's existing Azure
DevOps Git authentication. It does not need a local boilerplate checkout. If invoked in a chat container without access
to the developer's filesystem and Git credentials, explain that it must run in Claude Code instead.

Use the application name and destination from the request. Ask only for either that is missing and cannot be inferred.
Names use 2–40 lowercase letters, digits, or hyphens, starting with a letter; Windows reserved device names are invalid.
Resolve the destination to an absolute path outside the boilerplate. It must be new or empty. Preserve an occupied
destination and ask for another path; do not remove its contents or silently choose a different destination.

Use a requested release tag or branch. Until V2 is merged, the default is `boilerplate-v2`; prefer an approved release
tag once one exists. The default source is the private Dataloop Boilerplate Azure DevOps repository. Use `--source` only
when the user specifies another trusted template Git URL. Never place credentials in a URL or command, change Git's
credential configuration, or retry authentication failures without addressing the reported cause.

Locate the bundled [scripts/create-project.mjs](scripts/create-project.mjs) relative to this skill's directory, not the
current project. In Claude Code, `${CLAUDE_SKILL_DIR}` identifies the skill directory. If that placeholder is
unavailable, use the directory of the loaded SKILL.md. Run the helper with separately quoted arguments, for example:

```sh
node "${CLAUDE_SKILL_DIR}/scripts/create-project.mjs" --name my-app --directory "/absolute/path/my-app" --ref boilerplate-v2
```

The helper fetches the selected Git ref into a temporary directory, invokes that snapshot's existing initializer, and
removes the temporary checkout. The initializer stamps the application's identity, copies repository instructions and
skills, excludes secrets and build outputs, creates fresh Git history on `main`, and writes `template.json` provenance.
Do not recreate the scaffold by hand or switch to a different ref after a failed fetch.

After creation, read the generated AGENTS.md and README.md. Run `npm ci` and `npm run check` in the new project. Create
`.env` from `.env.example` only when local startup was requested and `.env` does not already exist. Follow the generated
README for startup and browser checks; report unavailable checks. Leave Entra and SQL placeholders until the user
provides the environment configuration; never introduce an authentication bypass.

If generation succeeds but installation or checks fail, preserve the new project and report the failing step. Finish
with the absolute project path, template ref/revision, checks passed, and next setup steps. Creation does not authorize
making a remote repository, committing, pushing, deploying, or changing cloud resources. Perform those only when the
user's request includes them.
