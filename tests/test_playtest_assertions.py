from __future__ import annotations

import unittest

from playtest.assertions import run_assertions
from playtest.models import PlaytestConfig, PlaytestReport, TurnRecord


class PlaytestAssertionTests(unittest.TestCase):
    def test_detects_menu_style_and_meta_dialogue(self) -> None:
        report = PlaytestReport(
            config=PlaytestConfig(scenario_id="scenario_01", character_id="tanaka"),
            turns=[
                TurnRecord(
                    turn_index=0,
                    kind="opening",
                    gm_reply="1. 玄関を調べる\n2. 2階へ行く\n9の結果とは、なかなかの説得力だね。",
                    state={"environment": {"scene": "玄関ホール", "scene_summary": "異臭が漂う。"}},
                )
            ],
            final_state={
                "environment": {
                    "scene": "玄関ホール",
                    "scene_summary": "異臭が漂う。",
                    "scene_goal": "",
                    "unresolved_threads": [],
                }
            },
        )

        run_assertions(report)
        codes = {issue.code for issue in report.issues}
        self.assertIn("menu_style_reply", codes)
        self.assertIn("meta_dialogue", codes)

    def test_detects_pending_without_offer(self) -> None:
        report = PlaytestReport(
            config=PlaytestConfig(scenario_id="scenario_01", character_id="tanaka"),
            turns=[
                TurnRecord(
                    turn_index=1,
                    kind="scene",
                    gm_reply="【目星】の判定をお願いします（成功値：70）",
                    state={"environment": {"scene": "玄関ホール", "scene_summary": "異臭が漂う。"}},
                    pending_check={"kind": "skill", "skill_name": "目星"},
                )
            ],
            final_state={
                "environment": {
                    "scene": "玄関ホール",
                    "scene_summary": "異臭が漂う。",
                    "scene_goal": "館の異変を探る",
                    "unresolved_threads": ["壁の模様の意味"],
                }
            },
        )

        run_assertions(report)
        codes = {issue.code for issue in report.issues}
        self.assertIn("pending_without_offer", codes)

    def test_detects_metadata_only_reply(self) -> None:
        report = PlaytestReport(
            config=PlaytestConfig(scenario_id="scenario_01", character_id="tanaka"),
            turns=[
                TurnRecord(
                    turn_index=2,
                    kind="scene",
                    gm_reply="(KP responded with metadata only)",
                    state={"environment": {"scene": "玄関ホール", "scene_summary": "異臭が漂う。"}},
                    proposed_check={"kind": "skill", "skill_name": "目星"},
                )
            ],
            final_state={
                "environment": {
                    "scene": "玄関ホール",
                    "scene_summary": "異臭が漂う。",
                    "scene_goal": "館の異変を探る",
                    "unresolved_threads": ["壁の模様の意味"],
                }
            },
        )

        run_assertions(report)
        codes = {issue.code for issue in report.issues}
        self.assertIn("metadata_only_reply", codes)
