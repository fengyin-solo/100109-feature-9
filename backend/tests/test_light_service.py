"""路灯管养回归测试：报修留存、记录归属、状态同步、历史不被覆盖。

直接跑：backend/.venv/bin/python -m unittest discover -s tests
"""
from __future__ import annotations

import importlib
import os
import tempfile
import unittest


def _fresh_app(data_dir: str):
    os.environ["APP_DATA_DIR"] = data_dir
    import app.store as store_module
    import app.services.light as light_module
    importlib.reload(store_module)
    importlib.reload(light_module)
    return light_module.LightService()


class LightServiceTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.service = _fresh_app(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_repair_edit_is_saved_and_reopened_unchanged(self) -> None:
        record, message = self.service.create_repair(2, {"故障类型": "灯具不亮", "处理情况": "已更换LED灯具"})
        self.assertIsNotNone(record)
        self.assertEqual(message, "报修记录已保存")
        repair_id = record["id"]

        updated, _ = self.service.update_repair(
            repair_id, {"故障类型": "灯泡烧毁", "处理情况": "更换灯泡并复测"}
        )
        self.assertEqual(updated["故障类型"], "灯泡烧毁")
        self.assertEqual(updated["处理情况"], "更换灯泡并复测")

        # 模拟"第二天再打开"：换一个全新的 Store 实例，只从磁盘恢复
        reopened = _fresh_app(self._tmp.name)
        again = reopened.list_repairs(light_id=2)
        target = [row for row in again if row["id"] == repair_id][0]
        self.assertEqual(target["故障类型"], "灯泡烧毁")
        self.assertEqual(target["处理情况"], "更换灯泡并复测")

    def test_new_repair_never_overwrites_history(self) -> None:
        first, _ = self.service.create_repair(2, {"故障类型": "灯具不亮"})
        second, _ = self.service.create_repair(2, {"故障类型": "灯杆倾斜", "更换灯型类别": "高压钠灯"})
        self.assertNotEqual(first["id"], second["id"])

        history = self.service.list_repairs(light_id=2)
        self.assertEqual(len(history), 2)
        self.assertEqual({row["故障类型"] for row in history}, {"灯具不亮", "灯杆倾斜"})

    def test_fault_and_report_date_only_belong_to_referenced_pole(self) -> None:
        self.service.create_repair(2, {"故障类型": "灯具不亮", "报修日期": "2026-09-20"})
        poles = {row["id"]: row for row in self.service.list_entries(size=200)[0]}
        self.assertEqual(poles[2]["故障类型"], "灯具不亮")
        self.assertEqual(poles[2]["报修日期"], "2026-09-20")
        self.assertIsNone(poles[1]["故障类型"])
        self.assertIsNone(poles[1]["报修日期"])

    def test_status_in_sync_across_ledger_repair_dialog_and_records(self) -> None:
        self.service.create_repair(2, {"故障类型": "灯具不亮"})
        pole = self.service.get_entry(2)
        record = self.service.list_repairs(light_id=2)[0]
        self.assertEqual(pole["亮灯状态"], "故障不亮")
        self.assertEqual(record["亮灯状态"], "故障不亮")

        self.service.run_action(2, "安排维修")
        self.assertEqual(self.service.get_entry(2)["亮灯状态"], "维修中")
        self.assertEqual(self.service.list_repairs(light_id=2)[0]["亮灯状态"], "维修中")

        groups = self.service.status_groups()
        for status, count in groups.items():
            actual = sum(
                1 for row in self.service.list_entries(status=status, size=200)[0]
            )
            self.assertEqual(count, actual)

    def test_replaced_lamp_type_is_recorded_and_synced_to_ledger(self) -> None:
        self.service.create_repair(2, {"故障类型": "灯具不亮", "更换灯型类别": "LED 灯"})
        self.assertEqual(self.service.get_entry(2)["灯型类别"], "LED 灯")
        record = self.service.list_repairs(light_id=2)[0]
        self.assertEqual(record["更换灯型类别"], "LED 灯")
        self.assertEqual(record["灯型类别"], "LED 灯")

    def test_fault_type_is_required(self) -> None:
        record, message = self.service.create_repair(1, {})
        self.assertIsNone(record)
        self.assertIn("故障类型", message)


if __name__ == "__main__":
    unittest.main()
