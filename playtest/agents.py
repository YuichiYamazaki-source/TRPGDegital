from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any, Protocol

from openai import AsyncOpenAI

from .models import PlaytestConfig, TurnRecord


class PlayerAgent(Protocol):
    async def choose_scene_action(self, config: PlaytestConfig, state: dict[str, Any], turns: list[TurnRecord]) -> str: ...

    async def choose_check_response(self, config: PlaytestConfig, state: dict[str, Any], turns: list[TurnRecord]) -> str: ...

    async def choose_roll(self, config: PlaytestConfig, state: dict[str, Any], turns: list[TurnRecord]) -> int | None: ...


def _recent_transcript(turns: list[TurnRecord], limit: int = 6) -> list[dict[str, Any]]:
    recent = turns[-limit:]
    return [
        {
            "turn": turn.turn_index,
            "kind": turn.kind,
            "player_message": turn.player_message,
            "player_decision": turn.player_decision,
            "player_roll": turn.player_roll,
            "gm_reply": turn.gm_reply,
            "scene": turn.state.get("environment", {}).get("scene"),
        }
        for turn in recent
    ]


@dataclass
class ScriptedPlayerAgent:
    """Simple deterministic player for tests and local smoke runs."""

    scripted_messages: list[str] = field(default_factory=list)
    accept_checks: bool = True

    async def choose_scene_action(self, config: PlaytestConfig, state: dict[str, Any], turns: list[TurnRecord]) -> str:
        if self.scripted_messages:
            return self.scripted_messages.pop(0)

        environment = state.get("environment", {})
        scene = environment.get("scene", "導入")
        threads = environment.get("unresolved_threads") or []
        highlights = environment.get("scene_highlights") or []

        if scene == "導入":
            return "周囲の様子と、すぐに気づける異変を確認します。"
        if "玄関" in scene:
            if threads:
                return f"{threads[0]}を確かめるために周囲を調べます。"
            if highlights:
                return f"{highlights[0]}を詳しく見ます。"
            return "玄関ホールで気になる痕跡を探します。"
        if "書斎" in scene:
            return "机の上の書類と本棚の様子を調べます。"
        if "地下室" in scene:
            return "祭壇と桐島の様子を慎重に観察します。"
        return "いま気になる場所や痕跡を詳しく調べます。"

    async def choose_check_response(self, config: PlaytestConfig, state: dict[str, Any], turns: list[TurnRecord]) -> str:
        return "accept" if self.accept_checks else "decline"

    async def choose_roll(self, config: PlaytestConfig, state: dict[str, Any], turns: list[TurnRecord]) -> int | None:
        return None


class OpenAIPlayerAgent:
    """LLM-backed investigator that produces structured actions."""

    def __init__(self, model: str | None = None) -> None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is not set in environment")
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model or os.getenv("PLAYTEST_PLAYER_MODEL", "gpt-4o-mini")

    async def _complete_json(self, system_prompt: str, user_payload: dict[str, Any]) -> dict[str, Any]:
        response = await self.client.chat.completions.create(
            model=self.model,
            temperature=0.2,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
            ],
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content or "{}"
        payload = json.loads(content)
        if not isinstance(payload, dict):
            raise ValueError("Player agent returned non-object JSON")
        return payload

    async def choose_scene_action(self, config: PlaytestConfig, state: dict[str, Any], turns: list[TurnRecord]) -> str:
        payload = await self._complete_json(
            (
                "あなたはTRPGのプレイヤーです。"
                "与えられた状況から、次に試したい自然な行動を1つだけ決めてください。"
                "返答は JSON オブジェクトで、message キーにだけ短い行動宣言を入れてください。"
                "選択肢の羅列はせず、探索者として自由に動いてください。"
            ),
            {
                "character_id": config.character_id,
                "scenario_id": config.scenario_id,
                "state": state,
                "recent_turns": _recent_transcript(turns),
            },
        )
        message = str(payload.get("message", "")).strip()
        if not message:
            raise ValueError("Player agent did not return a message")
        return message

    async def choose_check_response(self, config: PlaytestConfig, state: dict[str, Any], turns: list[TurnRecord]) -> str:
        payload = await self._complete_json(
            (
                "あなたはTRPGのプレイヤーです。"
                "提案された判定に対して accept か decline のどちらかを決めてください。"
                "返答は JSON オブジェクトで、decision キーに accept か decline を入れてください。"
            ),
            {
                "character_id": config.character_id,
                "scenario_id": config.scenario_id,
                "state": state,
                "recent_turns": _recent_transcript(turns),
            },
        )
        decision = str(payload.get("decision", "")).strip().lower()
        if decision not in {"accept", "decline"}:
            raise ValueError("Player agent returned an invalid decision")
        return decision

    async def choose_roll(self, config: PlaytestConfig, state: dict[str, Any], turns: list[TurnRecord]) -> int | None:
        return None
