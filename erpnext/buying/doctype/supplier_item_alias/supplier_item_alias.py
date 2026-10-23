# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Bảng ánh xạ tên (FRD-MAP-01 DT-06): NCC + tên trên hóa đơn → mặt hàng. Chỉ trong phạm vi một NCC
(BR-04); chỉ dòng Đang dùng được khớp tự động; đổi trạng thái là việc của người duyệt ánh xạ."""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime

from erpnext.buying.tiep_nhan_hoa_don.cau_hinh import bo_chuan_hoa, co_quyen_duyet_anh_xa

CHO_DUYET = "Chờ duyệt"
NGUNG = "Ngừng dùng"


class SupplierItemAlias(Document):
	def validate(self):
		self.ten_chuan_hoa = bo_chuan_hoa().chuan_hoa(self.ten_tren_hoa_don)
		if not self.ten_chuan_hoa:
			frappe.throw(_("Tên trên hóa đơn không có chữ hoặc số để so khớp."))
		if not self.nguon:
			self.nguon = "Nhập tay"
		if self.trang_thai != NGUNG and frappe.db.exists(
			"Supplier Item Alias",
			{
				"supplier": self.supplier,
				"ten_chuan_hoa": self.ten_chuan_hoa,
				"trang_thai": ("!=", NGUNG),
				"name": ("!=", self.name),
			},
		):
			frappe.throw(_("Nhà cung cấp {0} đã có ánh xạ cho tên này.").format(self.supplier))

		truoc = self.get_doc_before_save()
		cu = truoc.trang_thai if truoc else CHO_DUYET
		if self.trang_thai != cu:
			if not co_quyen_duyet_anh_xa():
				frappe.throw(
					_("Chỉ người có vai trò duyệt Bảng ánh xạ tên được đổi trạng thái."),
					frappe.PermissionError,
				)
			self.nguoi_duyet = frappe.session.user
			self.thoi_diem_duyet = now_datetime()
