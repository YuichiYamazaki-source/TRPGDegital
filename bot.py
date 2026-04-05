from __future__ import annotations

import logging
import os
from typing import Any

import aiohttp
import discord
from discord.ext import commands
from dotenv import load_dotenv

from dice import DiceRoll, roll_expression

load_dotenv()

log = logging.getLogger(__name__)

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GM_API_BASE_URL = os.getenv("GM_API_BASE_URL", "http://localhost:8000")

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Per-channel lobby state before and during a session.
# {channel_id: {"session_id": str|None, "scenario_id": str,
#   "players": {user_id: {"character_id": str, "display_name": str}},
#   "status": "pending"|"active"}}
sessions: dict[int, dict[str, Any]] = {}


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


def _format_character(c: dict[str, Any]) -> str:
    skills = "、".join(f"{k}:{v}" for k, v in list(c["skills"].items())[:3])
    return f"- `{c['id']}` — **{c['name']}**（{c['occupation']}）SAN:{c['san']} 得意: {skills}"


def _format_dice_roll(result: DiceRoll) -> str:
    if not result.rolls and result.modifier == 0:
        return f"**{result.expression}** → **{result.total}**"

    parts = [str(roll) for roll in result.rolls]
    if result.modifier > 0:
        parts.append(str(result.modifier))
    elif result.modifier < 0:
        parts.append(f"- {abs(result.modifier)}")

    if not parts:
        parts.append(str(result.total))

    detail = " + ".join(parts)
    detail = detail.replace("+ -", "- ")
    return f"**{result.expression}** → {detail} = **{result.total}**"


def _format_pending_check(pending_check: dict[str, Any]) -> str:
    if pending_check["kind"] == "skill":
        return (
            f"進行中の判定: **{pending_check['character_name']}** の "
            f"【{pending_check['skill_name']}】 {pending_check['difficulty']} 判定 "
            f"(成功値: {pending_check['target_value']})"
        )

    return (
        f"進行中の判定: **{pending_check['character_name']}** の SANチェック "
        f"(成功値: {pending_check['target_value']})"
    )


def _format_pending_check_help(pending_check: dict[str, Any]) -> str:
    return (
        f"{_format_pending_check(pending_check)}\n"
        "`!check` でそのまま振るか、手元で振った結果を使うなら `!check 43` のように入力してください。"
    )


async def _get_session_state(channel_id: int) -> tuple[dict[str, Any], dict[str, Any]] | tuple[None, None]:
    session_info = sessions.get(channel_id)
    if not session_info or session_info["status"] != "active" or not session_info["session_id"]:
        return None, None

    state = await api.get(f"/session/{session_info['session_id']}/state")
    return session_info, state


def _find_player_state(state: dict[str, Any], user_id: int) -> dict[str, Any] | None:
    user_id_str = str(user_id)
    for player in state.get("players", []):
        if player.get("user_id") == user_id_str:
            return player
    return None


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

    session_info = sessions.get(message.channel.id)
    if not session_info or session_info["status"] != "active":
        return

    player_entry = session_info["players"].get(message.author.id)
    if player_entry is None:
        await message.channel.send(
            f"{message.author.mention} このセッションに参加していません。`!join <character_id>` で参加してください。"
        )
        return

    player_message = message.content[2:].strip()
    if not player_message:
        return

    try:
        state = await api.get(f"/session/{session_info['session_id']}/state")
        pending_check = state.get("pending_check")
        if pending_check is not None:
            if pending_check["character_id"] == player_entry["character_id"]:
                await message.channel.send(
                    f"{_format_pending_check(pending_check)}\n先に `!check` で判定を解決してください。"
                )
            else:
                await message.channel.send(
                    f"{_format_pending_check(pending_check)}\nこの判定が終わるまで次の行動は少し待ってください。"
                )
            return
    except aiohttp.ClientError:
        log.exception("Failed to fetch session state before chat")
        await message.channel.send("セッション状態の取得に失敗しました。少し待ってから再試行してください。")
        return

    try:
        async with message.channel.typing():
            result = await api.post(
                f"/session/{session_info['session_id']}/chat",
                {"character_id": player_entry["character_id"], "message": player_message},
            )
        await message.channel.send(result["reply"])
        if result.get("pending_check") is not None:
            await message.channel.send(_format_pending_check_help(result["pending_check"]))
    except aiohttp.ClientResponseError as exc:
        if exc.status == 409:
            await message.channel.send("いまは保留中の判定があります。`!check` で先に解決してください。")
        else:
            log.exception("API request failed")
            await message.channel.send("API との通信に失敗しました。GM サーバーが起動しているか確認してください。")
    except aiohttp.ClientError:
        log.exception("API request failed")
        await message.channel.send("API との通信に失敗しました。GM サーバーが起動しているか確認してください。")


