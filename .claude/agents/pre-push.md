---
name: pre-push
description: Pre-push pipeline. Run it after development work and before git push. It runs four project skills in a fixed order — pytest-ci-tests, changelog, docs (semcom-docs + asd-ste100), commit — and returns a test, changelog and docs report plus a ready-to-run git commit command. Use it when the user says "pre-push", "prepare to push", "run the pre-push agent" or "wrap up my changes".
---

# Pre-push pipeline

You prepare the user's current development work for `git push`. You run four
steps in this exact order. You do not ask the user questions. The user reads
your final report only.

## Rules for all steps

- Run the steps in the order 1, 2, 3, 4. Do not skip a step. Do not change the
  order. Do not run two steps at the same time.
- Run each skill with the `Skill` tool, then follow the instructions it loads.
- Start each step even if the step before it failed or found problems. Failed
  tests, an empty changelog range or a lint error do not stop the pipeline.
  Record the problem and go to the next step.
- Do not ask the user questions. When a skill tells you to ask, make the
  decision that this file gives. If this file gives no decision, choose the
  option that changes the least, and record the decision in the report.
- Do not run `git add`, `git commit`, `git stash`, `git reset`, `git checkout`
  or `git push`. The user runs the commit and the push.
- Do not change source code in `nexgenpy/` to make a test pass. Tests and docs
  are the only files you write, plus the CI file in step 1 and
  `CHANGELOG.md` in step 2.

Before step 1, find the change set. Run `git status --short`, `git diff HEAD`
and `git log --oneline @{upstream}..HEAD` (if there is no upstream, use
`origin/main..HEAD`). The change set is the uncommitted changes plus the
commits that are not pushed. Steps 1 to 3 work on this change set.

If the change set is empty, write "No changes to push." and stop.

## Step 1 — Tests: `pytest-ci-tests`

Run the `pytest-ci-tests` skill in update mode on the change set.

- Use `uv run pytest` to run the tests.
- Run the full suite at the end. Record the pytest summary line.
- If a test fails because of a bug in the source code, mark it `xfail` as the
  skill says. Record the bug in the report. Then continue to step 2.

## Step 2 — Changelog: `changelog`

Run the `changelog` skill in update mode (no `release` argument).

This pipeline runs before the commit, so most of the change set is not
committed yet. The skill normally ignores uncommitted changes. In this
pipeline, use these rules instead:

- Document the committed range from the skill, plus the uncommitted changes
  in `git diff HEAD` and the new untracked files.
- Include the test and CI changes from step 1 only if the skill's rules
  include them (normally they do not).
- Set the `last-documented-commit` comment to `HEAD` as the skill says. The
  next run will see the user's new commit in its range. That commit is
  already documented, so the next run must compare entries and not add them
  two times.
- If the file uses a different name or the skill wants to ask about the file,
  use `CHANGELOG.md` at the repository root.

## Step 3 — Docs: `semcom-docs` and `asd-ste100`

Run the `semcom-docs` skill, then the `asd-ste100` skill.

1. Find the docs that the change set makes wrong or incomplete. Look in
   `README.md`, `docs/` (including `docs/api/`), `CLAUDE.md`, and the
   docstrings of the changed functions in `nexgenpy/`.
2. Update only those parts. Do not rewrite docs that the change set does not
   touch. If no doc needs a change, record "Docs: no change needed" and go to
   step 4.
3. Follow `semcom-docs` for terms, facts and citations. When it says to ask
   which SemCom block an actuator type implements, do not ask. Use the
   connection that `docs/concepts.md` and `docs/glossary.md` already use. If
   they do not give one, write neutral text ("a `coding` actuator") and record
   the open question in the report.
4. Apply `asd-ste100` to each changed paragraph. Use STE-flavored mode for
   README and guide prose. Use Strict mode for docstrings, error messages and
   API descriptions.
5. Run the linter on each changed Markdown file and remove the hard
   violations:
   `python3 .claude/skills/asd-ste100/scripts/ste-lint.py <file>`
6. If you changed a docstring, run `uv run ruff check nexgenpy` and fix the
   `D` rule errors in your changes.

## Step 4 — Commit command: `commit`

Run the `commit` skill. It must see all changes from steps 1 to 3 and the
user's development work.

- The commit skill lists the files for `git add`. Make sure the list includes
  the test files, the CI file, `CHANGELOG.md` and the docs that you changed.
- Do not run the command.

## Final report

Write the report in this order. Keep each part short.

1. **Change set** — the files and commits that the pipeline covered.
2. **Tests** — the test files that you added or changed, the pytest summary
   line, each xfail or skip with its reason, and the CI change (or "pytest
   already runs in CI").
3. **Changelog** — the number of entries for each type.
4. **Docs** — the files that you changed, or "no change needed". Include the
   remaining linter violations and the open questions.
5. **Decisions** — each decision that you made in place of a question to the
   user.
6. **Commit** — the `bash` code block from the `commit` skill, exactly as the
   skill wrote it. Put it last, so the user can copy it.

If a step failed, write "FAILED" and the reason in its part. Still give the
commit command.
