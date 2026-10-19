"""# Manager.

It manages the essential works for the actuators.
"""

import asyncio
import importlib.util
import inspect
import json
import logging
import os
import shutil
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any, Dict
from uuid import uuid4

import requests

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "http://localhost:8000/api/v1"


class Actuator:
    """# Actuator.

    It runs the actuator like run_actuator. It loads the method only once, in the
    constructor, so the next runs do not import method.py again.

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
        method (Callable[..., Any]): The function inside method.py.
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

        file_path = Path(f"{actuators_dir}/{name}/method.py").resolve()

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

        actuator_id = None
        if dst is not None:
            with open(f"{actuators_dir}/{name}/card.json", "r") as f:
                actuator_id = json.load(f)["id"]

        self.name = name
        self.actuators_dir = actuators_dir
        self.dst = dst
        self.dst_timeout = dst_timeout
        self.dst_headers = dst_headers if dst_headers is not None else {}
        self.dst_save_original = dst_save_original
        self.actuator_id = actuator_id
        self.method = methods[0]

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
        """
        # Checking The Datatypes
        if isinstance(data, dict) is False:
            logger.error("data is invalid, it has to be Dict[str, Any]")
            raise ValueError("data is invalid, it has to be Dict[str, Any]")

        if data_specs is not None and isinstance(data_specs, dict) is False:
            logger.error("data_specs is invalid, it has to be Dict[str, Any]")
            raise ValueError("data_specs is invalid, it has to be Dict[str, Any]")

        output = self.method(**data)

        if self.dst is None:
            return output

        linked_resource: str | None = None
        if self.dst_save_original is True:
            linked_resource = str(uuid4())

            # Lazy upload, so the main process does not wait for it
            threading.Thread(
                target=_send_content,
                kwargs={
                    "url": f"{self.dst}/content",
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
        """
        # Checking The Datatypes
        if isinstance(data, dict) is False:
            logger.error("data is invalid, it has to be Dict[str, Any]")
            raise ValueError("data is invalid, it has to be Dict[str, Any]")

        if data_specs is not None and isinstance(data_specs, dict) is False:
            logger.error("data_specs is invalid, it has to be Dict[str, Any]")
            raise ValueError("data_specs is invalid, it has to be Dict[str, Any]")

        output = await asyncio.to_thread(self.method, **data)

        if self.dst is None:
            return output

        linked_resource: str | None = None
        if self.dst_save_original is True:
            linked_resource = str(uuid4())

            # Lazy upload, so the main process does not wait for it
            threading.Thread(
                target=_send_content,
                kwargs={
                    "url": f"{self.dst}/content",
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
        logger.warning("POST /content failed: %s", e)
        return

    if result.ok is True:
        logger.info(
            "POST /content succeeded: status=%d, response=%s",
            result.status_code,
            result.text,
        )
    else:
        logger.warning(
            "POST /content failed: status=%d, response=%s",
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

    file_path = Path(f"{actuators_dir}/{name}/method.py").resolve()

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
    output = method(**data)

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
                "url": f"{dst}/content",
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
            existing_card.get("id") == response["id"]
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
        "id": response["id"],
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
