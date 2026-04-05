from fastapi import FastAPI
import random
import json
import os

app = FastAPI()

DATA_DIR = "../characters"

# フォルダなければ作成
os.makedirs(DATA_DIR, exist_ok=True)

# ===== データ =====

occupations = {
    "記者": {
        "skills": {
            "言いくるめ": 20,
            "図書館": 20,
            "心理学": 20,
            "目星": 20
        }
    }
}

shop_items = {
    "ナイフ": 1000,
    "懐中電灯": 2000
}

# ===== ユーティリティ =====

def get_file_path(user_id: str):
    return os.path.join(DATA_DIR, f"{user_id}.json")


def save_character(user_id: str, data: dict):
    with open(get_file_path(user_id), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_character(user_id: str):
    path = get_file_path(user_id)
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ===== 初期キャラ =====

def create_empty_character():
    return {
        "step": 1,
        "remaining": 0,
        "character": {
            "meta": {},
            "attributes": {},
            "derived": {},
            "combat": {
                "dodge": 0,
                "weapons": []
            },
            "skills": {},
            "background": {},
            "status": {
                "temporaryInsanity": False,
                "indefiniteInsanity": False,
                "majorWound": False
            },
            "finance": {
                "cash": 0,
                "assets": 0,
                "spendingLevel": ""
            },
            "inventory": [],
            "companions": []
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

# ===== API =====

# ① start（ファイル生成）
@app.post("/start")
def start(user_id: str):
    data = create_empty_character()
    save_character(user_id, data)
    return data


# ② roll
@app.post("/roll")
def roll(user_id: str):
    data = load_character(user_id)
    char = data["character"]

    attrs = roll_attributes()
    char["attributes"] = attrs

    char["derived"] = {
        "idea": attrs["INT"],
        "knowledge": attrs["EDU"],
        "luck": attrs["POW"],
        "sanity": {
            "current": attrs["POW"],
            "max": 99
        },
        "hp": {
            "current": (attrs["CON"] + attrs["SIZ"]) // 10,
            "max": (attrs["CON"] + attrs["SIZ"]) // 10
        },
        "mp": {
            "current": attrs["POW"] // 5,
            "max": attrs["POW"] // 5
        },
        "damageBonus": "0",
        "build": 0,
        "moveRate": 8
    }

    data["step"] = 2
    save_character(user_id, data)
    return data


# ③ job
@app.post("/job")
def job(user_id: str, job_name: str):
    data = load_character(user_id)
    char = data["character"]

    for skill, value in occupations[job_name]["skills"].items():
        char["skills"][skill] = char["skills"].get(skill, 0) + value

    char["meta"]["occupation"] = job_name

    edu = char["attributes"]["EDU"]
    data["remaining"] = edu * 4
    data["step"] = 3

    save_character(user_id, data)
    return data


# ④ skill
@app.post("/skill")
def skill(user_id: str, skill_name: str, value: int):
    data = load_character(user_id)
    char = data["character"]

    if value > data["remaining"]:
        return {
            "error": "ポイント不足",
            "remaining_points": data["remaining"]
        }

    char["skills"][skill_name] = char["skills"].get(skill_name, 0) + value
    data["remaining"] -= value

    save_character(user_id, data)

    return {
        "character": char,
        "remaining_points": data["remaining"]
    }


# ⑤ buy
@app.post("/buy")
def buy(user_id: str, item_name: str):
    data = load_character(user_id)
    char = data["character"]

    char["inventory"].append(item_name)

    save_character(user_id, data)
    return data


# ⑥ meta
@app.post("/meta")
def meta(user_id: str, name: str, age: int, sex: str):
    data = load_character(user_id)
    char = data["character"]

    char["meta"].update({
        "name": name,
        "age": age,
        "sex": sex
    })

    save_character(user_id, data)
    return data


# ===== 補助 =====

@app.get("/status")
def status(user_id: str):
    return load_character(user_id)


@app.post("/reset")
def reset(user_id: str):
    path = get_file_path(user_id)
    if os.path.exists(path):
        os.remove(path)
    return {"message": "削除しました"}