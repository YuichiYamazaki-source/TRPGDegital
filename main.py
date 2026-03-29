from __future__ import annotations

import json
import re
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from gm import GMEngine
from session import SessionManager

app = FastAPI(title="CoC AI GM API")

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


# --- Request / Response models ---


class SessionCreateRequest(BaseModel):
    channel_id: str
    scenario_id: str
    character_ids: list[str]


class ChatRequest(BaseModel):
    character_id: str
    message: str


class SessionCreateResponse(BaseModel):
    session_id: str
    characters: list[dict]


class ChatResponse(BaseModel):
    reply: str
    session_id: str


class ScenarioItem(BaseModel):
    id: str
    title: str


class MessageResponse(BaseModel):
    message: str


# --- Endpoints ---


@app.get("/scenarios", response_model=list[ScenarioItem])
def get_scenarios() -> list[dict[str, str]]:
    """Return the list of available scenarios."""
    return load_scenario_list()


@app.get("/characters")
def get_characters() -> list[dict]:
    """Return the list of selectable characters."""
    return list(CHARACTERS.values())


@app.post("/session", status_code=201, response_model=SessionCreateResponse)
def create_session(req: SessionCreateRequest) -> dict:
    """Start a new session with a scenario and selected characters."""
    scenario_path = SCENARIOS_DIR / f"{req.scenario_id}.md"
    if not scenario_path.exists():
        raise HTTPException(status_code=400, detail=f"Scenario '{req.scenario_id}' not found")

    for cid in req.character_ids:
        if cid not in CHARACTERS:
            raise HTTPException(status_code=400, detail=f"Character '{cid}' not found")

    selected = {cid: CHARACTERS[cid] for cid in req.character_ids}
    session_id = session_manager.create_session(req.channel_id, req.scenario_id, selected)
    return {"session_id": session_id, "characters": list(selected.values())}


@app.post("/session/{session_id}/chat", response_model=ChatResponse)
async def chat(session_id: str, req: ChatRequest) -> dict:
    """Send a player message and receive the KP reply."""
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if req.character_id not in session.characters:
        raise HTTPException(status_code=400, detail="Character not in this session")

    character = session.characters[req.character_id]
    reply = await gm_engine.respond(session, character, req.message)
    session_manager.add_message(session_id, character["name"], req.message, reply)

    return {"reply": reply, "session_id": session_id}


@app.delete("/session/{session_id}", response_model=MessageResponse)
def end_session(session_id: str) -> dict:
    """End a session and clear its history."""
    if not session_manager.delete_session(session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    return {"message": "Session ended"}
