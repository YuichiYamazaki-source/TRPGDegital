import discord
from discord.ext import commands
import random

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# ====== データ ======

occupations = {
    "記者": {
        "skills": {
            "言いくるめ": 20,
            "図書館": 20,
            "心理学": 20,
            "目星": 20
        }
    },
    "警察官": {
        "skills": {
            "威圧": 20,
            "射撃（拳銃）": 20,
            "法律": 20,
            "追跡": 20
        }
    }
}

shop_items = {
    "ナイフ": 1000,
    "懐中電灯": 2000,
    "救急キット": 3000
}


# ====== ユーティリティ ======

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


# ====== セッション管理 ======

sessions = {}


# ====== コマンド ======

@bot.command()
async def coc_start(ctx):
    sessions[ctx.author.id] = {
        "step": 1,
        "character": {
            "attributes": {},
            "skills": {},
            "inventory": [],
            "meta": {}
        }
    }
    await ctx.send("🎲 キャラクター作成開始！ `!roll` と入力して能力値を決定してください")


@bot.command()
async def roll(ctx):
    session = sessions.get(ctx.author.id)
    if not session or session["step"] != 1:
        return

    attrs = roll_attributes()
    session["character"]["attributes"] = attrs
    session["step"] = 2

    text = "\n".join([f"{k}: {v}" for k, v in attrs.items()])
    await ctx.send(f"🎲 能力値:\n{text}")
    await ctx.send("職業を選択してください: 記者 / 警察官")


@bot.command()
async def job(ctx, job_name):
    session = sessions.get(ctx.author.id)
    if not session or session["step"] != 2:
        return

    if job_name not in occupations:
        await ctx.send("その職業はありません")
        return

    session["character"]["skills"].update(occupations[job_name]["skills"])
    session["character"]["meta"]["occupation"] = job_name
    session["step"] = 3

    edu = session["character"]["attributes"]["EDU"]
    session["remaining_points"] = edu * 4

    await ctx.send(f"{job_name}を選択しました")
    await ctx.send(f"技能ポイント {edu * 4} を割り振ってください `!skill 技能名 数値`")


@bot.command()
async def skill(ctx, skill_name, value: int):
    session = sessions.get(ctx.author.id)
    if not session or session["step"] != 3:
        return

    if value > session["remaining_points"]:
        await ctx.send("ポイントが足りません")
        return

    session["character"]["skills"][skill_name] = \
        session["character"]["skills"].get(skill_name, 0) + value

    session["remaining_points"] -= value

    await ctx.send(f"{skill_name} に {value} 振りました（残り {session['remaining_points']}）")

    if session["remaining_points"] == 0:
        session["step"] = 4
        await ctx.send("🛒 アイテム購入フェーズです `!buy アイテム名`")


@bot.command()
async def buy(ctx, item_name):
    session = sessions.get(ctx.author.id)
    if not session or session["step"] != 4:
        return

    if item_name not in shop_items:
        await ctx.send("そのアイテムはありません")
        return

    session["character"]["inventory"].append(item_name)
    await ctx.send(f"{item_name} を購入しました")


@bot.command()
async def done_shop(ctx):
    session = sessions.get(ctx.author.id)
    if not session or session["step"] != 4:
        return

    session["step"] = 5
    await ctx.send("メタ情報を入力してください `!meta 名前 年齢 性別`")


@bot.command()
async def meta(ctx, name, age: int, sex):
    session = sessions.get(ctx.author.id)
    if not session or session["step"] != 5:
        return

    session["character"]["meta"].update({
        "name": name,
        "age": age,
        "sex": sex
    })

    await ctx.send("🎉 キャラクター完成！")
    await ctx.send(f"```json\n{session['character']}\n```")

    del sessions[ctx.author.id]


# ====== 起動 ======

bot.run("YOUR_BOT_TOKEN")