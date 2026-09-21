# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""`get_scope_doctype` — cầu nối client hỏi server DocType đích của bảng Phạm vi.

Đây là hàm sửa lỗi chặn: form không có JS, `scope_doctype` read-only, `scope_name`
là Dynamic Link cần biết trước DocType để tìm. Test này không lặp lại đường mòn
của 123 test cũ (dựng bản ghi rồi gán thẳng `scope_doctype`) — nó gọi thẳng hàm
whitelist mà form JS sẽ gọi, đúng đường mà người dùng thật đi qua.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext.tbyt.doctype.tbyt_regulatory_document.tbyt_regulatory_document import get_scope_doctype


class TestGetScopeDoctype(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		from erpnext.tbyt.setup import setup_tbyt_masters

		setup_tbyt_masters()

	def test_get_scope_doctype_maps_every_level(self):
		"""Bốn ca đại diện cho bốn cấp phạm vi khác nhau trong danh mục đã seed."""
		cases = {
			"gcn_dang_ky_luu_hanh": "TBYT Marketing Authorization",
			"iso_13485_nha_san_xuat": "Manufacturer",
			"cong_bo_dk_mua_ban": "Company",
			"cq_chung_nhan_chat_luong": "Batch",
		}
		for document_type, expected in cases.items():
			self.assertEqual(get_scope_doctype(document_type), expected, document_type)

	def test_get_scope_doctype_returns_none_for_empty_input(self):
		self.assertIsNone(get_scope_doctype(""))

	def test_transaction_level_type_has_no_scope_doctype(self):
		"""`ho_so_phan_phoi` ở cấp Giao dịch, vắng mặt trong SCOPE_DOCTYPE — phải trả
		None chứ không được nổ KeyError."""
		self.assertIsNone(get_scope_doctype("ho_so_phan_phoi"))
