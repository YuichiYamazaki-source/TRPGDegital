from __future__ import annotations

import json
import re
import random
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from gm import GMEngine
from session import SessionManager

app = FastAPI(title="CoC AI GM API")

session_manager = SessionManager()
gm_engine = GMEngine()

# ===== ディレクトリ =====

CHARACTERS_DIR = "characters"
SCENARIOS_DIR = "scenarios"
CHAR_BUILD_DIR = "character_builds"

CHARACTERS_DIR.mkdir(parents=True, exist_ok=True)
SCENARIOS_DIR.mkdir(parents=True, exist_ok=True)
CHAR_BUILD_DIR.mkdir(parents=True, exist_ok=True)


# ===== 既存ロード =====

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

# ===== キャラビルド用 =====

def get_build_path(build_id: str) -> Path:
    return CHAR_BUILD_DIR / f"{build_id}.json"


def save_build(build_id: str, data: dict):
   get_build_path(build_id).write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


def load_build(user_id: str) -> dict:
    path = get_build_path(user_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Build not found")
    return json.loads(path.read_text(encoding="utf-8"))


def create_empty_character(owner: str):
    return {
        "id": str(uuid.uuid4()),
        "owner": owner,
        "step": 1,
        "remaining": 0,
        "character": {
            "meta": {},
            "attributes": {},
            "derived": {},
            "skills": {},
            "inventory": [],
            "background": {
                "appearance": "",
                "ideology": "",
                "important_people": "",
                "meaningful_places": "",
                "treasured_possessions": "",
                "traits": "",
                "injuries": "",
                "phobias": "",
                "tomes": "",
                "encounters": ""
            }
        }
    }


# ===== ダイス =====

def roll_3d6x5():
    return sum(random.randint(1, 6) for _ in range(3)) * 5


def roll_attributes():
    return {
        "STR": roll_3d6x5(),
        "CON": roll_3d6x5(),
        "SIZ": roll_3d6x5(),
        "DEX": roll_3d6x5(),
        "APP": roll_3d6x5(),
        "INT": roll_3d6x5(),
        "POW": roll_3d6x5(),
        "EDU": roll_3d6x5()
    }


# ===== 職業 =====

OCCUPATIONS = {
    "記者": {"skills": {"言いくるめ": 20, "図書館": 20, "心理学": 20, "目星": 20}},
    "警察官": {"skills": {"威圧": 20, "射撃（拳銃）": 20, "法律": 20, "追跡": 20}}
}


# ===== Request / Response =====

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


# ===== 既存API =====

@app.get("/scenarios", response_model=list[ScenarioItem])
def get_scenarios():
    return load_scenario_list()


@app.get("/characters")
def get_characters():
    return list(CHARACTERS.values())


@app.post("/session", status_code=201, response_model=SessionCreateResponse)
def create_session(req: SessionCreateRequest):
    scenario_path = SCENARIOS_DIR / f"{req.scenario_id}.md"
    if not scenario_path.exists():
        raise HTTPException(status_code=400, detail="Scenario not found")

    for cid in req.character_ids:
        if cid not in CHARACTERS:
            raise HTTPException(status_code=400, detail="Character not found")

    selected = {cid: CHARACTERS[cid] for cid in req.character_ids}
    session_id = session_manager.create_session(req.channel_id, req.scenario_id, selected)

    return {"session_id": session_id, "characters": list(selected.values())}


@app.post("/session/{session_id}/chat", response_model=ChatResponse)
async def chat(session_id: str, req: ChatRequest):
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
def end_session(session_id: str):
    if not session_manager.delete_session(session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    return {"message": "Session ended"}


# ===== キャラ作成API =====

@app.post("/character/start")
def start_character(user_id: str):
    data = create_empty_character(user_id)
    save_build(data["id"], data)
    return data


@app.post("/character/roll")
def roll_character(build_id: str):
    data = load_build(build_id)

    attrs = roll_attributes()
    data["character"]["attributes"] = attrs

    data["character"]["derived"] = {
        "hp": (attrs["CON"] + attrs["SIZ"]) // 10,
        "mp": attrs["POW"] // 5,
        "san": attrs["POW"]
    }

    data["step"] = 2
    save_build(build_id, data)
    return data


@app.post("/character/job")
def select_job(build_id: str, job_name: str):
    data = load_build(build_id)

    if job_name not in OCCUPATIONS:
        raise HTTPException(status_code=400, detail="Invalid job")

    for k, v in OCCUPATIONS[job_name]["skills"].items():
        data["character"]["skills"][k] = v

    edu = data["character"]["attributes"]["EDU"]
    data["remaining"] = edu * 4

    data["character"]["meta"]["occupation"] = job_name
    data["step"] = 3

    save_build(build_id, data)
    return data


@app.post("/character/skill")
def add_skill(build_id: str, skill_name: str, value: int):
    data = load_build(build_id)

    if value > data["remaining"]:
        return {
            "error": "ポイント不足",
            "remaining": data["remaining"]
        }

    skills = data["character"]["skills"]
    skills[skill_name] = skills.get(skill_name, 0) + value

    data["remaining"] -= value

    save_build(build_id, data)
    return data


@app.post("/character/buy")
def buy_item(build_id: str, item: str):
    data = load_build(build_id)

    data["character"]["inventory"].append(item)

    save_build(build_id, data)
    return data


class CharacterMetaRequest(BaseModel):
    build_id: str
    name: str
    age: str = ""
    gender: str = ""
    appearance: str = ""
    ideology: str = ""
    important_people: str = ""
    meaningful_places: str = ""
    treasured_possessions: str = ""
    traits: str = ""
    injuries: str = ""
    phobias: str = ""
    tomes: str = ""
    encounters: str = ""


@app.post("/character/meta")
def finalize_character(req: CharacterMetaRequest):
    data = load_build(req.build_id)
    char = data["character"]

    # --- メタ情報 ---
    char["meta"] = {
        "name": req.name,
        "age": req.age,
        "gender": req.gender
    }

    # --- バックストーリー ---
    char["background"] = {
        "appearance": req.appearance,
        "ideology": req.ideology,
        "important_people": req.important_people,
        "meaningful_places": req.meaningful_places,
        "treasured_possessions": req.treasured_possessions,
        "traits": req.traits,
        "injuries": req.injuries,
        "phobias": req.phobias,
        "tomes": req.tomes,
        "encounters": req.encounters
    }

    save_build(req.build_id, data)

    # 必要なら完成キャラとして保存
    return {
        "id": data["id"],
        "name": req.name
    }