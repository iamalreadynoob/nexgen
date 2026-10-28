"""# Wrappers.

It contains the wrapper class structures for the API.
"""

import logging
import os
from typing import Any, Dict
from urllib.parse import quote

import requests

from .schema import ContentList, ContentOut, DataList, DataOut

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "http://localhost:8000/api/v1"


class Data:
    """The wrapper for data endpoints."""

    @staticmethod
    def get_data_list(
        page: int | None = None,
        limit: int | None = None,
        ascending: bool | None = None,
        actuator_id: str | None = None,
        timeout: int = 60,
    ) -> DataList:
        """# Get Data List.

        It returns the data list. Equivalent to GET `/data` endpoint.

        Args:
            page (int | None, optional): The page index.
            limit (int | None, optional): The page size.
            ascending (bool | None, optional): The date sort order.
            actuator_id (str | None, optional): It returns the data items only with
                related to the specified actuator.
            timeout (int, optional): The maximum response time for the endpoint.

        Returns:
            DataList: The data items.
        """
        if page is not None and isinstance(page, int) is False:
            logger.error("Page is invalid, it has to be int")
            raise ValueError("Page is invalid, it has to be int")

        if limit is not None and isinstance(limit, int) is False:
            logger.error("Limit is invalid, it has to be int")
            raise ValueError("Limit is invalid, it has to be int")

        if ascending is not None and isinstance(ascending, bool) is False:
            logger.error("Ascending is invalid, it has to be bool")
            raise ValueError("Ascending is invalid, it has to be bool")

        if actuator_id is not None and isinstance(actuator_id, str) is False:
            logger.error("Actuator ID is invalid, it has to be str")
            raise ValueError("Actuator ID is invalid, it has to be str")

        if isinstance(timeout, int) is False:
            logger.error("Timeout is invalid, it has to be int")
            raise ValueError("Timeout is invalid, it has to be int")

        params: Dict[str, Any] = {}
        if page is not None:
            params["page"] = page

        if limit is not None:
            params["limit"] = limit

        if ascending is not None:
            params["ascending"] = ascending

        if actuator_id is not None:
            params["actuator_id"] = actuator_id

        result = requests.get(
            f"{os.getenv('NEXGEN_BASE_URL', DEFAULT_BASE_URL)}/data",
            headers={
                "X-API-KEY": os.getenv("NEXGEN_API_KEY"),
            },
            params=params,
            timeout=timeout,
        )

        result.raise_for_status()

        result = result.json()

        total = result["total"]
        data = [DataOut.model_validate(data_dict) for data_dict in result["data"]]

        return DataList(
            total=total,
            data=data,
        )

    @staticmethod
    def create_data(
        actuator_id: str,
        metadata: object,
        linked_resource: str | None = None,
        specs: Dict[str, Any] | None = None,
        timeout: int = 60,
    ) -> DataOut:
        """# Create Data.

        Creates data. Equivalent to POST `/data` endpoint.

        Args:
            actuator_id (str): ID for the actuator.
            metadata (object): Transmitted input.
            linked_resource (str | None, optional): Original input.
            specs (Dict[str, Any] | None, optional): Extra information about the data.
            timeout: (int, optional): Timeout for the endpoint.

        Returns:
            DataOut: Created data object.
        """
        if isinstance(actuator_id, str) is False:
            logger.error("Actuator ID is invalid, it has to be str")
            raise ValueError("Actuator ID is invalid, it has to be str")

        if metadata is None:
            logger.error("Metadata is invalid, it has to be object")
            raise ValueError("Metadata is invalid, it has to be object")

        if linked_resource is not None and isinstance(linked_resource, str) is False:
            logger.error("Linked Resource is invalid, it has to be str")
            raise ValueError("Linked Resource is invalid, it has to be str")

        if specs is not None and isinstance(specs, dict) is False:
            logger.error("Specs is invalid, it has to be Dict[str, Any]")
            raise ValueError("Specs is invalid, it has to be Dict[str, Any]")

        if isinstance(timeout, int) is False:
            logger.error("Timeout is invalid, it has to be int")
            raise ValueError("Timeout is invalid, it has to be int")

        result = requests.post(
            f"{os.getenv('NEXGEN_BASE_URL', DEFAULT_BASE_URL)}/data",
            headers={
                "X-API-KEY": os.getenv("NEXGEN_API_KEY"),
            },
            json={
                "actuator_id": actuator_id,
                "metadata": metadata,
                "linked_resource": linked_resource,
                "specs": specs,
            },
            timeout=timeout,
        )

        result.raise_for_status()

        result = result.json()
        return DataOut.model_validate(result)

    @staticmethod
    def get_data(
        data_id: str,
        timeout: int = 60,
    ) -> DataOut:
        """# Get Data.

        It gets the data object for given ID.

        Args:
            data_id (str): ID for the requested data.
            timeout (int, optional): Timeout for the endpoint.

        Returns:
            DataOut: Data object.
        """
        if isinstance(data_id, str) is False:
            logger.error("data_id is invalid, it has to be str")
            raise ValueError("data_id is invalid, it has to be str")

        # quote() keeps ".", so these would leave /data/{data_id}
        if data_id in ("", ".", ".."):
            logger.error("data_id is invalid, it can not be empty, '.' or '..'")
            raise ValueError("data_id is invalid, it can not be empty, '.' or '..'")

        if isinstance(timeout, int) is False:
            logger.error("Timeout is invalid, it has to be int")
            raise ValueError("Timeout is invalid, it has to be int")

        data_id = quote(data_id, safe="")

        result = requests.get(
            f"{os.getenv('NEXGEN_BASE_URL', DEFAULT_BASE_URL)}/data/{data_id}",
            headers={
                "X-API-KEY": os.getenv("NEXGEN_API_KEY"),
            },
            timeout=timeout,
        )

        result.raise_for_status()

        result = result.json()
        return DataOut.model_validate(result)

    @staticmethod
    def update_data(
        data_id: str,
        linked_resource: str | None = None,
        specs: Dict[str, Any] | None = None,
        timeout: int = 60,
    ) -> DataOut:
        """# Update Data.

        It updates the existing data. Equivalent to PUT `/data/{data_id}`

        Args:
            data_id (str): ID for the data item.
            linked_resource (str | None, optional): Original input.
            specs (Dict[str, Any] | None, optional): Extra information about the data.
            timeout (int, optional): Timeout for the request.

        Returns:
            DataOut: Data object.
        """
        if isinstance(data_id, str) is False:
            logger.error("data_id is invalid, it has to be str")
            raise ValueError("data_id is invalid, it has to be str")

        # quote() keeps ".", so these would leave /data/{data_id}
        if data_id in ("", ".", ".."):
            logger.error("data_id is invalid, it can not be empty, '.' or '..'")
            raise ValueError("data_id is invalid, it can not be empty, '.' or '..'")

        if linked_resource is not None and isinstance(linked_resource, str) is False:
            logger.error("Linked Resource is invalid, it has to be str")
            raise ValueError("Linked Resource is invalid, it has to be str")

        if specs is not None and isinstance(specs, dict) is False:
            logger.error("Specs is invalid, it has to be Dict[str, Any]")
            raise ValueError("Specs is invalid, it has to be Dict[str, Any]")

        if isinstance(timeout, int) is False:
            logger.error("Timeout is invalid, it has to be int")
            raise ValueError("Timeout is invalid, it has to be int")

        data_id = quote(data_id, safe="")

        update_dict: Dict[str, Any] = {}

        if linked_resource is not None:
            update_dict["linked_resource"] = linked_resource

        if specs is not None:
            update_dict["specs"] = specs

        result = requests.put(
            f"{os.getenv('NEXGEN_BASE_URL', DEFAULT_BASE_URL)}/data/{data_id}",
            headers={
                "X-API-KEY": os.getenv("NEXGEN_API_KEY"),
            },
            json=update_dict,
            timeout=timeout,
        )

        result.raise_for_status()

        result = result.json()
        return DataOut.model_validate(result)

    @staticmethod
    def delete_data(
        data_id: str,
        timeout: int = 60,
    ) -> None:
        """# Delete Data.

        It deletes the data. Equivalent to DELETE `/data/{data_id}`

        Args:
            data_id (str): Data ID.
            timeout (int, optional): Timeout for the request.
        """
        if isinstance(data_id, str) is False:
            logger.error("data_id is invalid, it has to be str")
            raise ValueError("data_id is invalid, it has to be str")

        # quote() keeps ".", so these would leave /data/{data_id}
        if data_id in ("", ".", ".."):
            logger.error("data_id is invalid, it can not be empty, '.' or '..'")
            raise ValueError("data_id is invalid, it can not be empty, '.' or '..'")

        if isinstance(timeout, int) is False:
            logger.error("Timeout is invalid, it has to be int")
            raise ValueError("Timeout is invalid, it has to be int")

        data_id = quote(data_id, safe="")

        result = requests.delete(
            f"{os.getenv('NEXGEN_BASE_URL', DEFAULT_BASE_URL)}/data/{data_id}",
            headers={
                "X-API-KEY": os.getenv("NEXGEN_API_KEY"),
            },
            timeout=timeout,
        )

        result.raise_for_status()


