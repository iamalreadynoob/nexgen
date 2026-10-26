---
name: pytest-ci-tests
description: Set up pytest for a Python project that has no tests, or update and add tests for the development that changed, run them, and then make sure the project's existing CI pipeline (GitHub Actions, GitLab CI, Azure Pipelines, Bitbucket, CircleCI, Jenkins, Travis and others) runs pytest — adding the step only if it is missing. Use this skill whenever the user asks to add, write, start, set up, fix or update tests for a Python project, says "cover my changes with tests", "my tests are out of date", "add pytest", "make CI run the tests", or finishes a feature and wants it tested, even if they do not say "pytest" or "CI". Do not use it for non-Python test frameworks (Jest, Go test, JUnit), for running an existing test suite once with no changes, or for creating a brand-new CI pipeline from nothing unless the user asks for one.
---

# Pytest Tests and CI

This skill does three jobs, in order:

1. Choose the mode: **start** tests for a project without tests, or
   **update** tests for code that changed.
2. Write the tests and run them until the result is honest: green, or red
   only where the code has a real bug.
3. If the project has a CI file, make sure the CI runs pytest. Add the
   step only when it is missing.

At the end, give a short report (see "Report").

---

## Step 1 — Read the project

Learn how the project works before you write anything. Tests that do not
match the project's layout or tools are noise.

Find these facts:

- **Python version** — from `pyproject.toml` (`requires-python`),
  `.python-version`, `setup.cfg`, `runtime.txt`, or the CI file.
- **Package and environment tool** — the lock or config file tells you:

  | File | Tool | Add a dev dependency | Run pytest |
  | --- | --- | --- | --- |
  | `uv.lock` | uv | `uv add --dev pytest` | `uv run pytest` |
  | `poetry.lock` | Poetry | `poetry add --group dev pytest` | `poetry run pytest` |
  | `pdm.lock` | PDM | `pdm add -dG test pytest` | `pdm run pytest` |
  | `Pipfile` | Pipenv | `pipenv install --dev pytest` | `pipenv run pytest` |
  | `hatch.toml` or `[tool.hatch]` | Hatch | add to the test env in config | `hatch test` or `hatch run test` |
  | `requirements-dev.txt`, `requirements/test.txt` | pip | add a line to that file | `python -m pytest` |
  | only `requirements.txt` | pip | create `requirements-dev.txt` with `-r requirements.txt` and `pytest` | `python -m pytest` |
  | `[project.optional-dependencies]` with `test` or `dev` | pip | add `pytest` to that extra | `python -m pytest` |

- **Layout** — `src/<package>/` or a flat `<package>/`. With a `src/`
  layout, the package must be installed (`pip install -e .`) or the config
  must set `pythonpath = ["src"]`.
- **Existing tests** — `tests/`, `test/`, files named `test_*.py` or
  `*_test.py`, `conftest.py`, and pytest config in `pyproject.toml`
  (`[tool.pytest.ini_options]`), `pytest.ini`, `setup.cfg` or `tox.ini`.
- **Existing style** — plain functions or classes, fixtures in
  `conftest.py`, `unittest.TestCase`, plugins in use (`pytest-mock`,
  `pytest-asyncio`, `pytest-cov`, `hypothesis`, `freezegun`,
  `responses`, `respx`). Copy that style. Do not convert `unittest` tests
  to pytest style; pytest runs them as they are.

Choose the mode:

- No test files → **start mode**.
- Test files exist → **update mode**.
- If the project has tests in another framework only (for example `nose`),
  keep them and add pytest beside them. Do not delete working tests.

Install the dependencies before you run anything, with the project's own
tool. If the install fails because a service or a secret is missing,
continue with the tests that can run, and say so in the report.

## Step 2a — Start mode

1. **Add pytest** as a development dependency with the project's tool (see
   the table). Add a plugin only when the code needs it, for example
   `pytest-asyncio` for `async def` code.
2. **Add the config** to `pyproject.toml` if the file exists, otherwise
   create `pytest.ini`:

   ```toml
   [tool.pytest.ini_options]
   testpaths = ["tests"]
   addopts = "-ra"
   # pythonpath = ["src"]   # only for a src/ layout that is not installed
   ```

3. **Create `tests/`** and mirror the package structure:
   `mypkg/billing/invoice.py` → `tests/billing/test_invoice.py`. Add
   `tests/conftest.py` only for fixtures that more than one test file
   needs.
4. **Choose what to test first.** You cannot test everything in one pass,
   so cover the code where a bug costs the most:
   - Core business logic and pure functions: calculations, parsing,
     validation, state changes.
   - Public functions, classes and API endpoints that other code calls.
   - Error paths: invalid input, empty input, boundaries, missing files.
   - Leave out thin wrappers, generated code and `__main__` glue.
5. Write the tests (see "How to write the tests"), run them, and fix them
   (see "Run and fix").

## Step 2b — Update mode

