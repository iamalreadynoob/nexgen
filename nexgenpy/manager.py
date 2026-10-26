"""# Manager.

It manages the essential works for the actuators.
"""

import ast
import asyncio
import contextlib
import importlib.util
import inspect
import json
import logging
import os
import pickle
import queue
import shutil
import struct
import subprocess
import sys
import tempfile
import textwrap
import threading
import weakref
from collections import deque
from pathlib import Path
from typing import IO, Any, Dict, List, Self
from uuid import uuid4

import requests

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "http://localhost:8000/api/v1"

_RUNNER = textwrap.dedent(r"""
    import sys, pickle, importlib, traceback
    method_dir, module_name, func_name, in_path, out_path = sys.argv[1:6]
    sys.path.insert(0, method_dir)

    with open(in_path, "rb") as f:
        kwargs = pickle.load(f)

    try:
        func = getattr(importlib.import_module(module_name), func_name)
        payload = pickle.dumps({"ok": True, "result": func(**kwargs)}, protocol=4)
    except Exception:
        payload = pickle.dumps(
            {"ok": False, "error": traceback.format_exc()}, protocol=4,
        )

    with open(out_path, "wb") as f:
        f.write(payload)
""")

_WORKER = textwrap.dedent(r"""
    import importlib, os, pickle, struct, sys, traceback

    # Keep private copies of the real stdin/stdout for the protocol, then point
    # fd 1 at stderr so print() inside the method cannot corrupt the pipe.
    proto_in = os.fdopen(os.dup(0), "rb")
    proto_out = os.fdopen(os.dup(1), "wb")
    os.dup2(2, 1)
    sys.stdin = open(os.devnull)

    def send(obj):
        try:
            data = pickle.dumps(obj, protocol=4)
        except Exception:
            error = {"ok": False, "error": traceback.format_exc()}
            data = pickle.dumps(error, protocol=4)
        proto_out.write(struct.pack(">Q", len(data)) + data)
        proto_out.flush()

    def recv():
        header = proto_in.read(8)
        if len(header) < 8:
            return None                      # host closed the pipe
        return pickle.loads(proto_in.read(struct.unpack(">Q", header)[0]))

    method_dir, module_name, func_name = sys.argv[1:4]
    sys.path.insert(0, method_dir)
    try:
        func = getattr(importlib.import_module(module_name), func_name)
    except Exception:
        send({"ok": False, "error": traceback.format_exc()})   # handshake: failed
        sys.exit(1)
    send({"ok": True})                                          # handshake: ready

    while (kwargs := recv()) is not None:
        try:
            send({"ok": True, "result": func(**kwargs)})
        except Exception:
            send({"ok": False, "error": traceback.format_exc()})
""")