class Content:
    """The wrapper for the `/contents` endpoints."""

    @staticmethod
    def get_content_list(
        page: int | None = None,
        limit: int | None = None,
        ascending: bool | None = None,
        actuator_id: str | None = None,
        timeout: int = 60,
    ) -> ContentList:
        """# Get Content List.

        Get a page of content items from GET `/contents`.

        Args:
            page (int | None, optional): The page index.
            limit (int | None, optional): The number of items on one page.
            ascending (bool | None, optional): The sort order by date. If True,
                the order is ascending.
            actuator_id (str | None, optional): If given, get only the content
                items that are related to this actuator.
            timeout (int, optional): The timeout of the request in seconds.

        Returns:
            ContentList: The total number of content items and the items on
                the page.
        """
        if page is not None and isinstance(page, int) is False:
            logger.error("Page is invalid, it has to be int")
            raise ValueError("Page is invalid, it has to be int")

        if limit is not None and isinstance(limit, int) is False:
            logger.error("Limit is invalid, it has to be int")
            raise ValueError("Limit is invalid, it has to be int")

        if ascending is not None and isinstance(ascending, bool) is False:
            logger.error("Ascending is invalid, it has to be bool")
            raise ValueError("Ascending is invalid, it has to be bool")

        if actuator_id is not None and isinstance(actuator_id, str) is False:
            logger.error("Actuator ID is invalid, it has to be str")
            raise ValueError("Actuator ID is invalid, it has to be str")

        if isinstance(timeout, int) is False:
            logger.error("Timeout is invalid, it has to be int")
            raise ValueError("Timeout is invalid, it has to be int")

        params: Dict[str, Any] = {}
        if page is not None:
            params["page"] = page

        if limit is not None:
            params["limit"] = limit

        if ascending is not None:
            params["ascending"] = ascending

        if actuator_id is not None:
            params["actuator_id"] = actuator_id

        result = requests.get(
            f"{os.getenv('NEXGEN_BASE_URL', DEFAULT_BASE_URL)}/contents",
            headers={
                "X-API-KEY": os.getenv("NEXGEN_API_KEY"),
            },
            params=params,
            timeout=timeout,
        )

        result.raise_for_status()

        result = result.json()

        total = result["total"]
        data = [
            ContentOut.model_validate(content_dict) for content_dict in result["data"]
        ]

        return ContentList(
            total=total,
            data=data,
        )

    @staticmethod
    def get_content(
        content_id: str,
        timeout: int = 60,
    ) -> ContentOut:
        """# Get Content.

        Get one content item from GET `/contents/{content_id}`.

        Args:
            content_id (str): The ID of the content item.
            timeout (int, optional): The timeout of the request in seconds.

        Returns:
            ContentOut: The content item.
        """
        if isinstance(content_id, str) is False:
            logger.error("content_id is invalid, it has to be str")
            raise ValueError("content_id is invalid, it has to be str")

        # quote() keeps ".", so these would leave /contents/{content_id}
        if content_id in ("", ".", ".."):
            logger.error("content_id is invalid, it can not be empty, '.' or '..'")
            raise ValueError("content_id is invalid, it can not be empty, '.' or '..'")

        if isinstance(timeout, int) is False:
            logger.error("Timeout is invalid, it has to be int")
            raise ValueError("Timeout is invalid, it has to be int")

        content_id = quote(content_id, safe="")

        result = requests.get(
            f"{os.getenv('NEXGEN_BASE_URL', DEFAULT_BASE_URL)}/contents/{content_id}",
            headers={
                "X-API-KEY": os.getenv("NEXGEN_API_KEY"),
            },
            timeout=timeout,
        )

        result.raise_for_status()

        result = result.json()
        return ContentOut.model_validate(result)

    @staticmethod
    def create_content(
        identifier: str,
        specs: Dict[str, Any] | None = None,
        timeout: int = 60,
    ) -> ContentOut:
        """# Create Content.

        Create a content item with POST `/contents`.

        Args:
            identifier (str): The identifier of the content item.
            specs (Dict[str, Any] | None, optional): Extra information about the
                content item. If None, the request sends null.
            timeout (int, optional): The timeout of the request in seconds.

        Returns:
            ContentOut: The content item that the server created.
        """
        if isinstance(identifier, str) is False:
            logger.error("Identifier is invalid, it has to be str")
            raise ValueError("Identifier is invalid, it has to be str")

        if specs is not None and isinstance(specs, dict) is False:
            logger.error("Specs is invalid, it has to be Dict[str, Any]")
            raise ValueError("Specs is invalid, it has to be Dict[str, Any]")

        if isinstance(timeout, int) is False:
            logger.error("Timeout is invalid, it has to be int")
            raise ValueError("Timeout is invalid, it has to be int")

        result = requests.post(
            f"{os.getenv('NEXGEN_BASE_URL', DEFAULT_BASE_URL)}/contents",
            headers={
                "X-API-KEY": os.getenv("NEXGEN_API_KEY"),
            },
            json={
                "identifier": identifier,
                "specs": specs,
            },
            timeout=timeout,
        )

        result.raise_for_status()

        result = result.json()
        return ContentOut.model_validate(result)

    @staticmethod
    def update_specs(
        content_id: str,
        specs: Dict[str, Any],
        timeout: int = 60,
    ) -> ContentOut:
        """# Update Specs.

        Merge specs into the specs of a content item with PUT
        `/contents/{content_id}/specs`. The server keeps the keys that you do
        not send.

        Args:
            content_id (str): The ID of the content item.
            specs (Dict[str, Any]): The keys to add to or change in the specs of
                the content item.
            timeout (int, optional): The timeout of the request in seconds.

        Returns:
            ContentOut: The content item after the change.
        """
        if isinstance(content_id, str) is False:
            logger.error("content_id is invalid, it has to be str")
            raise ValueError("content_id is invalid, it has to be str")

        # quote() keeps ".", so these would leave /contents/{content_id}
        if content_id in ("", ".", ".."):
            logger.error("content_id is invalid, it can not be empty, '.' or '..'")
            raise ValueError("content_id is invalid, it can not be empty, '.' or '..'")

        if isinstance(specs, dict) is False:
            logger.error("Specs is invalid, it has to be Dict[str, Any]")
            raise ValueError("Specs is invalid, it has to be Dict[str, Any]")

        if isinstance(timeout, int) is False:
            logger.error("Timeout is invalid, it has to be int")
            raise ValueError("Timeout is invalid, it has to be int")

        content_id = quote(content_id, safe="")
        base_url = os.getenv("NEXGEN_BASE_URL", DEFAULT_BASE_URL)

        result = requests.put(
            f"{base_url}/contents/{content_id}/specs",
            headers={
                "X-API-KEY": os.getenv("NEXGEN_API_KEY"),
            },
            json={
                "specs": specs,
            },
            timeout=timeout,
        )

        result.raise_for_status()

        result = result.json()
        return ContentOut.model_validate(result)

    @staticmethod
    def delete_content(
        content_id: str,
        timeout: int = 60,
    ) -> None:
        """# Delete Content.

        Delete a content item with DELETE `/contents/{content_id}`.

        Args:
            content_id (str): The ID of the content item.
            timeout (int, optional): The timeout of the request in seconds.
        """
        if isinstance(content_id, str) is False:
            logger.error("content_id is invalid, it has to be str")
            raise ValueError("content_id is invalid, it has to be str")

        # quote() keeps ".", so these would leave /contents/{content_id}
        if content_id in ("", ".", ".."):
            logger.error("content_id is invalid, it can not be empty, '.' or '..'")
            raise ValueError("content_id is invalid, it can not be empty, '.' or '..'")

        if isinstance(timeout, int) is False:
            logger.error("Timeout is invalid, it has to be int")
            raise ValueError("Timeout is invalid, it has to be int")

        content_id = quote(content_id, safe="")

        result = requests.delete(
            f"{os.getenv('NEXGEN_BASE_URL', DEFAULT_BASE_URL)}/contents/{content_id}",
            headers={
                "X-API-KEY": os.getenv("NEXGEN_API_KEY"),
            },
            timeout=timeout,
        )

        result.raise_for_status()