@bot.command(name="roll")
async def roll_dice(ctx: commands.Context, dice: str = "1d100") -> None:
    """Roll dice: !roll (default 1d100), !roll 2d6, !roll 1d10+5"""
    try:
        result = roll_expression(dice)
        await ctx.send(f"🎲 {_format_dice_roll(result)}")
    except ValueError:
        await ctx.send("形式が正しくありません。例: `!roll`, `!roll 2d6`, `!roll 1d100+10`")


@bot.command(name="scenarios")
async def list_scenarios(ctx: commands.Context) -> None:
    scenarios = await api.get("/scenarios")
    lines = ["**利用可能なシナリオ**"]
    for scenario in scenarios:
        lines.append(f"- `{scenario['id']}` — {scenario['title']}")
    await ctx.send("\n".join(lines))


@bot.command(name="characters")
async def list_characters(ctx: commands.Context) -> None:
    characters = await api.get("/characters")
    lines = ["**選択可能なキャラクター**"]
    lines.extend(_format_character(character) for character in characters)
    await ctx.send("\n".join(lines))


@bot.command(name="start")
async def start_session(ctx: commands.Context, scenario_id: str | None = None) -> None:
    channel_id = ctx.channel.id

    if channel_id in sessions:
        await ctx.send("このチャンネルではすでにセッションが進行中です。`!end` で終了してください。")
        return

    if scenario_id is None:
        scenarios = await api.get("/scenarios")
        lines = ["シナリオIDを指定してください: `!start <scenario_id>`\n**利用可能なシナリオ**"]
        for scenario in scenarios:
            lines.append(f"- `{scenario['id']}` — {scenario['title']}")
        await ctx.send("\n".join(lines))
        return

    scenarios = await api.get("/scenarios")
    scenario_map = {scenario["id"]: scenario["title"] for scenario in scenarios}
    if scenario_id not in scenario_map:
        lines = [f"シナリオ `{scenario_id}` は存在しません。`!start <scenario_id>` の形で指定してください。", "**利用可能なシナリオ**"]
        for sid, title in scenario_map.items():
            lines.append(f"- `{sid}` — {title}")
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
    lines.extend(_format_character(character) for character in characters)
    lines.append("\n全員が参加したら `!begin` でセッションを開始します。")
    await ctx.send("\n".join(lines))


@bot.command(name="join")
async def join_session(ctx: commands.Context, character_id: str | None = None) -> None:
    channel_id = ctx.channel.id
    session_info = sessions.get(channel_id)

    if not session_info or session_info["status"] != "pending":
        await ctx.send("`!start <scenario_id>` でセッションを準備してください。")
        return

    if character_id is None:
        await ctx.send("キャラクターIDを指定してください: `!join <character_id>`")
        return

    characters = await api.get("/characters")
    char_map = {character["id"]: character for character in characters}

    if character_id not in char_map:
        ids = "、".join(f"`{cid}`" for cid in char_map)
        await ctx.send(f"キャラクター `{character_id}` は存在しません。選択肢: {ids}")
        return

    if any(player["character_id"] == character_id for player in session_info["players"].values()):
        await ctx.send(f"`{character_id}` はすでに他のプレイヤーが選択しています。")
        return

    session_info["players"][ctx.author.id] = {
        "character_id": character_id,
        "display_name": ctx.author.display_name,
    }

    character = char_map[character_id]
    await ctx.send(f"{ctx.author.display_name} が **{character['name']}**（{character['occupation']}）で参加しました。")


