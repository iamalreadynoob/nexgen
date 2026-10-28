"""# Schema.

It contains the schema classes for API objects.
"""

from datetime import datetime
from typing import Any, Dict, List

from pydantic import BaseModel, Field


class DataOut(BaseModel):
    """# Data Out."""

    id: str = Field(
        description="Data ID information",
    )
    actuator_id: str = Field(
        description="Used actuator for the data.",
    )
    metadata: object = Field(
        description="The output created with actuator.",
    )
    linked_resource: str | None = Field(
        description="The identifier for the original input.",
    )
    specs: Dict[str, Any] | None = Field(
        description="Extra information about the data.",
    )
    created_at: datetime = Field(
        description="The created time for the data.",
    )
    updated_at: datetime = Field(
        description="The last updated time for the data.",
    )


class DataList(BaseModel):
    """# Data List."""

    total: int = Field(
        description="Total data count",
    )
    data: List[DataOut] = Field(
        description="The data list",
    )


class ContentOut(BaseModel):
    """# Content Out."""

    id: str = Field(
        description="Content ID information",
    )
    identifier: str = Field(
        description="The identifier for the content.",
    )
    specs: Dict[str, Any] | None = Field(
        description="Extra information about the content.",
    )
    created_at: datetime = Field(
        description="The created time for the content.",
    )
    updated_at: datetime = Field(
        description="The last updated time for the content.",
    )


class ContentList(BaseModel):
    """# Content List."""

    total: int = Field(
        description="Total content count",
    )
    data: List[ContentOut] = Field(
        description="The content list",
    )
