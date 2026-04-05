from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from .agents import OpenAIPlayerAgent, ScriptedPlayerAgent
from .clients import InProcessSessionClient
from .models import PlaytestConfig
from .runner import PlaytestRunner


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run automated TRPG playtests in-process.")
    parser.add_argument("--scenario", default="scenario_01", help="Scenario id to play")
    parser.add_argument("--character", default="tanaka", help="Character id to use")
    parser.add_argument("--agent", choices=["scripted", "openai"], default="scripted", help="Player agent type")
    parser.add_argument("--max-turns", type=int, default=8, help="Maximum number of turns to play")
    parser.add_argument("--report-json", help="Write the report JSON to this file")
    parser.add_argument("--transcript-json", help="Alias for --report-json")
    return parser


async def _run(args: argparse.Namespace) -> int:
    config = PlaytestConfig(
        scenario_id=args.scenario,
        character_id=args.character,
        max_turns=args.max_turns,
    )

    agent = ScriptedPlayerAgent() if args.agent == "scripted" else OpenAIPlayerAgent()
    runner = PlaytestRunner(InProcessSessionClient(), agent)
    report = await runner.run(config)

    print(f"Scenario: {config.scenario_id}")
    print(f"Character: {config.character_id}")
    print(f"Turns: {len(report.turns)}")
    print(f"Final scene: {report.final_state.get('environment', {}).get('scene')}")
    print(f"Failures: {len(report.failures)}")
    print(f"Warnings: {len(report.warnings)}")

    for issue in report.issues:
        prefix = "FAIL" if issue.severity == "failure" else "WARN"
        location = f" turn={issue.turn_index}" if issue.turn_index is not None else ""
        print(f"[{prefix}] {issue.code}{location}: {issue.message}")

    output_path = args.report_json or args.transcript_json
    if output_path:
        Path(output_path).write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Report written to {output_path}")

    return 1 if report.failures else 0


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    raise SystemExit(asyncio.run(_run(args)))


if __name__ == "__main__":
    main()