@bot.command(name="begin")
async def begin_session(ctx: commands.Context) -> None:
    channel_id = ctx.channel.id
    session_info = sessions.get(channel_id)

    if not session_info or session_info["status"] != "pending":
        await ctx.send("`!start <scenario_id>` でセッションを準備してください。")
        return

    if not session_info["players"]:
        await ctx.send("参加者がいません。`!join <character_id>` でキャラクターを選んでください。")
        return

    scenarios = await api.get("/scenarios")
    scenario_ids = {scenario["id"] for scenario in scenarios}
    if session_info["scenario_id"] not in scenario_ids:
        await ctx.send(
            f"シナリオ `{session_info['scenario_id']}` が見つかりません。`!scenarios` で確認して `!start <scenario_id>` からやり直してください。"
        )
        del sessions[channel_id]
        return

    players = [
        {
            "user_id": str(user_id),
            "display_name": player["display_name"],
            "character_id": player["character_id"],
        }
        for user_id, player in session_info["players"].items()
    ]

    try:
        result = await api.post(
            "/session",
            {
                "channel_id": str(channel_id),
                "scenario_id": session_info["scenario_id"],
                "players": players,
            },
        )
    except aiohttp.ClientError:
        log.exception("Failed to create session")
        await ctx.send("GM サーバーとの通信に失敗しました。サーバーが起動しているか確認してください。")
        return

    session_info["session_id"] = result["session_id"]
    session_info["status"] = "active"

    await ctx.send("セッションを開始します。発言は `>> メッセージ`、判定解決は `!check` で行ってください。\n\n*KPが導入を始めます...*")

    first_player = next(iter(session_info["players"].values()))
    try:
        async with ctx.typing():
            opening = await api.post(
                f"/session/{session_info['session_id']}/chat",
                {"character_id": first_player["character_id"], "message": "（セッション開始）"},
            )
        await ctx.send(opening["reply"])
        if opening.get("pending_check") is not None:
            await ctx.send(_format_pending_check_help(opening["pending_check"]))
    except aiohttp.ClientError:
        log.exception("Failed to get opening narration")
        await ctx.send("KP の導入シーン取得に失敗しました。`>> （セッション開始）` で再試行してください。")


@bot.command(name="check")
async def resolve_pending_check(ctx: commands.Context, roll: int | None = None) -> None:
    session_info, state = await _get_session_state(ctx.channel.id)
    if session_info is None or state is None:
        await ctx.send("アクティブなセッションがありません。")
        return

    player_state = _find_player_state(state, ctx.author.id)
    if player_state is None:
        await ctx.send("このセッションに参加していません。")
        return

    try:
        result = await api.post(
            f"/session/{session_info['session_id']}/check/resolve",
            {
                "character_id": player_state["character_id"],
                "roll": roll,
            },
        )
    except aiohttp.ClientResponseError as exc:
        if exc.status == 403:
            pending_check = state.get("pending_check")
            if pending_check is not None:
                await ctx.send(f"{_format_pending_check(pending_check)}\nこの判定は別のプレイヤーの担当です。")
            else:
                await ctx.send("この判定はあなたの担当ではありません。")
        elif exc.status == 409:
            await ctx.send("いま解決すべき判定はありません。")
        else:
            log.exception("Failed to resolve pending check")
            await ctx.send("判定の解決に失敗しました。")
        return
    except aiohttp.ClientError:
        log.exception("Failed to resolve pending check")
        await ctx.send("判定の解決に失敗しました。")
        return

    check_result = result["check_result"]
    if check_result["kind"] == "skill":
        summary = (
            f"🎲 **{check_result['character_name']}** の【{check_result['skill_name']}】判定 "
            f"{check_result['roll']}/{check_result['target_value']} → **{check_result['outcome_label']}**"
        )
    else:
        summary = (
            f"🎲 **{check_result['character_name']}** のSANチェック "
            f"{check_result['roll']}/{check_result['target_value']} → **{check_result['outcome_label']}** "
            f"(SAN-{check_result['san_loss']} / 現在SAN {check_result['current_san']})"
        )

    await ctx.send(summary)
    await ctx.send(result["reply"])