class Actuator:
    """# Actuator.

    It runs the actuator like run_actuator, inside the actuator's own venv. It
    starts the worker processes once, in the constructor, and every worker
    imports method.py once. So the next runs do not import method.py again.
    Call close, or use it as a context manager, to stop the workers.

    Attributes:
        name (str): Name of the actuator.
        actuators_dir (str): Located directory for the actuators.
        dst (str | None): It pushes the data given endpoint if they have an
            nexgen compatible endpoint.
        dst_timeout (int): Timeout for the sending destination endpoint.
        dst_headers (Dict[str, Any]): Required headers for the destination
            endpoint.
        dst_save_original (bool): It saves the original data too with lazy upload.
        actuator_id (str | None): The server id of the actuator. It is None if dst
            is None.
        method_name (str): Name of the function inside method.py.
        workers (int): Number of worker processes, so the number of runs that
            can execute at the same time.
    """

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
    ) -> None:
        # Checking The Datatypes
        if isinstance(name, str) is False:
            logger.error("name is invalid, it has to be str")
            raise ValueError("name is invalid, it has to be str")

        if isinstance(actuators_dir, str) is False:
            logger.error("actuators_dir is invalid, it has to be str")
            raise ValueError("actuators_dir is invalid, it has to be str")

        if dst is not None and isinstance(dst, str) is False:
            logger.error("dst is invalid, it has to be str")
            raise ValueError("dst is invalid, it has to be str")

        if isinstance(dst_timeout, int) is False:
            logger.error("dst_timeout is invalid, it has to be int")
            raise ValueError("dst_timeout is invalid, it has to be int")

        if dst_headers is not None and isinstance(dst_headers, dict) is False:
            logger.error("dst_headers is invalid, it has to be Dict[str, Any]")
            raise ValueError("dst_headers is invalid, it has to be Dict[str, Any]")

        if isinstance(dst_save_original, bool) is False:
            logger.error("dst_save_original is invalid, it has to be bool")
            raise ValueError("dst_save_original is invalid, it has to be bool")

        if isinstance(try_load_actuator, bool) is False:
            logger.error("try_load_actuator is invalid, it has to be bool")
            raise ValueError("try_load_actuator is invalid, it has to be bool")

        if isinstance(workers, int) is False or workers < 1:
            logger.error("workers is invalid, it has to be a positive int")
            raise ValueError("workers is invalid, it has to be a positive int")

        if Path(f"{actuators_dir}/{name}").exists() is False:
            logger.warning(f"Actuator: {name} does not exist")
            if try_load_actuator is False:
                logger.error(f"Actuator {name} has to be downloaded first")
                raise ValueError(f"Actuator {name} has to be downloaded first")
            else:
                load_actuator(
                    name=name,
                    actuators_dir=actuators_dir,
                )

        actuator_dir = Path(f"{actuators_dir}/{name}").resolve()
        method_name = _method_name(actuator_dir / "method.py")

        actuator_id = None
        if dst is not None:
            with open(f"{actuators_dir}/{name}/card.json", "r") as f:
                actuator_id = json.load(f)["id"]

        python = _venv_python(actuator_dir / ".venv")

        self.name = name
        self.actuators_dir = actuators_dir
        self.dst = dst
        self.dst_timeout = dst_timeout
        self.dst_headers = dst_headers if dst_headers is not None else {}
        self.dst_save_original = dst_save_original
        self.actuator_id = actuator_id
        self.method_name = method_name
        self.workers = workers

        self._python = python
        self._actuator_dir = actuator_dir
        self._pool: List[_Worker] = []
        self._idle: queue.Queue[_Worker] = queue.Queue()
        # It gets the pool, not self, so it also runs on garbage collection
        self._finalizer = weakref.finalize(self, _close_all, self._pool)

        # Start every process first, so they import method.py at the same time
        try:
            for _ in range(workers):
                self._pool.append(_Worker(python, actuator_dir, method_name))
            for worker in self._pool:
                worker.handshake()
        except Exception:
            self.close()
            raise

        for worker in self._pool:
            self._idle.put(worker)

    def __enter__(self) -> Self:
        """# Enter.

        Returns:
            Self: The actuator itself.
        """
        return self

    def __exit__(self, *exc_info: object) -> None:
        """# Exit.

        It closes the actuator.
        """
        self.close()

    def close(self) -> None:
        """# Close.

        It stops the worker processes. It is safe to call it more than once. It
        also runs when the actuator is garbage collected or when Python exits.
        """
        self._finalizer()

    def _call(self, data: Dict[str, Any]) -> object:
        """# Call.

        It runs the method on a free worker. It waits until a worker is free.

        Args:
            data (Dict[str, Any]): Input data for the actuator.

        Returns:
            object: The output coming from the method.

        Raises:
            RuntimeError: If the actuator is closed, the method raises an error
                or the worker crashes.
        """
        if self._finalizer.alive is False:
            logger.error("Actuator is closed")
            raise RuntimeError("Actuator is closed")

        worker = self._idle.get()
        try:
            return worker.call(data)
        finally:
            # A crashed worker is replaced, so the pool keeps its size
            if worker.alive is False and self._finalizer.alive is True:
                worker = self._replace(worker)
            self._idle.put(worker)

    def _replace(self, dead: "_Worker") -> "_Worker":
        """# Replace.

        It starts a new worker in place of a stopped one. If the new worker
        cannot start, it logs the error and the next call tries again.

        Args:
            dead (_Worker): The stopped worker.

        Returns:
            _Worker: The new worker, or the stopped one if no process started.
        """
        self._pool.remove(dead)
        try:
            worker = _Worker(self._python, self._actuator_dir, self.method_name)
        except OSError:
            logger.exception("Actuator %s could not restart a worker", self.name)
            return dead

        self._pool.append(worker)
        with contextlib.suppress(RuntimeError):
            # handshake already logged the error, the next call raises it
            worker.handshake()
        return worker

    def run(
        self,
        data: Dict[str, Any],
        data_specs: Dict[str, Any] | None = None,
    ) -> object:
        """# Run.

        It runs the loaded method with the data. If dst is given, it also sends
        the output to the destination endpoint.

        Args:
            data (Dict[str, Any]): Input data for the actuator.
            data_specs (Dict[str, Any] | None, optional): Contains the extra
                information about the data.

        Returns:
            object: The output coming from actuator.

        Raises:
            ValueError: If data or data_specs is invalid.
            RuntimeError: If the actuator is closed, the method raises an error
                or the worker crashes.
        """
        # Checking The Datatypes
        if isinstance(data, dict) is False:
            logger.error("data is invalid, it has to be Dict[str, Any]")
            raise ValueError("data is invalid, it has to be Dict[str, Any]")

        if data_specs is not None and isinstance(data_specs, dict) is False:
            logger.error("data_specs is invalid, it has to be Dict[str, Any]")
            raise ValueError("data_specs is invalid, it has to be Dict[str, Any]")

        output = self._call(data)

        if self.dst is None:
            return output

        linked_resource: str | None = None
        if self.dst_save_original is True:
            linked_resource = str(uuid4())

            # Lazy upload, so the main process does not wait for it
            threading.Thread(
                target=_send_content,
                kwargs={
                    "url": f"{self.dst}/contents",
                    "headers": self.dst_headers,
                    "timeout": self.dst_timeout,
                    "identifier": linked_resource,
                    "specs": data,
                },
            ).start()

        result = requests.post(
            url=f"{self.dst}/data",
            headers=self.dst_headers,
            json={
                "actuator_id": self.actuator_id,
                "metadata": output,
                "linked_resource": linked_resource,
                "specs": data_specs,
            },
            timeout=self.dst_timeout,
        )

        if result.ok is True:
            logger.info(
                "POST /data succeeded: status=%d, response=%s",
                result.status_code,
                result.text,
            )
        else:
            logger.warning(
                "POST /data failed: status=%d, response=%s",
                result.status_code,
                result.text,
            )

        return output

    async def arun(
        self,
        data: Dict[str, Any],
        data_specs: Dict[str, Any] | None = None,
    ) -> object:
        """# Async Run.

        It is the async version of run. It runs the loaded method and the POST
        /data request in a worker thread, so they do not block the event loop.

        Args:
            data (Dict[str, Any]): Input data for the actuator.
            data_specs (Dict[str, Any] | None, optional): Contains the extra
                information about the data.

        Returns:
            object: The output coming from actuator.

        Raises:
            ValueError: If data or data_specs is invalid.
            RuntimeError: If the actuator is closed, the method raises an error
                or the worker crashes.
        """
        # Checking The Datatypes
        if isinstance(data, dict) is False:
            logger.error("data is invalid, it has to be Dict[str, Any]")
            raise ValueError("data is invalid, it has to be Dict[str, Any]")

        if data_specs is not None and isinstance(data_specs, dict) is False:
            logger.error("data_specs is invalid, it has to be Dict[str, Any]")
            raise ValueError("data_specs is invalid, it has to be Dict[str, Any]")

        output = await asyncio.to_thread(self._call, data)

        if self.dst is None:
            return output

        linked_resource: str | None = None
        if self.dst_save_original is True:
            linked_resource = str(uuid4())

            # Lazy upload, so the main process does not wait for it
            threading.Thread(
                target=_send_content,
                kwargs={
                    "url": f"{self.dst}/contents",
                    "headers": self.dst_headers,
                    "timeout": self.dst_timeout,
                    "identifier": linked_resource,
                    "specs": data,
                },
            ).start()

        result = await asyncio.to_thread(
            requests.post,
            url=f"{self.dst}/data",
            headers=self.dst_headers,
            json={
                "actuator_id": self.actuator_id,
                "metadata": output,
                "linked_resource": linked_resource,
                "specs": data_specs,
            },
            timeout=self.dst_timeout,
        )

        if result.ok is True:
            logger.info(
                "POST /data succeeded: status=%d, response=%s",
                result.status_code,
                result.text,
            )
        else:
            logger.warning(
                "POST /data failed: status=%d, response=%s",
                result.status_code,
                result.text,
            )

        return output


