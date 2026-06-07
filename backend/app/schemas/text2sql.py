from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class Text2SQLOperation(str, Enum):
    SCHEMA = "schema"
    SELECT_ENTITIES = "select_entities"
    CREATE_SCHEDULE = "create_schedule"
    UPDATE_SCHEDULE = "update_schedule"
    DELETE_SCHEDULE = "delete_schedule"


class Text2SQLRequest(BaseModel):
    operation: Text2SQLOperation
    filters: dict[str, Any] = Field(default_factory=dict)
    data: dict[str, Any] = Field(default_factory=dict)
    limit: int = Field(default=20, ge=1, le=100)
    confirm: bool = False
    confirmation_id: str | None = None


class Text2SQLResponse(BaseModel):
    success: bool
    message: str
    table_name: str | None = None
    allowed_fields: list[str] = Field(default_factory=list)
    sql_preview: str | None = None
    params: dict[str, Any] = Field(default_factory=dict)
    rows: list[dict[str, Any]] = Field(default_factory=list)
    affected_rows: int = 0
    requires_confirmation: bool = False
    confirmation_id: str | None = None