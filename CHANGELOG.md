# Changelog

All notable changes to this project are recorded in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

<!-- changelog-skill: last-documented-commit e1db30b22a2b3641288ede453eb6454efe4c506c -->

## [Unreleased]

### Added

- `workers` argument of `Actuator` that sets the number of parallel runs, with `1` as the default.
- `Actuator.close` method that stops the worker processes of the actuator.
- `Actuator` support for the `with` statement, which calls `close` at the end of the block.
- `Actuator` starts a new worker process when a worker process stops during a run.
- `Data` class in `nexgenpy.wrappers` that reads and changes the data items on the server.
- `Data.get_data_list` method that returns a page of data items from `GET /data` as a `DataList`.
- `page`, `limit`, `ascending` and `actuator_id` arguments of `Data.get_data_list` that filter and sort the data items.
- `Data.create_data` method that creates a data item with `POST /data`.
- `Data.get_data` method that returns one data item from `GET /data/{data_id}`.
- `Data.update_data` method that changes a data item with `PUT /data/{data_id}`.
- `Data.delete_data` method that removes a data item with `DELETE /data/{data_id}`.
- `DataOut` and `DataList` models in `nexgenpy.schema` for the data items that the server returns.
- `Data` methods raise `requests.HTTPError` when the server returns an error status.
- `Data` methods reject a `data_id` that is empty, `.` or `..`.

### Changed

- **Breaking:** `run_actuator`, `Actuator.run` and `Actuator.arun` raise `RuntimeError` when the actuator method raises an exception. Catch `RuntimeError` in place of the exceptions of the method.
- **Breaking:** The input data and the output of an actuator must be objects that `pickle` can serialize. Use built-in types, for example `dict`, `list` and `str`, for the data and the output.
- `run_actuator` and `Actuator` raise `FileNotFoundError` when the actuator directory has no `.venv`.
- `run_actuator` and `Actuator` send the `print()` output of the actuator method to the `nexgenpy.manager` logger.
- `nexgenpy` requires `pydantic` 2.13.5 or a later version.

### Removed

- **Breaking:** The `Actuator.method` attribute. Use `Actuator.run` to call the method, or `Actuator.method_name` to get its name.

### Fixed

- `run_actuator` and `Actuator` run the actuator method with the Python interpreter of the actuator `.venv`.

## [1.0.0] - 2026-10-24

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
- `dst_save_original` argument, `True` by default, that also sends the input data to `POST {dst}/contents` in the background.
- `data_specs` argument that sends extra information about the input data to `POST {dst}/data`.
- `NEXGEN_BASE_URL` environment variable for the API root, with `http://localhost:8000/api/v1` as the default.
- `NEXGEN_API_KEY` environment variable that the client sends in the `X-API-KEY` header.
- `NEXGEN_TIMEOUT` environment variable for the timeout of the `@actuator` request, with 60 seconds as the default.
- User documentation in `README.md` and `docs/`, with a quickstart, an API reference and a security guide.

[unreleased]: https://github.com/iamalreadynoob/nexgen/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/iamalreadynoob/nexgen/releases/tag/v1.0.0
