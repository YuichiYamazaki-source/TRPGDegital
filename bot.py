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

# ===== セッション管理 =====

sessions: dict[int, dict] = {}

# ===== キャラビルド管理（重要）=====
user_builds: dict[int, str] = {}


# --- API Client ---


class APIClient:
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
            return await resp.json()

    async def delete(self, path: str) -> dict[str, Any]:
        http = await self._session()
        async with http.delete(f"{self.base_url}{path}") as resp:
            resp.raise_for_status()
            return await resp.json()


api = APIClient(GM_API_BASE_URL)


# --- Helpers ---


def _format_character(c: dict) -> str:
    skills = "、".join(f"{k}:{v}" for k, v in list(c.get("skills", {}).items())[:3])
    return f"- `{c['id']}` — **{c['name']}**（{c.get('occupation','-')}） SAN:{c.get('san','-')} 得意: {skills}"


def _get_build_id(ctx: commands.Context) -> str | None:
    return user_builds.get(ctx.author.id)


# --- Events ---


@bot.event
async def on_ready() -> None:
    if bot.user:
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
        await message.channel.send("このセッションに参加していません。")
        return

    player_message = message.content[2:].strip()
    if not player_message:
        return

    character_id = s["players"][message.author.id]

    try:
        result = await api.post(
            f"/session/{s['session_id']}/chat",
            {"character_id": character_id, "message": player_message},
        )
        await message.channel.send(result["reply"])
    except aiohttp.ClientError:
        await message.channel.send("API通信エラー")


# --- Character Creation Commands ---


@bot.command(name="cstart")
async def char_start(ctx: commands.Context):
    try:
        result = await api.post("/character/start", {
            "user_id": str(ctx.author.id)
        })

        build_id = result["id"]
        user_builds[ctx.author.id] = build_id

        await ctx.send(f"作成開始！ID: `{build_id}`\n!croll で能力値を決定")
    except aiohttp.ClientError:
        await ctx.send("APIエラー")


@bot.command(name="croll")
async def char_roll(ctx: commands.Context):
    build_id = _get_build_id(ctx)
    if not build_id:
        await ctx.send("!cstart を先に実行してください")
        return

    result = await api.post("/character/roll", {"build_id": build_id})

    attrs = result["character"]["attributes"]
    lines = ["能力値"]
    lines.extend(f"{k}: {v}" for k, v in attrs.items())

    await ctx.send("\n".join(lines))


@bot.command(name="cjob")
async def char_job(ctx: commands.Context, job_name: str):
    build_id = _get_build_id(ctx)
    if not build_id:
        await ctx.send("!cstart を先に実行してください")
        return

    result = await api.post("/character/job", {
        "build_id": build_id,
        "job_name": job_name
    })

    await ctx.send(f"職業: {job_name} / 残り: {result['remaining']}")


@bot.command(name="cskill")
async def char_skill(ctx: commands.Context, skill_name: str, value: int):
    build_id = _get_build_id(ctx)
    if not build_id:
        await ctx.send("!cstart を先に実行してください")
        return

    result = await api.post("/character/skill", {
        "build_id": build_id,
        "skill_name": skill_name,
        "value": value
    })

    if "error" in result:
        await ctx.send(f"{result['error']}（残り: {result['remaining']}）")
        return

    await ctx.send(f"{skill_name} +{value}（残り: {result['remaining']}）")


@bot.command(name="cbuy")
async def char_buy(ctx: commands.Context, item: str):
    build_id = _get_build_id(ctx)
    if not build_id:
        await ctx.send("!cstart を先に実行してください")
        return

    await api.post("/character/buy", {
        "build_id": build_id,
        "item": item
    })

    await ctx.send(f"{item} を購入")


@bot.command(name="cmeta")
async def char_meta(ctx: commands.Context, name: str):
    build_id = _get_build_id(ctx)
    if not build_id:
        await ctx.send("!cstart を先に実行してください")
        return

    result = await api.post("/character/meta", {
        "build_id": build_id,
        "name": name
    })

    user_builds.pop(ctx.author.id, None)

    await ctx.send(f"完成！ {result['name']} / ID: `{result['id']}`")


@bot.command(name="cstatus")
async def char_status(ctx: commands.Context):
    build_id = _get_build_id(ctx)
    if not build_id:
        await ctx.send("作成中キャラなし")
        return

    result = await api.get(f"/character/status?build_id={build_id}")

    char = result["character"]

    lines = ["状態"]

    for k, v in char.get("attributes", {}).items():
        lines.append(f"{k}: {v}")

    for k, v in char.get("skills", {}).items():
        lines.append(f"{k}: {v}")

    lines.append(f"残り: {result['remaining']}")

    await ctx.send("\n".join(lines))


# --- Run ---


@bot.event
async def on_close() -> None:
    await api.close()


if __name__ == "__main__":
    if not DISCORD_TOKEN:
        raise RuntimeError("DISCORD_TOKEN not set")
    bot.run(DISCORD_TOKEN)