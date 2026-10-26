---
name: commit
description: Write a ready-to-run git commit command, with a clear commit message, for the current development work, and return only that command in one bash code block — no explanation, no questions, never executed. Use this skill whenever the user asks for a commit command, a commit message, "what should I commit this as", "give me the git commit", "commit msg for this", or wants to wrap up the changes made in the session as a commit, even if they do not say "command". Do not use it to actually create, amend, push or rebase commits, or to write pull request descriptions or GitHub issues.
---

# Git Commit Command

Produce one `git commit` command that the developer can copy and run. The
developer wants a fast, clean result: the command and nothing else.

## Output contract

The full reply is one fenced code block with the language `bash`:

```bash
git commit -m "Add retry limit to webhook delivery" -m "Move a delivery to the dead-letter queue after 5 failed attempts."
```

Follow these rules, because the developer copies the reply as it is and
reads nothing around it:

- Write no text before or after the code block. No summary, no notes, no
  "here is your command".
- Ask no questions. If information is missing, decide from what you can see
  and write the best message for it.
- Do not run the command. Do not run any command that changes the
  repository (`git add`, `git commit`, `git stash`, `git push`, `git reset`).
  The developer runs the command.

## Find what changed

Use read-only sources, in this order:

1. If a git repository is in the working directory or a connected folder,
   read it with read-only commands:
   - `git status --short`
   - `git diff --staged --stat` and `git diff --staged`
   - If nothing is staged: `git diff --stat` and `git diff`
   - `git log -n 15 --oneline` to learn the style of the project's messages
2. The work done in this conversation: files edited, bugs fixed, features
   added.
3. What the developer wrote in the request.

Describe the change that the commit will contain, not the whole session.
When files are staged, the commit contains only the staged files, so the
message describes only those.

## Staging

- If files are staged, return only the `git commit` command.
- If nothing is staged but files changed, add a `git add` command on the
  line before the commit. List the changed files by path, not `git add -A`
  or `git add .`, so the developer can see what goes in. Leave out files
  that clearly do not belong (build output, `.env`, local editor files).
- If no repository is visible, return only the `git commit` command.

```bash
git add src/webhooks/worker.py tests/test_worker.py
git commit -m "Add retry limit to webhook delivery"
```

## Message style

**Match the project first.** If `git log` shows a convention, use it:
Conventional Commits (`feat:`, `fix(api):`), a ticket prefix (`ABC-123:`),
or a tag style (`[api]`). Copy the casing and the form of the scope. If no
history is visible, use plain imperative subjects without a prefix.

**Subject line**

- Use the imperative mood: "Add", "Fix", "Remove", "Rename", "Update".
  The subject completes the sentence "If you apply this commit, it will …".
- Keep it to 50 characters if possible, and never more than 72.
- Name the specific thing that changed: "Fix null check in invoice export",
  not "Fix bug" or "Update files".
- Use no period at the end.

**Body** (optional)

Add a body only when the subject cannot carry the reason or the effect:

- Explain why the change was made and what it changes for a user or a
  developer. The diff already shows how.
- Write short, active sentences with simple words. Use one idea in each
  sentence.
- Use one `-m` flag for each paragraph. A list of points goes in one
  paragraph with `- ` items separated by real line breaks inside the
  quotes.
- Add a `BREAKING CHANGE:` paragraph if the change breaks an API or a
  configuration, and the project uses Conventional Commits.
- Add a closing reference such as `Closes #123` only if the developer or
  the branch name gave the number. Do not invent issue numbers.

**One commit, one purpose.** If the changes have several unrelated
purposes, still return one command. Name the main purpose in the subject
and list the others in the body.

## Shell safety

The developer pastes the command into a shell, so it must run without
errors:

- Use double quotes around each message.
- Escape `"`, `` ` ``, `$` and `\` inside a message with a backslash, or
  rewrite the text to avoid them.
- Write backticked code names without backticks in the message, or escape
  the backticks.

## Examples

Staged diff adds input validation to the signup form. History uses
Conventional Commits:

```bash
git commit -m "fix(signup): reject emails without a domain" -m "The form accepted values such as \"name@\". The server then failed to send the confirmation email."
```

Nothing staged. Two files changed for one feature. No history visible:

```bash
git add app/export.py tests/test_export.py
git commit -m "Add CSV export for monthly reports" -m "Users can now download the monthly report as a CSV file from the Reports page."
```

Small change with an obvious reason:

```bash
git commit -m "Fix typo in README install command"
```