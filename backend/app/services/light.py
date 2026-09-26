"""路灯管养业务规则。

数据分三张表，全部按「灯杆编号」挂接，互不串数据：

- ``light``：路灯台账，一根灯杆编号一行，是亮灯状态的唯一权威来源；
- ``light_repair``：报修记录，每次报修新增一行（历史不覆盖），再次编辑只改原单据；
- ``light_change``：灯型类别更换记录，台账灯型被换过一次就留一条。

报修单据上的「故障类型、报修日期」只属于对应灯杆编号；台账、报修弹窗、养护记录
三处看到的亮灯状态始终取台账同一份（``亮灯状态`` 与内部 ``status`` 也不再分叉）。
"""
from __future__ import annotations

from datetime import date
from typing import Any

from app.store import store

MODULE = "light"
REPAIR_MODULE = "light_repair"
CHANGE_MODULE = "light_change"

REQUIRED_FIELDS = ["灯杆编号", "所在路段", "灯型类别"]
LEDGER_FIELDS = ["灯杆编号", "所在路段", "灯型类别", "功率瓦数", "亮灯时段"]

STATUS_ORDER = ["正常亮灯", "故障不亮", "维修中", "已拆除"]
# 单据状态与灯杆亮灯状态共用一套口径，保证台账/报修/养护三处同步。
REPAIR_STATUS_FLOW = {
    "已登记": "故障不亮",
    "已派修": "维修中",
    "已修复": "正常亮灯",
}
FAULT_TYPES = ["光源不亮", "灯杆破损", "线路故障", "控制器故障", "灯罩损坏", "其他"]
DEFAULT_FAULT_TYPE = "光源不亮"

EDITABLE_REPAIR_FIELDS = ["故障类型", "报修日期", "处理情况", "更换灯型类别", "亮灯状态"]


def _next_id(rows: list[dict[str, Any]]) -> int:
    return max((int(row.get("id", 0)) for row in rows), default=0) + 1


def _clean(values: dict[str, Any], field: str) -> str:
    return str(values.get(field) or "").strip()


def _today() -> str:
    return date.today().isoformat()


