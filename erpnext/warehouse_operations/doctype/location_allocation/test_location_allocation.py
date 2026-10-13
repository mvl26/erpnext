"""Bảng phân bổ vị trí — nơi ghi "hàng của dòng này lấy ở ô nào".

Hỏng theo kiểu im lặng: thiếu patch thì field không có trên Delivery Note, trang
lấy hàng vẫn mở được, quét vẫn chạy, chỉ là không lưu được gì — và không lỗi nào
báo. Bài này khoá đúng hai điều: doctype có thật, và field đã gắn vào phiếu giao.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

TEN_BANG_PHAN_BO = "custom_phan_bo_vi_tri"


class TestBangPhanBo(FrappeTestCase):
	def test_doctype_ton_tai_va_la_bang_con(self):
		meta = frappe.get_meta("Location Allocation")
		self.assertTrue(meta.istable, "Location Allocation phải là bảng con (istable = 1)")
		co = {f.fieldname for f in meta.fields}
		self.assertTrue(
			{"dong_hang", "vat_tu", "so_lo", "o", "so_luong", "nguoi_lay", "luc_lay"} <= co,
			f"thiếu field: {co}",
		)

	def test_field_da_gan_vao_phieu_giao(self):
		"""Thiếu dòng trong patches.txt thì patch không chạy, field không có."""
		f = frappe.get_meta("Delivery Note").get_field(TEN_BANG_PHAN_BO)
		self.assertIsNotNone(f, "Delivery Note chưa có bảng phân bổ vị trí — kiểm patches.txt")
		self.assertEqual(f.fieldtype, "Table")
		self.assertEqual(f.options, "Location Allocation")
		self.assertTrue(f.read_only, "bảng phân bổ là KẾT QUẢ của việc quét, không khai tay")
