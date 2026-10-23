# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Cài đặt tiếp nhận hóa đơn NCC: ngưỡng, trọng số, từ điển, vai trò duyệt (FRD NFR-08, 20.3)."""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class SupplierInvoiceIntakeSettings(Document):
	def validate(self):
		if not 0 < flt(self.nguong_xac_nhan) <= flt(self.nguong_tu_dong) <= 1:
			frappe.throw(_("Cần 0 < Ngưỡng chờ xác nhận ≤ Ngưỡng khớp tự động ≤ 1."))
		if abs(flt(self.trong_so_jaccard) + flt(self.trong_so_chuoi) - 1) > 0.001:
			frappe.throw(_("Hai trọng số phải cộng lại bằng 1."))
		if not 0 < flt(self.nguong_canh_bao_han_muc) <= 100:
			frappe.throw(_("Ngưỡng cảnh báo hạn mức phải trong khoảng 1 - 100%."))
