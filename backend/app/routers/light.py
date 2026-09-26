"""路灯管养接口：灯杆台账、报修弹窗、养护记录，覆盖报修登记、安排维修、完成维修等动作。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.schemas import ActionResult, EntryPayload, PageResult
from app.services.light import LightService

router = APIRouter(prefix="/api/light", tags=["路灯管养"])

service = LightService()

LIST_FIELDS = ["灯杆编号", "所在路段", "灯型类别", "功率瓦数", "亮灯时段", "故障类型", "报修日期", "亮灯状态"]
REPAIR_FIELDS = ["报修日期", "故障类型", "处理情况", "更换灯型类别"]
STATUSES = ["正常亮灯", "故障不亮", "维修中", "已拆除"]


@router.get("", response_model=PageResult[dict])
def list_entries(
    keyword: str | None = Query(default=None, description="按灯杆编号检索"),
    status: str | None = Query(default=None, description="正常亮灯、故障不亮、维修中、已拆除"),
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """按灯杆编号与亮灯状态过滤路灯台账；没有数据时返回空页，不报错。"""
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    items, total = service.list_entries(keyword=keyword, status=status, page=page, size=size)
    return PageResult(items=items, total=total, page=page, size=size)


@router.get("/groups")
def status_groups() -> dict[str, Any]:
    """按亮灯状态分组统计；台账、报修弹窗、养护记录共用这一份口径。"""
    return {"groups": service.status_groups()}


@router.get("/repairs")
def list_repairs(
    keyword: str | None = Query(default=None, description="按灯杆编号检索"),
    status: str | None = Query(default=None, description="按灯杆当前亮灯状态过滤"),
    light_id: int | None = Query(default=None, description="只看某根灯杆的历史报修"),
) -> dict[str, Any]:
    """养护记录：全部报修/维修流水，亮灯状态实时取自灯杆台账。"""
    items = service.list_repairs(keyword=keyword, status=status, light_id=light_id)
    return {"total": len(items), "items": items}


@router.put("/repairs/{repair_id}", response_model=ActionResult)
def update_repair(repair_id: int, payload: EntryPayload) -> ActionResult:
    """修改某条报修记录（故障类型、处理情况、更换灯型类别等）；只动这一条，不碰历史。"""
    entry, message = service.update_repair(repair_id, payload.values)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)


@router.get("/export")
def export_entries() -> dict[str, Any]:
    """导出路灯管养清单：返回当前过滤条件下的全量数据。"""
    items, total = service.list_entries(page=1, size=10000)
    return {"module": "light", "total": total, "items": items}


@router.get("/{entry_id}", response_model=dict)
def get_entry(entry_id: int) -> dict:
    """读取单条路灯设施明细；不存在时给出可读的错误说明。"""
    entry = service.get_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"路灯设施 {entry_id} 不存在或已归档")
    return entry


@router.post("", response_model=ActionResult)
def create_entry(payload: EntryPayload) -> ActionResult:
    """登记一条路灯设施，缺字段时说明原因而不是静默丢弃。"""
    entry, missing = service.create_entry(payload.values)
    if missing:
        return ActionResult(ok=False, message=f"缺少必填字段：{'、'.join(missing)}")
    return ActionResult(ok=True, message="路灯设施已登记", entry=entry)


@router.post("/{entry_id}/actions", response_model=ActionResult)
def run_action(entry_id: int, payload: EntryPayload) -> ActionResult:
    """对单条路灯设施执行报修登记、安排维修、完成维修；不允许的动作会被拦下并说明原因。"""
    action = str(payload.values.get("action") or "").strip()
    entry, message = service.run_action(entry_id, action)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)


@router.get("/{entry_id}/repairs")
def list_pole_repairs(entry_id: int) -> dict[str, Any]:
    """读取某根灯杆的全部历史报修记录，按时间倒序返回。"""
    if service.get_entry(entry_id) is None:
        raise HTTPException(status_code=404, detail=f"路灯设施 {entry_id} 不存在或已归档")
    items = service.list_repairs(light_id=entry_id)
    return {"total": len(items), "items": items}


@router.post("/{entry_id}/repairs", response_model=ActionResult)
def create_repair(entry_id: int, payload: EntryPayload) -> ActionResult:
    """为某根灯杆新增一条报修记录：只新增不覆盖，故障类型与报修日期挂在这根灯杆上。"""
    entry, message = service.create_repair(entry_id, payload.values)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)