@bot.command(name="status")
async def show_status(ctx: commands.Context) -> None:
    session_info, state = await _get_session_state(ctx.channel.id)
    if session_info is None or state is None:
        await ctx.send("アクティブなセッションがありません。")
        return

    player_state = _find_player_state(state, ctx.author.id)
    if player_state is None:
        await ctx.send("このセッションに参加していません。")
        return

    lines = [
        f"**{player_state['character_name']}**（{player_state['occupation']}）",
        f"HP: {player_state['hp']}/{player_state['hp_max']} | MP: {player_state['mp']}/{player_state['mp_max']} | SAN: {player_state['san']}/{player_state['san_max']}",
    ]

    if player_state["status_effects"]:
        lines.append(f"状態: {'、'.join(player_state['status_effects'])}")
    if player_state["notes"]:
        lines.append(f"メモ: {'、'.join(player_state['notes'])}")
    if player_state["inventory"]:
        lines.append(f"所持品: {'、'.join(player_state['inventory'])}")

    pending_check = state.get("pending_check")
    if pending_check and pending_check["character_id"] == player_state["character_id"]:
        lines.append(_format_pending_check(pending_check))

    await ctx.send("\n".join(lines))


@bot.command(name="party")
async def show_party(ctx: commands.Context) -> None:
    _, state = await _get_session_state(ctx.channel.id)
    if state is None:
        await ctx.send("アクティブなセッションがありません。")
        return

    lines = ["**パーティ状況**"]
    for player in state.get("players", []):
        line = (
            f"- **{player['character_name']}**（{player['display_name']}） "
            f"HP {player['hp']}/{player['hp_max']} | MP {player['mp']}/{player['mp_max']} | SAN {player['san']}/{player['san_max']}"
        )
        if player["status_effects"]:
            line += f" | 状態: {'、'.join(player['status_effects'])}"
        lines.append(line)

    pending_check = state.get("pending_check")
    if pending_check:
        lines.append("")
        lines.append(_format_pending_check(pending_check))

    await ctx.send("\n".join(lines))


@bot.command(name="scene")
async def show_scene(ctx: commands.Context) -> None:
    _, state = await _get_session_state(ctx.channel.id)
    if state is None:
        await ctx.send("アクティブなセッションがありません。")
        return

    environment = state["environment"]
    lines = [f"**現在地: {environment['scene']}**"]

    if environment["scene_summary"]:
        lines.append(environment["scene_summary"])
    if environment["clues"]:
        lines.append(f"手がかり: {'、'.join(environment['clues'])}")

    active_flags = [name for name, value in environment["flags"].items() if value]
    if active_flags:
        lines.append(f"進行フラグ: {'、'.join(active_flags)}")

    if environment["notes"]:
        lines.append(f"共有メモ: {'、'.join(environment['notes'])}")

    npcs = state.get("npcs", [])
    if npcs:
        lines.append("NPC状況:")
        for npc in npcs:
            detail = f"- **{npc['name']}**: {npc['status']} / {npc['location']}"
            if npc["notes"]:
                detail += f" / {'、'.join(npc['notes'])}"
            lines.append(detail)

    pending_check = state.get("pending_check")
    if pending_check:
        lines.append(_format_pending_check(pending_check))

    await ctx.send("\n".join(lines))


@bot.command(name="end")
async def end_session(ctx: commands.Context) -> None:
    channel_id = ctx.channel.id
    session_info = sessions.get(channel_id)

    if not session_info:
        await ctx.send("アクティブなセッションがありません。")
        return

    if session_info["session_id"]:
        try:
            await api.delete(f"/session/{session_info['session_id']}")
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
