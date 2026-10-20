# Changelog

All notable changes to this project are recorded in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

<!-- changelog-skill: last-documented-commit cbf253e51d3c890daa405a004915ed059345dab4 -->

## [Unreleased]

### Added

- `@actuator` decorator that publishes the decorated function to `POST /actuators` when you call the function.
- The decorated function returns `True` when the server accepts the actuator and `False` when the request fails.
- `load_actuator` function that downloads the latest version of an actuator from `GET /actuators/{name}/latest`.
- `load_actuator` installs the requirements of each actuator in a separate virtual environment.
- `load_actuator` replaces a local actuator only when the `id` or `version` on the server is different.
- `update_actuator` argument of `load_actuator` that controls the version check for a local actuator.
- `load_actuator` rejects a `name` that points outside of `actuators_dir`.
- `run_actuator` function that runs a local actuator with the input data and returns its output.
- `run_actuator` downloads a missing actuator first, unless `try_load_actuator` is `False`.
- `Actuator` class that loads an actuator one time and runs it many times with `run`.
- `Actuator.arun` method that runs the actuator without a block on the `asyncio` event loop.
- `dst` argument that sends the actuator output to `POST {dst}/data`.
- `dst_headers` and `dst_timeout` arguments for the requests to `dst`.
- `dst_save_original` argument, `True` by default, that also sends the input data to `POST {dst}/content` in the background.
- `data_specs` argument that sends extra information about the input data to `POST {dst}/data`.
- `NEXGEN_BASE_URL` environment variable for the API root, with `http://localhost:8000/api/v1` as the default.
- `NEXGEN_API_KEY` environment variable that the client sends in the `X-API-KEY` header.
- `NEXGEN_TIMEOUT` environment variable for the timeout of the `@actuator` request, with 60 seconds as the default.
- User documentation in `README.md` and `docs/`, with a quickstart, an API reference and a security guide.

[unreleased]: https://github.com/iamalreadynoob/nexgen/commits/main
