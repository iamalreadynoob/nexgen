# API: `run_actuator` and `Actuator`

```python
from nexgenpy import Actuator, run_actuator
```

Use `run_actuator` for one call. Use the `Actuator` class for many calls, for parallel calls, or in `async` code.

Both run the actuator function in a separate process, with the Python of `{actuators_dir}/{name}/.venv`. `run_actuator` starts a new process for each call. The `Actuator` class starts its worker processes one time, and each worker imports `method.py` one time.

## `run_actuator`

### Signature

```python
def run_actuator(
    name: str,
    data: Dict[str, Any],
    data_specs: Dict[str, Any] | None = None,
    actuators_dir: str = "nexgen_actuators",
    dst: str | None = None,
    dst_timeout: int = 60,
    dst_headers: Dict[str, Any] | None = None,
    dst_save_original: bool = True,
    try_load_actuator: bool = True,
) -> object
```

Runs a local actuator with `data`. If `dst` is given, it also sends the output to the `dst` server.

### Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `name` | `str` | required | The name of the actuator. |
| `data` | `Dict[str, Any]` | required | The input of the actuator. The function gets it as `**data`. Each value must be an object that `pickle` can serialize. |
| `data_specs` | `Dict[str, Any]` or `None` | `None` | Free-form information about the data. It goes to the `specs` field of the data item. |
| `actuators_dir` | `str` | `"nexgen_actuators"` | The directory for the local actuators. |
| `dst` | `str` or `None` | `None` | The root URL of the server that stores the output, for example `http://localhost:8000/api/v1`. If `None`, the function sends nothing. |
| `dst_timeout` | `int` | `60` | The timeout in seconds for each `dst` request. |
| `dst_headers` | `Dict[str, Any]` or `None` | `None` | The headers for each `dst` request, for example `{"X-API-Key": "..."}`. |
| `dst_save_original` | `bool` | `True` | If `True` and `dst` is given, the function also sends `data` as a content item. |
| `try_load_actuator` | `bool` | `True` | If `True` and the actuator is not local, the function calls `load_actuator` first. If `False`, it raises `ValueError`. |

### Returns

The return value of the actuator function. The value comes back from the actuator process through `pickle`.

### Steps

1. Check the arguments.
2. If `{actuators_dir}/{name}` does not exist, call `load_actuator(name, actuators_dir)` or raise `ValueError`.
3. Import `{actuators_dir}/{name}/method.py` in the current process.
4. Find the one function in `method.py`.
5. Start a new process with the Python of `{actuators_dir}/{name}/.venv`. This process imports `method.py` and calls the function with `**data`.
6. Log the `print()` output of the function at the `INFO` level.
7. If `dst` is `None`, return the output.
8. Read `id` from `card.json`.
9. If `dst_save_original` is `True`, make a random UUID. Send the content item in a background thread.
10. Send the data item.
11. Return the output.

Step 3 runs the module-level code of `method.py` in the current process. For a `method.py` from the `@actuator` decorator, this code is only the `def` statement, with its default values and type hints. The function body runs only in the `.venv` process.

`run_actuator` does not update a local actuator that exists. To get a new version, call `load_actuator` first.

### Raises

