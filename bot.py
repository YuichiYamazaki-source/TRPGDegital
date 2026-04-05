from __future__ import annotations

import logging
import os
import random
from typing import Any

import aiohttp
import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

log = logging.getLogger(__name__)

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GM_API_BASE_URL = os.getenv("GM_API_BASE_URL", "http://localhost:8000")

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Per-channel session state
# {channel_id: {"session_id": str|None, "scenario_id": str,
#   "players": {user_id: character_id}, "status": "pending"|"active"}}
sessions: dict[int, dict] = {}


# --- Shared HTTP client ---


class APIClient:
    """Thin wrapper around the GM API that reuses a single aiohttp session."""

    def __init__(self, base_url: str) -> None:
        self.base_url = base_url
        self._http: aiohttp.ClientSession | None = None

    async def _session(self) -> aiohttp.ClientSession:
        if self._http is None or self._http.closed:
            self._http = aiohttp.ClientSession()
        return self._http

    async def close(self) -> None:
        if self._http and not self._http.closed:
            await self._http.close()

    async def get(self, path: str) -> Any:
        http = await self._session()
        async with http.get(f"{self.base_url}{path}") as resp:
            resp.raise_for_status()
            return await resp.json()

    async def post(self, path: str, data: dict[str, Any]) -> dict[str, Any]:
        http = await self._session()
        async with http.post(f"{self.base_url}{path}", json=data) as resp:
            resp.raise_for_status()
            return await resp.json()  # type: ignore[no-any-return]

    async def delete(self, path: str) -> dict[str, Any]:
        http = await self._session()
        async with http.delete(f"{self.base_url}{path}") as resp:
            resp.raise_for_status()
            return await resp.json()  # type: ignore[no-any-return]


api = APIClient(GM_API_BASE_URL)


# --- Helpers ---


def _format_character(c: dict) -> str:
    skills = "、".join(f"{k}:{v}" for k, v in list(c["skills"].items())[:3])
    return f"- `{c['id']}` — **{c['name']}**（{c['occupation']}）SAN:{c['san']} 得意: {skills}"


# --- Events ---


@bot.event
async def on_ready() -> None:
    if bot.user:
        log.info("Bot ready: %s (id: %s)", bot.user, bot.user.id)
        print(f"Bot ready: {bot.user} (id: {bot.user.id})")


@bot.event
async def on_message(message: discord.Message) -> None:
    if message.author.bot:
        return

    await bot.process_commands(message)

    if not message.content.startswith(">>"):
        return

    channel_id = message.channel.id
    s = sessions.get(channel_id)

    if not s or s["status"] != "active":
        return

    if message.author.id not in s["players"]:
        await message.channel.send(
            f"{message.author.mention} このセッションに参加していません。`!join <character_id>` で参加してください。"
        )
        return

    player_message = message.content[2:].strip()
    if not player_message:
        return

    character_id = s["players"][message.author.id]

    try:
        async with message.channel.typing():
            result = await api.post(
                f"/session/{s['session_id']}/chat",
                {"character_id": character_id, "message": player_message},
            )
        await message.channel.send(result["reply"])
    except aiohttp.ClientError:
        log.exception("API request failed")
        await message.channel.send("API との通信に失敗しました。GM サーバーが起動しているか確認してください。")


# --- Commands ---


@bot.command(name="roll")
async def roll_dice(ctx: commands.Context, dice: str = "1d100") -> None:
    """Roll dice: !roll (default 1d100), !roll 2d6, !roll 1d10+5"""
    try:
        bonus = 0
        base = dice
        if "+" in dice:
            base, bonus_str = dice.split("+", 1)
            bonus = int(bonus_str)
        elif "-" in dice and not dice.startswith("-"):
            parts = dice.split("-", 1)
            base = parts[0]
            bonus = -int(parts[1])

        count_str, sides_str = base.lower().split("d", 1)
        count = int(count_str) if count_str else 1
        sides = int(sides_str)

        if count < 1 or count > 20 or sides < 1 or sides > 1000:
            await ctx.send("ダイスは 1〜20個、面数は 1〜1000 で指定してください。")
            return

        rolls = [random.randint(1, sides) for _ in range(count)]
        total = sum(rolls) + bonus

        if count == 1 and bonus == 0:
            await ctx.send(f"🎲 **{dice}** → **{total}**")
        else:
            detail = " + ".join(str(r) for r in rolls)
            if bonus > 0:
                detail += f" + {bonus}"
            elif bonus < 0:
                detail += f" - {abs(bonus)}"
            await ctx.send(f"🎲 **{dice}** → {detail} = **{total}**")
    except (ValueError, IndexError):
        await ctx.send("形式が正しくありません。例: `!roll`, `!roll 2d6`, `!roll 1d100+10`")


