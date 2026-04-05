from __future__ import annotations

import importlib
import os
import uuid
from typing import Any


class InProcessSessionClient:
    """Drive the FastAPI app by calling the endpoint functions directly."""

    def __init__(self) -> None:
        os.environ.setdefault("OPENAI_API_KEY", "playtest-dummy-key")
        self._main = importlib.import_module("main")

    @property
    def main(self) -> Any:
        return self._main

    async def create_session(
        self,
        scenario_id: str,
        user_id: str,
        display_name: str,
        character_id: str,
        *,
        channel_id: str | None = None,
    ) -> dict[str, Any]:
        request = self._main.SessionCreateRequest(
            channel_id=channel_id or f"playtest-{uuid.uuid4()}",
            scenario_id=scenario_id,
            players=[
                self._main.SessionPlayerRequest(
                    user_id=user_id,
                    display_name=display_name,
                    character_id=character_id,
                )
            ],
        )
        return self._main.create_session(request)

    async def get_state(self, session_id: str) -> dict[str, Any]:
        return self._main.get_session_state(session_id)

    async def chat(self, session_id: str, character_id: str, message: str) -> dict[str, Any]:
        request = self._main.ChatRequest(character_id=character_id, message=message)
        return await self._main.chat(session_id, request)

    async def respond_to_check(self, session_id: str, character_id: str, decision: str) -> dict[str, Any]:
        request = self._main.CheckRespondRequest(character_id=character_id, decision=decision)
        return await self._main.respond_to_check(session_id, request)

    async def resolve_check(self, session_id: str, character_id: str, roll: int | None = None) -> dict[str, Any]:
        request = self._main.CheckResolveRequest(character_id=character_id, roll=roll)
        return await self._main.resolve_check(session_id, request)

    async def end_session(self, session_id: str) -> dict[str, Any]:
        return self._main.end_session(session_id)
