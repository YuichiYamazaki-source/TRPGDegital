from __future__ import annotations

import json
import logging
import re
import uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from dice import roll_expression, roll_percentile
from gm import GMEngine
from session import NPCState, PendingCheck, Session, SessionManager

app = FastAPI(title="CoC AI GM API")

log = logging.getLogger(__name__)

session_manager = SessionManager()
gm_engine = GMEngine()

CHARACTERS_DIR = Path("characters")
SCENARIOS_DIR = Path("scenarios")


def load_characters() -> dict[str, dict]:
    characters: dict[str, dict] = {}
    for f in CHARACTERS_DIR.glob("*.json"):
        char = json.loads(f.read_text(encoding="utf-8"))
        characters[char["id"]] = char
    return characters


def load_scenario_list() -> list[dict[str, str]]:
    scenarios: list[dict[str, str]] = []
    for f in SCENARIOS_DIR.glob("*.md"):
        text = f.read_text(encoding="utf-8")
        match = re.search(r"^#\s+(.+)", text, re.MULTILINE)
        title = match.group(1).strip() if match else f.stem
        scenarios.append({"id": f.stem, "title": title})
    return scenarios


CHARACTERS = load_characters()


def _model_to_dict(model: BaseModel) -> dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()


def _extend_unique(target: list[str], values: Any) -> None:
    if not isinstance(values, list):
        return

    for value in values:
        item = str(value)
        if item not in target:
            target.append(item)


def _string_list(values: Any) -> list[str] | None:
    if not isinstance(values, list):
        return None
    return [str(value) for value in values]


def _coerce_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "on"}:
            return True
        if normalized in {"false", "0", "no", "off"}:
            return False
    return None


def _get_skill_value(character: dict[str, Any], skill_name: str) -> int | None:
    skills = character.get("skills", {})
    if not isinstance(skills, dict):
        return None

    value = skills.get(skill_name)
    if isinstance(value, int):
        return value
    if isinstance(value, dict) and isinstance(value.get("value"), int):
        return int(value["value"])
    return None


