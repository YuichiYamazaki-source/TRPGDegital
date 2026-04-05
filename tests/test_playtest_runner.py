from __future__ import annotations

import os
import unittest

os.environ.setdefault("OPENAI_API_KEY", "playtest-dummy-key")

from gm import GMTurn
from main import _apply_state_update
from playtest.agents import ScriptedPlayerAgent
from playtest.clients import InProcessSessionClient
from playtest.models import PlaytestConfig
from playtest.runner import PlaytestRunner
from session import EnvironmentState, Session, SessionManager


class PlaytestRunnerTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.client = InProcessSessionClient()
        self.client.main.session_manager = SessionManager()

    async def test_runner_handles_offer_accept_and_resolution_flow(self) -> None:
        responses = [
            GMTurn(
                reply="洋館の扉はわずかに開き、異臭が漂ってくる。足元には雨に濡れた土が点々と続いている。",
                state_update={
                    "scene": "玄関ホール",
                    "scene_summary": "扉の向こうに異臭が漂い、足元には湿った土の痕が続いている。",
                    "scene_highlights": ["湿った土の痕", "壁際の古いコート"],
                    "scene_goal": "館の異変と桐島の行方を探る",
                    "unresolved_threads": ["土の痕はどこへ続くのか", "桐島は館の中にいるのか"],
                },
            ),
            GMTurn(
                reply="壁の黒ずんだ模様を詳しく追うなら【目星】で判定できます。成功値は70です。判定しますか？",
                proposed_check={
                    "type": "skill",
                    "phase": "offer",
                    "actor": "田中 勇",
                    "skill": "目星",
                    "target": 70,
                    "difficulty": "regular",
                    "reason": "壁の黒ずんだ模様を詳しく追う",
                },
                state_update={
                    "scene": "玄関ホール",
                    "scene_summary": "黒ずんだ模様が壁一面に浮かび、近づくほど規則性があるように見える。",
                    "scene_highlights": ["壁の黒ずんだ模様", "奥へ続く足跡"],
                    "scene_goal": "館の異変と桐島の行方を探る",
                    "unresolved_threads": ["壁の模様が何を示すのか", "足跡の主は誰か"],
                },
            ),
            GMTurn(
                reply="懐中電灯の光を滑らせると、黒ずんだ線は乱雑ではなく、同じ記号が何度も重ねられていることが分かる。足跡はその脇を抜け、館の奥へ向かっている。",
                state_update={
                    "scene": "玄関ホール",
                    "scene_summary": "壁の模様は記号の反復で、足跡は館の奥へ続いている。",
                    "scene_highlights": ["反復する記号", "館の奥へ続く足跡"],
                    "scene_goal": "足跡の先と記号の意味をつなげて考える",
                    "unresolved_threads": ["足跡の主は誰か", "記号は儀式と関係があるのか"],
                    "clues_added": ["壁の模様は同じ記号の反復"],
                },
            ),
        ]

        async def fake_respond(session, character, message):
            return responses.pop(0)

        self.client.main.gm_engine.respond = fake_respond

        runner = PlaytestRunner(
            self.client,
            ScriptedPlayerAgent(scripted_messages=["壁の模様を調べます。"]),
        )
        report = await runner.run(
            PlaytestConfig(
                scenario_id="scenario_01",
                character_id="tanaka",
                max_turns=3,
            )
        )

        self.assertEqual(report.final_state["environment"]["scene"], "玄関ホール")
        self.assertEqual(report.final_state["environment"]["scene_goal"], "足跡の先と記号の意味をつなげて考える")
        self.assertIn("壁の模様は同じ記号の反復", report.final_state["environment"]["clues"])
        self.assertEqual(len(report.failures), 0)
        self.assertTrue(any(turn.proposed_check is not None for turn in report.turns))
        self.assertTrue(any(turn.check_result is not None for turn in report.turns))

    async def test_state_update_preserves_goal_and_threads_when_omitted(self) -> None:
        session_id = self.client.main.session_manager.create_session(
            channel_id="preserve-test",
            scenario_id="scenario_01",
            characters={"tanaka": self.client.main.CHARACTERS["tanaka"]},
            players=[{"user_id": "user-1", "display_name": "player", "character_id": "tanaka"}],
        )
        session = self.client.main.session_manager.get_session(session_id)
        assert session is not None

        session.environment = EnvironmentState(
            scene="玄関ホール",
            scene_summary="異臭が漂う。",
            scene_highlights=["壁の模様"],
            scene_goal="館の異変と桐島の行方を探る",
            unresolved_threads=["壁の模様の意味", "足跡の主"],
        )

        _apply_state_update(
            session,
            {
                "scene": "書斎",
                "scene_summary": "書棚に囲まれた部屋だ。",
                "scene_highlights": ["散乱した原稿"],
            },
        )

        self.assertEqual(session.environment.scene, "書斎")
        self.assertEqual(session.environment.scene_goal, "館の異変と桐島の行方を探る")
        self.assertEqual(session.environment.unresolved_threads, ["壁の模様の意味", "足跡の主"])

    async def test_state_update_ignores_empty_goal_and_threads(self) -> None:
        session_id = self.client.main.session_manager.create_session(
            channel_id="preserve-empty-test",
            scenario_id="scenario_01",
            characters={"tanaka": self.client.main.CHARACTERS["tanaka"]},
            players=[{"user_id": "user-1", "display_name": "player", "character_id": "tanaka"}],
        )
        session = self.client.main.session_manager.get_session(session_id)
        assert session is not None

        session.environment = EnvironmentState(
            scene="玄関ホール",
            scene_summary="異臭が漂う。",
            scene_goal="館の異変と桐島の行方を探る",
            unresolved_threads=["壁の模様の意味", "足跡の主"],
        )

        _apply_state_update(
            session,
            {
                "scene": "地下室",
                "scene_goal": "",
                "unresolved_threads": [],
            },
        )

        self.assertEqual(session.environment.scene_goal, "館の異変と桐島の行方を探る")
        self.assertEqual(session.environment.unresolved_threads, ["壁の模様の意味", "足跡の主"])
