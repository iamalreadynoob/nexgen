# Development

This document is for contributors to `nexgenpy`.

## Project layout

```text
nexgen/
├── nexgenpy/
│   ├── __init__.py       # public API
│   ├── actuators.py      # @actuator decorator (register)
│   └── manager.py        # load_actuator, run_actuator, Actuator (load and use)
├── tests/
│   ├── conftest.py       # fake requests.post / requests.get fixtures
│   ├── test_actuators.py
│   └── test_manager.py
├── docs/                 # this documentation
├── dist/                 # built sdist and wheel (committed)
├── .github/workflows/ci.yml
├── .pre-commit-config.yaml
├── .semgrepignore        # paths that Semgrep does not scan
├── pyproject.toml
├── requirements.txt      # mirrors the pinned versions in uv.lock
└── uv.lock
```

## Set up

1. Install [uv](https://github.com/astral-sh/uv).
2. Clone the repository:

   ```bash
   git clone https://github.com/iamalreadynoob/nexgen.git
   cd nexgen
   ```

3. Make the virtual environment and install the dependencies:

   ```bash
   uv sync
   ```

4. Install the pre-commit hooks:

   ```bash
   uv run pre-commit install
   ```

## Commands

| Task | Command |
|---|---|
| Run all tests | `uv run pytest` |
| Run the unit tests only | `uv run pytest -m "not integration"` |
| Run the integration tests only | `uv run pytest -m integration` |
| Lint | `uv run ruff check .` |
| Lint and fix | `uv run ruff check --fix .` |
| Format | `uv run ruff format .` |
| Type check | `uv run pre-commit run mypy --all-files` |
| Run the Semgrep scan | `uv run pre-commit run semgrep --all-files` |
| Scan the full git history for secrets | `uv run pre-commit run gitleaks-history --hook-stage manual --all-files` |
| Run all pre-commit hooks | `uv run pre-commit run --all-files` |
| Build the sdist and the wheel | `uv run python -m build` |

## Tests

The tests do not need a running Nexgen Server. The fixtures in `tests/conftest.py` replace `requests.post` and `requests.get`. They also remove the `NEXGEN_*` environment variables of the host.

The tests with the `integration` marker make real virtual environments and run pip. They are slow.

## Continuous integration

`.github/workflows/ci.yml` runs on each push to `main` and on each pull request.

| Job | Platforms | Python | Steps |
|---|---|---|---|
| Ruff | Ubuntu | default | `ruff check`, `ruff format --check` |
| Semgrep | Ubuntu | default | `pre-commit run semgrep --all-files` |
| Mypy | Ubuntu | default | `pre-commit run mypy --all-files` |
| Gitleaks | Ubuntu | default | `pre-commit run gitleaks-history --hook-stage manual --all-files` |
| Actuators tests | Ubuntu | 3.12, 3.13 | `pytest tests/test_actuators.py` |
| Wrappers tests | Ubuntu | 3.12, 3.13 | `pytest tests/test_wrappers.py` |
| Manager tests | Ubuntu, macOS, Windows | 3.12, 3.13 | `pytest tests/test_manager.py`, unit tests first, then integration tests |

The manager tests run on Windows because `load_actuator` uses a different `pip` path there.

The workflow pins each action to a full commit SHA. A tag can move to a different commit, but a SHA cannot. When you update an action, change the SHA and the version comment together.

## Semgrep

[Semgrep](https://semgrep.dev) analyzes the code without running it, to find security and correctness problems. The `semgrep` hook in `.pre-commit-config.yaml` sets the rulesets: `p/python`, `p/security-audit`, `p/secrets` and `p/github-actions`. The CI job runs the same hook. Thus the rulesets are in one location only.

- Each finding stops the commit and makes the CI job fail.
- Semgrep does not scan `dist/` and `.claude/skills/`. These paths are in `.semgrepignore` and in the `exclude` of the hook. Change the two locations together.
- The hook uses `--jobs=1`. With more jobs, Semgrep can fail with `io_uring_queue_init: Cannot allocate memory` when the memlock limit is 8 MB, the Linux default.

If a finding is an accepted risk, put a `nosemgrep` comment with the rule ID on the line before the code. Tell why in the comment, or refer to a document:

```python
# Accepted risk, see docs/security.md
# nosemgrep: python.lang.security.deserialization.pickle.avoid-pickle
data = pickle.dumps(obj, protocol=4)
```

## Mypy

[Mypy](https://mypy-lang.org) checks the type annotations without running the code. The settings are in `[tool.mypy]` in `pyproject.toml`. The `mypy` hook in `.pre-commit-config.yaml` checks `nexgenpy/` and `tests/`. The CI job runs the same hook.

- Mypy checks `nexgenpy/` in strict mode, with the `pydantic.mypy` plugin.
- Tests do not need annotations. Mypy still checks the bodies of the test functions.
- The hook runs in a separate virtual environment. When the code imports a new third-party package, add the package or its `types-*` stubs to `additional_dependencies` of the hook.

If a finding is a false positive, put a `# type: ignore[<code>]` comment with the error code on that line.

## Gitleaks

[Gitleaks](https://github.com/gitleaks/gitleaks) finds secrets in the code, for example API keys and tokens. `.pre-commit-config.yaml` has two Gitleaks hooks:

| Hook | Stage | What it scans |
|---|---|---|
| `gitleaks` | each commit | the staged changes only, also with `--all-files` |
| `gitleaks-history` | `manual` | all commits in the git history |

The CI job runs `gitleaks-history`. The job clones the full history (`fetch-depth: 0`), because Gitleaks scans each commit.

If a finding is an accepted risk, put a `gitleaks:allow` comment on that line. You can also add the fingerprint of the finding to `.gitleaksignore`. A secret stays in the git history after a new commit changes it. Thus, if a real secret goes into a commit, make the secret unusable (revoke it) and make a new one.

## Code conventions

Ruff enforces a broad rule set. The line length is 88. Ruff does not check `__init__.py`. Some of the rules:

| Rule set | Requirement |
|---|---|
| `ANN` | Add type annotations to each function. |
| `D` | Write Google-style docstrings. |
| `S` | Obey the bandit security checks. |
| `T20` | Do not use `print`. Use the module-level `logger`. |

### Docstrings

Start each docstring with a Markdown-style heading line. Then add the Google-style sections:

```python
def load_actuator(name: str, actuators_dir: str = "nexgen_actuators") -> None:
    """# Load Actuator.

    Args:
        name (str): The name of the actuator.
        actuators_dir (str, optional): Located directory for the actuators.
    """
```

### Argument checks

Check the type of each argument at the start of each public function. Log the error, then raise `ValueError`:

```python
if isinstance(name, str) is False:
    logger.error("name is invalid, it has to be str")
    raise ValueError("name is invalid, it has to be str")
```

### Commit messages

Use the conventional commit style, for example `feat: add arun to Actuator` or `fix: ...`.

## Release

A release puts a new version of `nexgenpy` on [PyPI](https://pypi.org/project/nexgenpy/). Users can then install it with `pip install nexgenpy`.

There are two procedures:

- [Manual release](#manual-release): you build and upload the package from your computer with an API token.
- [Automatic release](#automatic-release-trusted-publishing): GitHub Actions builds and uploads the package when you push a version tag. This procedure does not use a token. We recommend it after the first release.

### Before the first release

Do these steps one time only.

#### 1. Remove the development tools from the runtime dependencies

pip installs each package in `[project] dependencies` on the computer of each user. At the moment, this list contains `build`, `pre-commit` and `ruff`. Users do not need these tools. Move them to the `dev` dependency group:

```toml
[project]
dependencies = [
    "requests>=2.34.2",
]

[dependency-groups]
dev = [
    "build>=1.6.1",
    "pre-commit>=4.6.2",
    "pytest>=9.1.1",
    "ruff>=0.16.10",
]
```

`uv sync` installs the `dev` group by default. Thus the development commands in this document continue to work. Run `uv lock` after this change, and update `requirements.txt`.

#### 2. Add the PyPI metadata

PyPI shows these fields on the project page. Add them to `[project]` in `pyproject.toml`:

```toml
[project]
license = "Apache-2.0"
license-files = ["LICENSE"]
keywords = ["semantic communication", "semcom", "6g", "actuator"]
classifiers = [
    "Development Status :: 4 - Beta",
    "Intended Audience :: Developers",
    "Intended Audience :: Science/Research",
    "Operating System :: OS Independent",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.12",
    "Programming Language :: Python :: 3.13",
    "Topic :: Communications",
]

[project.urls]
Homepage = "https://github.com/iamalreadynoob/nexgen"
Documentation = "https://github.com/iamalreadynoob/nexgen/tree/main/docs"
Issues = "https://github.com/iamalreadynoob/nexgen/issues"
Changelog = "https://github.com/iamalreadynoob/nexgen/blob/main/CHANGELOG.md"
```

The `license = "Apache-2.0"` format needs setuptools 77 or later. Change the build system requirement:

```toml
[build-system]
requires = ["setuptools>=77"]
build-backend = "setuptools.build_meta"
```

#### 3. Make the README links absolute

PyPI uses `README.md` as the project description. PyPI cannot resolve relative links such as `docs/quickstart.md` or `pyproject.toml`. These links do not work on the PyPI page. Change each relative link in `README.md` to a full GitHub URL, for example:

```text
docs/quickstart.md  ->  https://github.com/iamalreadynoob/nexgen/blob/main/docs/quickstart.md
```

#### 4. Make the accounts

1. Make an account on [PyPI](https://pypi.org/account/register/).
2. Make a different account on [TestPyPI](https://test.pypi.org/account/register/). TestPyPI is a separate test index. It does not share accounts with PyPI.
3. Enable two-factor authentication on the two accounts. PyPI does not let you upload without it.

The first upload of `nexgenpy` makes the project on PyPI and makes you its owner. Nobody else can then use the name.

### Manual release

#### 1. Prepare the version

1. Change `version` in `pyproject.toml`. Use [semantic versioning](https://semver.org/): `MAJOR.MINOR.PATCH`.
2. Add the version to `CHANGELOG.md`.
3. Change the version badge in `README.md`.
4. Run the tests and the linter:

   ```bash
   uv run pytest
   uv run ruff check .
   uv run ruff format --check .
   ```

#### 2. Build the package

```bash
uv build
```

This command writes two files to `dist/`. In this example the version is `1.1.0`:

- `nexgenpy-1.1.0.tar.gz`: the source distribution (sdist).
- `nexgenpy-1.1.0-py3-none-any.whl`: the wheel.

Check the metadata and the README rendering:

```bash
uvx twine check dist/nexgenpy-1.1.0*
```

`dist/` also contains the files of the earlier versions, because they are in git. Always give the files of the new version only to the upload commands. Do not use `dist/*`.

#### 3. Upload to TestPyPI

1. On TestPyPI, go to **Account settings > API tokens** and make a token.
2. Upload the package:

   ```bash
   uv publish \
     --publish-url https://test.pypi.org/legacy/ \
     --token pypi-XXXXXXXX \
     dist/nexgenpy-1.1.0*
   ```

3. Install the package from TestPyPI in a new virtual environment and test it:

   ```bash
   cd "$(mktemp -d)"
   uv venv
   uv pip install \
     --index-url https://test.pypi.org/simple/ \
     --extra-index-url https://pypi.org/simple/ \
     --index-strategy unsafe-best-match \
     nexgenpy==1.1.0
   uv run python -c "import nexgenpy; print(nexgenpy.__file__)"
   ```

   The `--extra-index-url` option is necessary because TestPyPI does not have all the dependencies, for example `requests`.

#### 4. Upload to PyPI

1. On PyPI, go to **Account settings > API tokens** and make a token. For the first upload, the token scope must be **Entire account**, because the project does not exist yet. After the first upload, delete this token and make a new token with the scope **Project: nexgenpy**.
2. Upload the package:

   ```bash
   uv publish --token pypi-XXXXXXXX dist/nexgenpy-1.1.0*
   ```

   You can also put the token in the `UV_PUBLISH_TOKEN` environment variable. Then you do not have to type it in the command.

3. Open <https://pypi.org/project/nexgenpy/> and examine the page.

#### 5. Commit and tag

```bash
git add pyproject.toml CHANGELOG.md README.md dist/nexgenpy-1.1.0*
git commit -m "release: 1.1.0"
git tag v1.1.0
git push origin main --tags
```

### Automatic release (trusted publishing)

With [trusted publishing](https://docs.pypi.org/trusted-publishers/), PyPI accepts uploads from one GitHub Actions workflow. You do not keep a token on your computer or in the GitHub secrets.

#### 1. Add the trusted publisher on PyPI

1. On PyPI, go to **Your projects > nexgenpy > Publishing**. Before the first release, go to **Account settings > Publishing** and add a *pending* publisher.
2. Enter these values:

   | Field | Value |
   |---|---|
   | PyPI project name | `nexgenpy` |
   | Owner | `iamalreadynoob` |
   | Repository name | `nexgen` |
   | Workflow name | `publish.yml` |
   | Environment name | `pypi` |

3. On GitHub, go to **Settings > Environments** and make an environment with the name `pypi`. You can add a protection rule, for example a required reviewer.

#### 2. Add the workflow

Make the file `.github/workflows/publish.yml`:

```yaml
name: Publish

on:
  push:
    tags: ["v*"]

jobs:
  publish:
    name: Build and publish to PyPI
    runs-on: ubuntu-latest
    environment: pypi
    permissions:
      contents: read
      id-token: write  # necessary for trusted publishing
    steps:
      - uses: actions/checkout@11d5960a326750d5838078e36cf38b85af677262 # v4.4.0

      - uses: astral-sh/setup-uv@d0cc045d04ccac9d8b7881df0226f9e82c39688e # v6.8.0

      - name: Run tests
        run: |
          uv sync --locked
          uv run pytest -m "not integration"

      - name: Build
        # Use a separate directory, because dist/ contains the earlier versions
        run: uv build --out-dir release-dist

      - name: Publish
        run: uv publish release-dist/*
```

#### 3. Release

1. Do the steps in [Prepare the version](#1-prepare-the-version).
2. Build the package with `uv build` and commit the new files in `dist/`.
3. Push a tag that agrees with the version in `pyproject.toml`:

   ```bash
   git tag v1.1.0
   git push origin main --tags
   ```

The workflow then builds and uploads the package. See the result in the **Actions** tab on GitHub.

### Rules of PyPI

- You cannot upload the same version two times. If a release has an error, increase the version and release again.
- You cannot use a file name again, also after you delete the file.
- Do not delete a bad release. *Yank* it on the PyPI project page. pip then does not install it, except when a user asks for that exact version.
- Do not commit an API token. If a token becomes public, delete it on PyPI immediately.

## Documentation

The documentation is in `README.md` and `docs/`. Add each new document to the table in the [README](../README.md#documentation).

Write the documentation in Simplified Technical English style:

- Use short sentences and the active voice.
- Write one instruction in each sentence.
- Do not use semicolons.
- Use one term for one thing. See the [Glossary](glossary.md).