def _target_for_difficulty(base_value: int, difficulty: str) -> int:
    if difficulty == "hard":
        return max(1, base_value // 2)
    if difficulty == "extreme":
        return max(1, base_value // 5)
    return base_value


def _evaluate_roll(roll: int, pending: PendingCheck) -> str:
    if roll == 1:
        return "critical"
    if 96 <= roll <= 100:
        return "fumble"
    if roll <= max(1, pending.base_value // 5):
        return "extreme"
    if roll <= max(1, pending.base_value // 2):
        return "hard"
    if roll <= pending.target_value:
        return "success"
    return "failure"


def _outcome_label(outcome: str) -> str:
    labels = {
        "critical": "クリティカル",
        "extreme": "スペシャル成功",
        "hard": "ハード成功",
        "success": "成功",
        "failure": "失敗",
        "fumble": "ファンブル",
    }
    return labels.get(outcome, outcome)


def _parse_session_players(req: "SessionCreateRequest") -> list[dict[str, str]]:
    if req.players:
        players = []
        seen_users: set[str] = set()
        seen_characters: set[str] = set()

        for player in req.players:
            payload = _model_to_dict(player)
            character_id = payload["character_id"]
            if character_id in seen_characters:
                raise HTTPException(status_code=400, detail=f"Character '{character_id}' selected twice")
            if payload["user_id"] in seen_users:
                raise HTTPException(status_code=400, detail=f"User '{payload['user_id']}' joined twice")
            if character_id not in CHARACTERS:
                raise HTTPException(status_code=400, detail=f"Character '{character_id}' not found")

            seen_users.add(payload["user_id"])
            seen_characters.add(character_id)
            players.append(payload)

        return players

    if req.character_ids:
        players = []
        for character_id in req.character_ids:
            if character_id not in CHARACTERS:
                raise HTTPException(status_code=400, detail=f"Character '{character_id}' not found")
            players.append(
                {
                    "user_id": character_id,
                    "display_name": CHARACTERS[character_id]["name"],
                    "character_id": character_id,
                }
            )
        return players

    raise HTTPException(status_code=400, detail="At least one player is required")


def _apply_state_update(session: Session, update: dict[str, Any] | None) -> None:
    if not isinstance(update, dict):
        return

    environment = session.environment

    scene = update.get("scene")
    scene_changed = False
    if isinstance(scene, str) and scene.strip():
        scene_changed = environment.scene != scene.strip()
        environment.scene = scene.strip()

    scene_summary = update.get("scene_summary")
    if isinstance(scene_summary, str) and scene_summary.strip():
        environment.scene_summary = scene_summary.strip()

    scene_highlights = _string_list(update.get("scene_highlights"))
    if scene_highlights is not None:
        environment.scene_highlights = scene_highlights
    elif scene_changed:
        environment.scene_highlights = []

    scene_goal = update.get("scene_goal")
    if isinstance(scene_goal, str):
        environment.scene_goal = scene_goal.strip()
    elif scene_changed:
        environment.scene_goal = ""

    unresolved_threads = _string_list(update.get("unresolved_threads"))
    if unresolved_threads is not None:
        environment.unresolved_threads = unresolved_threads
    elif scene_changed:
        environment.unresolved_threads = []

    _extend_unique(environment.clues, update.get("clues_added"))
    _extend_unique(environment.shared_inventory, update.get("shared_inventory_added"))
    _extend_unique(environment.notes, update.get("notes_added"))

    flags = update.get("flags")
    if isinstance(flags, dict):
        for key, raw_value in flags.items():
            value = _coerce_bool(raw_value)
            if value is not None:
                environment.flags[str(key)] = value

    npcs = update.get("npcs")
    if isinstance(npcs, dict):
        for name, npc_update in npcs.items():
            npc_name = str(name)
            existing = session.npcs.get(npc_name)
            if existing is None:
                existing = session.npcs[npc_name] = NPCState(name=npc_name)

            if isinstance(npc_update, dict):
                status = npc_update.get("status")
                location = npc_update.get("location")
                if isinstance(status, str) and status.strip():
                    existing.status = status.strip()
                if isinstance(location, str) and location.strip():
                    existing.location = location.strip()
                _extend_unique(existing.notes, npc_update.get("notes_added"))

    players = update.get("players")
    if isinstance(players, dict):
        for player_key, player_update in players.items():
            player = session.players.get(str(player_key)) or session.find_player_by_name(str(player_key))
            if player is None or not isinstance(player_update, dict):
                continue

            _extend_unique(player.status_effects, player_update.get("status_effects_added"))
            _extend_unique(player.notes, player_update.get("notes_added"))


def _build_pending_check(
    session: Session,
    payload: dict[str, Any] | None,
    default_character_id: str,
) -> PendingCheck | None:
    if not isinstance(payload, dict):
        return None

    kind = str(payload.get("type", payload.get("kind", ""))).strip().lower()
    if kind not in {"skill", "san"}:
        return None

    actor = payload.get("actor") or payload.get("character_name")
    player = None
    if isinstance(actor, str) and actor.strip():
        player = session.find_player_by_name(actor.strip())

    character_id = payload.get("character_id")
    if player is None and isinstance(character_id, str) and character_id:
        player = session.find_player(character_id)

    if player is None:
        player = session.find_player(default_character_id)

    if player is None:
        raise ValueError("Pending check actor could not be resolved")

    difficulty = str(payload.get("difficulty", "regular")).strip().lower()
    if difficulty not in {"regular", "hard", "extreme"}:
        difficulty = "regular"

    reason = str(payload.get("reason", "")).strip()
    raw_target = payload.get("target")
    explicit_target: int | None = None
    if raw_target is not None:
        explicit_target = int(raw_target)

    if kind == "skill":
        skill_name = str(payload.get("skill", payload.get("skill_name", ""))).strip()
        if not skill_name:
            raise ValueError("Skill check is missing skill name")

        character = session.characters[player.character_id]
        base_value = _get_skill_value(character, skill_name)
        if base_value is None:
            if explicit_target is None:
                raise ValueError(f"Skill '{skill_name}' not found on character '{player.character_name}'")
            base_value = explicit_target

        if explicit_target is not None:
            target_value = explicit_target
            if target_value == max(1, base_value // 5):
                difficulty = "extreme"
            elif target_value == max(1, base_value // 2):
                difficulty = "hard"
            elif target_value == base_value:
                difficulty = "regular"
        else:
            target_value = _target_for_difficulty(base_value, difficulty)

        return PendingCheck(
            check_id=str(uuid.uuid4()),
            kind="skill",
            character_id=player.character_id,
            character_name=player.character_name,
            skill_name=skill_name,
            base_value=base_value,
            target_value=target_value,
            difficulty=difficulty,
            reason=reason,
        )

    return PendingCheck(
        check_id=str(uuid.uuid4()),
        kind="san",
        character_id=player.character_id,
        character_name=player.character_name,
        skill_name=None,
        base_value=player.san,
        target_value=explicit_target if explicit_target is not None else player.san,
        difficulty="regular",
        reason=reason,
        success_san_loss=str(payload.get("success_loss", "0")),
        failure_san_loss=str(payload.get("failure_loss", "1D3")),
    )


def _resolve_pending_check(session: Session, pending: PendingCheck, roll: int) -> dict[str, Any]:
    player = session.find_player(pending.character_id)
    if player is None:
        raise HTTPException(status_code=404, detail="Player not found")

    outcome = _evaluate_roll(roll, pending)
    result = {
        "kind": pending.kind,
        "character_id": pending.character_id,
        "character_name": pending.character_name,
        "skill_name": pending.skill_name,
        "difficulty": pending.difficulty,
        "target_value": pending.target_value,
        "base_value": pending.base_value,
        "roll": roll,
        "outcome": outcome,
        "outcome_label": _outcome_label(outcome),
        "reason": pending.reason,
        "san_loss": 0,
        "current_san": player.san,
    }

    if pending.kind == "san":
        loss_expression = pending.success_san_loss if outcome in {"critical", "extreme", "hard", "success"} else pending.failure_san_loss
        rolled_loss = roll_expression(loss_expression or "0")
        loss = max(0, rolled_loss.total)
        player.san = max(0, player.san - loss)
        result["san_loss"] = loss
        result["san_loss_expression"] = loss_expression
        result["current_san"] = player.san
        result["resolution_message"] = (
            f"判定結果: {pending.character_name} のSANチェックは {roll}/{pending.target_value} で"
            f"{_outcome_label(outcome)}。SANを{loss}失い、現在SANは{player.san}。"
        )
        return result

    result["resolution_message"] = (
        f"判定結果: {pending.character_name} の【{pending.skill_name}】判定は {roll}/{pending.target_value} で"
        f"{_outcome_label(outcome)}。"
    )
    return result


class SessionPlayerRequest(BaseModel):
    user_id: str
    display_name: str
    character_id: str


class SessionCreateRequest(BaseModel):
    channel_id: str
    scenario_id: str
    character_ids: list[str] | None = None
    players: list[SessionPlayerRequest] | None = None


class ChatRequest(BaseModel):
    character_id: str
    message: str


class CheckResolveRequest(BaseModel):
    character_id: str
    roll: int | None = None


class CheckRespondRequest(BaseModel):
    character_id: str
    decision: str


class SessionCreateResponse(BaseModel):
    session_id: str
    characters: list[dict]


class ChatResponse(BaseModel):
    reply: str
    session_id: str
    proposed_check: dict[str, Any] | None = None
    pending_check: dict[str, Any] | None = None


class CheckResolveResponse(BaseModel):
    reply: str
    session_id: str
    check_result: dict[str, Any]
    proposed_check: dict[str, Any] | None = None
    pending_check: dict[str, Any] | None = None


class CheckRespondResponse(BaseModel):
    message: str
    session_id: str
    proposed_check: dict[str, Any] | None = None
    pending_check: dict[str, Any] | None = None


class ScenarioItem(BaseModel):
    id: str
    title: str


class MessageResponse(BaseModel):
    message: str


@app.get("/scenarios", response_model=list[ScenarioItem])
def get_scenarios() -> list[dict[str, str]]:
    return load_scenario_list()


@app.get("/characters")
def get_characters() -> list[dict]:
    return list(CHARACTERS.values())


@app.post("/session", status_code=201, response_model=SessionCreateResponse)
def create_session(req: SessionCreateRequest) -> dict[str, Any]:
    scenario_path = SCENARIOS_DIR / f"{req.scenario_id}.md"
    if not scenario_path.exists():
        raise HTTPException(status_code=400, detail=f"Scenario '{req.scenario_id}' not found")

    players = _parse_session_players(req)
    selected = {player["character_id"]: CHARACTERS[player["character_id"]] for player in players}

    try:
        session_id = session_manager.create_session(req.channel_id, req.scenario_id, selected, players)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return {"session_id": session_id, "characters": list(selected.values())}


@app.get("/session/{session_id}/state")
def get_session_state(session_id: str) -> dict[str, Any]:
    session = session_manager.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return session.to_state_dict()


@app.post("/session/{session_id}/chat", response_model=ChatResponse)
async def chat(session_id: str, req: ChatRequest) -> dict[str, Any]:
    session = session_manager.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    if req.character_id not in session.characters:
        raise HTTPException(status_code=400, detail="Character not in this session")

    character = session.characters[req.character_id]

    async with session.chat_lock:
        if session.pending_check is not None:
            raise HTTPException(status_code=409, detail="Resolve the pending check before continuing the scene")
        if session.proposed_check is not None:
            raise HTTPException(status_code=409, detail="Respond to the proposed check before continuing the scene")

        turn = await gm_engine.respond(session, character, req.message)
        _apply_state_update(session, turn.state_update)

        proposed_check = None
        if turn.proposed_check is not None:
            try:
                proposed_check = _build_pending_check(session, turn.proposed_check, req.character_id)
            except ValueError:
                log.exception("Failed to build proposed check from GM response")
            session.proposed_check = proposed_check
        else:
            session.proposed_check = None

        pending_check = None
        if turn.pending_check is not None:
            try:
                pending_check = _build_pending_check(session, turn.pending_check, req.character_id)
            except ValueError:
                log.exception("Failed to build pending check from GM response")
            session.pending_check = pending_check
        else:
            session.pending_check = None

        session_manager.add_message(session_id, character["name"], req.message, turn.reply)

    return {
        "reply": turn.reply,
        "session_id": session_id,
        "proposed_check": session.proposed_check.to_dict() if session.proposed_check else None,
        "pending_check": session.pending_check.to_dict() if session.pending_check else None,
    }


@app.post("/session/{session_id}/check/respond", response_model=CheckRespondResponse)
async def respond_to_check(session_id: str, req: CheckRespondRequest) -> dict[str, Any]:
    session = session_manager.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    async with session.chat_lock:
        proposed = session.proposed_check
        if proposed is None:
            raise HTTPException(status_code=409, detail="There is no proposed check to respond to")

        if req.character_id != proposed.character_id:
            raise HTTPException(status_code=403, detail="This proposed check belongs to another player")

        decision = req.decision.strip().lower()
        if decision in {"accept", "yes", "ok", "confirm"}:
            session_manager.add_history_entry(session_id, "user", f"[{proposed.character_name}]: 判定します")
            session.pending_check = proposed
            session.proposed_check = None
            return {
                "message": "判定を開始します。",
                "session_id": session_id,
                "proposed_check": None,
                "pending_check": session.pending_check.to_dict(),
            }

        if decision in {"decline", "no", "cancel", "skip"}:
            session_manager.add_history_entry(session_id, "user", f"[{proposed.character_name}]: 判定は見送ります")
            session.proposed_check = None
            return {
                "message": "判定は見送りました。別の行動を選べます。",
                "session_id": session_id,
                "proposed_check": None,
                "pending_check": None,
            }

        raise HTTPException(status_code=400, detail="Decision must be accept or decline")


@app.post("/session/{session_id}/check/resolve", response_model=CheckResolveResponse)
async def resolve_check(session_id: str, req: CheckResolveRequest) -> dict[str, Any]:
    session = session_manager.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    async with session.chat_lock:
        pending = session.pending_check
        if pending is None:
            raise HTTPException(status_code=409, detail="There is no pending check to resolve")

        if req.character_id != pending.character_id:
            raise HTTPException(status_code=403, detail="This pending check belongs to another player")

        roll = req.roll if req.roll is not None else roll_percentile()
        if roll < 1 or roll > 100:
            raise HTTPException(status_code=400, detail="Roll must be between 1 and 100")

        result = _resolve_pending_check(session, pending, roll)
        session.pending_check = None

        character = session.characters[req.character_id]
        turn = await gm_engine.respond(session, character, result["resolution_message"])
        _apply_state_update(session, turn.state_update)

        next_proposed_check = None
        if turn.proposed_check is not None:
            try:
                next_proposed_check = _build_pending_check(session, turn.proposed_check, req.character_id)
            except ValueError:
                log.exception("Failed to build follow-up proposed check from GM response")
            session.proposed_check = next_proposed_check
        else:
            session.proposed_check = None

        next_pending_check = None
        if turn.pending_check is not None:
            try:
                next_pending_check = _build_pending_check(session, turn.pending_check, req.character_id)
            except ValueError:
                log.exception("Failed to build follow-up pending check from GM response")
            session.pending_check = next_pending_check
        else:
            session.pending_check = None

        session_manager.add_message(session_id, character["name"], result["resolution_message"], turn.reply)

    return {
        "reply": turn.reply,
        "session_id": session_id,
        "check_result": result,
        "proposed_check": session.proposed_check.to_dict() if session.proposed_check else None,
        "pending_check": session.pending_check.to_dict() if session.pending_check else None,
    }


@app.delete("/session/{session_id}", response_model=MessageResponse)
def end_session(session_id: str) -> dict[str, str]:
    if not session_manager.delete_session(session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    return {"message": "Session ended"}
