"""备件领用统一状态规则与既有外部行为回归测试。"""
from __future__ import annotations

import unittest

from app.seed import SEED_ROWS
from app.services import sparepart_rules as rules
from app.services.sparepart import SparepartService
from app.store import store

MODULE = "sparepart"


def reset_sparepart_rows() -> None:
    store.rows(MODULE)[:] = [dict(row) for row in SEED_ROWS[MODULE]]


class SparepartRuleTest(unittest.TestCase):
    def tearDown(self) -> None:
        rules.SPEC_RULES.clear()

    def test_default_rule_keeps_existing_return_entries_available(self) -> None:
        for row in SEED_ROWS[MODULE]:
            entry = dict(row)
            target, message = rules.validate_action("退回备件", entry)
            self.assertEqual(target, rules.STATUS_RETURNED)
            self.assertIsNone(message)

    def test_quantity_rule_is_configured_in_one_spec_table(self) -> None:
        rules.SPEC_RULES["熔断器"] = rules.ReturnRule(min_quantity=5)
        entry = {"备件规格": "熔断器", "领用数量": 4, "所属班组": "其他班组"}

        self.assertIsNotNone(rules.return_rule("熔断器").reject_reason(entry))

        entry["领用数量"] = 5
        self.assertIsNone(rules.return_rule("熔断器").reject_reason(entry))

    def test_team_rule_is_configured_in_one_spec_table(self) -> None:
        rules.SPEC_RULES["IGBT模块"] = rules.ReturnRule(allowed_teams=frozenset({"变电一班"}))
        entry = {"备件规格": "IGBT模块", "领用数量": 1, "所属班组": "其他班组"}

        self.assertIsNotNone(rules.return_rule("IGBT模块").reject_reason(entry))

        entry["所属班组"] = "变电一班"
        self.assertIsNone(rules.return_rule("IGBT模块").reject_reason(entry))

    def test_quantity_and_team_checks_share_one_spec_rule(self) -> None:
        rules.SPEC_RULES["驱动板"] = rules.ReturnRule(
            min_quantity=5,
            allowed_teams=frozenset({"检修一班"}),
        )
        entry = {"备件规格": "驱动板", "领用数量": 4, "所属班组": "检修二班"}

        approve_target, _ = rules.validate_action("批准领用", entry)
        issue_target, _ = rules.validate_action("确认发放", entry)
        return_target, reason = rules.validate_action("退回备件", entry)

        self.assertEqual(approve_target, rules.STATUS_APPROVED)
        self.assertEqual(issue_target, rules.STATUS_ISSUED)
        self.assertIsNone(return_target)
        self.assertEqual(reason, "领用数量不少于 5 才允许退回")

        entry["领用数量"] = 5
        _, reason = rules.validate_action("退回备件", entry)
        self.assertEqual(reason, "当前所属班组不允许退回该备件规格")

        entry["所属班组"] = "检修一班"
        return_target, reason = rules.validate_action("退回备件", entry)
        self.assertEqual(return_target, rules.STATUS_RETURNED)
        self.assertIsNone(reason)

    def test_unknown_action_does_not_change_entry(self) -> None:
        entry = dict(SEED_ROWS[MODULE][0])
        before = dict(entry)

        target, message = rules.validate_action("未知动作", entry)

        self.assertIsNone(target)
        self.assertEqual(message, "动作「未知动作」不属于备件领用可执行范围")
        self.assertEqual(entry, before)


class SparepartServiceBehaviorTest(unittest.TestCase):
    def setUp(self) -> None:
        reset_sparepart_rows()
        self.service = SparepartService()

    def tearDown(self) -> None:
        reset_sparepart_rows()

    def test_seed_list_filters_and_return_count_remain_unchanged(self) -> None:
        self.assertEqual(self.service.list_entries()[1], 3)
        self.assertEqual(self.service.list_entries(status="待审批")[1], 1)
        self.assertEqual(self.service.list_entries(status="已批准")[1], 1)
        self.assertEqual(self.service.list_entries(status="已领用")[1], 1)
        self.assertEqual(self.service.list_entries(status="未知状态")[1], 0)
        self.assertEqual(self.service.list_entries(keyword="SPAR-000")[1], 3)
        self.assertEqual(self.service.list_entries(keyword="missing")[1], 0)

        for row in store.rows(MODULE):
            entry, message = self.service.run_action(int(row["id"]), "退回备件")
            self.assertEqual(entry["status"], "已退回")
            self.assertFalse(entry["pending"])
            self.assertFalse(entry["abnormal"])
            self.assertEqual(message, "备件领用单已退回备件")

        self.assertEqual(self.service.list_entries(status="已退回")[1], 3)

    def test_issue_result_remains_unchanged(self) -> None:
        approved = store.rows(MODULE)[1]
        self.assertTrue(approved["abnormal"])

        entry, message = self.service.run_action(2, "确认发放")

        self.assertEqual(entry["status"], "已领用")
        self.assertTrue(entry["pending"])
        self.assertFalse(entry["abnormal"])
        self.assertEqual(message, "备件领用单已确认发放")
        self.assertEqual(entry["领用状态"], approved["领用状态"])


if __name__ == "__main__":
    unittest.main()
