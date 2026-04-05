from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionMessageParam

from session import Session

load_dotenv()

log = logging.getLogger(__name__)

SCENARIOS_DIR = Path("scenarios")
RULES_DIR = Path("Rule")
SYSTEM_PROMPT_PATH = Path("prompts/system_prompt.txt")


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
        rules_parts: list[str] = []
        for path in sorted(RULES_DIR.glob("*.md")):
            rules_parts.append(path.read_text(encoding="utf-8"))
        return "\n\n".join(rules_parts)

    def _load_scenario(self, scenario_id: str) -> str:
        if scenario_id not in self._scenario_cache:
            path = SCENARIOS_DIR / f"{scenario_id}.md"
            self._scenario_cache[scenario_id] = path.read_text(encoding="utf-8")
        return self._scenario_cache[scenario_id]

    def _build_system_prompt(self, session: Session) -> str:
        scenario = self._load_scenario(session.scenario_id)
        characters_text = json.dumps(
            list(session.characters.values()),
            ensure_ascii=False,
            indent=2,
        )
        return self.system_prompt_template.format(
            rules=self._rules_text,
            scenario=scenario,
            characters=characters_text,
        )

    async def respond(self, session: Session, character: dict, message: str) -> str:
        system_prompt = self._build_system_prompt(session)

        messages: list[ChatCompletionMessageParam] = [
            {"role": "system", "content": system_prompt},
        ]
        for h in session.history:
            if h["role"] == "assistant":
                messages.append({"role": "assistant", "content": h["content"]})
            else:
                messages.append({"role": "user", "content": h["content"]})
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
            return "(KP responded with no content)"
        return content
