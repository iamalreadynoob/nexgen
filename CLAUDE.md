# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

`nexgenpy` is a Python (>=3.12) client library for a separate Nexgen API server ("Post Shannon Communication for every day systems"). The server is not in this repo. There is no README yet; `pyproject.toml` references a `README.md` that does not exist.

## Commands

Dependencies are managed with `uv` (`uv.lock`). `requirements.txt` mirrors the pinned versions.

```bash
uv sync                          # create .venv and install deps
uv run pytest                    # run tests (tests/)
uv run pytest -m "not integration"  # skip the tests that build real venvs
uv run ruff check .              # lint (strict rule set, see pyproject.toml)
uv run ruff check --fix .        # autofix
uv run ruff format .             # format
uv run pre-commit run --all-files  # yaml/toml/json checks, private-key detection, ruff
uv run python -m build           # build sdist + wheel into dist/
```

Built artifacts in `dist/` are committed to git, so rebuild them when releasing a version.

## Architecture

The library is about **actuators**: single Python functions whose source code is stored on the Nexgen server and later downloaded and run on client machines. Actuators have a type of `"coding"` or `"decoding"`.

- **`nexgenpy/actuators.py`: publishing.** The `@actuator(name, atype, version, is_latest, requirements)` decorator gets the decorated function's source (`inspect.getsource`), its signature and its type hints. It then sends `POST {NEXGEN_BASE_URL}/actuators` with `method`, `method_args`, `requirements`, `set_latest`, and related fields. Registration goes through the API. An earlier version wrote directly to the DB through a now-deleted `nexconf.py`.
- **`nexgenpy/manager.py`: consuming.**
  - `load_actuator` calls `GET {NEXGEN_BASE_URL}/actuators/{name}/latest` and writes the result to `{actuators_dir}/{name}/`. The directory gets `card.json` (metadata including the server `id`), `method.py` (the source) and `requirements.txt`. It then creates a per-actuator `.venv` there and pip-installs the requirements.
  - `run_actuator` imports `method.py` with `importlib`. The file must define **exactly one** top-level function. It calls that function with `**data`. If `dst` is given, it also sends `POST {dst}/data` with `{actuator_id, metadata: output}`.
  - The default `actuators_dir` is `nexgen_actuators`, relative to the working directory.

Environment variables:
- `NEXGEN_BASE_URL`: API root. The decorator and `load_actuator` fall back to `http://localhost:8000/api/v1`.
- `NEXGEN_API_KEY`: sent as the `X-API-KEY` header when set.
- `NEXGEN_TIMEOUT`: decorator request timeout (default 60).

## Conventions

- Ruff enforces a broad rule set, including `ANN` (annotations required), `D` (Google docstrings), `S` (bandit) and `T20` (no `print`; use the module-level `logger`). Line length is 88. Ruff skips `__init__.py`.
- Docstrings start with a Markdown-style heading line, e.g. `"""# Load Actuator.`, followed by Google-style `Args:`/`Returns:`.
- Public functions check every argument's type up front with the pattern `if isinstance(x, T) is False: logger.error(msg); raise ValueError(msg)`. Follow this pattern in new public functions.
- Commit messages loosely follow conventional commits (`feat: ...`).
