from __future__ import annotations

import re
from typing import Callable

from .models import PlaytestIssue, PlaytestReport

AssertionFn = Callable[[PlaytestReport], list[PlaytestIssue]]

MENU_STYLE_RE = re.compile(r"(^|\n)\s*(?:\d+[.)]|[-*])\s")
META_DIALOGUE_RE = re.compile(r"(?:\d+の結果とは|成功だね|失敗だね|ファンブルだから)")


def _issue(severity: str, code: str, message: str, turn_index: int | None = None) -> PlaytestIssue:
    return PlaytestIssue(severity=severity, code=code, message=message, turn_index=turn_index)


def assert_scene_progress(report: PlaytestReport) -> list[PlaytestIssue]:
    scene_turns = [turn for turn in report.turns if turn.kind in {"opening", "scene", "check_resolution"}]
    if len(scene_turns) < 3:
        return []

    final_scene = report.final_state.get("environment", {}).get("scene")
    if final_scene == "導入":
        return [
            _issue(
                "failure",
                "scene_stuck_intro",
                "複数ターン進行しても最終 scene が '導入' のままです。",
                scene_turns[-1].turn_index,
            )
        ]
    return []


def assert_scene_metadata_present(report: PlaytestReport) -> list[PlaytestIssue]:
    issues: list[PlaytestIssue] = []
    for turn in report.turns:
        if turn.kind not in {"opening", "scene", "check_resolution"}:
            continue
        environment = turn.state.get("environment", {})
        if not environment.get("scene"):
            issues.append(_issue("failure", "scene_missing", "scene が state にありません。", turn.turn_index))
        if not environment.get("scene_summary"):
            issues.append(_issue("warning", "scene_summary_missing", "scene_summary が空です。", turn.turn_index))
    return issues


def assert_goal_and_threads_present(report: PlaytestReport) -> list[PlaytestIssue]:
    issues: list[PlaytestIssue] = []
    scene_turns = [turn for turn in report.turns if turn.kind in {"opening", "scene", "check_resolution"}]
    if len(scene_turns) < 2:
        return issues

    environment = report.final_state.get("environment", {})
    if not environment.get("scene_goal"):
        issues.append(_issue("warning", "scene_goal_missing", "最終 state に scene_goal がありません。"))
    if not environment.get("unresolved_threads"):
        issues.append(_issue("warning", "unresolved_threads_missing", "最終 state に unresolved_threads がありません。"))
    return issues


def assert_check_offer_precedes_pending(report: PlaytestReport) -> list[PlaytestIssue]:
    issues: list[PlaytestIssue] = []

    for turn in report.turns:
        if turn.pending_check is not None and turn.kind in {"opening", "scene"}:
            issues.append(
                _issue(
                    "failure",
                    "pending_without_offer",
                    "opening/scene ターンで proposed_check を経ず pending_check が出ています。",
                    turn.turn_index,
                )
            )
    return issues


def assert_no_metadata_only_reply(report: PlaytestReport) -> list[PlaytestIssue]:
    issues: list[PlaytestIssue] = []
    for turn in report.turns:
        if turn.gm_reply == "(KP responded with metadata only)":
            issues.append(
                _issue(
                    "warning",
                    "metadata_only_reply",
                    "GM 返答が本文なしのメタデータのみになっています。",
                    turn.turn_index,
                )
            )
    return issues


def assert_no_menu_style_reply(report: PlaytestReport) -> list[PlaytestIssue]:
    issues: list[PlaytestIssue] = []
    for turn in report.turns:
        if turn.gm_reply and MENU_STYLE_RE.search(turn.gm_reply):
            issues.append(
                _issue(
                    "warning",
                    "menu_style_reply",
                    "GM 返答が選択肢メニュー風になっています。",
                    turn.turn_index,
                )
            )
    return issues


def assert_no_meta_dialogue(report: PlaytestReport) -> list[PlaytestIssue]:
    issues: list[PlaytestIssue] = []
    for turn in report.turns:
        if turn.gm_reply and META_DIALOGUE_RE.search(turn.gm_reply):
            issues.append(
                _issue(
                    "failure",
                    "meta_dialogue",
                    "GM 返答が判定結果やダイス目を会話内でそのまま扱っています。",
                    turn.turn_index,
                )
            )
    return issues


DEFAULT_ASSERTIONS: list[AssertionFn] = [
    assert_scene_progress,
    assert_scene_metadata_present,
    assert_goal_and_threads_present,
    assert_check_offer_precedes_pending,
    assert_no_metadata_only_reply,
    assert_no_menu_style_reply,
    assert_no_meta_dialogue,
]


def run_assertions(report: PlaytestReport, assertions: list[AssertionFn] | None = None) -> PlaytestReport:
    for assertion in assertions or DEFAULT_ASSERTIONS:
        report.issues.extend(assertion(report))
    return report
