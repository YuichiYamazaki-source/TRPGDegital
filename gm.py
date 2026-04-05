from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionMessageParam

from session import Session

load_dotenv()

log = logging.getLogger(__name__)

SCENARIOS_DIR = Path("scenarios")
RULES_DIR = Path("Rule")
SYSTEM_PROMPT_PATH = Path("prompts/system_prompt.txt")

SKILL_CHECK_RE = re.compile(
    r"【(?P<skill>[^】]+)】(?:の)?判定をお願いします[（(]成功値[:：]\s*(?P<target>\d+)[）)]"
)
SAN_CHECK_RE = re.compile(
    r"SAN(?:値)?チェックをお願いします[（(]成功値[:：]\s*(?P<target>\d+|現在のSAN値|現在のＳＡＮ値)[）)]"
)
SKILL_CHECK_OFFER_RE = re.compile(
    r"【(?P<skill>[^】]+)】(?:で|の)?判定(?:が)?できます。?\s*成功値は(?P<target>\d+)です。?\s*判定しますか"
)
SAN_CHECK_OFFER_RE = re.compile(
    r"SAN(?:値)?チェック(?:が)?(?:入ります|できます)。?\s*(?:現在のSAN値(?:が成功値|です))。?\s*判定しますか"
)
SCENE_H2_RE = re.compile(r"^##\s+(.+)$")
SCENE_H3_RE = re.compile(r"^###\s+(.+)$")
METADATA_LINE_RE = re.compile(r"^(?:>\s*)?(?:`+)?(?P<kind>CHECK|STATE)[:：]\s*(?P<payload>.+?)(?:`+)?$")
SCENE_TOKEN_SPLIT_RE = re.compile(r"[\s、。,.!！?？:：/・「」『』（）()\[\]【】]+")
SCENE_FRAGMENT_SPLIT_RE = re.compile(
    r"(?:について|として|により|から|まで|ので|ため|ように|ような|ようだ|ている|ていた|ており|"
    r"している|していた|されている|されていた|した|して|され|する|れる|られる|"
    r"だった|です|ます|ない|なり|なっ|かけて|かかって|覆い|差し込み|混じって|"
    r"向かって|呼んで|浮かび上がって|降りると|見つかる|見つける|呼ぶ|聞こえる|"
    r"書かれている|の|を|が|に|へ|で|と|や|も|は)"
)

SCENE_KEYWORD_STOPWORDS = {
    "描写",
    "到着時",
    "技能判定",
    "成功",
    "失敗",
    "情報",
    "入手可能アイテム",
    "アクセス",
    "クライマックス",
    "判定",
    "難易度",
    "成功値",
    "成功値2",
    "場合",
    "可能",
    "現在",
    "探索者たち",
    "手紙",
    "今夜",
    "目黒",
    "東京",
    "昭和初期",
    "想定プレイ時間",
    "SAN値チェック",
    "光源",
    "中央",
    "中心",
    "大きな",
    "奇妙な",
    "低い",
    "最後",
    "上記情報",
    "上記",
    "同じ",
    "特殊な",
    "可能性",
    "記述",
    "玄関ホール",
    "書斎",
    "地下室",
    "導入",
    "いる",
    "ある",
    "する",
    "なる",
    "それ",
    "もの",
    "こと",
    "ため",
    "よう",
    "直後",
    "本",
    "紙",
    "部屋",
    "記",
    "血",
    "鍵",
    "情報",
    "入手",
    "成功時",
    "失敗時",
}


@dataclass
class GMTurn:
    reply: str
    proposed_check: dict[str, Any] | None = None
    pending_check: dict[str, Any] | None = None
    state_update: dict[str, Any] | None = None


