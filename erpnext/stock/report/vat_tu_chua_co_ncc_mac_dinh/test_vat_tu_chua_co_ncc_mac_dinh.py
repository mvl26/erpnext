# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Báo cáo xử lý tay sau patch đánh dấu NCC mặc định (mục 8 của kế hoạch sinh mã).

Patch chỉ tự quyết được khi dữ liệu đủ rõ; phần còn lại phải có chỗ để người làm
danh mục nhìn thấy — không thì chúng chỉ lộ ra khi ai đó sửa Item và bị chặn.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext.stock.report.vat_tu_chua_co_ncc_mac_dinh.vat_tu_chua_co_ncc_mac_dinh import execute
from erpnext.stock.tests.test_item_code_rule import make_group, make_supplier, new_item, use_naming_mode


class TestVatTuChuaCoNCCMacDinh(FrappeTestCase):
	def setUp(self):
		# Báo cáo dành cho Item có từ trước khi bật quy tắc, nên các Item mẫu phải
		# được tạo ở chế độ cũ — bất kể site đang để chế độ nào.
		use_naming_mode(self, "Item Code")
		self.sfx = frappe.generate_hash(length=6)
		self.group = make_group(f"G{self.sfx}")
		self.supplier = make_supplier(self.sfx)
		self.other = make_supplier(f"{self.sfx}-2")

	def item(self, suppliers=(), **fields):
		code = f"_TEST-ICR-RPT-{frappe.generate_hash(length=6)}"
		return new_item(self.group, None, suppliers, item_code=code, **fields).insert()

	def rows(self):
		_columns, data = execute({"item_group": self.group})
		return {row["item_code"]: row for row in data}

	def test_item_with_several_suppliers_and_no_default_is_listed(self):
		item = self.item([(self.supplier, "AAA1"), (self.other, "BBB2")])

		row = self.rows()[item.name]

		self.assertEqual(row["supplier_rows"], 2)
		self.assertIn("chưa chọn", row["reason"])

	def test_item_without_suppliers_is_listed(self):
		item = self.item()

		self.assertIn("Chưa khai", self.rows()[item.name]["reason"])

	def test_item_with_a_default_supplier_row_is_not_listed(self):
		item = self.item([(self.supplier, "AAA1", 1), (self.other, "BBB2")])

		self.assertNotIn(item.name, self.rows())

	def test_item_outside_the_rule_scope_is_not_listed(self):
		item = self.item(is_stock_item=0)

		self.assertNotIn(item.name, self.rows())
