from __future__ import annotations

from typing import Any

from .assertions import AssertionFn, run_assertions
from .clients import InProcessSessionClient
from .models import PlaytestConfig, PlaytestReport, TurnRecord


class PlaytestRunner:
    def __init__(
        self,
        session_client: InProcessSessionClient,
        player_agent: Any,
        *,
        assertions: list[AssertionFn] | None = None,
    ) -> None:
        self.session_client = session_client
        self.player_agent = player_agent
        self.assertions = assertions

    async def run(self, config: PlaytestConfig) -> PlaytestReport:
        created = await self.session_client.create_session(
            config.scenario_id,
            config.user_id,
            config.display_name,
            config.character_id,
        )
        session_id = created["session_id"]
        turns: list[TurnRecord] = []

        try:
            opening = await self.session_client.chat(session_id, config.character_id, "（セッション開始）")
            opening_state = await self.session_client.get_state(session_id)
            turns.append(
                TurnRecord(
                    turn_index=0,
                    kind="opening",
                    player_message="（セッション開始）",
                    gm_reply=opening["reply"],
                    state=opening_state,
                    proposed_check=opening.get("proposed_check"),
                    pending_check=opening.get("pending_check"),
                )
            )

            for turn_index in range(1, config.max_turns + 1):
                state = await self.session_client.get_state(session_id)

                if state.get("pending_check") is not None:
                    roll = await self.player_agent.choose_roll(config, state, turns)
                    result = await self.session_client.resolve_check(session_id, config.character_id, roll)
                    next_state = await self.session_client.get_state(session_id)
                    turns.append(
                        TurnRecord(
                            turn_index=turn_index,
                            kind="check_resolution",
                            player_roll=roll,
                            gm_reply=result["reply"],
                            state=next_state,
                            proposed_check=result.get("proposed_check"),
                            pending_check=result.get("pending_check"),
                            check_result=result.get("check_result"),
                        )
                    )
                    continue

                if state.get("proposed_check") is not None:
                    decision = await self.player_agent.choose_check_response(config, state, turns)
                    result = await self.session_client.respond_to_check(session_id, config.character_id, decision)
                    next_state = await self.session_client.get_state(session_id)
                    turns.append(
                        TurnRecord(
                            turn_index=turn_index,
                            kind="check_offer_response",
                            player_decision=decision,
                            gm_reply=result["message"],
                            state=next_state,
                            proposed_check=result.get("proposed_check"),
                            pending_check=result.get("pending_check"),
                        )
                    )
                    continue

                message = await self.player_agent.choose_scene_action(config, state, turns)
                result = await self.session_client.chat(session_id, config.character_id, message)
                next_state = await self.session_client.get_state(session_id)
                turns.append(
                    TurnRecord(
                        turn_index=turn_index,
                        kind="scene",
                        player_message=message,
                        gm_reply=result["reply"],
                        state=next_state,
                        proposed_check=result.get("proposed_check"),
                        pending_check=result.get("pending_check"),
                    )
                )

            final_state = await self.session_client.get_state(session_id)
        finally:
            try:
                await self.session_client.end_session(session_id)
            except Exception:
                pass

        report = PlaytestReport(config=config, turns=turns, final_state=final_state)
        return run_assertions(report, self.assertions)