def _send_content(
    url: str,
    headers: Dict[str, Any],
    timeout: int,
    identifier: str,
    specs: Dict[str, Any],
) -> None:
    """# Send Content.

    It sends the original data to the content endpoint. It runs in a background
    thread, so it logs the errors and does not raise them.

    Args:
        url (str): The content endpoint.
        headers (Dict[str, Any]): Headers for the content endpoint.
        timeout (int): Timeout for the content endpoint.
        identifier (str): The linked resource of the data.
        specs (Dict[str, Any]): The original data.
    """
    try:
        result = requests.post(
            url=url,
            headers=headers,
            json={
                "identifier": identifier,
                "specs": specs,
            },
            timeout=timeout,
        )
    except requests.RequestException as e:
        logger.warning("POST /contents failed: %s", e)
        return

    if result.ok is True:
        logger.info(
            "POST /contents succeeded: status=%d, response=%s",
            result.status_code,
            result.text,
        )
    else:
        logger.warning(
            "POST /contents failed: status=%d, response=%s",
            result.status_code,
            result.text,
        )


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
) -> object:
    """# Run Actuator.

    It basically runs the actuator. It raises error if actuator is not seen.

    Args:
        name (str): Name of the actuator.
        data (Dict[str, Any]): Input data for the actuator.
        data_specs (Dict[str, Any] | None): Contains the extra information about the
            data.
        actuators_dir (str, optional): Located directory for the actuators.
        dst (str | None, optional): It pushes the data given endpoint if they have an
            nexgen compatible endpoint.
        dst_timeout (int, optional): Timeout for the sending destination endpoint.
        dst_headers (Dict[str, Any] | None, optional): Required headers for the
            destination endpoint, if needed.
        dst_save_original (bool): It saves the original data too with lazy upload.
        try_load_actuator (bool, optional): It tries to download the actuator first
            if it is does not exist locally.

    Returns:
        object: The output coming from actuator.
    """
    # Checking The Datatype
    if isinstance(name, str) is False:
        logger.error("name is invalid, it has to be str")
        raise ValueError("name is invalid, it has to be str")

    if isinstance(data, dict) is False:
        logger.error("data is invalid, it has to be Dict[str, Any]")
        raise ValueError("data is invalid, it has to be Dict[str, Any]")

    if data_specs is not None and isinstance(data_specs, dict) is False:
        logger.error("data_specs is invalid, it has to be Dict[str, Any]")
        raise ValueError("data_specs is invalid, it has to be Dict[str, Any]")

    if isinstance(actuators_dir, str) is False:
        logger.error("actuators_dir is invalid, it has to be str")
        raise ValueError("actuators_dir is invalid, it has to be str")

    if dst is not None and isinstance(dst, str) is False:
        logger.error("dst is invalid, it has to be str")
        raise ValueError("dst is invalid, it has to be str")

    if isinstance(dst_timeout, int) is False:
        logger.error("dst_timeout is invalid, it has to be int")
        raise ValueError("dst_timeout is invalid, it has to be int")

    if dst_headers is not None and isinstance(dst_headers, dict) is False:
        logger.error("dst_headers is invalid, it has to be Dict[str, Any]")
        raise ValueError("dst_headers is invalid, it has to be Dict[str, Any]")

    if isinstance(dst_save_original, bool) is False:
        logger.error("dst_save_original is invalid, it has to be bool")
        raise ValueError("dst_save_original is invalid, it has to be bool")

    if isinstance(try_load_actuator, bool) is False:
        logger.error("try_load_actuator is invalid, it has to be bool")
        raise ValueError("try_load_actuator is invalid, it has to be bool")

    if Path(f"{actuators_dir}/{name}").exists() is False:
        logger.warning(f"Actuator: {name} does not exist")
        if try_load_actuator is False:
            logger.error(f"Actuator {name} has to be downloaded first")
            raise ValueError(f"Actuator {name} has to be downloaded first")
        else:
            load_actuator(
                name=name,
                actuators_dir=actuators_dir,
            )

    actuator_dir = Path(f"{actuators_dir}/{name}").resolve()
    file_path = actuator_dir / "method.py"

    spec = importlib.util.spec_from_file_location(
        file_path.stem,
        file_path,
    )

    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load module: {file_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    # Find functions defined in this file
    methods = [
        obj
        for _, obj in inspect.getmembers(module, inspect.isfunction)
        if obj.__module__ == module.__name__
    ]

    if len(methods) != 1:
        raise ValueError(
            f"Expected exactly one function, found {len(methods)}",
        )

    method = methods[0]
    method_name: str = method.__name__
    output = _run(
        actuator_dir=actuator_dir,
        fn_args=data,
        method_name=method_name,
    )

    if dst is None:
        return output

    if dst_headers is None:
        dst_headers = {}

    with open(f"{actuators_dir}/{name}/card.json", "r") as f:
        actuator_id = json.load(f)["id"]

    linked_resource: str | None = None
    if dst_save_original is True:
        linked_resource = str(uuid4())

        # Lazy upload, so the main process does not wait for it
        threading.Thread(
            target=_send_content,
            kwargs={
                "url": f"{dst}/contents",
                "headers": dst_headers,
                "timeout": dst_timeout,
                "identifier": linked_resource,
                "specs": data,
            },
        ).start()

    result = requests.post(
        url=f"{dst}/data",
        headers=dst_headers,
        json={
            "actuator_id": actuator_id,
            "metadata": output,
            "linked_resource": linked_resource,
            "specs": data_specs,
        },
        timeout=dst_timeout,
    )

    if result.ok is True:
        logger.info(
            "POST /data succeeded: status=%d, response=%s",
            result.status_code,
            result.text,
        )
    else:
        logger.warning(
            "POST /data failed: status=%d, response=%s",
            result.status_code,
            result.text,
        )

    return output


def load_actuator(
    name: str,
    actuators_dir: str = "nexgen_actuators",
    load_timeout: int = 60,
    update_actuator: bool = True,
) -> None:
    """# Load Actuator.

    Args:
        name (str): The name of the actuator.
        actuators_dir (str, optional): Located directory for the actuators.
        load_timeout (int, optional): The timeout for the loading the actuator.
        update_actuator (bool, optional): If it is true, even though the actuator exists
            it checks that the latest version is changed and if it is changed then
            override the existing actuator.
    """
    # Checking The Datatypes
    if isinstance(name, str) is False:
        logger.error("name is invalid, it has to be str")
        raise ValueError("name is invalid, it has to be str")

    if isinstance(actuators_dir, str) is False:
        logger.error("actuators_dir is invalid, it has to be str")
        raise ValueError("actuators_dir is invalid, it has to be str")

    if isinstance(load_timeout, int) is False:
        logger.error("load_timeout is invalid, it has to be int")
        raise ValueError("load_timeout is invalid, it has to be int")

    if isinstance(update_actuator, bool) is False:
        logger.error("update_actuator is invalid, it has to be bool")
        raise ValueError("update_actuator is invalid, it has to be bool")

    # The name has to point to a directory directly inside actuators_dir
    actuators_path = Path(actuators_dir).resolve()
    if (actuators_path / name).resolve().parent != actuators_path:
        logger.error("name is invalid, it has to be a plain directory name")
        raise ValueError("name is invalid, it has to be a plain directory name")

    if update_actuator is False and Path(f"{actuators_dir}/{name}").exists() is True:
        logger.info(f"Actuator {name} already exists")
        return

    headers = {}
    if os.getenv("NEXGEN_API_KEY") is not None:
        headers["X-API-KEY"] = os.getenv("NEXGEN_API_KEY")

    result = requests.get(
        f"{os.getenv('NEXGEN_BASE_URL', DEFAULT_BASE_URL)}/actuators/{name}/latest",
        headers=headers,
        timeout=load_timeout,
    )

    result.raise_for_status()

    logger.info(
        "GET /actuators/actuator_name/latest succeeded: status=%d, response=%s",
        result.status_code,
        result.text,
    )

    response = result.json()

    card_path = Path(f"{actuators_dir}/{name}/card.json")
    if card_path.exists() is True:
        with open(card_path, "r") as f:
            existing_card = json.load(f)

        if (
            existing_card.get("id") == response["_id"]
            and existing_card.get("version") == response["version"]
        ):
            logger.info(f"Actuator {name} is already up to date")
            return

    if Path(f"{actuators_dir}/{name}").exists():
        logger.info("Existing directory has been found")
        shutil.rmtree(f"{actuators_dir}/{name}")
        logger.info("Existing directory deleted")

    os.makedirs(f"{actuators_dir}/{name}")
    logger.info(f"New directory has been created: {actuators_dir}/{name}")

    card = {
        "id": response["_id"],
        "name": response["name"],
        "version": response["version"],
        "actuator_type": response["actuator_type"],
        "method_args": response["method_args"],
        "latest": response["latest"],
        "created_at": response["created_at"],
        "updated_at": response["updated_at"],
    }

    requirements = "\n".join(response["requirements"])
    method = response["method"]

    with open(f"{actuators_dir}/{name}/method.py", "w") as f:
        f.write(method)

    logger.info("method.py has been created")

    with open(f"{actuators_dir}/{name}/requirements.txt", "w") as f:
        f.write(requirements)

    logger.info("requirements.txt has been created")

    subprocess.run(  # noqa: S603
        [sys.executable, "-m", "venv", f"{actuators_dir}/{name}/.venv"],
        check=True,
    )

    logger.info(".venv has been created")
    logger.info("requirements are being downloaded...")

    if sys.platform == "win32":
        pip_path = f"{actuators_dir}/{name}/.venv/Scripts/pip.exe"
    else:
        pip_path = f"{actuators_dir}/{name}/.venv/bin/pip"

    subprocess.run(  # noqa: S603
        [
            pip_path,
            "install",
            "-r",
            f"{actuators_dir}/{name}/requirements.txt",
        ],
        check=True,
    )

    logger.info("requirements downloaded")

    # card.json is written last, so a failed load is not seen as up to date
    with open(f"{actuators_dir}/{name}/card.json", "w") as f:
        json.dump(
            card,
            f,
            indent=4,
            ensure_ascii=True,
        )

    logger.info("card.json has been created")


def _venv_python(venv_dir: Path) -> Path:
    """Return the Python executable inside a venv, on any OS."""
    if os.name == "nt":
        python = venv_dir / "Scripts" / "python.exe"
    else:
        python = venv_dir / "bin" / "python"

    if not python.exists():
        raise FileNotFoundError(f"No Python interpreter found in venv: {python}")
    return python


def _run(
    actuator_dir: Path,
    fn_args: Dict[str, Any],
    method_name: str,
) -> object:
    """# Run.

    It runs the method in method.py inside the actuator's own venv.

    Args:
        actuator_dir (Path): Directory of the actuator.
        fn_args (Dict[str, Any]): Keyword arguments for the method.
        method_name (str): Name of the function in method.py.

    Returns:
        object: The output coming from the method.

    Raises:
        RuntimeError: If the worker crashes or the method raises an error.
    """
    python = _venv_python(actuator_dir / ".venv")

    with tempfile.TemporaryDirectory() as tmp:
        in_path = Path(tmp) / "in.pkl"
        out_path = Path(tmp) / "out.pkl"

        with open(in_path, "wb") as f:
            # Accepted risk, see docs/security.md
            # nosemgrep: python.lang.security.deserialization.pickle.avoid-pickle
            pickle.dump(fn_args, f, protocol=4)

        proc = subprocess.run(  # noqa: S603
            [
                str(python),
                "-c",
                _RUNNER,
                str(actuator_dir),
                "method",
                method_name,
                str(in_path),
                str(out_path),
            ],
            capture_output=True,
            text=True,
            check=False,
        )

        if proc.stdout:
            logger.info("Actuator stdout:\n%s", proc.stdout)

        if out_path.exists() is False:
            msg = f"Worker failed (exit code {proc.returncode}):\n{proc.stderr}"
            logger.error(msg)
            raise RuntimeError(msg)

        with open(out_path, "rb") as f:
            # nosemgrep: python.lang.security.deserialization.pickle.avoid-pickle
            outcome = pickle.load(f)  # noqa: S301

    if outcome["ok"] is False:
        msg = f"Actuator {method_name} failed:\n{outcome['error']}"
        logger.error(msg)
        raise RuntimeError(msg)

    return outcome["result"]


def _method_name(file_path: Path) -> str:
    """# Method Name.

    It finds the only top-level function of method.py with ast, so the host
    process does not run the actuator's code.

    Args:
        file_path (Path): Path of method.py.

    Returns:
        str: Name of the function.

    Raises:
        ValueError: If method.py does not have exactly one top-level function.
    """
    tree = ast.parse(file_path.read_text())
    methods = [node.name for node in tree.body if isinstance(node, ast.FunctionDef)]

    if len(methods) != 1:
        msg = f"Expected exactly one function, found {len(methods)}"
        logger.error(msg)
        raise ValueError(msg)

    return methods[0]


def _write_msg(stream: IO[bytes], obj: object) -> None:
    """# Write Message.

    It writes obj as an 8-byte length and the pickled bytes, like _WORKER reads.
    It pickles obj before it writes, so a pickle error sends nothing.

    Args:
        stream (IO[bytes]): The stdin pipe of the worker.
        obj (object): The object to send.
    """
    # Accepted risk, see docs/security.md
    # nosemgrep: python.lang.security.deserialization.pickle.avoid-pickle
    data = pickle.dumps(obj, protocol=4)
    stream.write(struct.pack(">Q", len(data)) + data)
    stream.flush()


def _read_msg(stream: IO[bytes]) -> Dict[str, Any]:
    """# Read Message.

    It reads one message that _WORKER sent.

    Args:
        stream (IO[bytes]): The stdout pipe of the worker.

    Returns:
        Dict[str, Any]: The outcome, with "ok" and "result" or "error".

    Raises:
        EOFError: If the worker closed the pipe, so it stopped.
    """
    header = stream.read(8)
    if len(header) < 8:
        raise EOFError("The worker closed the pipe")

    size = struct.unpack(">Q", header)[0]
    data = stream.read(size)
    if len(data) < size:
        raise EOFError("The worker closed the pipe")

    # nosemgrep: python.lang.security.deserialization.pickle.avoid-pickle
    return pickle.loads(data)  # noqa: S301


class _Worker:
    """# Worker.

    It is one long-lived process that runs the method inside the actuator's
    venv. The process imports method.py once, then it answers the calls over
    its stdin and stdout pipes. The constructor does not wait for the import,
    so call handshake before the first call.

    Attributes:
        method_name (str): Name of the function inside method.py.
        alive (bool): It is False after the process stops or crashes.
    """

    def __init__(self, python: Path, actuator_dir: Path, method_name: str) -> None:
        self.method_name = method_name
        self.alive = True
        self._stderr_tail: deque[str] = deque(maxlen=20)

        self._proc = subprocess.Popen(  # noqa: S603
            [
                str(python),
                "-c",
                _WORKER,
                str(actuator_dir),
                "method",
                method_name,
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        # stderr has to be read all the time, or a full pipe blocks the worker
        self._drain = threading.Thread(target=self._drain_stderr, daemon=True)
        self._drain.start()

    def _drain_stderr(self) -> None:
        """# Drain Stderr.

        It logs the stderr of the worker line by line. print() inside the
        method also comes here, because _WORKER moves stdout to stderr.
        """
        with self._proc.stderr as stream:
            for raw_line in stream:
                line = raw_line.decode(errors="replace")
                self._stderr_tail.append(line)
                logger.info("Actuator %s: %s", self.method_name, line.rstrip())

    def _crashed(self) -> RuntimeError:
        """# Crashed.

        It stops the worker and builds the error with its last stderr lines.

        Returns:
            RuntimeError: The error to raise.
        """
        self.close()
        self._drain.join(timeout=1)
        msg = (
            f"Actuator {self.method_name} worker stopped "
            f"(exit code {self._proc.returncode}):\n{''.join(self._stderr_tail)}"
        )
        logger.error(msg)
        return RuntimeError(msg)

    def handshake(self) -> None:
        """# Handshake.

        It waits until the worker imported method.py.

        Raises:
            RuntimeError: If the worker cannot import method.py.
        """
        try:
            outcome = _read_msg(self._proc.stdout)
        except EOFError as e:
            raise self._crashed() from e

        if outcome["ok"] is False:
            self.close()
            msg = (
                f"Actuator {self.method_name} worker cannot import method.py:\n"
                f"{outcome['error']}"
            )
            logger.error(msg)
            raise RuntimeError(msg)

    def call(self, kwargs: Dict[str, Any]) -> object:
        """# Call.

        It runs the method in the worker. The worker stays alive if the method
        raises an error.

        Args:
            kwargs (Dict[str, Any]): Keyword arguments for the method.

        Returns:
            object: The output coming from the method.

        Raises:
            RuntimeError: If the worker is stopped, it crashes or the method
                raises an error.
        """
        if self.alive is False:
            msg = f"Actuator {self.method_name} worker is not running"
            logger.error(msg)
            raise RuntimeError(msg)

        try:
            _write_msg(self._proc.stdin, kwargs)
            outcome = _read_msg(self._proc.stdout)
        except (EOFError, OSError) as e:
            raise self._crashed() from e

        if outcome["ok"] is False:
            msg = f"Actuator {self.method_name} failed:\n{outcome['error']}"
            logger.error(msg)
            raise RuntimeError(msg)

        return outcome["result"]

    def close(self) -> None:
        """# Close.

        It closes stdin, so the worker leaves its loop and exits. If it does not
        exit in 5 seconds, it is killed. It is safe to call it more than once.
        """
        self.alive = False
        with contextlib.suppress(OSError):
            self._proc.stdin.close()

        try:
            self._proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self._proc.kill()
            self._proc.wait()

        self._proc.stdout.close()


def _close_all(workers: List[_Worker]) -> None:
    """# Close All.

    It closes every worker of an actuator. weakref.finalize calls it.

    Args:
        workers (List[_Worker]): The worker pool.
    """
    for worker in list(workers):
        worker.close()