@bot.command(name="scenarios")
async def list_scenarios(ctx: commands.Context) -> None:
    """Show available scenarios."""
    scenarios = await api.get("/scenarios")
    lines = ["**利用可能なシナリオ**"]
    for s in scenarios:
        lines.append(f"- `{s['id']}` — {s['title']}")
    await ctx.send("\n".join(lines))


@bot.command(name="characters")
async def list_characters(ctx: commands.Context) -> None:
    """Show available characters."""
    characters = await api.get("/characters")
    lines = ["**選択可能なキャラクター**"]
    lines.extend(_format_character(c) for c in characters)
    await ctx.send("\n".join(lines))


@bot.command(name="start")
async def start_session(ctx: commands.Context, scenario_id: str | None = None) -> None:
    """Prepare a session: !start <scenario_id>"""
    channel_id = ctx.channel.id

    if channel_id in sessions:
        await ctx.send("このチャンネルではすでにセッションが進行中です。`!end` で終了してください。")
        return

    if scenario_id is None:
        scenarios = await api.get("/scenarios")
        lines = ["シナリオIDを指定してください: `!start <scenario_id>`\n**利用可能なシナリオ**"]
        for s in scenarios:
            lines.append(f"- `{s['id']}` — {s['title']}")
        await ctx.send("\n".join(lines))
        return

    sessions[channel_id] = {
        "session_id": None,
        "scenario_id": scenario_id,
        "players": {},
        "status": "pending",
    }

    characters = await api.get("/characters")
    lines = [
        f"シナリオ `{scenario_id}` でセッションを準備しました。",
        "キャラクターを選んで参加してください: `!join <character_id>`\n**選択可能なキャラクター**",
    ]
    lines.extend(_format_character(c) for c in characters)
    lines.append("\n全員が参加したら `!begin` でセッションを開始します。")
    await ctx.send("\n".join(lines))


@bot.command(name="join")
async def join_session(ctx: commands.Context, character_id: str | None = None) -> None:
    """Join the pending session with a character: !join <character_id>"""
    channel_id = ctx.channel.id
    s = sessions.get(channel_id)

    if not s or s["status"] != "pending":
        await ctx.send("`!start <scenario_id>` でセッションを準備してください。")
        return

    if character_id is None:
        await ctx.send("キャラクターIDを指定してください: `!join <character_id>`")
        return

    characters = await api.get("/characters")
    char_map = {c["id"]: c for c in characters}

    if character_id not in char_map:
        ids = "、".join(f"`{cid}`" for cid in char_map)
        await ctx.send(f"キャラクター `{character_id}` は存在しません。選択肢: {ids}")
        return

    if character_id in s["players"].values():
        await ctx.send(f"`{character_id}` はすでに他のプレイヤーが選択しています。")
        return

    s["players"][ctx.author.id] = character_id
    char = char_map[character_id]
    await ctx.send(f"{ctx.author.display_name} が **{char['name']}**（{char['occupation']}）で参加しました。")


@bot.command(name="begin")
async def begin_session(ctx: commands.Context) -> None:
    """Start the session and trigger the KP opening narration: !begin"""
    channel_id = ctx.channel.id
    s = sessions.get(channel_id)

    if not s or s["status"] != "pending":
        await ctx.send("`!start <scenario_id>` でセッションを準備してください。")
        return

    if not s["players"]:
        await ctx.send("参加者がいません。`!join <character_id>` でキャラクターを選んでください。")
        return

    try:
        result = await api.post(
            "/session",
            {
                "channel_id": str(channel_id),
                "scenario_id": s["scenario_id"],
                "character_ids": list(s["players"].values()),
            },
        )
    except aiohttp.ClientError:
        log.exception("Failed to create session")
        await ctx.send("GM サーバーとの通信に失敗しました。サーバーが起動しているか確認してください。")
        return

    s["session_id"] = result["session_id"]
    s["status"] = "active"

    await ctx.send("セッションを開始します。発言は `>> メッセージ` で行ってください。\n\n*KPが導入を始めます...*")

    first_char_id = next(iter(s["players"].values()))
    try:
        async with ctx.typing():
            opening = await api.post(
                f"/session/{s['session_id']}/chat",
                {"character_id": first_char_id, "message": "（セッション開始）"},
            )
        await ctx.send(opening["reply"])
    except aiohttp.ClientError:
        log.exception("Failed to get opening narration")
        await ctx.send("KP の導入シーン取得に失敗しました。`>> （セッション開始）` で再試行してください。")


