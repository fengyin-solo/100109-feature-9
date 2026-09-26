"""路灯管养业务规则：灯杆台账、报修记录、养护记录与状态同步都收在这里。

口径约定：
- 亮灯状态只有一个权威来源：灯杆台账行的 status；报修弹窗、养护记录里看到的
  亮灯状态全部从这里 join 过去，避免两个入口结论不一致。
- 故障类型、报修日期、处理情况、更换灯型类别只属于某一根灯杆的某一条报修记录，
  按报修记录 id 增改；新报修只新增行，永不覆盖历史记录。
"""
from __future__ import annotations

from datetime import date
from typing import Any

from app.store import store

MODULE = "light"
REPAIR_MODULE = "light_repair"
REQUIRED_FIELDS = ["灯杆编号", "所在路段", "灯型类别"]
STATUS_ORDER = ["正常亮灯", "故障不亮", "维修中", "已拆除"]
ACTION_RULES = {"报修登记": "故障不亮", "安排维修": "维修中", "完成维修": "正常亮灯"}
NEGATIVE_ACTIONS = []

# 报修弹窗里允许填写/修改的字段；任何提交都只落到对应那一条报修记录上
REPAIR_FIELDS = ["报修日期", "故障类型", "处理情况", "更换灯型类别"]


class LightService:
    # ---- 灯杆台账 -------------------------------------------------------

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
            rows = [row for row in rows if keyword in str(row.get("灯杆编号", ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        total = len(rows)
        start = max(page - 1, 0) * size
        return [self._serialize_pole(row) for row in rows[start:start + size]], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        entry = store.find(MODULE, entry_id)
        return self._serialize_pole(entry) if entry is not None else None

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing
        rows = store.rows(MODULE)
        code = str(values.get("灯杆编号") or "").strip()
        if any(str(row.get("灯杆编号") or "").strip() == code for row in rows):
            return None, [f"灯杆编号 {code} 已登记，不能重复建档"]
        entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        entry.update({field: values.get(field) for field in REQUIRED_FIELDS})
        entry["功率瓦数"] = values.get("功率瓦数")
        entry["亮灯时段"] = values.get("亮灯时段")
        entry["status"] = STATUS_ORDER[0]
        entry["pending"] = True
        entry["abnormal"] = False
        rows.append(entry)
        store.save()
        return self._serialize_pole(entry), []

    def run_action(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"路灯设施 {entry_id} 不存在或已归档"
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于路灯管养可执行范围"
        target = ACTION_RULES[action]
        if target not in STATUS_ORDER:
            return None, f"目标状态「{target}」不在允许的状态序列里"
        entry["status"] = target
        entry["pending"] = target != STATUS_ORDER[-1]
        entry["abnormal"] = action in NEGATIVE_ACTIONS
        store.save()
        return self._serialize_pole(entry), f"路灯设施已{action}"

    def status_groups(self) -> dict[str, int]:
        """按亮灯状态分组统计；台账、弹窗、养护记录共用这一份口径。"""
        groups = {status: 0 for status in STATUS_ORDER}
        for row in store.rows(MODULE):
            groups[str(row.get("status"))] = groups.get(str(row.get("status")), 0) + 1
        return groups

    # ---- 报修记录 / 养护记录 --------------------------------------------

    def list_repairs(
        self,
        *,
        keyword: str | None = None,
        light_id: int | None = None,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        repairs = store.rows(REPAIR_MODULE)
        if light_id is not None:
            repairs = [row for row in repairs if int(row.get("light_id", 0)) == light_id]
        if keyword:
            repairs = [row for row in repairs if keyword in str(row.get("灯杆编号", ""))]
        serialized = [self._serialize_repair(row) for row in repairs]
        if status:
            serialized = [row for row in serialized if row.get("亮灯状态") == status]
        # 新报修在前，保证历史记录按时间排开、互不遮挡
        serialized.sort(key=lambda row: int(row["id"]), reverse=True)
        return serialized

    def create_repair(
        self, light_id: int, values: dict[str, Any]
    ) -> tuple[dict[str, Any] | None, str]:
        pole = store.find(MODULE, light_id)
        if pole is None:
            return None, f"路灯设施 {light_id} 不存在或已归档"
        fault_type = str(values.get("故障类型") or "").strip()
        if not fault_type:
            return None, "故障类型不能为空"
        report_date = str(values.get("报修日期") or "").strip() or date.today().isoformat()
        handle_result = str(values.get("处理情况") or "").strip()
        new_lamp_type = str(values.get("更换灯型类别") or "").strip()

        rows = store.rows(REPAIR_MODULE)
        record = {
            "id": max((int(row.get("id", 0)) for row in rows), default=0) + 1,
            "light_id": light_id,
            # 编号快照：记录只挂在对应那根灯杆上，台账后续改名也不影响历史归属
            "灯杆编号": pole.get("灯杆编号"),
            "所在路段": pole.get("所在路段"),
            "报修日期": report_date,
            "故障类型": fault_type,
            "处理情况": handle_result,
            "更换灯型类别": new_lamp_type or None,
        }
        rows.append(record)

        # 更换灯型：养护记录留痕，同时更新台账当前灯型类别
        if new_lamp_type:
            pole["灯型类别"] = new_lamp_type
        # 新报修意味着灯杆当前故障不亮（已拆除除外）
        if pole.get("status") != STATUS_ORDER[-1]:
            pole["status"] = "故障不亮"
            pole["pending"] = True
            pole["abnormal"] = True
        store.save()
        return self._serialize_repair(record), "报修记录已保存"

    def update_repair(
        self, repair_id: int, values: dict[str, Any]
    ) -> tuple[dict[str, Any] | None, str]:
        record = store.find(REPAIR_MODULE, repair_id)
        if record is None:
            return None, f"报修记录 {repair_id} 不存在或已归档"
        if "故障类型" in values:
            fault_type = str(values.get("故障类型") or "").strip()
            if not fault_type:
                return None, "故障类型不能为空"
            record["故障类型"] = fault_type
        for field in ("报修日期", "处理情况"):
            if field in values:
                record[field] = str(values.get(field) or "").strip()
        if "更换灯型类别" in values:
            new_lamp_type = str(values.get("更换灯型类别") or "").strip()
            record["更换灯型类别"] = new_lamp_type or None
            # 灯型更换同步到台账；改的是哪条记录，就只影响它所属的那根灯杆
            if new_lamp_type:
                pole = store.find(MODULE, int(record["light_id"]))
                if pole is not None:
                    pole["灯型类别"] = new_lamp_type
        store.save()
        return self._serialize_repair(record), "报修记录已更新"

    # ---- 序列化：统一亮灯状态口径 ---------------------------------------

    def _latest_repair(self, light_id: int) -> dict[str, Any] | None:
        rows = [
            row for row in store.rows(REPAIR_MODULE)
            if int(row.get("light_id", 0)) == light_id
        ]
        return max(rows, key=lambda row: int(row.get("id", 0)), default=None)

    def _serialize_pole(self, row: dict[str, Any]) -> dict[str, Any]:
        """台账行对外结构：亮灯状态直接取 status，故障/报修取最近一次报修记录。"""
        item = dict(row)
        status = str(row.get("status") or STATUS_ORDER[0])
        item["亮灯状态"] = status  # 唯一权威来源，覆盖 seed 里的占位文本
        latest = self._latest_repair(int(row.get("id", 0)))
        item["故障类型"] = latest.get("故障类型") if latest else None
        item["报修日期"] = latest.get("报修日期") if latest else None
        return item

    def _serialize_repair(self, row: dict[str, Any]) -> dict[str, Any]:
        """报修/养护记录对外结构：亮灯状态从灯杆台账实时 join 过来保持同步。"""
        item = dict(row)
        pole = store.find(MODULE, int(row.get("light_id", 0)))
        if pole is not None:
            item["灯杆编号"] = pole.get("灯杆编号")
            item["所在路段"] = pole.get("所在路段")
            item["灯型类别"] = pole.get("灯型类别")
            item["亮灯状态"] = pole.get("status")
        else:
            item["亮灯状态"] = "已拆除"
        item.setdefault("处理情况", None)
        item.setdefault("更换灯型类别", None)
        return item
