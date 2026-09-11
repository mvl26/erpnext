"""Cây vị trí là HÌNH CHIẾU của mã, không phải dữ liệu độc lập.

Mọi bài ở đây khoá đúng một điều: không tồn tại thao tác nào của người dùng
đặt được cây lệch khỏi mã. Đó là lý do spec 2026-09-09 từng bỏ cây đi, và là
điều kiện để dựng lại nó.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

KHO = "Kho Miyano - MYN"


def _o(ma):
	if not frappe.db.exists("Storage Location", ma):
		frappe.get_doc({"doctype": "Storage Location", "ma_o": ma, "kho": KHO}).insert(
			ignore_permissions=True
		)
	return ma


class TestCaySuyTuMa(FrappeTestCase):
	def test_tu_sinh_du_to_tien(self):
		_o("9Z18010101")
		for cha in ("9Z", "9Z18", "9Z1801", "9Z180101"):
			self.assertTrue(frappe.db.exists("Storage Location", cha), f"thiếu nút {cha}")

	def test_cha_dung_theo_ma(self):
		_o("9Z18010101")
		self.assertEqual(
			frappe.db.get_value("Storage Location", "9Z18010101", "parent_storage_location"),
			"9Z180101",
		)

	def test_nut_nhom_la_is_group(self):
		_o("9Z18010101")
		for cha in ("9Z", "9Z18", "9Z1801", "9Z180101"):
			self.assertTrue(frappe.db.get_value("Storage Location", cha, "is_group"), cha)
		self.assertFalse(
			frappe.db.get_value("Storage Location", "9Z18010101", "is_group"),
			"ô lá không được là nút nhóm",
		)

	def test_sua_tay_cha_bi_ghi_de_ve_dung(self):
		"""`parent` là read_only trên form, nhưng API vẫn đặt được — chặn ở validate."""
		_o("9Z18010101")
		_o("9Z18020101")
		d = frappe.get_doc("Storage Location", "9Z18010101")
		d.parent_storage_location = "9Z180201"  # sai: thuộc dãy 02
		d.save(ignore_permissions=True)
		self.assertEqual(
			frappe.db.get_value("Storage Location", "9Z18010101", "parent_storage_location"),
			"9Z180101",
			"cha phải được tính lại từ mã, không nhận giá trị người dùng đặt",
		)

	def test_o_chua_xep_dung_ngoai_cay(self):
		from erpnext.vi_tri_kho.vitri.bat_kho import tao_o_chua_xep

		ma = tao_o_chua_xep(KHO)
		self.assertIsNone(
			frappe.db.get_value("Storage Location", ma, "parent_storage_location"),
			"ô hệ thống không thuộc cây — nó không ứng với chỗ nào ngoài kho",
		)

	def test_nut_nhom_khong_bi_ep_dinh_dang_o_la(self):
		"""Nút nhóm có mã 2/4/6/8 ký tự — không được đòi đủ 10."""
		_o("9Z18010101")
		self.assertEqual(frappe.db.get_value("Storage Location", "9Z18", "ma_o"), "9Z18")

	def test_ma_sai_cap_bi_chan(self):
		with self.assertRaises(frappe.ValidationError):
			frappe.get_doc({"doctype": "Storage Location", "ma_o": "9Z180", "kho": KHO}).insert(
				ignore_permissions=True
			)

	def test_xoa_o_la_dong_lai_khoang_lft_rgt(self):
		"""ĐIỀU PHỐI F1: `on_trash` phải gọi `super().on_trash()` — không thì xoá một ô
		lá để lại một khoảng `lft/rgt` mồ côi trong cha, không ai báo lỗi.
		"""
		_o("9Z19010101")
		truoc = frappe.db.get_value("Storage Location", "9Z190101", ["lft", "rgt"], as_dict=True)
		frappe.delete_doc("Storage Location", "9Z19010101", ignore_permissions=True)
		sau = frappe.db.get_value("Storage Location", "9Z190101", ["lft", "rgt"], as_dict=True)
		self.assertEqual(
			sau.rgt - sau.lft,
			truoc.rgt - truoc.lft - 2,
			"xoá ô lá phải đóng lại khoảng lft/rgt của cha, không để khoảng mồ côi",
		)

	def test_khong_xoa_duoc_nut_nhom_con_con(self):
		"""ĐIỀU PHỐI F1: `super().on_trash()` tự chặn xoá một nút nhóm còn con —
		không phải logic riêng của `StorageLocation`, nhưng chỉ có khi gọi super.
		"""
		from frappe.utils.nestedset import NestedSetChildExistsError

		_o("9Z19010101")
		with self.assertRaises(NestedSetChildExistsError):
			frappe.delete_doc("Storage Location", "9Z190101", ignore_permissions=True)
