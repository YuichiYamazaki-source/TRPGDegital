from __future__ import annotations

import uuid
from dataclasses import dataclass, field

HISTORY_WINDOW = 20


@dataclass
class Session:
    session_id: str
    channel_id: str
    scenario_id: str
    characters: dict[str, dict]
    history: list[dict[str, str]] = field(default_factory=list)


class SessionManager:
    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}

    def create_session(
        self,
        channel_id: str,
        scenario_id: str,
        characters: dict[str, dict],
    ) -> str:
        session_id = str(uuid.uuid4())
        self._sessions[session_id] = Session(
            session_id=session_id,
            channel_id=channel_id,
            scenario_id=scenario_id,
            characters=characters,
        )
        return session_id

    def get_session(self, session_id: str) -> Session | None:
        return self._sessions.get(session_id)

    def add_message(
        self,
        session_id: str,
        character_name: str,
        message: str,
        reply: str,
    ) -> None:
        session = self._sessions.get(session_id)
        if session is None:
            return

        session.history.append({"role": "user", "content": f"[{character_name}]: {message}"})
        session.history.append({"role": "assistant", "content": reply})

        max_messages = HISTORY_WINDOW * 2
        if len(session.history) > max_messages:
            session.history = session.history[-max_messages:]

    def delete_session(self, session_id: str) -> bool:
        return self._sessions.pop(session_id, None) is not None
