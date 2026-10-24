# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Cài đặt tiếp nhận hóa đơn NCC: ngưỡng, trọng số, từ điển, vai trò duyệt (FRD NFR-08, 20.3) và trường
bắt buộc khi Nộp hợp đồng khung (D4-13)."""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

from erpnext.buying.tiep_nhan_hoa_don.cau_hinh import danh_sach_truong


class SupplierInvoiceIntakeSettings(Document):
	def validate(self):
		if not 0 < flt(self.nguong_xac_nhan) <= flt(self.nguong_tu_dong) <= 1:
			frappe.throw(_("Cần 0 < Ngưỡng chờ xác nhận ≤ Ngưỡng khớp tự động ≤ 1."))
		if abs(flt(self.trong_so_jaccard) + flt(self.trong_so_chuoi) - 1) > 0.001:
			frappe.throw(_("Hai trọng số phải cộng lại bằng 1."))
		if not 0 < flt(self.nguong_canh_bao_han_muc) <= 100:
			frappe.throw(_("Ngưỡng cảnh báo hạn mức phải trong khoảng 1 - 100%."))
		for f, dt in (
			("truong_bat_buoc_hdk", "Blanket Order"),
			("truong_bat_buoc_dong_hdk", "Blanket Order Item"),
		):
			ds = danh_sach_truong(self.get(f))
			sai = [t for t in ds if not frappe.get_meta(dt).has_field(t)]
			if sai:
				frappe.throw(_("{0} không có trường: {1}").format(_(dt), ", ".join(sai)))
			self.set(f, "\n".join(ds))
