# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Bảng ánh xạ tên (FRD-MAP-01 DT-06): NCC + tên trên hóa đơn → mặt hàng. Chỉ trong phạm vi một NCC
(BR-04); chỉ dòng Đang dùng được khớp tự động; đổi trạng thái là việc của người duyệt ánh xạ. Sửa NCC,
tên hoặc mặt hàng của dòng đã duyệt thì dòng về Chờ duyệt, trừ khi chính người duyệt sửa."""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime

from erpnext.buying.tiep_nhan_hoa_don.cau_hinh import bo_chuan_hoa, co_quyen_duyet_anh_xa

CHO_DUYET = "Chờ duyệt"
NGUNG = "Ngừng dùng"
TRUONG_ANH_XA = ("supplier", "ten_chuan_hoa", "item_code")


class SupplierItemAlias(Document):
	def validate(self):
		self.ten_chuan_hoa = bo_chuan_hoa().chuan_hoa(self.ten_tren_hoa_don)
		if not self.ten_chuan_hoa:
			frappe.throw(_("Tên trên hóa đơn không có chữ hoặc số để so khớp."))
		if not self.nguon:
			self.nguon = "Nhập tay"
		truoc = self.get_doc_before_save()
		cu = truoc.trang_thai if truoc else CHO_DUYET
		duyet = co_quyen_duyet_anh_xa()
		# Người duyệt / thời điểm duyệt chỉ do server ghi: giá trị gửi từ form, API, import bị bỏ.
		self.nguoi_duyet = truoc.nguoi_duyet if truoc else None
		self.thoi_diem_duyet = truoc.thoi_diem_duyet if truoc else None
		if self.trang_thai != cu and not duyet:
			frappe.throw(
				_("Chỉ người có vai trò duyệt Bảng ánh xạ tên được đổi trạng thái."),
				frappe.PermissionError,
			)
		sua = bool(truoc) and any(truoc.get(f) != self.get(f) for f in TRUONG_ANH_XA)
		if sua and cu != CHO_DUYET and not duyet:
			# Ánh xạ đã duyệt bị đổi nội dung: không còn là ánh xạ đã duyệt, tầng 2 thôi dùng tới khi duyệt lại.
			self.trang_thai = CHO_DUYET
			self.nguoi_duyet = self.thoi_diem_duyet = None
			frappe.msgprint(
				_("Ánh xạ đã duyệt vừa bị sửa nên chuyển về Chờ duyệt, cần người duyệt ánh xạ duyệt lại."),
				indicator="orange",
			)
		elif self.trang_thai != cu or (sua and cu != CHO_DUYET):
			self.nguoi_duyet = frappe.session.user
			self.thoi_diem_duyet = now_datetime()

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