def _merge_nested_dict(base: dict[str, Any], update: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in update.items():
        current = merged.get(key)
        if isinstance(current, dict) and isinstance(value, dict):
            merged[key] = _merge_nested_dict(current, value)
        else:
            merged[key] = value
    return merged


def _infer_check_offer_from_reply(reply: str) -> dict[str, Any] | None:
    skill_match = SKILL_CHECK_OFFER_RE.search(reply)
    if skill_match:
        return {
            "type": "skill",
            "phase": "offer",
            "skill": skill_match.group("skill").strip(),
            "target": int(skill_match.group("target")),
            "reason": "",
        }

    if SAN_CHECK_OFFER_RE.search(reply):
        return {
            "type": "san",
            "phase": "offer",
            "reason": "",
        }

    return None


def _infer_pending_check_from_reply(reply: str) -> dict[str, Any] | None:
    skill_match = SKILL_CHECK_RE.search(reply)
    if skill_match:
        return {
            "type": "skill",
            "phase": "pending",
            "skill": skill_match.group("skill").strip(),
            "target": int(skill_match.group("target")),
            "reason": "",
        }

    san_match = SAN_CHECK_RE.search(reply)
    if san_match:
        target_text = san_match.group("target").strip()
        payload: dict[str, Any] = {
            "type": "san",
            "phase": "pending",
            "reason": "",
        }
        if target_text.isdigit():
            payload["target"] = int(target_text)
        return payload

    return None


def _parse_metadata_line(line: str) -> tuple[str, dict[str, Any] | None] | None:
    stripped = line.strip()
    match = METADATA_LINE_RE.match(stripped)
    if match is None:
        return None

    kind = match.group("kind")
    payload_text = match.group("payload").strip()

    start = payload_text.find("{")
    end = payload_text.rfind("}")
    if start == -1 or end == -1 or end < start:
        return kind, None

    json_text = payload_text[start : end + 1]
    try:
        payload = json.loads(json_text)
    except json.JSONDecodeError:
        log.warning("Failed to parse %s metadata: %s", kind, stripped)
        return kind, None

    if not isinstance(payload, dict):
        return kind, None

    return kind, payload


def _normalize_scene_name(name: str) -> str:
    normalized = name.strip()
    normalized = re.sub(r"^\d+\.\s*", "", normalized)
    normalized = re.sub(r"^[A-Z]\.\s*", "", normalized)
    normalized = re.sub(r"[（(].*?[）)]", "", normalized)
    return normalized.strip()


def _check_phase(payload: dict[str, Any]) -> str:
    raw_phase = payload.get("phase", payload.get("status", payload.get("stage", "pending")))
    phase = str(raw_phase).strip().lower()
    if phase in {"offer", "proposal", "proposed", "confirm"}:
        return "offer"
    return "pending"


def _extract_scene_aliases(scenario_text: str) -> list[tuple[str, set[str]]]:
    aliases: list[tuple[str, set[str]]] = [("導入", {"導入"})]
    current_section = ""

    for line in scenario_text.splitlines():
        h2_match = SCENE_H2_RE.match(line.strip())
        if h2_match:
            current_section = h2_match.group(1).strip()
            continue

        if current_section != "探索場所":
            continue

        h3_match = SCENE_H3_RE.match(line.strip())
        if not h3_match:
            continue

        raw_name = h3_match.group(1).strip()
        canonical_name = _normalize_scene_name(raw_name)
        scene_aliases = {
            raw_name,
            canonical_name,
            re.sub(r"^\d+\.\s*", "", raw_name).strip(),
        }

        if "玄関" in canonical_name:
            scene_aliases.add("玄関")
            scene_aliases.add("玄関ホール")
        if "書斎" in canonical_name:
            scene_aliases.add("書斎")
        if "地下室" in canonical_name:
            scene_aliases.add("地下室")
            scene_aliases.add("地下")

        aliases.append((canonical_name, {alias for alias in scene_aliases if alias}))

    return aliases


def _extract_scene_sections(scenario_text: str) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {}
    current_section = ""
    active_scene: str | None = None

    for raw_line in scenario_text.splitlines():
        line = raw_line.strip()

        h2_match = SCENE_H2_RE.match(line)
        if h2_match:
            current_section = h2_match.group(1).strip()
            active_scene = None
            continue

        h3_match = SCENE_H3_RE.match(line)
        if h3_match and current_section == "探索場所":
            active_scene = _normalize_scene_name(h3_match.group(1).strip())
            sections[active_scene] = []
            continue

        if active_scene is not None:
            sections[active_scene].append(line)

    return sections


def _normalize_scene_fragment(fragment: str) -> str:
    normalized = fragment.strip(" 　")
    normalized = re.sub(r"^[ぁ-んー]+", "", normalized)
    normalized = re.sub(r"[ぁ-んー]+$", "", normalized)
    normalized = re.sub(r"^[^一-龥ぁ-んァ-ヶA-Za-z0-9]+", "", normalized)
    normalized = re.sub(r"[^一-龥ぁ-んァ-ヶA-Za-z0-9]+$", "", normalized)
    return normalized


def _extract_scene_fragments(text: str) -> set[str]:
    cleaned = re.sub(r"[*_`>#-]", " ", text)
    fragments: set[str] = set()

    for piece in SCENE_TOKEN_SPLIT_RE.split(cleaned):
        if not piece:
            continue

        for raw_fragment in SCENE_FRAGMENT_SPLIT_RE.split(piece):
            fragment = _normalize_scene_fragment(raw_fragment)
            if not fragment:
                continue
            if len(fragment) < 2:
                continue
            if re.fullmatch(r"[ぁ-んー]+", fragment):
                continue
            if fragment.isdigit():
                continue
            if re.search(r"[0-9]", fragment):
                continue
            if len(fragment) > 12:
                continue
            if fragment in SCENE_KEYWORD_STOPWORDS:
                continue
            fragments.add(fragment)

    return fragments


def _extract_scene_keywords(scenario_text: str) -> dict[str, set[str]]:
    sections = _extract_scene_sections(scenario_text)
    keyword_map: dict[str, set[str]] = {}
    keyword_counts: dict[str, int] = {}

    for scene_name, lines in sections.items():
        keywords = set()
        for line in lines:
            keywords.update(_extract_scene_fragments(line))
        keyword_map[scene_name] = keywords
        for keyword in keywords:
            keyword_counts[keyword] = keyword_counts.get(keyword, 0) + 1

    return {
        scene_name: {
            keyword
            for keyword in keywords
            if keyword_counts.get(keyword, 0) == 1 and keyword not in SCENE_KEYWORD_STOPWORDS
        }
        for scene_name, keywords in keyword_map.items()
    }


def _infer_scene_from_keywords(
    scenario_text: str,
    player_message: str,
    reply: str,
) -> str | None:
    combined_text = f"{player_message}\n{reply}"
    keyword_map = _extract_scene_keywords(scenario_text)

    best_scene: str | None = None
    best_score = 0

    for scene_name, keywords in keyword_map.items():
        score = 0
        match_count = 0
        for keyword in keywords:
            if keyword and keyword in combined_text:
                score += max(2, len(keyword))
                match_count += 1

        if score > best_score and (score >= 4 or match_count >= 2):
            best_scene = scene_name
            best_score = score

    return best_scene


def _infer_scene_from_texts(
    scenario_text: str,
    player_message: str,
    reply: str,
) -> str | None:
    scene_aliases = _extract_scene_aliases(scenario_text)

    # Prefer the player's explicit movement/action declaration when possible.
    for scene_name, aliases in scene_aliases:
        for alias in sorted(aliases, key=len, reverse=True):
            if alias and alias in player_message:
                return scene_name

    # Fall back to the full KP reply, which may mention the location outside the opening paragraph.
    for scene_name, aliases in scene_aliases:
        for alias in sorted(aliases, key=len, reverse=True):
            if alias and alias in reply:
                return scene_name

    return _infer_scene_from_keywords(scenario_text, player_message, reply)


def _summarize_scene(reply: str) -> str:
    lines = [line.strip() for line in reply.splitlines() if line.strip()]
    if not lines:
        return ""

    summary = lines[0]
    if len(lines) > 1 and len(summary) < 80:
        summary = f"{summary} {lines[1]}"
    return summary[:180]


class GMEngine:
    def __init__(self) -> None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is not set in environment")
        self.client = AsyncOpenAI(api_key=api_key)
        self.system_prompt_template = SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")
        self._scenario_cache: dict[str, str] = {}
        self._rules_text = self._load_rules()

    def _load_rules(self) -> str:
        path = RULES_DIR / "game_rules.md"
        return path.read_text(encoding="utf-8")

    def _load_scenario(self, scenario_id: str) -> str:
        if scenario_id not in self._scenario_cache:
            path = SCENARIOS_DIR / f"{scenario_id}.md"
            self._scenario_cache[scenario_id] = path.read_text(encoding="utf-8")
        return self._scenario_cache[scenario_id]

    def _extract_metadata(self, content: str) -> GMTurn:
        visible_lines: list[str] = []
        proposed_check: dict[str, Any] | None = None
        pending_check: dict[str, Any] | None = None
        state_update: dict[str, Any] | None = None

        for line in content.splitlines():
            parsed = _parse_metadata_line(line)
            if parsed is not None:
                kind, payload = parsed
                if kind == "CHECK":
                    if payload is not None:
                        if _check_phase(payload) == "offer":
                            proposed_check = payload
                        else:
                            pending_check = payload
                elif payload is not None:
                    state_update = payload if state_update is None else _merge_nested_dict(state_update, payload)
                continue

            visible_lines.append(line)

        reply = "\n".join(visible_lines).strip()
        if not reply:
            reply = "(KP responded with metadata only)"

        if proposed_check is None:
            proposed_check = _infer_check_offer_from_reply(reply)
        if pending_check is None:
            pending_check = _infer_pending_check_from_reply(reply)

        return GMTurn(
            reply=reply,
            proposed_check=proposed_check,
            pending_check=pending_check,
            state_update=state_update,
        )

    def _build_system_prompt(self, session: Session) -> str:
        scenario = self._load_scenario(session.scenario_id)
        characters_text = json.dumps(
            list(session.characters.values()),
            ensure_ascii=False,
            indent=2,
        )
        live_state_text = json.dumps(
            session.to_state_dict(),
            ensure_ascii=False,
            indent=2,
        )
        prompt = self.system_prompt_template
        prompt = prompt.replace("{rules}", self._rules_text)
        prompt = prompt.replace("{scenario}", scenario)
        prompt = prompt.replace("{characters}", characters_text)
        prompt = prompt.replace("{live_state}", live_state_text)
        return prompt

    async def respond(self, session: Session, character: dict, message: str) -> GMTurn:
        system_prompt = self._build_system_prompt(session)
        scenario_text = self._load_scenario(session.scenario_id)

        messages: list[ChatCompletionMessageParam] = [
            {"role": "system", "content": system_prompt},
        ]
        for history_entry in session.history:
            if history_entry["role"] == "assistant":
                messages.append({"role": "assistant", "content": history_entry["content"]})
            else:
                messages.append({"role": "user", "content": history_entry["content"]})
        messages.append({"role": "user", "content": f"[{character['name']}]: {message}"})

        log.debug("Sending %d messages to OpenAI (scenario=%s)", len(messages), session.scenario_id)

        response = await self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            temperature=0.8,
            max_tokens=800,
        )

        content = response.choices[0].message.content
        if content is None:
            return GMTurn(reply="(KP responded with no content)")
        turn = self._extract_metadata(content)

        if turn.state_update is None:
            turn.state_update = {}

        if "scene" not in turn.state_update:
            inferred_scene = _infer_scene_from_texts(scenario_text, message, turn.reply)
            if inferred_scene is not None:
                turn.state_update["scene"] = inferred_scene

        if turn.state_update and "scene_summary" not in turn.state_update:
            scene_summary = _summarize_scene(turn.reply)
            if scene_summary:
                turn.state_update["scene_summary"] = scene_summary

        if turn.state_update == {}:
            turn.state_update = None

        return turn
