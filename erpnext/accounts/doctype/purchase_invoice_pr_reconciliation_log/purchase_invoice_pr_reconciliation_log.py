# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Nhật ký đối soát Phiếu nhập mua ↔ Hóa đơn mua (YC5, spec 6.3.4: nhật ký không xóa được).

Chỉ `doi_soat.py` ghi (insert, bỏ qua quyền). Không ai sửa hay xóa được, kể cả System Manager:
quyền trên DocType chỉ có đọc, và controller chặn cả đường bỏ qua quyền (code, API, import).
"""

import frappe
from frappe import _
from frappe.model.document import Document


class PurchaseInvoicePRReconciliationLog(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		chi_tiet: DF.LongText | None
		hoa_don: DF.Data | None
		ly_do: DF.SmallText | None
		nguoi: DF.Link | None
		nha_cung_cap: DF.Link | None
		phieu_nhap: DF.Data | None
		so_diem_lech: DF.Int
		su_kien: DF.Literal["", "Đối soát", "Duyệt ngoại lệ", "Nộp hóa đơn", "Phiếu nhập thay đổi"]
		thoi_diem: DF.Datetime | None
		trang_thai: DF.Literal["", "Chưa đối soát", "Khớp", "Lệch", "Ngoại lệ đã duyệt"]
		van_tay: DF.Data | None
	# end: auto-generated types

	def validate(self):
		if not self.is_new():
			frappe.throw(_("Nhật ký đối soát không sửa được."))

	def on_trash(self):
		frappe.throw(_("Nhật ký đối soát không xóa được."))
