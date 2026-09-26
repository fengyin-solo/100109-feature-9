"""路灯管养接口。

三类资源：
- ``/api/light``：路灯台账（亮灯状态的唯一来源）；
- ``/api/light/repairs``：报修单据，可新增、可再次编辑，历史单据不覆盖；
- ``/api/light/maintenances`` / ``/api/light/type-changes``：养护记录与灯型更换记录。
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.schemas import ActionResult, EntryPayload, PageResult
from app.services.light import (
    FAULT_TYPES,
    STATUS_ORDER,
    LightService,
)

router = APIRouter(prefix="/api/light", tags=["路灯管养"])

service = LightService()

LIST_FIELDS = ["灯杆编号", "所在路段", "灯型类别", "功率瓦数", "亮灯时段", "故障类型", "报修日期", "亮灯状态"]
REPAIR_FIELDS = ["灯杆编号", "故障类型", "报修日期", "处理情况", "更换灯型类别", "单据状态", "亮灯状态"]
STATUSES = STATUS_ORDER


# ------------------------------------------------------------------ 元数据
@router.get("/meta")
def light_meta() -> dict[str, Any]:
    """下拉选项：故障类型、亮灯状态等，前后端口径统一从这里取。"""
    return {
        "statuses": STATUS_ORDER,
        "fault_types": FAULT_TYPES,
        "doc_statuses": ["已登记", "已派修", "已修复"],
        "ledger_fields": LIST_FIELDS,
        "repair_fields": REPAIR_FIELDS,
    }


@router.get("/stats")
def light_stats() -> dict[str, Any]:
    """首页卡片：按亮灯状态分组统计，分组口径与台账行内状态完全一致。"""
    return {"items": service.overview_stats()}


# ------------------------------------------------------------------ 报修单据
@router.get("/repairs", response_model=PageResult[dict])
def list_repairs(
    pole: str | None = Query(default=None, description="按灯杆编号过滤"),
    status: str | None = Query(default=None, description="按单据状态过滤"),
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """列出报修单据；同一灯杆的历史报修全部保留，最新单据在前。"""
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    items, total = service.list_repairs(pole_no=pole, status=status, page=page, size=size)
    return PageResult(items=items, total=total, page=page, size=size)


@router.post("/repairs", response_model=ActionResult)
def create_repair(payload: EntryPayload) -> ActionResult:
    """按灯杆编号登记报修：故障类型、报修日期只挂该杆，并同步亮灯状态为故障不亮。"""
    record, message = service.create_repair(payload.values)
    if record is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=record)


@router.get("/repairs/{repair_id}", response_model=dict)
def get_repair(repair_id: int) -> dict:
    """再次打开报修弹窗时读到的就是当初保存（或上次修改后）的那份内容。"""
    record = service.get_repair(repair_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"报修记录 {repair_id} 不存在或已归档")
    return record


@router.put("/repairs/{repair_id}", response_model=ActionResult)
def update_repair(repair_id: int, payload: EntryPayload) -> ActionResult:
    """修改已有报修单：只改原单据，不新建、不覆盖该杆的其他历史报修。"""
    record, message = service.update_repair(repair_id, payload.values)
    if record is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=record)


@router.post("/repairs/{repair_id}/actions", response_model=ActionResult)
def advance_repair(repair_id: int, payload: EntryPayload) -> ActionResult:
    """安排维修 / 完成维修：单据状态与灯杆亮灯状态在同一事务里同步。"""
    action = str(payload.values.get("action") or "").strip()
    record, message = service.advance_repair(repair_id, action, payload.values)
    if record is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=record)


# ------------------------------------------------------------------ 养护与灯型更换
@router.get("/maintenances", response_model=PageResult[dict])
def list_maintenances(
    pole: str | None = Query(default=None, description="按灯杆编号过滤"),
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """养护记录来自已填写处理情况的报修单，亮灯状态与台账、报修弹窗同源。"""
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    items, total = service.list_maintenances(pole_no=pole, page=page, size=size)
    return PageResult(items=items, total=total, page=page, size=size)


@router.get("/type-changes")
def list_type_changes(pole: str | None = Query(default=None, description="按灯杆编号过滤")) -> dict[str, Any]:
    """灯型类别更换历史：每换一次留一条，原类别可追溯。"""
    items = service.list_type_changes(pole_no=pole)
    return {"total": len(items), "items": items}


# ------------------------------------------------------------------ 台账
@router.get("", response_model=PageResult[dict])
def list_entries(
    keyword: str | None = Query(default=None, description="按灯杆编号检索"),
    status: str | None = Query(default=None, description="正常亮灯、故障不亮、维修中、已拆除"),
    road: str | None = Query(default=None, description="按所在路段检索"),
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """按灯杆编号、所在路段与亮灯状态过滤路灯台账；没有数据时返回空页，不报错。"""
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    items, total = service.list_entries(keyword=keyword, status=status, road=road, page=page, size=size)
    return PageResult(items=items, total=total, page=page, size=size)


@router.post("", response_model=ActionResult)
def create_entry(payload: EntryPayload) -> ActionResult:
    """登记一根灯杆的台账，缺字段或灯杆编号重复时说明原因而不是静默丢弃。"""
    entry, missing = service.create_entry(payload.values)
    if missing:
        return ActionResult(ok=False, message=f"缺少必填字段或编号重复：{'、'.join(missing)}")
    return ActionResult(ok=True, message="路灯设施已登记", entry=entry)


@router.put("/{entry_id}", response_model=ActionResult)
def update_entry(entry_id: int, payload: EntryPayload) -> ActionResult:
    """修改台账（含更换灯型类别）；更换动作会额外写入灯型更换记录。"""
    entry, message = service.update_ledger(entry_id, payload.values)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)


@router.post("/{entry_id}/actions", response_model=ActionResult)
def run_action(entry_id: int, payload: EntryPayload) -> ActionResult:
    """台账行上的快捷动作：报修登记 / 安排维修 / 完成维修（作用于该杆最新报修单）。"""
    action = str(payload.values.get("action") or "").strip()
    entry, message = service.run_action(entry_id, action)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)


@router.get("/export")
def export_entries() -> dict[str, Any]:
    """导出路灯管养全量数据：台账、报修历史、养护记录、灯型更换记录一并导出。"""
    ledger, total = service.list_entries(page=1, size=10000)
    repairs, repair_total = service.list_repairs(page=1, size=10000)
    maintenances, maintenance_total = service.list_maintenances(page=1, size=10000)
    return {
        "module": "light",
        "total": total,
        "items": ledger,
        "repairs": repairs,
        "repair_total": repair_total,
        "maintenances": maintenances,
        "maintenance_total": maintenance_total,
        "type_changes": service.list_type_changes(),
    }


@router.get("/{entry_id}", response_model=dict)
def get_entry(entry_id: int) -> dict:
    """读取单根灯杆明细，含它的报修历史与灯型更换记录；不存在时给可读错误说明。"""
    entry = service.get_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"路灯设施 {entry_id} 不存在或已归档")
    pole = str(entry.get("灯杆编号", ""))
    repairs, _ = service.list_repairs(pole_no=pole, page=1, size=10000)
    maintenances, _ = service.list_maintenances(pole_no=pole, page=1, size=10000)
    return {
        **entry,
        "repairs": repairs,
        "maintenances": maintenances,
        "type_changes": service.list_type_changes(pole_no=pole),
    }
