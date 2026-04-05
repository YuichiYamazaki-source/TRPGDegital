from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from typing import Any, Literal

HISTORY_WINDOW = 20

CheckDifficulty = Literal["regular", "hard", "extreme"]
CheckKind = Literal["skill", "san"]


def _resource_values(value: Any) -> tuple[int, int]:
    if isinstance(value, dict):
        current = int(value.get("current", value.get("max", 0)))
        maximum = int(value.get("max", current))
        return current, maximum

    if value is None:
        return 0, 0

    current = int(value)
    return current, current


def _get_resource_pair(character: dict[str, Any], key: str) -> tuple[int, int]:
    current, maximum = _resource_values(character.get(key))
    if maximum:
        return current, maximum

    derived = character.get("derived", {})
    if isinstance(derived, dict):
        current, maximum = _resource_values(derived.get(key))
        if maximum:
            return current, maximum

    return 0, 0


@dataclass
class PlayerState:
    user_id: str
    display_name: str
    character_id: str
    character_name: str
    occupation: str
    hp: int
    hp_max: int
    mp: int
    mp_max: int
    san: int
    san_max: int
    inventory: list[str] = field(default_factory=list)
    status_effects: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "user_id": self.user_id,
            "display_name": self.display_name,
            "character_id": self.character_id,
            "character_name": self.character_name,
            "occupation": self.occupation,
            "hp": self.hp,
            "hp_max": self.hp_max,
            "mp": self.mp,
            "mp_max": self.mp_max,
            "san": self.san,
            "san_max": self.san_max,
            "inventory": list(self.inventory),
            "status_effects": list(self.status_effects),
            "notes": list(self.notes),
        }


@dataclass
class EnvironmentState:
    scene: str = "導入"
    scene_summary: str = ""
    scene_highlights: list[str] = field(default_factory=list)
    scene_goal: str = ""
    unresolved_threads: list[str] = field(default_factory=list)
    clues: list[str] = field(default_factory=list)
    shared_inventory: list[str] = field(default_factory=list)
    flags: dict[str, bool] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "scene": self.scene,
            "scene_summary": self.scene_summary,
            "scene_highlights": list(self.scene_highlights),
            "scene_goal": self.scene_goal,
            "unresolved_threads": list(self.unresolved_threads),
            "clues": list(self.clues),
            "shared_inventory": list(self.shared_inventory),
            "flags": dict(self.flags),
            "notes": list(self.notes),
        }


@dataclass
class NPCState:
    name: str
    status: str = "不明"
    location: str = "不明"
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status,
            "location": self.location,
            "notes": list(self.notes),
        }


@dataclass
class PendingCheck:
    check_id: str
    kind: CheckKind
    character_id: str
    character_name: str
    skill_name: str | None
    base_value: int
    target_value: int
    difficulty: CheckDifficulty
    reason: str
    success_san_loss: str | None = None
    failure_san_loss: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "check_id": self.check_id,
            "kind": self.kind,
            "character_id": self.character_id,
            "character_name": self.character_name,
            "skill_name": self.skill_name,
            "base_value": self.base_value,
            "target_value": self.target_value,
            "difficulty": self.difficulty,
            "reason": self.reason,
            "success_san_loss": self.success_san_loss,
            "failure_san_loss": self.failure_san_loss,
        }


@dataclass
class Session:
    session_id: str
    channel_id: str
    scenario_id: str
    characters: dict[str, dict[str, Any]]
    players: dict[str, PlayerState]
    history: list[dict[str, str]] = field(default_factory=list)
    environment: EnvironmentState = field(default_factory=EnvironmentState)
    npcs: dict[str, NPCState] = field(default_factory=dict)
    proposed_check: PendingCheck | None = None
    pending_check: PendingCheck | None = None
    chat_lock: asyncio.Lock = field(default_factory=asyncio.Lock, repr=False)

    def to_state_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "channel_id": self.channel_id,
            "scenario_id": self.scenario_id,
            "players": [player.to_dict() for player in self.players.values()],
            "environment": self.environment.to_dict(),
            "npcs": [npc.to_dict() for npc in self.npcs.values()],
            "proposed_check": self.proposed_check.to_dict() if self.proposed_check else None,
            "pending_check": self.pending_check.to_dict() if self.pending_check else None,
            "history_size": len(self.history),
        }

    def find_player(self, character_id: str) -> PlayerState | None:
        return self.players.get(character_id)

    def find_player_by_name(self, character_name: str) -> PlayerState | None:
        normalized = character_name.strip().strip("[]")
        for player in self.players.values():
            if player.character_name == normalized or player.display_name == normalized:
                return player
        return None


def build_player_state(character: dict[str, Any], player_info: dict[str, str]) -> PlayerState:
    hp, hp_max = _get_resource_pair(character, "hp")
    mp, mp_max = _get_resource_pair(character, "mp")
    san, san_max = _get_resource_pair(character, "san")

    inventory = character.get("inventory")
    if not isinstance(inventory, list):
        inventory = []

    return PlayerState(
        user_id=player_info["user_id"],
        display_name=player_info["display_name"],
        character_id=character["id"],
        character_name=character["name"],
        occupation=str(character.get("occupation") or character.get("meta", {}).get("occupation", "不明")),
        hp=hp,
        hp_max=hp_max,
        mp=mp,
        mp_max=mp_max,
        san=san,
        san_max=san_max if san_max else san,
        inventory=[str(item) for item in inventory],
    )


class SessionManager:
    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}
        self._channel_to_session: dict[str, str] = {}

    def create_session(
        self,
        channel_id: str,
        scenario_id: str,
        characters: dict[str, dict[str, Any]],
        players: list[dict[str, str]],
    ) -> str:
        if channel_id in self._channel_to_session:
            raise ValueError("Session already exists for this channel")

        session_id = str(uuid.uuid4())
        player_states = {
            player["character_id"]: build_player_state(characters[player["character_id"]], player)
            for player in players
        }

        self._sessions[session_id] = Session(
            session_id=session_id,
            channel_id=channel_id,
            scenario_id=scenario_id,
            characters=characters,
            players=player_states,
        )
        self._channel_to_session[channel_id] = session_id
        return session_id

    def get_session(self, session_id: str) -> Session | None:
        return self._sessions.get(session_id)

    def add_history_entry(self, session_id: str, role: str, content: str) -> None:
        session = self._sessions.get(session_id)
        if session is None:
            return

        session.history.append({"role": role, "content": content})

        max_messages = HISTORY_WINDOW * 2
        if len(session.history) > max_messages:
            session.history = session.history[-max_messages:]

    def add_message(
        self,
        session_id: str,
        character_name: str,
        message: str,
        reply: str,
    ) -> None:
        self.add_history_entry(session_id, "user", f"[{character_name}]: {message}")
        self.add_history_entry(session_id, "assistant", reply)

    def delete_session(self, session_id: str) -> bool:
        session = self._sessions.pop(session_id, None)
        if session is None:
            return False

        self._channel_to_session.pop(session.channel_id, None)
        return True
