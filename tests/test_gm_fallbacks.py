from __future__ import annotations

import unittest

from gm import _infer_check_offer_from_reply, _normalize_mixed_check_reply, _synthesize_metadata_reply


class GMFallbackTests(unittest.TestCase):
    def test_skill_offer_without_explicit_target_line_is_detected(self) -> None:
        payload = _infer_check_offer_from_reply(
            "この模様を詳しく調べるには、【目星】の判定が必要です。判定しますか？"
        )
        self.assertIsNotNone(payload)
        assert payload is not None
        self.assertEqual(payload["type"], "skill")
        self.assertEqual(payload["phase"], "offer")
        self.assertEqual(payload["skill"], "目星")

    def test_san_offer_fallback_is_detected(self) -> None:
        payload = _infer_check_offer_from_reply(
            "その光景を正面から見てしまったなら、SAN値チェックが必要です。判定しますか？"
        )
        self.assertIsNotNone(payload)
        assert payload is not None
        self.assertEqual(payload["type"], "san")
        self.assertEqual(payload["phase"], "offer")

    def test_mixed_offer_and_pending_reply_is_downgraded_to_offer(self) -> None:
        reply, proposed, pending = _normalize_mixed_check_reply(
            "ここで、手がかりを見抜くための技能判定が必要です。判定しますか？【目星】の判定をお願いします（成功値：70）",
            None,
            {
                "type": "skill",
                "phase": "pending",
                "skill": "目星",
                "target": 70,
                "reason": "",
            },
        )
        self.assertIsNotNone(proposed)
        self.assertIsNone(pending)
        assert proposed is not None
        self.assertEqual(proposed["phase"], "offer")
        self.assertNotIn("判定をお願いします", reply)

    def test_skill_offer_using_skill_usage_phrase_is_detected(self) -> None:
        payload = _infer_check_offer_from_reply(
            "この不気味な光景を詳しく調べたくなります。『聞き耳』の技能を使って音の正体を探りますか？"
        )
        self.assertIsNotNone(payload)
        assert payload is not None
        self.assertEqual(payload["type"], "skill")
        self.assertEqual(payload["phase"], "offer")
        self.assertEqual(payload["skill"], "聞き耳")

    def test_metadata_only_reply_gets_human_fallback_text(self) -> None:
        reply = _synthesize_metadata_reply(
            None,
            {"type": "skill", "phase": "offer", "skill": "目星", "target": 70, "reason": ""},
            None,
        )
        self.assertIn("【目星】", reply)
        self.assertIn("判定しますか", reply)