@bot.command(name="end")
async def end_session(ctx: commands.Context) -> None:
    """End the current session: !end"""
    channel_id = ctx.channel.id
    s = sessions.get(channel_id)

    if not s:
        await ctx.send("アクティブなセッションがありません。")
        return

    if s["session_id"]:
        try:
            await api.delete(f"/session/{s['session_id']}")
        except aiohttp.ClientError:
            log.warning("Failed to delete session on server side")

    del sessions[channel_id]
    await ctx.send("セッションを終了しました。お疲れ様でした！")


@bot.event
async def on_close() -> None:
    await api.close()


if __name__ == "__main__":
    if not DISCORD_TOKEN:
        raise RuntimeError("DISCORD_TOKEN is not set in environment")
    bot.run(DISCORD_TOKEN)

# ===== Character Creation Commands =====

@bot.command(name="cstart")
async def char_start(ctx: commands.Context):
    user_id = str(ctx.author.id)

    try:
        result = await api.post("/character/start", {"user_id": user_id})
        await ctx.send("キャラクター作成を開始しました！ `!croll` で能力値を決定してください。")
    except aiohttp.ClientError:
        await ctx.send("APIエラー：キャラ作成開始に失敗しました")


@bot.command(name="croll")
async def char_roll(ctx: commands.Context):
    user_id = str(ctx.author.id)

    try:
        result = await api.post("/character/roll", {"user_id": user_id})
        attrs = result["character"]["attributes"]

        lines = ["能力値を決定しました:"]
        lines.extend(f"{k}: {v}" for k, v in attrs.items())
        lines.append("\n職業を選択してください: `!cjob 記者`")

        await ctx.send("\n".join(lines))
    except aiohttp.ClientError:
        await ctx.send("APIエラー：ロールに失敗しました")


@bot.command(name="cjob")
async def char_job(ctx: commands.Context, job_name: str):
    user_id = str(ctx.author.id)

    try:
        result = await api.post("/character/job", {
            "user_id": user_id,
            "job_name": job_name
        })

        remaining = result["remaining"]

        await ctx.send(
            f"職業 **{job_name}** を選択しました！\n"
            f"技能ポイント: {remaining}\n"
            f"`!cskill スキル名 値` で割り振ってください"
        )
    except aiohttp.ClientError:
        await ctx.send("APIエラー：職業選択に失敗しました")


@bot.command(name="cskill")
async def char_skill(ctx: commands.Context, skill_name: str, value: int):
    user_id = str(ctx.author.id)

    try:
        result = await api.post("/character/skill", {
            "user_id": user_id,
            "skill_name": skill_name,
            "value": value
        })

        if "error" in result:
            await ctx.send(
                f" {result['error']}（残り: {result['remaining']}）"
            )
            return

        remaining = result["remaining"]

        await ctx.send(
            f"{skill_name} +{value}（残り: {remaining}）"
        )
    except aiohttp.ClientError:
        await ctx.send("APIエラー：技能割り振り失敗")


@bot.command(name="cbuy")
async def char_buy(ctx: commands.Context, item: str):
    user_id = str(ctx.author.id)

    try:
        await api.post("/character/buy", {
            "user_id": user_id,
            "item": item
        })

        await ctx.send(f" **{item}** を購入しました")
    except aiohttp.ClientError:
        await ctx.send("APIエラー：購入失敗")


@bot.command(name="cmeta")
async def char_meta(ctx: commands.Context, name: str):
    user_id = str(ctx.author.id)

    try:
        result = await api.post("/character/meta", {
            "user_id": user_id,
            "name": name
        })

        await ctx.send(
            f"🎉 キャラクター完成！\n"
            f"名前: {result['name']}\n"
            f"ID: `{result['id']}`\n\n"
            f"`!characters` で確認できます"
        )
    except aiohttp.ClientError:
        await ctx.send("APIエラー：キャラ完成失敗")


@bot.command(name="cstatus")
async def char_status(ctx: commands.Context):
    user_id = str(ctx.author.id)

    try:
        result = await api.get(f"/character/status?user_id={user_id}")
        char = result["character"]

        attrs = char.get("attributes", {})
        skills = char.get("skills", {})

        lines = ["現在のキャラクター状態"]

        if attrs:
            lines.append("\n【能力値】")
            lines.extend(f"{k}: {v}" for k, v in attrs.items())

        if skills:
            lines.append("\n【技能】")
            lines.extend(f"{k}: {v}" for k, v in skills.items())

        lines.append(f"\n残りポイント: {result.get('remaining', 0)}")

        await ctx.send("\n".join(lines))

    except aiohttp.ClientError:
        await ctx.send("APIエラー：状態取得失敗")