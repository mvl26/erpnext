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

	def test_chi_truong_kho_GHI_duoc_vi_o_cho_de_khoa_API_nam_o_day(self):
		"""Quyền GHI trên doctype này LÀ hàng rào của lối thoát `cho_de_khoa_api`.

		Từ vòng sửa 2, `cap_khoa_may` TỪ CHỐI cấp máy cho tài khoản đang giữ một khoá API
		lạ (cấp máy sẽ xoay `api_secret` và giết tích hợp đang dùng khoá đó — tức thì,
		không hoàn nguyên được). Lối thoát duy nhất là ô `cho_de_khoa_api` trên chính
		doctype này, và thứ giữ cho "chỉ trưởng kho bật được" **không phải một phép kiểm
		trong `cap_khoa_may`** mà là bảng quyền ở đây — đúng chỗ của nó.

		Nên bài này khoá quyền **GHI** (bài trên chỉ khoá quyền ĐỌC). Nới quyền ghi
		`PDA Badge` cho một vai trò rộng hơn là nới luôn lối thoát, **im lặng** — và đó
		là đúng hạng lỗi mà cả Task này sinh ra để chặn. Khoá bằng chính hằng số
		`VAI_TRO_QUAN_LY_THE`, không bằng hai chuỗi gõ tay."""
		from erpnext.warehouse_operations.vitri.the_pda import VAI_TRO_QUAN_LY_THE

		meta = frappe.get_meta("PDA Badge")
		ghi_duoc = {p.role for p in meta.permissions if p.write}
		self.assertEqual(
			ghi_duoc,
			VAI_TRO_QUAN_LY_THE,
			f"quyền GHI phải đúng tập trưởng kho — đây là hàng rào của ô 'Cho phép đè khoá "
			f"API có sẵn'; thực tế: {ghi_duoc}",
		)
		self.assertIsNotNone(
			meta.get_field("cho_de_khoa_api"), "thiếu ô lối thoát thì ca hợp lệ kẹt cứng"
		)
