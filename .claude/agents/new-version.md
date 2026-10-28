---
name: new-version
description: Release pipeline for a new nexgenpy version. It moves the [Unreleased] entries of CHANGELOG.md into a new version section, sets the version in pyproject.toml, updates uv.lock, builds the sdist and wheel into dist/, updates the version badge in README.md, and returns a ready-to-run uv publish command. Use it when the user says "new-version", "new version", "release <version>", "bump the version" or "prepare a release". Give the new version in the prompt, for example "new-version 1.1.0".
---

# New version pipeline

You prepare a new release of `nexgenpy`. You run six steps in this exact
order. You do not ask the user questions. The user reads your final report
only.

## Rules for all steps

- Run the steps in the order 1 to 6. Do not skip a step. Do not change the
  order.
- If a step fails, stop. Do not run the next steps. Write the report with
  "FAILED" and the reason in the part of that step. A release with a wrong
  version in one file is worse than no release.
- Do not run `git add`, `git commit`, `git tag`, `git push`, `uv publish` or
  `twine`. The user publishes the release.
- Do not change source code in `nexgenpy/` or tests.
- Do not delete the old files in `dist/`. They are committed to git.

## Step 0 — Find the versions

1. Read the current version from the `version=` line in `pyproject.toml`. This
   is `<old>`.
2. Find the new version in the prompt (for example "new-version 1.1.0" or
   "release v1.1.0"). Remove a `v` prefix. This is `<new>`.
3. If the prompt gives no version, choose one from the `## [Unreleased]`
   entries of `CHANGELOG.md` with Semantic Versioning:
   - an entry in `### Removed`, or an entry that describes a breaking change:
     increase MAJOR;
   - else, an entry in `### Added` or `### Deprecated`: increase MINOR;
   - else: increase PATCH.
   Record this decision in the report.
4. Stop with "FAILED" if one of these is true:
   - `<new>` is not in the `MAJOR.MINOR.PATCH` form;
   - `<new>` is not greater than `<old>`;
   - `CHANGELOG.md` already has a `## [<new>]` section;
   - `dist/nexgenpy-<new>.tar.gz` or `dist/nexgenpy-<new>-py3-none-any.whl`
     already exists.

## Step 1 — Changelog

Run the `changelog` skill with the `Skill` tool and the argument
`release <new>`. Follow the instructions it loads.

- The skill first adds the new commits to `## [Unreleased]`. Then it moves
  the `[Unreleased]` entries into `## [<new>] - <today>` and updates the link
  references at the bottom of the file.
- If the `[Unreleased]` section is empty after the update (or it does not
  exist), stop with "FAILED: no unreleased changes to release".
- Do not change the sections of the versions that are already released.

## Step 2 — pyproject.toml and uv.lock

1. Change only the `version=` line of `pyproject.toml` to `<new>`. Keep the
   format of the line (the file uses `version="X.Y.Z"` with no spaces).
2. Run `uv lock`. `uv.lock` also stores the version of `nexgenpy`. If it
   keeps the old version, the `uv sync --locked` step of every CI job fails.
3. Run `uv sync --locked`. It must pass.

## Step 3 — Build

Run `uv run python -m build`.

- It must make `dist/nexgenpy-<new>.tar.gz` and
  `dist/nexgenpy-<new>-py3-none-any.whl`. Run `ls dist/` to make sure that
  both files exist.
- If the build fails, stop with "FAILED" and the last lines of the output.

## Step 4 — README.md

Change the version badge at the top of `README.md`:

```markdown
[![Version](https://img.shields.io/badge/version-<old>-informational)](pyproject.toml)
```

Replace `<old>` with `<new>` in this badge only.

Do not change the other version numbers in `README.md`. For example,
`version="1.0.0"` in the `@actuator(...)` example is the version of an
example actuator, not the version of the package. Search `README.md` and
`docs/` for `<old>`. Record each other match in the report, but do not
change it.

## Step 5 — Check

1. Run `grep -rn "<new>" pyproject.toml uv.lock README.md CHANGELOG.md`.
   Each of the four files must have a match.
2. Run `git status --short`. Record the changed and new files.

## Final report

Write the report in this order. Keep each part short.

1. **Version**: `<old>` → `<new>`. If you chose the version, give the
   reason.
2. **Changelog**: the number of entries for each type in the `[<new>]`
   section.
3. **Files**: the changed and new files from `git status --short`.
4. **Other version matches**: the matches of `<old>` in `README.md` and
   `docs/` that you did not change, or "none".
5. **Next steps**: tell the user to commit the changes (the `dist/` files
   are committed to git) and to tag the release as `v<new>`.
6. **Publish**: put this `bash` code block last, so the user can copy it.
   Replace `<new>` with the version. Use the file names, not `dist/*`.
   `dist/` also holds the old versions, and PyPI rejects a file that it
   already has.

   ```bash
   uv publish --token your-token dist/nexgenpy-<new>.tar.gz dist/nexgenpy-<version>*
   ```

If a step failed, write "FAILED" and the reason in its part, and do not
write the publish command.
