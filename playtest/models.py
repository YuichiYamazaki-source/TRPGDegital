from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

IssueSeverity = Literal["warning", "failure"]
TurnKind = Literal["opening", "scene", "check_offer_response", "check_resolution"]


@dataclass
class PlaytestConfig:
    scenario_id: str
    character_id: str
    user_id: str = "playtest-user"
    display_name: str = "Codex Player"
    max_turns: int = 8
    stop_on_failure: bool = False


@dataclass
class TurnRecord:
    turn_index: int
    kind: TurnKind
    player_message: str | None = None
    player_decision: str | None = None
    player_roll: int | None = None
    gm_reply: str | None = None
    state: dict[str, Any] = field(default_factory=dict)
    proposed_check: dict[str, Any] | None = None
    pending_check: dict[str, Any] | None = None
    check_result: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PlaytestIssue:
    severity: IssueSeverity
    code: str
    message: str
    turn_index: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PlaytestReport:
    config: PlaytestConfig
    turns: list[TurnRecord]
    final_state: dict[str, Any]
    issues: list[PlaytestIssue] = field(default_factory=list)

    @property
    def failures(self) -> list[PlaytestIssue]:
        return [issue for issue in self.issues if issue.severity == "failure"]

    @property
    def warnings(self) -> list[PlaytestIssue]:
        return [issue for issue in self.issues if issue.severity == "warning"]

    def to_dict(self) -> dict[str, Any]:
        return {
            "config": asdict(self.config),
            "turns": [turn.to_dict() for turn in self.turns],
            "final_state": self.final_state,
            "issues": [issue.to_dict() for issue in self.issues],
            "summary": {
                "turn_count": len(self.turns),
                "failure_count": len(self.failures),
                "warning_count": len(self.warnings),
                "final_scene": self.final_state.get("environment", {}).get("scene"),
            },
        }