| Exception | Condition |
|---|---|
| `ValueError` | An argument has a wrong type. |
| `ValueError` | The actuator is not local and `try_load_actuator` is `False`. |
| `ValueError` | `method.py` does not define exactly one function. |
| `ImportError` | Python cannot load `method.py`. |
| `FileNotFoundError` | `{actuators_dir}/{name}/.venv` has no Python interpreter. |
| `RuntimeError` | The actuator function raises an exception. The message contains the traceback of that exception. |
| `RuntimeError` | `pickle` cannot serialize the output of the function. |
| `RuntimeError` | The actuator process stops before it writes the output. The message contains the stderr output of the process. |
| The exception of `pickle` | `pickle` cannot serialize a value in `data`, for example a `lambda`. |
| `ModuleNotFoundError` | The current process cannot import the class of the output. See [Writing actuators](../writing-actuators.md#5-return-a-json-compatible-value). |
| `requests.RequestException` | `POST {dst}/data` cannot connect or times out. |

`run_actuator` can also raise the exceptions of [`load_actuator`](load-actuator.md#raises) when it loads the actuator.

If `POST {dst}/data` returns a status that is not 2xx, the function logs a warning and returns the output. It does not raise.

### Requests

The requests go only to `dst`. They use `dst_headers`, not `NEXGEN_API_KEY`.

`POST {dst}/data`:

```json
{
    "actuator_id": "<id from card.json>",
    "metadata": "<output of the actuator>",
    "linked_resource": "<UUID, or null if dst_save_original is False>",
    "specs": "<data_specs, or null>"
}
```

`POST {dst}/contents`, only if `dst_save_original` is `True`:

```json
{
    "identifier": "<the same UUID as linked_resource>",
    "specs": "<data>"
}
```

The content request runs in a background thread. The function does not wait for it. If the request fails, the thread logs a warning.

### Examples

Run an actuator locally:

```python
from nexgenpy import run_actuator

output = run_actuator(name="keyword-extractor", data={"text": "rain in the north"})
```

Run an actuator and store the output and the original input:

```python
import os

output = run_actuator(
    name="keyword-extractor",
    data={"text": "rain in the north"},
    data_specs={"language": "en", "source": "sensor-12"},
    dst=os.environ["NEXGEN_BASE_URL"],
    dst_headers={"X-API-Key": os.environ["NEXGEN_API_KEY"]},
)
```

Run an actuator only if it is already local:

```python
output = run_actuator(
    name="keyword-extractor",
    data={"text": "rain in the north"},
    try_load_actuator=False,
)
```

## `Actuator`

### Constructor

```python
class Actuator:
    def __init__(
        self,
        name: str,
        actuators_dir: str = "nexgen_actuators",
        dst: str | None = None,
        dst_timeout: int = 60,
        dst_headers: Dict[str, Any] | None = None,
        dst_save_original: bool = True,
        try_load_actuator: bool = True,
        workers: int = 1,
    ) -> None
```

The first seven parameters have the same meaning as in [`run_actuator`](#parameters).

| Parameter | Type | Default | Description |
|---|---|---|---|
| `workers` | `int` | `1` | The number of worker processes. Each worker does one run at a time. Thus `workers` is the number of runs that can occur at the same time. It must be 1 or more. |

The constructor does these steps:

1. Check the arguments.
2. If `{actuators_dir}/{name}` does not exist, call `load_actuator(name, actuators_dir)` or raise `ValueError`.
3. Read `method.py` with `ast` and find the one function. The constructor does not import `method.py` in the current process.
4. If `dst` is given, read `id` from `card.json`.
5. Start `workers` processes with the Python of `{actuators_dir}/{name}/.venv`. Each process imports `method.py` one time.
6. Wait until each process is ready.

If a step fails, the constructor stops the workers that it started. Then it raises the exception.

| Exception | Condition |
|---|---|
| `ValueError` | An argument has a wrong type, or `workers` is less than 1. |
| `ValueError` | The actuator is not local and `try_load_actuator` is `False`. |
| `ValueError` | `method.py` does not define exactly one top-level function. |
| `FileNotFoundError` | `{actuators_dir}/{name}/.venv` has no Python interpreter. |
| `RuntimeError` | A worker cannot import `method.py`, or a worker stops before it is ready. |

The constructor can also raise the exceptions of [`load_actuator`](load-actuator.md#raises) when it loads the actuator.

### Attributes

| Attribute | Type | Description |
|---|---|---|
| `name` | `str` | The name of the actuator. |
| `actuators_dir` | `str` | The directory for the local actuators. |
| `dst` | `str` or `None` | The root URL of the `dst` server. |
| `dst_timeout` | `int` | The timeout for each `dst` request. |
| `dst_headers` | `Dict[str, Any]` | The headers for each `dst` request. `{}` if `None` was given. |
| `dst_save_original` | `bool` | If `True`, each run also sends a content item. |
| `actuator_id` | `str` or `None` | The server `id` of the actuator. `None` if `dst` is `None`. |
| `method_name` | `str` | The name of the function in `method.py`. |
| `workers` | `int` | The number of worker processes. |

### `run`

```python
def run(
    self,
    data: Dict[str, Any],
    data_specs: Dict[str, Any] | None = None,
) -> object
```

Sends `data` to a free worker. The worker calls the function with `**data`. If all workers are busy, `run` waits until one worker is free. Then `run` does steps 7 to 11 of [`run_actuator`](#steps). It returns the output.

You can call `run` from many threads at the same time. Each worker does one call at a time. The other calls wait for a free worker.

| Exception | Condition |
|---|---|
| `ValueError` | `data` or `data_specs` has a wrong type. |
| `RuntimeError` | The `Actuator` is closed. |
| `RuntimeError` | The actuator function raises an exception. The message contains the traceback of that exception. The worker continues to run. |
| `RuntimeError` | `pickle` cannot serialize the output of the function. |
| `RuntimeError` | The worker stops during the run. The message contains the last 20 lines of its stderr output. The `Actuator` starts a new worker in its place. |
| The exception of `pickle` | `pickle` cannot serialize a value in `data`, for example a `lambda`. |
| `ModuleNotFoundError` | The current process cannot import the class of the output. |
| `requests.RequestException` | `POST {dst}/data` cannot connect or times out. |

### `arun`

```python
async def arun(
    self,
    data: Dict[str, Any],
    data_specs: Dict[str, Any] | None = None,
) -> object
```

The `async` version of `run`. It waits for the worker in a separate thread with `asyncio.to_thread`. It sends `POST {dst}/data` in the same way. Thus the event loop can do other work. The content upload uses a background thread, as in `run`.

`arun` raises the same exceptions as `run`.

### `close`

```python
def close(self) -> None
```

Stops the worker processes. Each worker gets 5 seconds to stop. After 5 seconds, `close` kills the worker.

You can call `close` more than one time. After `close`, `run` and `arun` raise `RuntimeError`.

Python also calls `close` when the garbage collector frees the `Actuator` object, or when the program exits.

### The `with` statement

`Actuator` supports the `with` statement. The `with` block calls `close` at the end:

```python
with Actuator(name="keyword-extractor") as extractor:
    output = extractor.run(data={"text": "rain in the north"})
```

### Examples

Run an actuator many times:

```python
from nexgenpy import Actuator

with Actuator(name="keyword-extractor") as extractor:
    for sentence in ["rain in the north", "sun in the south"]:
        print(extractor.run(data={"text": sentence}))
```

Run an actuator in `async` code, with two runs at the same time:

```python
import asyncio

from nexgenpy import Actuator


async def main() -> None:
    with Actuator(name="keyword-extractor", workers=2) as extractor:
        outputs = await asyncio.gather(
            extractor.arun(data={"text": "rain in the north"}),
            extractor.arun(data={"text": "sun in the south"}),
        )
    print(outputs)


asyncio.run(main())
```

With `workers=2`, the two runs occur at the same time. With `workers=1`, the second run waits for the first run.

The constructor blocks the event loop while it starts the workers. If the actuator is not local, the constructor also downloads it and runs pip. Call `load_actuator` before the event loop starts.

### Notes

- Each worker keeps the function that it imported. Before you call `load_actuator` for a new version, close the `Actuator`. `load_actuator` deletes the directory with the `.venv` that the workers use. Then make a new `Actuator` object.
- Each worker is a separate process. Two workers do not share variables.
- The function runs with the Python of `.venv`. See [Architecture](../architecture.md#the-actuator-environment).

## See also

- [`load_actuator`](load-actuator.md)
- [Writing actuators](../writing-actuators.md)
- [Configuration](../configuration.md)
- [Concepts: data and content items](../concepts.md#data-and-content-items)
