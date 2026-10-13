"""Bảng con vị trí của bản gán — khoá đúng hai điều: doctype là bảng con thật, và
bản gán cha đã trỏ vào nó. Hành vi (chồng lấn, gợi ý) nằm ở `tests/test_gan_vi_tri.py`."""

import frappe
from frappe.tests.utils import FrappeTestCase


class TestBangConViTriGan(FrappeTestCase):
	def test_doctype_la_bang_con_du_truong(self):
		meta = frappe.get_meta("Item Location Preference Row")
		self.assertTrue(meta.istable)
		self.assertTrue({"vi_tri", "kho", "cap_do", "ghi_chu"} <= {f.fieldname for f in meta.fields})
		self.assertTrue(meta.get_field("kho").read_only, "kho tự theo nút, không khai tay")

	def test_ban_gan_tro_vao_bang_con_va_bat_buoc(self):
		f = frappe.get_meta("Item Location Preference").get_field("vi_tri_gan")
		self.assertIsNotNone(f)
		self.assertEqual((f.fieldtype, f.options), ("Table", "Item Location Preference Row"))
		self.assertTrue(f.reqd, "bản gán phải có ít nhất một vị trí")
