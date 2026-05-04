from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
from typing import Any


class CharacterCreate(BaseModel):
    session_id: UUID | None = None
    name: str
    data: dict[str, Any] = {}


class CharacterResponse(BaseModel):
    id: UUID
    session_id: UUID | None
    name: str
    data: dict[str, Any]
    created_at: datetime

    model_config = {"from_attributes": True}
