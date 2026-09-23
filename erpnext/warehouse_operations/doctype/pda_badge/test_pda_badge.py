"""Kiểm cấu trúc DocType PDA Badge — tồn tại, schema đúng, permissions đúng.

Bài kiểm logic thực tế nằm ở `warehouse_operations/tests/test_the_pda.py` — cùng chỗ
với các bài khác của module, đúng bảng đường dẫn trong `scripts/file_structure/gate.py`.
"""

import frappe
from frappe.tests.utils import FrappeTestCase


class TestPDABadgeSchema(FrappeTestCase):
	def test_doctype_ton_tai_va_co_nhung_field_bat_buoc(self):
		meta = frappe.get_meta("PDA Badge")
		self.assertIsNotNone(meta, "DocType PDA Badge phải tồn tại")
		co = {f.fieldname for f in meta.fields}
		self.assertTrue(
			{"nguoi_dung", "ho_ten", "con_hieu_luc", "ma_bam"} <= co,
			f"thiếu field bắt buộc: {co}",
		)

	def test_autoname_field_nguoi_dung(self):
		meta = frappe.get_meta("PDA Badge")
		self.assertEqual(meta.autoname, "field:nguoi_dung", "autoname phải là field:nguoi_dung")

	def test_ma_bam_hidden_va_no_copy(self):
		meta = frappe.get_meta("PDA Badge")
		f = meta.get_field("ma_bam")
		self.assertIsNotNone(f, "field ma_bam phải tồn tại")
		self.assertTrue(f.hidden, "ma_bam phải hidden = 1 (không hiển thị giao diện)")
		self.assertTrue(f.no_copy, "ma_bam phải no_copy = 1 (không sao chép)")

	def test_permissions_dung_cho_system_manager_stock_manager(self):
		meta = frappe.get_meta("PDA Badge")
		co_quyen = {p.role for p in meta.permissions if p.read}
		self.assertEqual(co_quyen, {"System Manager", "Stock Manager"},
			f"quyền đọc phải là chuỗi (System Manager, Stock Manager), thực tế: {co_quyen}")
