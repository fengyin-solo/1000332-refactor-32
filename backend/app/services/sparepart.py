"""备件领用业务规则：状态流转、字段校验与筛选口径都收在这里。"""
from __future__ import annotations

from typing import Any

from app.services import sparepart_rules as rules
from app.store import store

MODULE = "sparepart"
REQUIRED_FIELDS = ["领用单号", "备件名称", "备件规格"]
STATUS_ORDER = rules.STATUS_ORDER
ACTION_RULES = rules.ACTION_TARGETS
NEGATIVE_ACTIONS = rules.NEGATIVE_ACTIONS


class SparepartService:
    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(MODULE)
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("领用单号", ""))]
        if status:
            rows = [row for row in rows if rules.matches_list_status(row, status)]
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        return store.find(MODULE, entry_id)

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing
        rows = store.rows(MODULE)
        entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        entry.update({field: values.get(field) for field in REQUIRED_FIELDS})
        entry["status"] = rules.STATUS_PENDING
        entry["pending"] = True
        entry["abnormal"] = False
        rows.append(entry)
        return entry, []

    def run_action(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"备件领用单 {entry_id} 不存在或已归档"
        return rules.apply_action(entry, str(action))
