from fastapi import FastAPI, HTTPException

app = FastAPI(title="CoC AI GM API")

WEAPON_TEMPLATES = {
    "fist": {
        "name": "素手",
        "skill": "こぶし",
        "damage": "1d3+db",
        "range": "接触",
        "attacks_per_round": 1,
        "malfunction": 100
    },
    "knife": {
        "name": "ナイフ",
        "skill": "ナイフ",
        "damage": "1d4+db",
        "range": "接触",
        "attacks_per_round": 1,
        "malfunction": 100
    },
    "pistol": {
        "name": "拳銃",
        "skill": "拳銃",
        "damage": "1d10",
        "range": "15m",
        "attacks_per_round": 1,
        "ammo": 6,
        "malfunction": 99
    },
    "shotgun": {
        "name": "ショットガン",
        "skill": "ショットガン",
        "damage": "4d6/2d6/1d6",
        "range": "10/20/50m",
        "attacks_per_round": 1,
        "ammo": 2,
        "malfunction": 100
    }
}