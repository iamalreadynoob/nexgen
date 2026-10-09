"""# Actuators.

It contains the decorators for the actuators.
"""

import inspect
import logging
import os
from functools import wraps
from typing import Any, Dict, List, Literal, get_type_hints

import requests

logger = logging.getLogger(__name__)


def actuator(
    name: str,
    atype: Literal["coding", "decoding"],
    version: str,
    is_latest: bool,
    requirements: List[str] | None,
) -> bool:
    """# Actuator.

    It holds the information for the actuator.
    """

    def decorator(func):  # noqa: ANN001, ANN202
        """# Decorator Method."""

        @wraps(func)
        def wrapper(*args, **kwargs):  # noqa: ANN002, ANN003, ANN202, ARG001
            """# Wrapper Method.."""
            if isinstance(name, str) is False:
                logger.error("name is invalid, it has to be str")
                raise ValueError("name is invalid, it has to be str")

            if atype not in ["coding", "decoding"]:
                logger.error("name is invalid, it has to be either coding or decoding")
                raise ValueError(
                    "name is invalid, it has to be either coding or decoding",
                )

            if isinstance(version, str) is False:
                logger.error("version is invalid, it has to be str")
                raise ValueError("version is invalid, it has to be str")

            if isinstance(is_latest, bool) is False:
                logger.error("is_latest is invalid, it has to be bool")
                raise ValueError("is_latest is invalid, it has to be bool")

            if requirements is not None and (
                isinstance(requirements, list) is False
                or all(isinstance(r, str) for r in requirements) is False
            ):
                logger.error("requirements is invalid, it has to be str")
                raise ValueError("requirements is invalid, it has to be str")

            sample: Dict[str, Any] = {
                "name": name,
                "version": version,
                "actuator_type": atype,
                "set_latest": is_latest,
                "requirements": requirements,
            }

            source_code = inspect.getsource(func)

            signature = inspect.signature(func)

            type_hints = get_type_hints(func)

            arguments = {}

            for parameter_name, parameter in signature.parameters.items():
                annotation = type_hints.get(parameter_name)

                arguments[parameter_name] = {
                    "type": str(annotation) if annotation else None,
                    "default": (
                        str(parameter.default)
                        if parameter.default is not inspect.Parameter.empty
                        else None
                    ),
                }

            sample["method"] = source_code
            sample["method_args"] = arguments

            base_url: str = os.getenv("NEXGEN_BASE_URL")
            if base_url is None:
                base_url = "http://localhost:8000/api/v1"

            api_key: str | None = os.getenv("NEXGEN_API_KEY")
            headers: Dict[str, str] = {}

            if api_key is not None:
                headers["X-API-KEY"] = api_key

            request_timeout: int = os.getenv("NEXGEN_TIMEOUT")
            if (
                request_timeout is None
                or isinstance(request_timeout, (int, float)) is False
            ):
                request_timeout = 60

            result = None
            try:
                result = requests.post(
                    f"{base_url}/actuators",
                    headers=headers,
                    json=sample,
                    timeout=request_timeout,
                )
            except Exception as e:
                logger.warning(e)

            if result is not None:
                if result.ok is True:
                    logger.info(
                        "POST /actuators succeeded: status=%d, response=%s",
                        result.status_code,
                        result.text,
                    )
                else:
                    logger.warning(
                        "POST /actuators failed: status=%d, response=%s",
                        result.status_code,
                        result.text,
                    )
