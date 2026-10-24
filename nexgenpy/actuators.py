"""# Actuators.

It contains the decorators for the actuators.
"""

import ast
import inspect
import logging
import os
import textwrap
from functools import wraps
from typing import Any, Callable, Dict, List, Literal, get_type_hints

import requests

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "http://localhost:8000/api/v1"
DEFAULT_TIMEOUT = 60


def _function_source(func: Callable[..., Any]) -> str:
    """# Function Source.

    It returns the source code of the function without its decorators, so the
    downloaded method.py does not need to import them.

    Args:
        func (Callable[..., Any]): The decorated function.

    Returns:
        str: The source code that starts at the `def` line.
    """
    source = textwrap.dedent(inspect.getsource(func))
    node = ast.parse(source).body[0]
    lines = source.splitlines(keepends=True)
    return "".join(lines[node.lineno - 1 :])


def _request_timeout() -> float:
    """# Request Timeout.

    Returns:
        float: The value of NEXGEN_TIMEOUT, or the default if it is not valid.
    """
    raw_timeout = os.getenv("NEXGEN_TIMEOUT")
    if raw_timeout is None:
        return DEFAULT_TIMEOUT

    try:
        timeout = float(raw_timeout)
    except ValueError:
        timeout = 0

    if timeout <= 0:
        logger.warning(
            "NEXGEN_TIMEOUT is invalid: %r, using %d",
            raw_timeout,
            DEFAULT_TIMEOUT,
        )
        return DEFAULT_TIMEOUT

    return timeout


def actuator(
    name: str,
    atype: Literal["coding", "decoding"],
    version: str,
    is_latest: bool,
    requirements: List[str] | None,
) -> Callable[[Callable[..., Any]], Callable[..., bool]]:
    """# Actuator.

    It holds the information for the actuator. A call to the decorated function
    publishes the actuator to the Nexgen API.

    Args:
        name (str): Name of the actuator.
        atype (Literal["coding", "decoding"]): Type of the actuator.
        version (str): Version of the actuator.
        is_latest (bool): If it is true, the server marks this version as latest.
        requirements (List[str] | None): Pip requirements of the actuator.

    Returns:
        Callable[[Callable[..., Any]], Callable[..., bool]]: The decorator.
    """
    # Checking The Datatypes
    if isinstance(name, str) is False:
        logger.error("name is invalid, it has to be str")
        raise ValueError("name is invalid, it has to be str")

    if atype not in ["coding", "decoding"]:
        logger.error("atype is invalid, it has to be either coding or decoding")
        raise ValueError("atype is invalid, it has to be either coding or decoding")

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
        logger.error("requirements is invalid, it has to be List[str]")
        raise ValueError("requirements is invalid, it has to be List[str]")

    def decorator(func: Callable[..., Any]) -> Callable[..., bool]:
        """# Decorator Method."""
        signature = inspect.signature(func)
        type_hints = get_type_hints(func)

        arguments: Dict[str, Dict[str, str]] = {}

        # The server accepts only str values, so missing info is left out
        for parameter_name, parameter in signature.parameters.items():
            annotation = type_hints.get(parameter_name)
            argument: Dict[str, str] = {}

            if annotation is not None:
                argument["type"] = str(annotation)

            if parameter.default is not inspect.Parameter.empty:
                argument["default"] = str(parameter.default)

            arguments[parameter_name] = argument

        sample: Dict[str, Any] = {
            "name": name,
            "version": version,
            "actuator_type": atype,
            "set_latest": is_latest,
            "requirements": requirements if requirements is not None else [],
            "method": _function_source(func),
            "method_args": arguments,
        }

        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> bool:  # noqa: ANN401, ARG001
            """# Wrapper Method.

            Returns:
                bool: True if the server accepted the actuator, else False.
            """
            base_url = os.getenv("NEXGEN_BASE_URL", DEFAULT_BASE_URL)

            api_key = os.getenv("NEXGEN_API_KEY")
            headers: Dict[str, str] = {}

            if api_key is not None:
                headers["X-API-KEY"] = api_key

            try:
                result = requests.post(
                    f"{base_url}/actuators",
                    headers=headers,
                    json=sample,
                    timeout=_request_timeout(),
                )
            except requests.RequestException as e:
                logger.warning("POST /actuators failed: %s", e)
                return False

            if result.ok is True:
                logger.info(
                    "POST /actuators succeeded: status=%d, response=%s",
                    result.status_code,
                    result.text,
                )
                return True

            logger.warning(
                "POST /actuators failed: status=%d, response=%s",
                result.status_code,
                result.text,
            )
            return False

        return wrapper

    return decorator