class LightService:
    # ------------------------------------------------------------------ 台账
    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        road: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(MODULE)
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("灯杆编号", ""))]
        if road:
            rows = [row for row in rows if road in str(row.get("所在路段", ""))]
        if status:
            # 亮灯状态只有一份：展示列、过滤条件、内部 status 完全一致。
            rows = [row for row in rows if row.get("亮灯状态") == status]
        rows = sorted(rows, key=lambda row: int(row.get("id", 0)))
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        return store.find(MODULE, entry_id)

    def find_by_pole(self, pole_no: str) -> dict[str, Any] | None:
        for row in store.rows(MODULE):
            if str(row.get("灯杆编号", "")).strip() == pole_no.strip():
                return row
        return None

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [field for field in REQUIRED_FIELDS if not _clean(values, field)]
        if missing:
            return None, missing
        pole_no = _clean(values, "灯杆编号")
        if self.find_by_pole(pole_no) is not None:
            return None, [f"灯杆编号 {pole_no} 已登记，不能重复建台账"]
        rows = store.rows(MODULE)
        entry: dict[str, Any] = {"id": _next_id(rows)}
        for field in LEDGER_FIELDS:
            entry[field] = _clean(values, field)
        entry["status"] = STATUS_ORDER[0]
        entry["亮灯状态"] = STATUS_ORDER[0]
        entry["故障类型"] = None
        entry["报修日期"] = None
        entry["pending"] = True
        entry["abnormal"] = False
        rows.append(entry)
        return entry, []

    def _sync_status(self, entry: dict[str, Any], status: str) -> None:
        """亮灯状态的唯一写入口：台账展示列与内部 status 一起改。"""
        entry["亮灯状态"] = status
        entry["status"] = status
        entry["abnormal"] = status in {"故障不亮", "维修中"}
        entry["pending"] = status != "已拆除"

    def update_ledger(self, entry_id: int, values: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"路灯设施 {entry_id} 不存在或已归档"
        new_type = _clean(values, "灯型类别")
        if new_type and new_type != str(entry.get("灯型类别") or ""):
            # 更换灯型类别：台账换新值，同时单独留一条更换历史，旧类别可追溯。
            self._record_type_change(entry, new_type)
            entry["灯型类别"] = new_type
        for field in ("所在路段", "功率瓦数", "亮灯时段"):
            if field in values:
                entry[field] = _clean(values, field)
        new_status = _clean(values, "亮灯状态")
        if new_status:
            if new_status not in STATUS_ORDER:
                return None, f"亮灯状态「{new_status}」不在允许范围内"
            self._sync_status(entry, new_status)
        return entry, "路灯台账已更新"

    def _record_type_change(self, entry: dict[str, Any], new_type: str) -> dict[str, Any]:
        change = {
            "id": _next_id(store.rows(CHANGE_MODULE)),
            "灯杆编号": entry["灯杆编号"],
            "原灯型类别": entry.get("灯型类别"),
            "新灯型类别": new_type,
            "更换日期": _today(),
        }
        store.rows(CHANGE_MODULE).append(change)
        return change

    # ------------------------------------------------------------------ 报修
    def list_repairs(
        self,
        *,
        pole_no: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(REPAIR_MODULE)
        if pole_no:
            rows = [row for row in rows if pole_no in str(row.get("灯杆编号", ""))]
        if status:
            rows = [row for row in rows if row.get("单据状态") == status]
        # 同杆多单时最新报修在前，历史单据原样保留。
        rows = sorted(rows, key=lambda row: int(row.get("id", 0)), reverse=True)
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def get_repair(self, repair_id: int) -> dict[str, Any] | None:
        return store.find(REPAIR_MODULE, repair_id)

    def create_repair(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
        pole_no = _clean(values, "灯杆编号")
        if not pole_no:
            return None, "缺少灯杆编号，报修必须挂在具体灯杆上"
        entry = self.find_by_pole(pole_no)
        if entry is None:
            return None, f"灯杆编号 {pole_no} 未登记台账，请先登记路灯设施"
        fault_type = _clean(values, "故障类型") or DEFAULT_FAULT_TYPE
        if fault_type not in FAULT_TYPES:
            return None, f"故障类型「{fault_type}」不在允许范围内"
        repair_date = _clean(values, "报修日期") or _today()
        # 每次报修都新开一张单据，绝不用新值覆盖该杆的历史报修。
        record: dict[str, Any] = {
            "id": _next_id(store.rows(REPAIR_MODULE)),
            "灯杆编号": pole_no,
            "故障类型": fault_type,
            "报修日期": repair_date,
            "处理情况": _clean(values, "处理情况") or None,
            "更换灯型类别": None,
            "单据状态": "已登记",
        }
        record["亮灯状态"] = REPAIR_STATUS_FLOW["已登记"]
        store.rows(REPAIR_MODULE).append(record)
        # 故障类型与报修日期只挂在对应灯杆编号上（台账镜像该杆最新报修）。
        entry["故障类型"] = fault_type
        entry["报修日期"] = repair_date
        self._sync_status(entry, REPAIR_STATUS_FLOW["已登记"])
        return record, "报修登记已保存"

    def update_repair(self, repair_id: int, values: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
        """再次打开报修单时，改的是原单据本身；保存后再次打开仍是改过的那份。"""
        record = store.find(REPAIR_MODULE, repair_id)
        if record is None:
            return None, f"报修记录 {repair_id} 不存在或已归档"
        entry = self.find_by_pole(str(record["灯杆编号"]))
        if entry is None:
            return None, f"灯杆编号 {record.get('灯杆编号')} 的台账已不存在"

        fault_type = _clean(values, "故障类型")
        if fault_type:
            if fault_type not in FAULT_TYPES:
                return None, f"故障类型「{fault_type}」不在允许范围内"
            record["故障类型"] = fault_type
        repair_date = _clean(values, "报修日期")
        if repair_date:
            record["报修日期"] = repair_date
        if "处理情况" in values:
            record["处理情况"] = _clean(values, "处理情况") or None

        new_type = _clean(values, "更换灯型类别")
        if new_type and new_type != str(record.get("更换灯型类别") or ""):
            record["更换灯型类别"] = new_type
            self._record_type_change(entry, new_type)
            entry["灯型类别"] = new_type

        new_status = _clean(values, "亮灯状态")
        if new_status:
            if new_status not in STATUS_ORDER:
                return None, f"亮灯状态「{new_status}」不在允许范围内"
            record["亮灯状态"] = new_status
            # 反向同步单据状态，保证弹窗与养护记录口径一致。
            for doc_status, pole_status in REPAIR_STATUS_FLOW.items():
                if pole_status == new_status:
                    record["单据状态"] = doc_status
            self._sync_status(entry, new_status)

        # 台账上的故障类型/报修日期始终跟着「该杆最新一张单据」走，
        # 但旧单据本身不会被改动，历史仍可追溯。
        latest, _ = self.list_repairs(pole_no=str(record["灯杆编号"]), size=10000)
        if latest and int(latest[0]["id"]) == repair_id:
            entry["故障类型"] = record["故障类型"]
            entry["报修日期"] = record["报修日期"]
        return record, "报修记录修改已保存"

    def advance_repair(self, repair_id: int, action: str, values: dict[str, Any] | None = None) -> tuple[dict[str, Any] | None, str]:
        """安排维修 / 完成维修：流转单据并同步灯杆亮灯状态。"""
        record = store.find(REPAIR_MODULE, repair_id)
        if record is None:
            return None, f"报修记录 {repair_id} 不存在或已归档"
        action = (action or "").strip()
        if action == "安排维修":
            record["单据状态"] = "已派修"
            target = REPAIR_STATUS_FLOW["已派修"]
        elif action == "完成维修":
            values = values or {}
            handle = _clean(values, "处理情况")
            if not handle:
                return None, "完成维修前请填写处理情况"
            record["处理情况"] = handle
            new_type = _clean(values, "更换灯型类别")
            if new_type:
                entry = self.find_by_pole(str(record["灯杆编号"]))
                if entry is not None and new_type != str(entry.get("灯型类别") or ""):
                    record["更换灯型类别"] = new_type
                    self._record_type_change(entry, new_type)
                    entry["灯型类别"] = new_type
            record["单据状态"] = "已修复"
            target = REPAIR_STATUS_FLOW["已修复"]
        else:
            return None, f"动作「{action}」不属于路灯管养可执行范围"
        record["亮灯状态"] = target
        entry = self.find_by_pole(str(record["灯杆编号"]))
        if entry is not None:
            self._sync_status(entry, target)
        return record, f"报修单已{action}"

    # ------------------------------------------------------------------ 养护
    def list_maintenances(
        self,
        *,
        pole_no: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        """养护记录 = 已有处理结论的报修单，亮灯状态直接取单据上与台账同步的那份。"""
        rows = [row for row in store.rows(REPAIR_MODULE) if row.get("处理情况")]
        if pole_no:
            rows = [row for row in rows if pole_no in str(row.get("灯杆编号", ""))]
        rows = sorted(rows, key=lambda row: int(row.get("id", 0)), reverse=True)
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def list_type_changes(self, *, pole_no: str | None = None) -> list[dict[str, Any]]:
        rows = store.rows(CHANGE_MODULE)
        if pole_no:
            rows = [row for row in rows if pole_no in str(row.get("灯杆编号", ""))]
        return sorted(rows, key=lambda row: int(row.get("id", 0)), reverse=True)

    def overview_stats(self) -> list[dict[str, Any]]:
        rows = store.rows(MODULE)
        return [
            {"label": "正常亮灯", "value": sum(1 for row in rows if row.get("亮灯状态") == "正常亮灯")},
            {"label": "故障路灯", "value": sum(1 for row in rows if row.get("亮灯状态") == "故障不亮")},
            {"label": "维修中路灯", "value": sum(1 for row in rows if row.get("亮灯状态") == "维修中")},
        ]

    # 兼容旧的台账动作入口（表格上的快捷按钮）。
    def run_action(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"路灯设施 {entry_id} 不存在或已归档"
        if action == "报修登记":
            record, message = self.create_repair({"灯杆编号": entry["灯杆编号"]})
            if record is None:
                return None, message
            return entry, message
        if action in {"安排维修", "完成维修"}:
            latest, _ = self.list_repairs(pole_no=str(entry["灯杆编号"]), size=1)
            if not latest:
                return None, f"灯杆 {entry['灯杆编号']} 暂无报修记录，无法{action}"
            values = {"处理情况": "现场处置完成，恢复亮灯"} if action == "完成维修" else None
            record, message = self.advance_repair(int(latest[0]["id"]), action, values)
            if record is None:
                return None, message
            return entry, message
        return None, f"动作「{action}」不属于路灯管养可执行范围"