1. **Find what changed.** Use the first source that gives an answer:
   - The edits made in this conversation.
   - Uncommitted work: `git status --short`, `git diff`, `git diff --staged`.
   - The current branch against the default branch:
     `git diff $(git merge-base HEAD origin/main)...HEAD` (use the real
     default branch name: `main`, `master` or `develop`).
   - The user's description.
2. **Map each changed source file to its tests.** Search the test folder
   for imports and names of the changed functions and classes.
3. **Run the current tests first**, before you edit them. This shows which
   tests the change broke.
4. **Update and add:**
   - A test fails because the behavior changed on purpose → update the
     expected value in the test, and keep the test's intent.
   - New function, branch, parameter or endpoint → add tests for the
     normal case, the edge cases and the error case.
   - Bug fix → add a regression test that fails on the old code and
     passes on the new code.
   - Removed code → remove its tests.
   - Renamed code → rename the test and keep the assertions.

## How to write the tests

- **Test behavior, not implementation.** Assert on return values, raised
  errors, saved data and HTTP responses. Do not assert on private helpers
  or on the order of internal calls unless that order is the contract.
- **One behavior per test**, with a name that says it:
  `test_invoice_total_includes_tax`, `test_parse_rejects_empty_string`.
- **Use `pytest.mark.parametrize`** for the same check over several
  inputs.
- **Use `pytest.raises`** for errors, with `match=` when the message
  matters.
- **Keep tests fast and isolated:**
  - Use `tmp_path` for files and `monkeypatch` for environment variables.
  - Mock the network, external APIs, the clock and randomness. Use the
    project's mocking library if it has one, otherwise `unittest.mock`.
  - Use an in-memory or temporary database when the project supports it.
    If a test needs a real service (Postgres, Redis), mark it with a
    marker the project already uses, such as `@pytest.mark.integration`,
    and register the marker in the config.
- **Use the framework's test tools** when they exist: Django `TestCase`
  or `pytest-django`, Flask `app.test_client()`, FastAPI `TestClient`.
- Do not write tests that only check that a function exists or returns
  something not `None`. Each assertion must fail if the behavior breaks.

## Run and fix

Run pytest with the project's command, for example `uv run pytest -q`.
Then handle each failure:

- **The test is wrong** (bad import, wrong fixture, wrong expected value
  for intended behavior) → fix the test.
- **The code is wrong** (the test describes the intended behavior and the
  code does not do it) → do not weaken the test to make it pass, and do
  not change the source code unless the user asked you to fix bugs. Mark
  the test `@pytest.mark.xfail(reason="...", strict=True)` with a clear
  reason, and list it in the report as a bug found.
- **The environment is missing something** (a service, a secret, a system
  package) → skip with `pytest.mark.skipif` and a reason, and list it in
  the report.

Run the suite again until no unexplained failure remains. If the project
already uses `pytest-cov`, report the coverage of the changed files.

## Step 3 — CI

Look for CI configuration anywhere in the repository. The common files are
listed in `references/ci-platforms.md`, with a snippet for each platform.
Read that file when you find a CI file.

**If no CI file exists**, do not create one. Say in the report that the
project has no CI, and offer to add one. A new pipeline needs decisions
(platform, runners, secrets) that belong to the team.

**If CI files exist**, check whether any job already runs the tests. Count
these as "pytest runs":

- `pytest`, `python -m pytest`, `py.test`, `uv run pytest`,
  `poetry run pytest`, `pdm run pytest`, `hatch test`.
- `tox`, `nox`, `make test`, `just test`, or a script such as
  `scripts/test.sh` — open the target and check that it runs pytest.
- A reusable workflow, template or include — open it and check.

Then act:

- **Pytest already runs** → do not change the CI. Check only that the
  dependencies you added get installed by the CI's install step. If they
  do not, fix the install step.
- **Pytest does not run** → add a test step to the existing pipeline.
  - Put it in the job that already installs the Python dependencies, after
    the install step. If no such job exists, add a new job.
  - Use the same Python version, runner or image, install command and
    trigger rules that the file already uses.
  - Use the project's pytest command from Step 1.
  - Make the minimal edit. Keep the file's comments, order, indentation
    and style.
- **Several pipelines** (for example GitHub Actions and Azure) → add the
  step to each one that builds the Python code.

After the edit, check that the file is still valid YAML (or valid
`Jenkinsfile` structure):

```bash
python -c "import yaml,sys; yaml.safe_load(open(sys.argv[1]))" path/to/file.yml
```

Do not commit, push, or trigger a pipeline. The user reviews the changes.

## Report

End with a short report in plain sentences, in this order:

1. **Mode** — start or update, and the tool and layout you found.
2. **Tests** — the files you added or changed, and what they cover.
3. **Result** — the pytest summary line (for example "42 passed, 1
   xfailed"), and each bug or skipped test with its reason.
4. **CI** — what you found and what you changed (file path and step
   name), or "pytest already runs in CI", or "no CI file found".