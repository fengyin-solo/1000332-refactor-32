"""备件领用状态与退回规则。

列表入口的状态筛选以及审批、发放、退回动作都只依赖这里的同一份规则。新增备件
规格时，只需在 SPEC_RULES 中补充对应规格的退回条件；没有特殊要求的规格沿用默认规则。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

STATUS_PENDING = "待审批"
STATUS_APPROVED = "已批准"
STATUS_ISSUED = "已领用"
STATUS_RETURNED = "已退回"

STATUS_ORDER = [STATUS_PENDING, STATUS_APPROVED, STATUS_ISSUED, STATUS_RETURNED]
ACTION_TARGETS: dict[str, str] = {
    "批准领用": STATUS_APPROVED,
    "确认发放": STATUS_ISSUED,
    "退回备件": STATUS_RETURNED,
}
NEGATIVE_ACTIONS: list[str] = []


@dataclass(frozen=True)
class ReturnRule:
    """描述一个备件规格允许退回的条件。

    - min_quantity：领用数量不少于该值；为 None 时不检查数量。
    - allowed_teams：所属班组必须在名单内；为 None 时不检查班组。
    """

    min_quantity: float | None = None
    allowed_teams: frozenset[str] | None = None

    def reject_reason(self, entry: dict[str, Any]) -> str | None:
        if self.min_quantity is not None and _to_number(entry.get("领用数量")) < self.min_quantity:
            return f"领用数量不少于 {_format_number(self.min_quantity)} 才允许退回"
        team = str(entry.get("所属班组") or "").strip()
        if self.allowed_teams is not None and team not in self.allowed_teams:
            return "当前所属班组不允许退回该备件规格"
        return None


DEFAULT_RETURN_RULE = ReturnRule()

# 新增有特殊退回要求的备件规格时，只在这里增加一项。
SPEC_RULES: dict[str, ReturnRule] = {}


def return_rule(specification: Any) -> ReturnRule:
    return SPEC_RULES.get(str(specification or "").strip(), DEFAULT_RETURN_RULE)


def matches_list_status(entry: dict[str, Any], status: str) -> bool:
    """判断领用单是否命中列表入口的状态筛选。未知状态不匹配任何领用单。"""
    return status in STATUS_ORDER and entry.get("status") == status


def validate_action(action: str, entry: dict[str, Any]) -> tuple[str | None, str | None]:
    """校验动作并返回目标状态。

    返回 ``(target_status, error_message)``。未配置特殊规格规则时，三个已登记动作
    均保持原有外部行为；配置后，退回动作的规格、数量、班组条件统一由 ``ReturnRule`` 判断。
    """
    target = ACTION_TARGETS.get(action)
    if target is None:
        return None, f"动作「{action}」不属于备件领用可执行范围"
    if target not in STATUS_ORDER:
        return None, f"目标状态「{target}」不在允许的状态序列里"
    if action == "退回备件":
        reason = return_rule(entry.get("备件规格")).reject_reason(entry)
        if reason is not None:
            return None, reason
    return target, None


def apply_action(entry: dict[str, Any], action: str) -> tuple[dict[str, Any] | None, str]:
    """执行状态变更，并返回与原服务一致的消息格式。"""
    target, message = validate_action(action, entry)
    if target is None:
        return None, message or "备件领用动作校验未通过"
    entry["status"] = target
    entry["pending"] = target != STATUS_RETURNED
    entry["abnormal"] = action in NEGATIVE_ACTIONS
    return entry, f"备件领用单已{action}"


def _to_number(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _format_number(value: float | int) -> str:
    number = float(value)
    return str(int(number)) if number.is_integer() else str(number)
