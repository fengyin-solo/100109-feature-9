"""数据仓库：给每个业务模块准备一份可筛选、可流转的示例数据。

数据落在后端进程之外的 JSON 文件里（data/store.json），重启服务、跨天都不会丢；
只有文件不存在时才用示例数据初始化。真实项目里这里会换成数据库访问层。
"""
from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any

from app.seed import SEED_ROWS

_DATA_DIR = Path(os.environ.get("APP_DATA_DIR", Path(__file__).resolve().parent.parent / "data"))
_DATA_FILE = _DATA_DIR / "store.json"


class Store:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._tables: dict[str, list[dict[str, Any]]] = {}
        self._load()

    def _load(self) -> None:
        if _DATA_FILE.exists():
            try:
                with _DATA_FILE.open("r", encoding="utf-8") as handle:
                    payload = json.load(handle)
                if isinstance(payload, dict):
                    self._tables = {
                        name: [dict(row) for row in rows]
                        for name, rows in payload.items()
                        if isinstance(rows, list)
                    }
                    return
            except (json.JSONDecodeError, OSError):
                # 文件损坏时退回示例数据，避免整个服务起不来
                pass
        self._tables = {
            name: [dict(row) for row in rows] for name, rows in SEED_ROWS.items()
        }
        self._flush()

    def _flush(self) -> None:
        _DATA_DIR.mkdir(parents=True, exist_ok=True)
        tmp_file = _DATA_FILE.with_suffix(".json.tmp")
        with tmp_file.open("w", encoding="utf-8") as handle:
            json.dump(self._tables, handle, ensure_ascii=False, indent=2)
        os.replace(tmp_file, _DATA_FILE)

    def module_names(self) -> list[str]:
        with self._lock:
            return sorted(self._tables)

    def rows(self, module: str) -> list[dict[str, Any]]:
        with self._lock:
            return self._tables.setdefault(module, [])

    def find(self, module: str, entry_id: int) -> dict[str, Any] | None:
        with self._lock:
            for row in self.rows(module):
                if int(row.get("id", 0)) == entry_id:
                    return row
            return None

    def save(self) -> None:
        """把当前数据落盘；业务层改完记录后调用，保证编辑结果真正留住。"""
        with self._lock:
            self._flush()

    def overview(self) -> dict[str, object]:
        with self._lock:
            modules: list[dict[str, object]] = []
            for name in self.module_names():
                rows = self.rows(name)
                modules.append({
                    "name": name,
                    "created": len(rows),
                    "pending": sum(1 for row in rows if row.get("pending")),
                    "abnormal": sum(1 for row in rows if row.get("abnormal")),
                })
            cards = [
                {"label": "业务模块", "value": len(modules)},
                {"label": "今日新增", "value": sum(int(item["created"]) for item in modules)},
                {"label": "待处理", "value": sum(int(item["pending"]) for item in modules)},
                {"label": "异常量", "value": sum(int(item["abnormal"]) for item in modules)},
            ]
            return {"cards": cards, "modules": modules}


store = Store()
