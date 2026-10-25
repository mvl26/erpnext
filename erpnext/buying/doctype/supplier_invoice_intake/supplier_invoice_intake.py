# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Phiếu tiếp nhận hóa đơn NCC (FRD-MAP-01 DT-07). Logic ở `erpnext.buying.tiep_nhan_hoa_don`."""

import frappe
from frappe import _
from frappe.model.document import Document

from erpnext.buying.tiep_nhan_hoa_don import hoa_don_lien_quan
from erpnext.buying.tiep_nhan_hoa_don.cau_hinh import cai_dat, co_quyen_duyet_lech_gia
from erpnext.buying.tiep_nhan_hoa_don.doi_soat import xu_ly


class SupplierInvoiceIntake(Document):
	def validate(self):
		if not cai_dat().bat:
			frappe.throw(_("Tiếp nhận hóa đơn đang tắt (Cài đặt tiếp nhận hóa đơn)."))
		xu_ly(self)

	def on_update(self):
		hoa_don_lien_quan.sau_khi_luu(self, "on_update")

	def after_delete(self):
		hoa_don_lien_quan.sau_khi_luu(self, "after_delete")

	def onload(self):
		self.set_onload("co_quyen_duyet", co_quyen_duyet_lech_gia())
		goc = self.phieu_lien_quan and frappe.db.get_value(
			"Supplier Invoice Intake", self.phieu_lien_quan, "purchase_invoice"
		)
		# Nút "Bỏ hóa đơn bị thay thế" / "Lập lại Hóa đơn mua": hóa đơn gốc đang có bản nháp do phiếu lập.
		self.set_onload(
			"goc_co_hoa_don_nhap",
			bool(goc and frappe.db.get_value("Purchase Invoice", goc, "docstatus") == 0),
		)

	def on_trash(self):
		if self.purchase_invoice and frappe.db.get_value(
			"Purchase Invoice", self.purchase_invoice, "docstatus"
		) in (0, 1):
			frappe.throw(
				_("Phiếu đã có Hóa đơn mua {0}: xóa hoặc hủy hóa đơn trước.").format(self.purchase_invoice)
			)
