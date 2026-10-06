"""# Actuators.

It contains the decorators for the actuators.
"""

import inspect
import logging
import os
from datetime import UTC, datetime
from functools import wraps
from typing import Any, Dict, List, Literal, get_type_hints

from pymongo import MongoClient

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

            client = MongoClient(os.getenv("NEXGEN_MONGO_CONNSTR"))
            db = client[os.getenv("NEXGEN_MONGO_DBNAME")]

            current_collection = (
                os.getenv("NEXGEN_MONGO_C_COLNAME")
                if atype == "coding"
                else os.getenv("NEXGEN_MONGO_D_COLNAME")
            )

            logger.info(f"MongoDB collection selected: {current_collection}")

            if current_collection not in db.list_collection_names():
                db.create_collection(current_collection)

            is_exist = db[current_collection].count_documents(
                {
                    "name": name,
                    "version": version,
                },
            )

            if is_exist != 0:
                return None

            sample: Dict[str, Any] = {
                "name": name,
                "version": version,
                "is_latest": is_latest,
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
            sample["created_at"] = datetime.now(UTC).isoformat()

            result = db[current_collection].insert_one(sample)

            if result.inserted_id is not None:
                logger.warning("Actuator creation has been failed")
                return None
            else:
                logger.info("Actuator has been created")
                return result.inserted_id
